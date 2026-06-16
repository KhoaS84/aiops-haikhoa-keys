#!/usr/bin/env python3
"""
chaos_runner.py — W3-D2 Chaos Engineering Lab
Automates: load experiments → inject fault → query pipeline → score results.

Usage:
    python chaos_runner.py [--config experiments.yaml] [--cooldown 120]

Requires:
    - Docker stack running (start_stack.sh)
    - Pumba + Toxiproxy available in PATH or chaos_tools/
    - AIOps pipeline on port 8000
    - baseline.json captured
    - synthetic_probe.sh running in background
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
PIPELINE_BASE_URL = "http://localhost:8000"
PROBE_ENDPOINT = "http://localhost:8080/checkout/health"
RESULTS_FILE = "chaos_results.json"
COOLDOWN_SECONDS = 120


# ─────────────────────────────────────────────────────────────
# Helper: query AIOps pipeline API
# ─────────────────────────────────────────────────────────────
def query_pipeline_alerts(since: float = None, window: str = None) -> list:
    """
    GET /alerts — lấy danh sách alert từ pipeline.
    Args:
        since: Unix timestamp, lấy alert từ thời điểm này trở đi
        window: string "5m", "10m", etc. — alternative to since
    Returns:
        list of alert dicts: [{service, metric, value, timestamp, severity}, ...]
    """
    params = {}
    if since is not None:
        params["since"] = str(int(since))
    elif window is not None:
        # Convert window string to since timestamp
        minutes = int(window.replace("m", ""))
        params["since"] = str(int(time.time()) - minutes * 60)

    try:
        resp = requests.get(
            f"{PIPELINE_BASE_URL}/alerts",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("alerts", [])
    except requests.RequestException as e:
        print(f"  [WARN] Failed to query alerts: {e}")
        return []


def query_pipeline_rca(alerts: list) -> dict:
    """
    POST /correlate → POST /rca — chạy correlation rồi RCA.
    Returns:
        dict: {root_service, confidence, evidence}
    """
    try:
        # Step 1: Correlate alerts into cluster
        correlate_resp = requests.post(
            f"{PIPELINE_BASE_URL}/correlate",
            json={"alerts": alerts, "window": "5m"},
            timeout=15,
        )
        correlate_resp.raise_for_status()
        cluster = correlate_resp.json()

        # Step 2: RCA on cluster
        rca_resp = requests.post(
            f"{PIPELINE_BASE_URL}/rca",
            json={"cluster": cluster},
            timeout=15,
        )
        rca_resp.raise_for_status()
        return rca_resp.json()

    except requests.RequestException as e:
        print(f"  [WARN] Failed to query RCA: {e}")
        return {"root_service": None, "confidence": 0.0, "evidence": []}


# ─────────────────────────────────────────────────────────────
# TODO 1: build_inject_cmd(exp)
# Dispatcher theo fault_type, return command list cho subprocess
# ─────────────────────────────────────────────────────────────
def get_peer_ip(exp: dict) -> str:
    """
    Extract peer IP for network partition experiments.
    Reads from blast_radius.target to determine peer container,
    then queries Docker for its IP.
    """
    target = exp["blast_radius"]["target"]
    # For partition experiments, target contains "↔"
    if "↔" in target or "<->" in target:
        parts = target.replace("↔", " ").replace("<->", " ").split()
        # Pick the second service as peer
        peer_container = parts[-2] if len(parts) >= 2 else parts[0]
    else:
        peer_container = target.split()[0]

    try:
        result = subprocess.run(
            [
                "docker", "inspect", "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                peer_container,
            ],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "172.20.0.2"
    except Exception:
        return "172.20.0.2"  # fallback


def extract_container_name(target: str) -> str:
    """Extract container name from blast_radius.target string."""
    # Handle various formats:
    #   "payment-svc container" → "payment-svc"
    #   "frontend ↔ api-gateway network link" → "frontend"
    #   "dns-resolver container" → "dns-resolver"
    name = target.split()[0]
    # Remove trailing punctuation if any
    return name.strip("\"'")


def build_inject_cmd(exp: dict) -> list:
    """
    Dispatcher: đọc fault_type từ experiment ground_truth,
    return command list cho subprocess.Popen.

    Supports 10 fault types:
      latency, network_loss, availability, cpu_saturation,
      memory, disk_fill, time_skew, network_partition,
      dns_latency, cascade_retry
    """
    fault = exp["ground_truth"]["fault_type"]
    target = exp["blast_radius"]["target"]
    duration = exp["blast_radius"]["duration"]
    container = extract_container_name(target)

    # ─── Network Faults ───
    if fault == "latency":
        return [
            "pumba", "netem",
            "--duration", f"{duration}s",
            "--tc-image", "gaiadocker/iproute2",
            "delay",
            "--time", "500",
            "--jitter", "100",
            container,
        ]

    elif fault == "network_loss":
        return [
            "pumba", "netem",
            "--duration", f"{duration}s",
            "--tc-image", "gaiadocker/iproute2",
            "loss",
            "--percent", "30",
            container,
        ]

    elif fault == "network_partition":
        peer_ip = get_peer_ip(exp)
        # Inject iptables rule to drop all traffic from peer
        return [
            "docker", "exec", container,
            "iptables", "-A", "INPUT",
            "-s", peer_ip,
            "-j", "DROP",
        ]

    elif fault == "dns_latency":
        return [
            "toxiproxy-cli", "toxic", "add",
            "--type", "latency",
            "--attribute", "latency=2000",
            "--upstream",
            container,
        ]

    # ─── Resource Faults ───
    elif fault == "cpu_saturation":
        return [
            "pumba", "stress",
            "--duration", f"{duration}s",
            "--stressors", "--cpu 4 --cpu-load 90",
            container,
        ]

    elif fault == "memory":
        return [
            "pumba", "stress",
            "--duration", f"{duration}s",
            "--stressors", "--vm 1 --vm-bytes 95%",
            container,
        ]

    elif fault == "disk_fill":
        return [
            "docker", "exec", container,
            "sh", "-c",
            "dd if=/dev/zero of=/tmp/fill_chaos bs=1M count=500 2>/dev/null || true",
        ]

    # ─── Application Faults ───
    elif fault == "availability":
        return [
            "pumba", "kill",
            "--interval", "60s",
            "--signal", "SIGKILL",
            container,
        ]

    elif fault == "cascade_retry":
        # Inject HTTP 500 via Toxiproxy — reset_peer at 20% toxicity
        return [
            "toxiproxy-cli", "toxic", "add",
            "--type", "reset_peer",
            "--toxicity", "0.2",
            container,
        ]

    # ─── State Faults ───
    elif fault == "time_skew":
        # Use libfaketime to skew clock +60s inside container
        return [
            "docker", "exec", container,
            "sh", "-c",
            (
                "export LD_PRELOAD=/usr/lib/faketime/libfaketime.so.1 "
                "FAKETIME='+60s' && "
                f"sleep {duration}"
            ),
        ]

    else:
        raise ValueError(
            f"Unknown fault type: '{fault}'. "
            f"Supported: latency, network_loss, network_partition, "
            f"dns_latency, cpu_saturation, memory, disk_fill, "
            f"availability, cascade_retry, time_skew"
        )


# ─────────────────────────────────────────────────────────────
# Rollback logic
# ─────────────────────────────────────────────────────────────
def rollback(exp: dict):
    """
    Execute rollback command based on experiment spec.
    Tries the method specified in experiments.yaml rollback.method.
    """
    method = exp.get("rollback", {}).get("method", "")
    container = extract_container_name(exp["blast_radius"]["target"])
    fault = exp["ground_truth"]["fault_type"]

    print(f"  [ROLLBACK] Executing rollback for {container}...")

    try:
        # Generic rollback: stop pumba, remove tc rules, remove toxiproxy toxics
        if fault in ("latency", "network_loss"):
            subprocess.run(["pumba", "stop"], capture_output=True, timeout=10)
            subprocess.run(
                ["docker", "exec", container, "tc", "qdisc", "del", "dev", "eth0", "root"],
                capture_output=True, timeout=10,
            )

        elif fault == "network_partition":
            subprocess.run(
                ["docker", "exec", container, "iptables", "-F"],
                capture_output=True, timeout=10,
            )

        elif fault in ("dns_latency", "cascade_retry"):
            subprocess.run(
                ["toxiproxy-cli", "toxic", "remove", container, "--toxicName", "latency_upstream"],
                capture_output=True, timeout=10,
            )

        elif fault in ("cpu_saturation", "memory"):
            subprocess.run(["pumba", "stop"], capture_output=True, timeout=10)
            subprocess.run(
                ["docker", "exec", container, "pkill", "-f", "stress-ng"],
                capture_output=True, timeout=10,
            )

        elif fault == "disk_fill":
            subprocess.run(
                ["docker", "exec", container, "rm", "-f", "/tmp/fill_chaos"],
                capture_output=True, timeout=10,
            )

        elif fault == "availability":
            subprocess.run(["pumba", "stop"], capture_output=True, timeout=10)
            subprocess.run(
                ["docker", "restart", container],
                capture_output=True, timeout=30,
            )

        elif fault == "time_skew":
            subprocess.run(
                ["docker", "restart", container],
                capture_output=True, timeout=30,
            )

        print(f"  [ROLLBACK] Done.")

    except Exception as e:
        print(f"  [ROLLBACK] Warning — rollback had issues: {e}")


# ─────────────────────────────────────────────────────────────
# TODO 2: print_scoreboard(results)
# Print confusion matrix + per-experiment table theo §8.6 format
# ─────────────────────────────────────────────────────────────
def print_scoreboard(results: list):
    """
    Print scoreboard theo format bắt buộc §8.6.

    Args:
        results: list of dict, mỗi dict có keys:
          name, detected (bool), mttd (float|None),
          rca_service (str|None), rca_correct (bool|None),
          false_alarms (int)
    """
    total = len(results)
    detected_count = sum(1 for r in results if r["detected"])
    rca_correct_count = sum(1 for r in results if r.get("rca_correct") is True)
    total_false_alarms = sum(r.get("false_alarms", 0) for r in results)

    # Precision & Recall
    tp = detected_count
    fp = total_false_alarms
    fn = total - detected_count
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # MTTD percentiles
    mttd_values = sorted(
        [r["mttd"] for r in results if r.get("mttd") is not None]
    )
    if mttd_values:
        idx_p50 = len(mttd_values) // 2
        idx_p95 = min(int(len(mttd_values) * 0.95), len(mttd_values) - 1)
        mttd_p50 = mttd_values[idx_p50]
        mttd_p95 = mttd_values[idx_p95]
    else:
        mttd_p50 = 0
        mttd_p95 = 0

    # ─── Header ───
    print()
    print("=" * 60)
    print("==== Chaos Run ====")
    print("=" * 60)
    print(f"Total: {total}")
    print(f"Detected: {detected_count}/{total}")
    print(f"RCA correct: {rca_correct_count}/{detected_count}")
    print(f"False alarms in baseline windows: {total_false_alarms}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")
    print(f"MTTD p50: {mttd_p50:.0f}s, p95: {mttd_p95:.0f}s")
    print()

    # ─── Per-experiment table ───
    print("Per-experiment:")
    header = "| #  | name                        | detected | mttd  | rca_service    | rca_correct |"
    sep =    "|----|-----------------------------|---------:|------:|----------------|:-----------:|"
    print(header)
    print(sep)

    for i, r in enumerate(results, 1):
        det = "Y" if r["detected"] else "N"
        mttd_str = f"{r['mttd']:.0f}s" if r.get("mttd") is not None else "—"
        rca_svc = r.get("rca_service") or "—"
        if r.get("rca_correct") is True:
            rca_ok = "Y"
        elif r.get("rca_correct") is False:
            rca_ok = "N"
        else:
            rca_ok = "—"

        print(
            f"| {i:<2} | {r['name']:<27} | {det:<8} | {mttd_str:<5} "
            f"| {rca_svc:<14} | {rca_ok:<11} |"
        )

    # ─── Gaps identified ───
    gaps = [
        r for r in results
        if not r["detected"] or r.get("rca_correct") is False
    ]
    if gaps:
        print()
        print("Gaps identified:")
        for r in gaps:
            if not r["detected"]:
                print(
                    f"  - {r['name']}: NOT DETECTED "
                    f"→ pipeline detector miss (fault type: "
                    f"{r.get('fault_type', 'unknown')})"
                )
            elif r.get("rca_correct") is False:
                print(
                    f"  - {r['name']}: RCA wrong "
                    f"(picked '{r.get('rca_service', '?')}', "
                    f"expected '{r.get('expected_rca', '?')}') "
                    f"→ RCA logic issue"
                )

    print()
    print("=" * 60)

    # ─── Verdict ───
    verdict_pass = (
        detected_count >= 7
        and (rca_correct_count >= 5 or detected_count == 0)
        and total_false_alarms <= 1
    )
    verdict = "PASS ✅" if verdict_pass else "FAIL ❌"
    print(f"Verdict: {verdict}")
    print(
        f"  Detected {detected_count}/10 (need ≥7), "
        f"RCA {rca_correct_count}/{detected_count} (need ≥5), "
        f"FA {total_false_alarms} (need ≤1)"
    )
    print("=" * 60)


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────
def run_experiments(config_path: str, cooldown: int):
    """
    Main experiment loop:
    1. Load experiments.yaml
    2. For each experiment:
       a. Check baseline alerts (measure FP)
       b. Inject fault
       c. Wait for duration
       d. Query pipeline for detection + RCA
       e. Rollback
       f. Cooldown
    3. Save results + print scoreboard
    """
    # Load config
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    experiments = config.get("experiments", config)
    if not isinstance(experiments, list):
        print("ERROR: experiments.yaml must contain a list of experiments")
        sys.exit(1)

    print(f"Loaded {len(experiments)} experiments from {config_path}")
    print(f"Cooldown between experiments: {cooldown}s")
    print(f"Pipeline URL: {PIPELINE_BASE_URL}")
    print(f"Start time: {datetime.now(timezone.utc).isoformat()}")
    print()

    results = []

    for i, exp in enumerate(experiments):
        exp_name = exp.get("name", f"experiment_{i+1}")
        fault_type = exp["ground_truth"]["fault_type"]
        duration = exp["blast_radius"]["duration"]

        print(f"\n{'─' * 60}")
        print(f"  Experiment {i+1}/{len(experiments)}: {exp_name}")
        print(f"  Fault: {fault_type} | Duration: {duration}s")
        print(f"{'─' * 60}")

        # ── Step 1: Baseline check (5-min window before inject) ──
        print("  [1/6] Checking baseline alerts (FP measurement)...")
        baseline_alerts = query_pipeline_alerts(window="5m")
        false_alarms = len(baseline_alerts)
        if false_alarms > 0:
            print(f"  [WARN] {false_alarms} alerts in baseline window (false alarms)")

        # ── Step 2: Build and execute inject command ──
        print("  [2/6] Injecting fault...")
        try:
            cmd = build_inject_cmd(exp)
            print(f"  [CMD] {' '.join(cmd)}")
            inject_start = time.time()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print(f"  [OK] Fault injected at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"  [ERROR] Failed to inject: {e}")
            results.append({
                "name": exp_name,
                "detected": False,
                "mttd": None,
                "rca_service": None,
                "rca_correct": None,
                "false_alarms": false_alarms,
                "fault_type": fault_type,
                "expected_rca": exp["ground_truth"]["expected_rca_service"],
                "error": str(e),
            })
            continue

        # ── Step 3: Wait for fault duration ──
        print(f"  [3/6] Waiting {duration}s for fault duration...")
        time.sleep(duration)

        # ── Step 4: Query pipeline — was fault detected? ──
        print("  [4/6] Querying pipeline for detection...")
        alerts = query_pipeline_alerts(since=inject_start)
        detected = len(alerts) > 0

        mttd = None
        if detected:
            # MTTD = first alert timestamp - inject start
            first_alert_ts = alerts[0].get("timestamp", inject_start)
            mttd = first_alert_ts - inject_start
            if mttd < 0:
                mttd = 0  # Clamp to 0 if timestamp ordering issue
            print(f"  [DETECTED] {len(alerts)} alerts, MTTD = {mttd:.1f}s")
        else:
            print("  [MISS] Pipeline did not detect the fault")

        # ── Step 5: Query RCA ──
        rca_service = None
        rca_correct = None
        if detected:
            print("  [5/6] Querying RCA...")
            rca_result = query_pipeline_rca(alerts)
            rca_service = rca_result.get("root_service")
            expected_rca = exp["ground_truth"]["expected_rca_service"]
            rca_correct = (rca_service == expected_rca)

            confidence = rca_result.get("confidence", 0.0)
            evidence_count = len(rca_result.get("evidence", []))
            print(
                f"  [RCA] Service: {rca_service} "
                f"(expected: {expected_rca}) → "
                f"{'✅ Correct' if rca_correct else '❌ Wrong'} "
                f"(confidence: {confidence:.2f}, evidence: {evidence_count})"
            )
        else:
            print("  [5/6] Skipping RCA (fault not detected)")

        # ── Step 6: Rollback ──
        print("  [6/6] Rolling back...")
        rollback(exp)

        # ── Cooldown ──
        if i < len(experiments) - 1:
            print(f"  [COOLDOWN] Waiting {cooldown}s for system to stabilize...")
            time.sleep(cooldown)

        # ── Collect result ──
        results.append({
            "name": exp_name,
            "detected": detected,
            "mttd": mttd,
            "rca_service": rca_service,
            "rca_correct": rca_correct,
            "false_alarms": false_alarms,
            "fault_type": fault_type,
            "expected_rca": exp["ground_truth"]["expected_rca_service"],
            "alert_count": len(alerts) if detected else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ── Save results ──
    print(f"\nSaving results to {RESULTS_FILE}...")
    with open(RESULTS_FILE, "w") as f:
        json.dump(
            {
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_experiments": len(results),
                "config_file": config_path,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"Results saved to {RESULTS_FILE}")

    # ── Print scoreboard ──
    print_scoreboard(results)

    return results


# ─────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="W3-D2 Chaos Runner — inject faults and score AIOps pipeline",
    )
    parser.add_argument(
        "--config",
        default="experiments.yaml",
        help="Path to experiments YAML config (default: experiments.yaml)",
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=COOLDOWN_SECONDS,
        help=f"Cooldown seconds between experiments (default: {COOLDOWN_SECONDS})",
    )
    parser.add_argument(
        "--pipeline-url",
        default=PIPELINE_BASE_URL,
        help=f"AIOps pipeline base URL (default: {PIPELINE_BASE_URL})",
    )
    args = parser.parse_args()

    global PIPELINE_BASE_URL
    PIPELINE_BASE_URL = args.pipeline_url

    print("=" * 60)
    print("  W3-D2 Chaos Runner")
    print("  Chaos Engineering — Validate AIOps Pipeline")
    print("=" * 60)

    run_experiments(args.config, args.cooldown)


if __name__ == "__main__":
    main()
