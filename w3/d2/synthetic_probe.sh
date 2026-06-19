#!/usr/bin/env bash
# synthetic_probe.sh — W3-D2 Chaos Engineering Lab
# External blackbox probe: log pass/fail mỗi 5s
# Dùng làm steady-state signal (§6.4)
#
# Usage:
#   nohup bash synthetic_probe.sh http://localhost:8080/checkout/health probe.log &
#   echo $! > probe.pid
#
# Steady-state: ≥ 99% pass trong window 60s
# Before inject: chạy 5 phút → confirm baseline
# During inject: pass-rate drop → quantify user impact
# After rollback: pass-rate về ≥ 99% trong 2 phút

ENDPOINT="${1:-http://localhost:8080/checkout/health}"
LOG="${2:-probe.log}"
TIMEOUT_SEC=2
LATENCY_THRESHOLD_MS=500
INTERVAL_SEC=5

echo "=== Synthetic Probe Started ===" >> "$LOG"
echo "Endpoint: $ENDPOINT" >> "$LOG"
echo "Threshold: HTTP 200 && latency < ${LATENCY_THRESHOLD_MS}ms" >> "$LOG"
echo "Interval: ${INTERVAL_SEC}s" >> "$LOG"
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
echo "---" >> "$LOG"

while true; do
  ts=$(date -u +%s)
  start=$(date +%s%N)

  # Gọi endpoint, capture HTTP status code
  code=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time "$TIMEOUT_SEC" \
    "$ENDPOINT" 2>/dev/null)

  end=$(date +%s%N)
  latency_ms=$(( (end - start) / 1000000 ))

  # Evaluate pass/fail
  if [[ "$code" == "200" && "$latency_ms" -lt "$LATENCY_THRESHOLD_MS" ]]; then
    echo "$ts pass $latency_ms" >> "$LOG"
  else
    echo "$ts fail $code $latency_ms" >> "$LOG"
  fi

  sleep "$INTERVAL_SEC"
done
