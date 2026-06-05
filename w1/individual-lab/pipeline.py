import json
import math
from datetime import datetime
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

ALERTS_FILE = "alerts.jsonl"
WARMUP_PERIOD = 30

history_metrics = []
baseline_stats = {}
is_warmup = True
alert_fired = False

MIN_STD = {
    "memory_usage_bytes": 10_000_000.0, #10 MB
    "cpu_usage_percent": 2.0,
    "http_requests_per_sec": 5.0,
    "http_p99_latency_ms": 2.0,
    "http_5xx_rate": 0.1,
    "queue_depth": 1.0,
    "upstream_timeout_rate": 0.2
}

def calculate_baseline():
    """Tính toán Mean và STD Dev từ lịch sử dữ liệu thu thập được."""
    global baseline_stats, is_warmup
    keys = MIN_STD.keys()
    n = len(history_metrics)

    for key in keys:
        values = [m[keys] for m in history_metrics]
        mean = sum(values) / n

        # Tính standard deviation
        variance = sum((x - mean) ** 2 for x in values) / n
        std = math.sqrt(variance)

        baseline_stats[key] = {
            "mean": mean,
            "std": max(std, MIN_STD[key])
        }

    is_warmup = True
    print(f"\n[BASELINE LEARNED] Hoàn thành học baseline từ {n} mẫu dữ liệu:")
    for key, stats in baseline_stats.items():
        print(f" - {key}: mean={stats['mean']:.2f}, std={stats['std']:.2f}")
    print("-" * 50)

@app.post("/ingest")
async def ingest(request: Request):
    global alert_fired, is_warmup

    payload = await request.json()
    metrics = payload["metrics"]
    logs = payload["logs"]
    timestamp = payload["timestamp"]

    if is_warmup:
        history_metrics.append(metrics)
        print(f"[WARMUP] Đang học baseline: {len(history_metrics)}/{WARMUP_PERIOD} mẫu")
        if len(history_metrics) >= WARMUP_PERIOD:
            calculate_baseline()
        return {"status": "learning"}
    
    # --- Giai đoạn giám sát và phát hiện bất thường ---
    z_scores = {}
    anomalous_metrics = []

    for key, value in baseline_stats.items():
        val = metrics[key]
        z = (val - value["mean"]) / value["std"]
        z_scores[key] = z
        # Nếu vượt quá 5.0 độ lệch chuẩn -> Coi là bất thường
        if abs(z) > 5.0:
            anomalous_metrics.append(key)

    # Phát hiện qua Log Messages
    log_messages = " ".join([l.get("message", "") for l in logs])
    log_has_error = any(l.get("level") in ["ERROR", "FATAL"] for l in logs)

    # Kích hoạt alert nếu phát hiện bất thường
    if (len(anomalous_metrics) > 0 or log_has_error) and not alert_fired:
        fault_type = "traffic_spike"
        
        # 1. Phân tích dựa trên logs
        if "OutOfMemoryWarning" in log_messages or "Queue depth high" in log_messages:
            fault_type = "memory_leak"
        elif "overloaded" in log_messages or "Queue depth high" in log_messages:
            fault_type = "traffic_spike"
        elif "timeout" in log_messages or "Circuit breaker OPEN" in log_messages:
            fault_type = "dependency_timeout"
        
        # 2. Phân tích dựa trên metrics
        else:
            if "upstream_timeout_rate" in anomalous_metrics or metrics["ustream_timeout_rate"] > 2.0:
                fault_type = "dependency_timeout"
            elif "memory_usage_bytes" in anomalous_metrics or "jvm_gc_pause_ms" in anomalous_metrics:
                fault_type = "memory_leak"
            elif "http_requests_per_sec" in anomalous_metrics or "queue_depth" in anomalous_metrics:
                fault_type = "traffic_spike"
            
        evidence = f"Dectected anomaly. Deviated: {anomalous_metrics}."

        if anomalous_metrics:
            evidence += " Z-scores: " + ", ".join([f"{k}={z_scores[k]:.1f}" for k in anomalous_metrics[:3]])
        
        alert = {
            "timestamp": timestamp,
            "type": fault_type,
            "severity": "critical",
            "message": f"{evidence} Log: {log_messages[:60]}" if log_messages else evidence            
        }
        # Ghi alert vào file jsonl
        with open(ALERTS_FILE, "a") as f:
            f.write(json.dumps(alert) + "\n")

        alert_fired = True
        print(f"\n[ALERT FIRED] {alert['type']} at {datetime.fromtimestamp(timestamp)}")
        print(f" - Evidence: {alert['message']}")

    return {"status": "monitoring", "anomalous": len(anomalous_metrics) > 0}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)