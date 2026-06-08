#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx

DEFAULT_GAP_SEC = 120
DEFAULT_MAX_HOP = 1


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    alerts = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                alerts.append(json.loads(line))
    return alerts


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def severity_rank(severity: str | None) -> int:
    return {"info": 0, "warn": 1, "warning": 1, "crit": 2, "critical": 2}.get(str(severity).lower(), 0)


def max_severity(alerts: list[dict[str, Any]]) -> str:
    return max((a.get("severity", "info") for a in alerts), key=severity_rank)


def build_graph(services_data: dict[str, Any]) -> nx.DiGraph:
    """Build directed graph. Edge A -> B means A calls/depends on B."""
    graph = nx.DiGraph()

    for service in services_data.get("services", []):
        name = service.get("name")
        if name:
            graph.add_node(name, kind="service", **service)

    for store in services_data.get("stores", []):
        name = store.get("name")
        if name:
            graph.add_node(name, kind="store", **store)

    for edge in services_data.get("edges", []):
        src = edge.get("from")
        dst = edge.get("to")
        if src and dst:
            graph.add_edge(src, dst, **edge)

    return graph


def fingerprint(alert: dict[str, Any]) -> str:
    return f"{alert['service']}|{alert['metric']}|{alert['severity']}"


def deduplicate_alerts(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for alert in sorted(alerts, key=lambda a: a["ts"]):
        fp = fingerprint(alert)

        if fp not in groups:
            item = alert.copy()
            item["fingerprint"] = fp
            item["duplicate_count"] = 1
            item["alert_ids"] = [alert["id"]]
            item["first_seen"] = alert["ts"]
            item["last_seen"] = alert["ts"]
            groups[fp] = item
            continue

        groups[fp]["duplicate_count"] += 1
        groups[fp]["alert_ids"].append(alert["id"])
        groups[fp]["first_seen"] = min(groups[fp]["first_seen"], alert["ts"])
        groups[fp]["last_seen"] = max(groups[fp]["last_seen"], alert["ts"])

        if severity_rank(alert.get("severity")) > severity_rank(groups[fp].get("severity")):
            old_meta = {
                "fingerprint": groups[fp]["fingerprint"],
                "duplicate_count": groups[fp]["duplicate_count"],
                "alert_ids": groups[fp]["alert_ids"],
                "first_seen": groups[fp]["first_seen"],
                "last_seen": groups[fp]["last_seen"],
            }
            groups[fp] = alert.copy()
            groups[fp].update(old_meta)

    return sorted(groups.values(), key=lambda a: a["first_seen"])


def session_groups(alerts: list[dict[str, Any]], gap_sec: int = DEFAULT_GAP_SEC) -> list[list[dict[str, Any]]]:
    if not alerts:
        return []

    sorted_alerts = sorted(alerts, key=lambda a: parse_ts(a.get("first_seen", a["ts"])))
    groups = [[sorted_alerts[0]]]

    for alert in sorted_alerts[1:]:
        current_ts = parse_ts(alert.get("first_seen", alert["ts"]))
        last_ts = parse_ts(groups[-1][-1].get("last_seen", groups[-1][-1]["ts"]))
        gap = (current_ts - last_ts).total_seconds()

        if gap <= gap_sec:
            groups[-1].append(alert)
        else:
            groups.append([alert])

    return groups


def metric_family(metric: str) -> str:
    metric = metric.lower()

    if "db" in metric or "connection" in metric or "pool" in metric:
        return "db"
    if "latency" in metric or "p99" in metric:
        return "latency"
    if "error" in metric or "5xx" in metric or "drop" in metric:
        return "error"
    if "queue" in metric or "lag" in metric or "depth" in metric:
        return "queue"
    if "cpu" in metric or "memory" in metric:
        return "resource"

    return "other"


def metric_compatible(a1: dict[str, Any], a2: dict[str, Any]) -> bool:
    f1 = metric_family(a1["metric"])
    f2 = metric_family(a2["metric"])

    sync_causal = {"db", "latency", "error"}

    if f1 in sync_causal and f2 in sync_causal:
        return True

    if f1 == f2 and f1 != "other":
        return True

    return False


def shortest_path_len(graph: nx.DiGraph, src: str, dst: str) -> int | None:
    try:
        return nx.shortest_path_length(graph, src, dst)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def topology_causal_direction(
    a1: dict[str, Any],
    a2: dict[str, Any],
    graph: nx.DiGraph,
    max_hop: int = DEFAULT_MAX_HOP,
) -> bool:
    """Check dependency direction. Edge A -> B means B can impact A."""
    s1, s2 = a1["service"], a2["service"]

    if s1 == s2:
        return True

    t1 = parse_ts(a1.get("first_seen", a1["ts"]))
    t2 = parse_ts(a2.get("first_seen", a2["ts"]))

    d_1_depends_2 = shortest_path_len(graph, s1, s2)
    d_2_depends_1 = shortest_path_len(graph, s2, s1)

    allowed_disorder_sec = 30

    if d_1_depends_2 is not None and d_1_depends_2 <= max_hop:
        return (t1 - t2).total_seconds() >= -allowed_disorder_sec

    if d_2_depends_1 is not None and d_2_depends_1 <= max_hop:
        return (t2 - t1).total_seconds() >= -allowed_disorder_sec

    return False


def should_merge_alerts(
    a1: dict[str, Any],
    a2: dict[str, Any],
    graph: nx.DiGraph,
    max_hop: int = DEFAULT_MAX_HOP,
) -> bool:
    if a1["service"] == a2["service"]:
        return True

    if not topology_causal_direction(a1, a2, graph, max_hop=max_hop):
        return False

    if not metric_compatible(a1, a2):
        return False

    return True


def topology_grouping(
    alerts: list[dict[str, Any]],
    graph: nx.DiGraph,
    max_hop: int = DEFAULT_MAX_HOP,
) -> list[list[dict[str, Any]]]:
    n = len(alerts)
    if n == 0:
        return []

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if should_merge_alerts(alerts[i], alerts[j], graph, max_hop=max_hop):
                union(i, j)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for i, alert in enumerate(alerts):
        groups[find(i)].append(alert)

    return list(groups.values())


def summarize_cluster(cluster_id: str, grouped_alerts: list[dict[str, Any]]) -> dict[str, Any]:
    all_alert_ids = []
    for alert in grouped_alerts:
        all_alert_ids.extend(alert.get("alert_ids", [alert["id"]]))

    return {
        "cluster_id": cluster_id,
        "alert_count": sum(a.get("duplicate_count", 1) for a in grouped_alerts),
        "services": sorted({a["service"] for a in grouped_alerts}),
        "time_range": [
            min(a.get("first_seen", a["ts"]) for a in grouped_alerts),
            max(a.get("last_seen", a["ts"]) for a in grouped_alerts),
        ],
        "max_severity": max_severity(grouped_alerts),
        "fingerprints": sorted({a["fingerprint"] for a in grouped_alerts}),
        "alert_ids": sorted(all_alert_ids),
    }


def correlate(
    alerts: list[dict[str, Any]],
    graph: nx.DiGraph,
    gap_sec: int = DEFAULT_GAP_SEC,
    max_hop: int = DEFAULT_MAX_HOP,
) -> dict[str, Any]:
    deduped = deduplicate_alerts(alerts)
    sessions = session_groups(deduped, gap_sec=gap_sec)

    clusters = []
    for s_idx, session_alerts in enumerate(sessions):
        for g_idx, group in enumerate(topology_grouping(session_alerts, graph, max_hop=max_hop)):
            clusters.append(summarize_cluster(f"c-{s_idx:03d}-{g_idx:03d}", group))

    input_alerts = len(alerts)
    output_clusters = len(clusters)
    reduction_ratio = 1 - output_clusters / input_alerts if input_alerts else 0

    return {
        "input_alerts": input_alerts,
        "output_clusters": output_clusters,
        "reduction_ratio": round(reduction_ratio, 4),
        "gap_sec": gap_sec,
        "max_hop": max_hop,
        "deduped_alerts": len(deduped),
        "clusters": clusters,
    }


def run_from_files(
    alerts_path: str | Path = "dataset/alerts_sample.jsonl",
    services_path: str | Path = "dataset/services.json",
    output_path: str | Path = "results/cluster_summary.json",
    gap_sec: int = DEFAULT_GAP_SEC,
    max_hop: int = DEFAULT_MAX_HOP,
    verbose: bool = True,
) -> dict[str, Any]:
    alerts_path = Path(alerts_path)
    services_path = Path(services_path)
    output_path = Path(output_path)

    if verbose:
        print("=" * 60)
        print("LOADING DATA")
        print("=" * 60)

    alerts = load_jsonl(alerts_path)
    services_data = load_json(services_path)

    if verbose:
        print("Services:", len(services_data.get("services", [])))
        print("Stores  :", len(services_data.get("stores", [])))
        print("Alerts  :", len(alerts))
        print()
        print("Building graph...")

    graph = build_graph(services_data)

    if verbose:
        print("Nodes:", graph.number_of_nodes())
        print("Edges:", graph.number_of_edges())
        print()
        print("Running full correlation pipeline...")
        print("Layer 1 Dedup fingerprint = service|metric|severity")
        print(f"Layer 2 Session gap_sec = {gap_sec}")
        print(f"Layer 3 Topology max_hop = {max_hop}")
        print("No hard-coded service names")

    result = correlate(alerts, graph, gap_sec=gap_sec, max_hop=max_hop)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if verbose:
        print("Deduped Alerts    :", result["deduped_alerts"])
        print()
        print("=" * 60)
        print("RESULT")
        print("=" * 60)
        print("Input Alerts      :", result["input_alerts"])
        print("Deduped Alerts    :", result["deduped_alerts"])
        print("Output Clusters   :", result["output_clusters"])
        print("Reduction Ratio   :", f'{result["reduction_ratio"]:.2%}')
        print()
        print("Saved ->", output_path)
        print()
        print("Cluster preview:")
        for cluster in result["clusters"]:
            print(
                cluster["cluster_id"],
                "alerts=", cluster["alert_count"],
                "services=", cluster["services"],
                "fingerprints=", len(cluster["fingerprints"]),
            )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AIOps alert correlation pipeline.")
    parser.add_argument("--alerts", default="dataset/alerts_sample.jsonl")
    parser.add_argument("--services", default="dataset/services.json")
    parser.add_argument("--output", default="results/cluster_summary.json")
    parser.add_argument("--gap-sec", type=int, default=DEFAULT_GAP_SEC)
    parser.add_argument("--max-hop", type=int, default=DEFAULT_MAX_HOP)

    args = parser.parse_args()

    run_from_files(
        alerts_path=args.alerts,
        services_path=args.services,
        output_path=args.output,
        gap_sec=args.gap_sec,
        max_hop=args.max_hop,
        verbose=True,
    )


if __name__ == "__main__":
    main()
