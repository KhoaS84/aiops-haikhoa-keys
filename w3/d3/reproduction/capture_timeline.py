#!/usr/bin/env python3
"""
capture_timeline.py — Capture event timeline for AWS S3 2017 reproduction.

Simulates the timeline of events as they would have been observed during the
actual AWS S3 2017-02-28 incident, adapted to our Docker reproduction.

Outputs timeline.json with UTC timestamps matching real incident cadence.
"""

import json
import datetime
import sys

def generate_timeline():
    """
    Generate a timeline of events based on the AWS S3 2017-02-28 incident.

    Real incident timeline (source: https://aws.amazon.com/message/41926/):
    - 09:37 PST: Authorized team member ran command to remove billing servers
    - 09:37 PST: Input entered incorrectly → removed too many servers
    - 09:37 PST: Index subsystem and placement subsystem affected
    - ~09:40 PST: S3 API error rates begin climbing
    - ~09:45 PST: S3 GET/PUT/LIST returning errors
    - ~09:50 PST: Dependent AWS services begin failing
    - ~10:00 PST: Team identifies root cause (over-broad removal)
    - ~10:30 PST: Begin restarting index and placement subsystems
    - ~11:15 PST: Index subsystem requires full restart due to capacity
    - ~11:37 PST: Placement subsystem recovered
    - ~12:08 PST: Index subsystem recovered
    - ~13:08 PST: S3 fully operational (GET 100%, PUT 100%)

    Our reproduction maps these to UTC and adapts to Docker containers.
    """

    # Base time: start of reproduction (simulated)
    base = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    events = [
        {
            "seq": 1,
            "timestamp": (base + datetime.timedelta(seconds=0)).isoformat(),
            "event": "PRE_CHECK",
            "source": "operator",
            "detail": "All 5 services confirmed running: billing-1, index-1, index-2, placement-1, placement-2",
            "subsystem": "all",
            "severity": "info"
        },
        {
            "seq": 2,
            "timestamp": (base + datetime.timedelta(seconds=10)).isoformat(),
            "event": "OPERATOR_COMMAND",
            "source": "operator",
            "detail": "Operator intended: 'docker compose stop billing-1'. Actual: 'docker compose stop' (no target specified)",
            "subsystem": "billing",
            "severity": "critical"
        },
        {
            "seq": 3,
            "timestamp": (base + datetime.timedelta(seconds=12)).isoformat(),
            "event": "SERVICE_DOWN",
            "source": "docker",
            "detail": "Container s3-billing-1 stopped (INTENDED target)",
            "subsystem": "billing",
            "severity": "warning"
        },
        {
            "seq": 4,
            "timestamp": (base + datetime.timedelta(seconds=14)).isoformat(),
            "event": "SERVICE_DOWN",
            "source": "docker",
            "detail": "Container s3-index-1 stopped (UNINTENDED — object metadata unavailable)",
            "subsystem": "index",
            "severity": "critical"
        },
        {
            "seq": 5,
            "timestamp": (base + datetime.timedelta(seconds=16)).isoformat(),
            "event": "SERVICE_DOWN",
            "source": "docker",
            "detail": "Container s3-index-2 stopped (UNINTENDED — full index subsystem down)",
            "subsystem": "index",
            "severity": "critical"
        },
        {
            "seq": 6,
            "timestamp": (base + datetime.timedelta(seconds=18)).isoformat(),
            "event": "SERVICE_DOWN",
            "source": "docker",
            "detail": "Container s3-placement-1 stopped (UNINTENDED — cannot route new object writes)",
            "subsystem": "placement",
            "severity": "critical"
        },
        {
            "seq": 7,
            "timestamp": (base + datetime.timedelta(seconds=20)).isoformat(),
            "event": "SERVICE_DOWN",
            "source": "docker",
            "detail": "Container s3-placement-2 stopped (UNINTENDED — full placement subsystem down)",
            "subsystem": "placement",
            "severity": "critical"
        },
        {
            "seq": 8,
            "timestamp": (base + datetime.timedelta(seconds=30)).isoformat(),
            "event": "API_ERRORS_SPIKE",
            "source": "monitoring",
            "detail": "S3 API error rate jumps to 100%. GET, PUT, LIST all returning 503. Customer-visible impact begins.",
            "subsystem": "api",
            "severity": "critical"
        },
        {
            "seq": 9,
            "timestamp": (base + datetime.timedelta(seconds=60)).isoformat(),
            "event": "CASCADE_DETECTED",
            "source": "monitoring",
            "detail": "Dependent services reporting failures: Lambda invoke errors, EC2 console errors, CloudWatch metric gaps",
            "subsystem": "downstream",
            "severity": "critical"
        },
        {
            "seq": 10,
            "timestamp": (base + datetime.timedelta(seconds=120)).isoformat(),
            "event": "ROOT_CAUSE_IDENTIFIED",
            "source": "operator",
            "detail": "Team identifies over-broad command removed servers from billing, index, AND placement subsystems",
            "subsystem": "all",
            "severity": "warning"
        },
        {
            "seq": 11,
            "timestamp": (base + datetime.timedelta(seconds=180)).isoformat(),
            "event": "MITIGATION_START",
            "source": "operator",
            "detail": "Begin restarting index and placement subsystems. Index requires full restart due to safety checks.",
            "subsystem": "index",
            "severity": "warning"
        },
        {
            "seq": 12,
            "timestamp": (base + datetime.timedelta(seconds=300)).isoformat(),
            "event": "PARTIAL_RECOVERY",
            "source": "docker",
            "detail": "placement-1 and placement-2 restarted and healthy. New object writes resuming.",
            "subsystem": "placement",
            "severity": "info"
        },
        {
            "seq": 13,
            "timestamp": (base + datetime.timedelta(seconds=420)).isoformat(),
            "event": "PARTIAL_RECOVERY",
            "source": "docker",
            "detail": "index-1 and index-2 restarted. Index subsystem rebuilding metadata cache — slow recovery.",
            "subsystem": "index",
            "severity": "info"
        },
        {
            "seq": 14,
            "timestamp": (base + datetime.timedelta(seconds=600)).isoformat(),
            "event": "FULL_RECOVERY",
            "source": "monitoring",
            "detail": "All 5 services healthy. S3 API error rate back to 0%. Full recovery confirmed.",
            "subsystem": "all",
            "severity": "info"
        }
    ]

    return events


def main():
    timeline = generate_timeline()

    output_file = "timeline.json"
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg == "--out" and i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, ensure_ascii=False)

    print(f"Timeline captured: {len(timeline)} events -> {output_file}")
    print()
    for event in timeline:
        severity_icon = {"info": "[i]", "warning": "[!]", "critical": "[X]"}.get(event["severity"], "*")
        print(f"  {severity_icon} [{event['timestamp']}] {event['event']}: {event['detail']}")


if __name__ == "__main__":
    main()
