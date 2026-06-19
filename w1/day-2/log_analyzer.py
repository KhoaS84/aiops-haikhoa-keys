import argparse
import re
from datetime import datetime
from pathlib import Path

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
import pandas as pd


def parse_timestamp(line: str):
    match = re.match(r"^(?P<date>\d{6})\s+(?P<time>\d{6})", line)
    if not match:
        return None
    return datetime.strptime(match.group("date") + match.group("time"), "%y%m%d%H%M%S")


def analyze_log(log_path: Path, sim_th: float = 0.5, max_lines: int | None = None):
    cfg = TemplateMinerConfig()
    cfg.drain_sim_th = sim_th
    miner = TemplateMiner(config=cfg)

    records = []
    total_lines = 0
    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            total_lines += 1
            ts = parse_timestamp(line)
            result = miner.add_log_message(line.strip())
            records.append({
                "timestamp": ts,
                "template_id": result["cluster_id"],
                "template": result["template_mined"],
            })
            if max_lines is not None and total_lines >= max_lines:
                break

    df_logs = pd.DataFrame(records)
    num_templates = len(miner.drain.clusters)

    top5 = (
        df_logs["template_id"]
        .value_counts()
        .head(5)
        .rename_axis("template_id")
        .reset_index(name="count")
    )
    top5["pct"] = (top5["count"] / total_lines * 100).round(2)

    if df_logs["timestamp"].notna().any():
        df_logs = df_logs.dropna(subset=["timestamp"]).sort_values("timestamp")
        df_logs["hour"] = df_logs["timestamp"].dt.floor("1h")
        hour_counts = (
            df_logs.groupby(["hour", "template_id"]).size().unstack(fill_value=0)
        )

        last_hour = hour_counts.index.max()
        last_counts = hour_counts.loc[last_hour]
        prev = hour_counts.loc[hour_counts.index < last_hour]
        if not prev.empty:
            mean = prev.mean()
            std = prev.std().replace(0, pd.NA)
            spike_mask = last_counts > (mean + 3 * std)
            spike_templates = last_counts[spike_mask].sort_values(ascending=False)
        else:
            spike_templates = pd.Series(dtype=int)

        first_seen = df_logs.groupby("template_id")["hour"].min()
        new_templates = first_seen[first_seen == last_hour].index.tolist()
    else:
        spike_templates = pd.Series(dtype=int)
        new_templates = []

    return {
        "total_lines": total_lines,
        "num_templates": num_templates,
        "top5": top5,
        "spike_templates": spike_templates,
        "new_templates": new_templates,
    }


def main():
    parser = argparse.ArgumentParser(description="Mini log analyzer")
    parser.add_argument("log_file", help="Path to log file")
    parser.add_argument("--sim-th", type=float, default=0.5, help="Drain3 sim threshold")
    parser.add_argument("--max-lines", type=int, default=None, help="Max lines to read")
    args = parser.parse_args()

    result = analyze_log(Path(args.log_file), sim_th=args.sim_th, max_lines=args.max_lines)

    print(f"Total lines: {result['total_lines']}")
    print(f"Unique templates: {result['num_templates']}")

    print("Top-5 templates (count, %):")
    for _, row in result["top5"].iterrows():
        print(f"  {row['template_id']}: {row['count']} ({row['pct']}%)")

    print("Templates spike in last hour:")
    if result["spike_templates"].empty:
        print("  None")
    else:
        for tid, cnt in result["spike_templates"].items():
            print(f"  {tid}: {cnt}")

    print("New templates in last hour:")
    if not result["new_templates"]:
        print("  None")
    else:
        for tid in result["new_templates"]:
            print(f"  {tid}")


if __name__ == "__main__":
    main()
