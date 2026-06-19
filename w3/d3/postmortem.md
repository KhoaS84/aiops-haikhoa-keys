# Postmortem: AWS S3 us-east-1 Outage (Reproduction)

**Status:** complete  
**Date:** 2026-06-17  
**Authors:** haikhoa  
**Severity:** SEV1  
**Duration:** ~240 minutes (17:37 UTC → 21:08 UTC, 2017-02-28)

## Summary

On 2017-02-28, an authorized S3 team member executed a command intended to remove a small number of servers for the S3 billing subsystem. Due to an incorrect input to the command, a much larger set of servers was removed than intended, including critical servers for the S3 index subsystem (which maps object keys to storage locations) and the S3 placement subsystem (which manages allocation of new storage). This caused S3 to be unable to serve GET, PUT, and LIST requests, triggering cascading failures across AWS services dependent on S3 (Lambda, EC2 console, CloudWatch, IoT, etc.). Recovery took approximately 4 hours due to the index subsystem requiring a full restart — a process that had not been exercised at this scale in years.

## Impact

- Users affected: millions of AWS customers globally (S3 us-east-1 serves ~50% of all S3 traffic)
- Revenue impact: estimated $150M+ across AWS customers (ITIC downtime survey extrapolation)
- SLO budget consumed: S3 availability SLO (99.99%) burned through entire monthly error budget in ~4 hours. 240 minutes downtime = 55× the allowed 4.3 minutes/month.
- External communication: AWS Service Health Dashboard initially showed green (the dashboard itself depended on S3), status page updated manually after ~45 minutes, full post-event summary published at https://aws.amazon.com/message/41926/

## Timeline (UTC)

| Time  | Event |
|-------|-------|
| 17:37 | Operator executes removal command targeting billing subsystem servers. Input entered incorrectly — command scope far broader than intended. |
| 17:37 | Index subsystem servers removed (UNINTENDED). Object metadata lookups begin failing. |
| 17:38 | Placement subsystem servers removed (UNINTENDED). New object allocation impossible. |
| 17:40 | S3 API error rate spikes. GET, PUT, LIST returning 503 ServiceUnavailable. Customer-visible impact begins. |
| 17:45 | Cascading failures propagate: AWS Lambda (stores code in S3), EC2 console (static assets in S3), CloudWatch (metric storage), IoT platform all degraded. |
| 17:52 | AWS internal monitoring detects anomaly. On-call team paged. |
| 18:00 | Root cause identified: over-broad server removal command affected 3 subsystems instead of 1. |
| 18:15 | Mitigation begins: team starts restarting index and placement subsystems. |
| 18:30 | Placement subsystem recovery begins. Placement uses a simpler architecture — restarts proceed. |
| 19:37 | Placement subsystem fully recovered. New object writes resume. |
| 20:15 | Index subsystem recovery complicated: full restart required because index had not been restarted at scale in years. Safety checks and capacity validation slow the process. |
| 21:08 | Index subsystem fully recovered. S3 GET/PUT/LIST back to 100% success rate. Full recovery confirmed. |

## Root cause

The removal tool accepted a parameter specifying the number of servers to remove from a given subsystem. The operator entered an incorrect value that was significantly larger than intended. The tool did not validate whether the removal scope would cross subsystem boundaries or exceed safe operational limits.

The tool had no blast-radius limit — it would faithfully remove however many servers were specified, even if that meant removing all servers from multiple critical subsystems. There was no confirmation prompt, no dry-run mode, and no rate-limit on concurrent removals.

Detection was delayed because the AWS Service Health Dashboard itself depended on S3, creating a monitoring dependency loop — the very system meant to report outages was affected by the outage.

## Contributing factors

- Removal tool lacked blast-radius guardrails: no maximum removal count, no cross-subsystem protection, no confirmation prompt for large-scale operations
- Index subsystem had not been fully restarted in years — the team did not know how long a full restart would take at current scale, extending recovery time
- Service Health Dashboard depended on S3 — monitoring dependency loop meant customers (and AWS) couldn't see the outage status through normal channels
- No canary/staged removal process — the command executed atomically against the full target set instead of removing in small batches with health checks between batches

## Detection

- The incident was detected by internal monitoring approximately 15 minutes after the operator command, after S3 error rates exceeded threshold.
- Could it have been detected earlier? **Yes.** Two gaps identified:
  1. **Gap 1: No pre-execution validation.** The removal tool could have checked: "This operation will remove N servers across M subsystems. Subsystems affected: billing, index, placement. Proceed? [y/N]". This would have caught the error before any server was removed.
  2. **Gap 2: Monitoring dependency on S3.** The Service Health Dashboard stored its data in S3 — when S3 went down, the dashboard showed green. An independent monitoring path (not dependent on S3) would have surfaced the outage to customers sooner.

## Response

- **What went well:** Root cause was identified quickly once the team was engaged (~23 minutes). The placement subsystem recovered within 2 hours.
- **What went poorly:** Index subsystem recovery took much longer than expected because a full restart at this scale had never been tested. The team had to discover the restart procedure under incident pressure.
- **Where we got lucky:** The operator command did not affect the S3 storage subsystem itself — data was intact, only the metadata index and placement routing were affected. If storage nodes had been removed, data loss could have been permanent.

## Action items

| Item | Owner | Due | Priority |
|------|-------|-----|----------|
| Add blast-radius limit to removal tool: max N servers per invocation, require explicit override for cross-subsystem operations | S3 Tooling Team | 2017-03-15 | P0 |
| Add confirmation prompt with dry-run output showing affected subsystems and server count before execution | S3 Tooling Team | 2017-03-15 | P0 |
| Implement staged removal: remove in batches of 5%, health-check between batches, auto-abort if error rate exceeds threshold | S3 Tooling Team | 2017-03-31 | P0 |
| Decouple Service Health Dashboard from S3: use independent storage/CDN for status page | AWS Platform Team | 2017-04-30 | P1 |
| Run full index subsystem restart drill quarterly to validate recovery time and identify bottlenecks | S3 Operations Team | 2017-04-15 | P1 |
| Add meta-monitoring: independent watchdog that checks S3 availability from outside the AWS network | AWS Monitoring Team | 2017-04-30 | P2 |
