# ADR-001: Use topology-aware RCA over count-based alert ranking

## Status

Accepted

## Context

Our AIOps pipeline needs to identify the root-cause service when multiple services fire alerts simultaneously during an incident. The current RCA approach ranks services by **alert count / severity** — the service with the most or loudest alerts is designated as root cause.

This approach fails in two observed scenarios from our chaos engineering validation (W3-D2):

1. **Retry storm amplification (Experiment #10):** checkout-svc returns 500 → payment-svc retries 3× → payment-svc generates 3× more error alerts than checkout-svc → RCA picks payment-svc (wrong). The actual root cause (checkout-svc) had fewer alerts because it failed fast while downstream amplified the noise.

2. **Cascade through API gateway (Experiment #4):** api-gateway CPU stress → all downstream services slow → payment-svc has highest absolute latency increase (because it does the most work per request) → RCA picks payment-svc (wrong). The actual root cause (api-gateway) showed moderate latency increase because it's just a proxy.

3. **Infrastructure blind spot (Experiment #9):** DNS slow → all services affected → payment-svc loudest → RCA picks payment-svc (wrong). dns-resolver is not even in the dependency graph.

These failures match the **cascading failure** pattern from the AWS S3 2017 postmortem: the most-affected component is not the root cause — it's the downstream victim. The S3 outage showed that without topology awareness, teams waste time investigating symptoms instead of causes.

## Decision

Replace count-based RCA ranking with a **3-signal composite scorer**:

1. **Topology distance (upstream bias):** Services closer to the edge (upstream) in the dependency graph receive higher root-cause likelihood scores. Rationale: in cascading failures, the root cause is upstream and downstream services are victims.

2. **First-drift time (temporal causality):** The service whose metrics deviated from baseline *earliest* receives a higher score. Implementation: compare anomaly onset timestamps across services. The service that drifted first is more likely to be root cause. Advanced: Granger causality test on metric time series pairs.

3. **Alert volume (tiebreaker only):** When topology distance and first-drift time are tied, use alert count as tiebreaker. Never as primary signal.

Scoring formula:
```
score(service) = w1 * topology_rank(service)     # 0.5 weight
               + w2 * first_drift_rank(service)  # 0.4 weight  
               + w3 * alert_volume_rank(service)  # 0.1 weight
```

## Alternatives considered

### Alternative A: Count-based ranking (current approach)
- **Pros:** Simple to implement, fast (O(n) where n = services), no dependency graph needed, zero infrastructure overhead
- **Cons:** Fails on cascading failures (3/9 RCA wrong in chaos tests), fails on retry storms, picks downstream victims instead of upstream root cause. Fundamentally flawed for microservice architectures where downstream amplification is common.
- **Why rejected:** 33% wrong RCA rate is unacceptable. Each wrong RCA adds ~15 minutes of wasted investigation time during incidents.

### Alternative B: LLM-only RCA (GPT-4 / Claude with alert context)
- **Pros:** Flexible, can reason about novel failure modes, can incorporate free-text logs and runbooks, no dependency graph maintenance needed
- **Cons:** Hallucination risk — LLM can confidently name wrong root cause. Latency (3-10s per inference vs <100ms for graph scoring). Cost ($0.03-0.10 per RCA query). Requires internet/API access during incidents (when network may be degraded). Non-deterministic — same input can produce different answers.
- **Why rejected as primary:** Cannot be trusted as sole RCA signal during SEV1 incidents. Acceptable as secondary signal or for generating human-readable explanation of RCA result.

### Alternative C: Graph PageRank only (topology-only)
- **Pros:** Captures topology relationships, well-understood algorithm, deterministic, fast
- **Cons:** Ignores temporal causality — doesn't know *when* each service started failing. Two services at same topology depth are indistinguishable. Cannot handle infrastructure dependencies not in the graph (DNS, load balancers).
- **Why rejected as standalone:** Necessary but not sufficient. Combining with temporal analysis addresses the temporal blind spot.

## Consequences

### Positive
- Catches cascading failure patterns that count-based ranking misses. Verified against Experiment #4 (api-gateway cascade) and #10 (checkout retry storm) scenarios — topology + first-drift correctly identifies upstream root cause in both cases.
- Composable and graceful degradation: if dependency graph is stale, first-drift + alert volume still provide reasonable RCA. If timing data is noisy, topology + alert volume still outperforms count-only.

### Negative (trade-offs accepted)
- Higher compute cost: Granger causality test is O(n × lag_window) per service pair. For 60 services with 5-minute lag window at 1s resolution, this is ~540K operations per RCA query. Acceptable given RCA runs only during incidents (not continuous).
- Requires dependency graph to be kept up-to-date. Stale graph = degraded topology signal. Adds operational burden: graph must be refreshed on every deploy that changes service dependencies. Mitigation: auto-discover topology from trace data (OpenTelemetry span parent-child relationships).

### Risks
- Signal weights (0.5 / 0.4 / 0.1) are initial estimates, not empirically tuned. Need to validate against more incident scenarios and adjust. Plan: run all 10 chaos experiments with new scorer, compare RCA accuracy, tune weights via grid search.
- Infrastructure dependencies (DNS, load balancers, storage) are still not in the default dependency graph. Mitigated by ADR follow-up: expand graph to include infrastructure components.
