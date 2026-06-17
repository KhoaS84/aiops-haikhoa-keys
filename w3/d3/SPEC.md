# AIOps Mini-Platform Spec — haikhoa

## 1. Platform overview

AIOps platform monitoring a 10-service microservice stack (api-gateway, payment-svc, payment-db, inventory-svc, checkout-svc, auth-svc, notification-svc, log-collector, frontend, dns-resolver). The platform provides automated anomaly detection, alert correlation, and root cause analysis to reduce MTTR for the on-call SRE team. Target users: SRE on-call engineers and platform team leads.

## 2. SLO definition (from W3-D1)

3 services with SLI + SLO + error budget:

| Service | SLI | SLO Target | Error Budget (events/month) | Downtime Equivalent |
|---------|-----|------------|---------------------------|---------------------|
| **api** | Availability: `count(2xx,3xx,4xx_not_429 AND latency<500ms) / count(all)` | 99.9% | 20,737 failures allowed out of 20,737,800 total | 43 minutes/month |
| **db** | Latency: `count(success AND duration<100ms) / count(all)` | 99.95% | 863 failures allowed out of 1,726,380 total | 22 minutes/month |
| **frontend** | Availability: `count(dom_ready<3000 AND no_js_err AND no_net_err) / count(all)` | 99.0% | 51,840 failures allowed out of 5,184,000 total | 432 minutes/month |

Burn-rate alerting: 3-tier MWMBR (Multi-Window, Multi-Burn-Rate) alerts configured per service. Tier 1 (burn rate ≥ 14.4×, 1h+5m windows) → page on-call. Tier 2 (burn rate ≥ 6×, 6h+30m windows) → page. Tier 3 (burn rate ≥ 1×, 3d+6h windows) → ticket. Noise reduction: 86.4% compared to static threshold alerts.

Reference: `slo_spec.yaml`, `burn_rate_alerts.yaml` (W3-D1 deliverables)

## 3. Detection + Correlation + RCA stack (from W1+W2)

**Detection layer:** Z-score anomaly detection (3σ threshold) on sliding windows of metric time series. Monitors error_rate, latency_p99, availability, and connection_pool_usage per service. Strengths: zero false alarms (precision 1.00), fast detection for clear signals (MTTD p50=28s). Weakness: 3σ threshold too conservative for subtle faults — consider 2σ for tier-2 dashboard alerts.

**Correlation layer:** Alert correlation groups co-occurring alerts within a configurable time window. Groups alerts by temporal proximity and service dependency graph edges. Reduces alert noise by presenting correlated alert groups instead of individual alerts.

**RCA layer:** Currently count-based ranking (pick loudest service). Per ADR-001, migrating to topology-aware composite scorer combining: (1) topology distance with upstream bias, (2) first-drift time via Granger causality, (3) alert volume as tiebreaker only. Expected improvement: RCA accuracy from 67% (6/9) to >85%.

## 4. Reliability validation (from W3-D2)

Chaos engineering scoreboard (10 experiments):

| Metric | Result |
|--------|--------|
| Detected | 9/10 (90%) |
| RCA correct | 6/9 (67%) |
| False alarms | 0 |
| MTTD p50 | 28s |
| MTTD p95 | 53s |
| Verdict | PASS |

Top 3 gaps:
1. **No meta-monitoring:** Pipeline cannot monitor its own infrastructure (Experiment #7 — log-collector disk fill missed entirely). Monitoring dependency loop.
2. **RCA picks loudest, not root:** Experiments #4, #9, #10 — downstream retry amplification fools count-based RCA.
3. **Infrastructure dependencies invisible:** DNS resolver not in dependency graph — DNS faults misattributed to payment-svc.

Reference: `chaos_report.md` (W3-D2 deliverable)

## 5. Operational pattern (from W3-D3)

**Reproduced outage:** AWS S3 2017-02-28 — Operator action without guardrail.

Reproduction used Docker Compose with 5 containers (billing-1, index-1, index-2, placement-1, placement-2) across 3 subsystems. Injection: `docker compose stop` without service target → all 5 containers stopped (intended: only billing-1).

**Key learnings:**
1. Blast-radius guardrails are mandatory — one over-broad command should never be able to affect multiple critical subsystems.
2. Monitoring dependency loops are real — AWS Service Health Dashboard depended on S3, making the outage invisible through normal channels. Same pattern as our Experiment #7 (log-collector).
3. Recovery time for systems that have never been fully restarted is unpredictable — S3 index subsystem restart took hours because it had never been exercised at scale.

**Architecture decision:** ADR-001 — Switch from count-based to topology-aware RCA. Motivated by the cascading failure pattern observed in both the S3 outage and our chaos experiments.

Reference: `postmortem.md`, `ADR.md` (W3-D3 deliverables)

## 6. Cost model (from W3-D3)

Cost model output for our current stack profile (Vietnamese fintech, 60 services):

```
Scenario: Vietnamese fintech (60 services, 4 inc/mo, $30k/h)
  Monthly value saved: $72,000
  Monthly AIOps cost:  $12,000
  ROI: 6.0x
  Payback: 0.17 months (~5 days)
  Verdict: worth_it
```

Break-even point: AIOps becomes worth_it when `incidents/mo × duration × MTTR_reduction% × downtime_cost/h > 1.5 × aiops_cost`. For our stack, even reducing to 2 incidents/month at $15k/h downtime still yields ROI 1.5× — the break-even floor.

Reference: `cost_model.py` (W3-D3 deliverable)

## 7. Open risks

| # | Risk | Severity | Mitigation Plan |
|---|------|----------|-----------------|
| 1 | **Meta-monitoring gap:** Pipeline cannot detect its own infrastructure failures (log-collector, Prometheus, Kafka). If monitoring stack fails during an incident, on-call has no visibility. | High | Add independent watchdog process that checks pipeline health via heartbeat. Deploy on separate infrastructure from monitored stack. Target: 2 weeks. |
| 2 | **RCA weight tuning:** ADR-001 topology-aware scorer uses untested weights (0.5/0.4/0.1). May perform worse than count-based in some edge cases until empirically tuned. | Medium | Run full chaos suite (10 experiments) with new scorer, grid-search weights, validate RCA accuracy ≥ 80%. Target: 1 week after ADR-001 implementation. |
| 3 | **Dependency graph staleness:** Topology-aware RCA depends on an accurate service dependency graph. Graph not auto-updated on deploys — will drift from reality over time. | Medium | Auto-discover topology from OpenTelemetry trace span parent-child relationships. Run nightly graph refresh job. Alert if graph age > 48 hours. Target: 3 weeks. |
| 4 | **Single-region deployment:** All monitoring infrastructure runs in one region. Regional outage (like S3 us-east-1) would take down both the monitored stack AND the monitoring stack. | High | Deploy monitoring stack replica in second region with independent storage. Cross-region health check. Target: 6 weeks (requires infrastructure budget approval). |
| 5 | **3σ threshold too conservative for subtle faults:** Current detector misses slow-burn degradation that stays within 3σ but still impacts user experience. SLO burn-rate alerts partially cover this gap but rely on Prometheus availability. | Low | Implement dual-threshold: 3σ for page-level alerts, 2σ for dashboard/ticket-level alerts. Combine with SLO burn-rate as independent signal. Target: 2 weeks. |
