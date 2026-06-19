"""
cost_model.py — Break-even analysis for AIOps platform investment.

Implements the cost model from W3-D3 theory to determine whether
deploying an AIOps platform is financially justified given the
organization's incident profile and downtime costs.
"""


def is_worth_it(
    num_services: int,
    incidents_per_month: int,
    avg_incident_duration_hours: float,
    downtime_cost_per_hour: float,
    expected_mttr_reduction_pct: float = 0.4,
    aiops_monthly_cost: float = 15_000,
) -> dict:
    """
    Calculate ROI and break-even for an AIOps platform investment.

    Args:
        num_services: Number of microservices being monitored.
        incidents_per_month: Average incidents per month.
        avg_incident_duration_hours: Average incident duration in hours.
        downtime_cost_per_hour: Cost of downtime per hour ($).
        expected_mttr_reduction_pct: Expected MTTR reduction from AIOps (0-1).
            Default 0.4 = 40% reduction, based on industry benchmarks
            (Moogsoft 2023, PagerDuty State of Digital Operations 2024).
        aiops_monthly_cost: Total monthly cost of running AIOps platform ($).
            Includes: compute, storage, ingestion, engineer time allocation.

    Returns:
        dict with keys:
            monthly_value: Dollar value of downtime saved per month
            monthly_cost: Total AIOps platform cost per month
            roi: Return on investment ratio (value / cost)
            payback_months: Months to break even (inf if no value)
            verdict: "worth_it" | "marginal" | "not_worth_it"

    Verdict rules:
        roi > 1.5  -> worth_it       (clear positive ROI)
        1.0 < roi <= 1.5 -> marginal (barely positive, consider other factors)
        roi <= 1.0 -> not_worth_it   (costs exceed value)
    """
    # Value = hours saved * cost per hour
    monthly_downtime_hours = incidents_per_month * avg_incident_duration_hours
    monthly_value = (
        monthly_downtime_hours
        * expected_mttr_reduction_pct
        * downtime_cost_per_hour
    )

    # ROI and payback
    roi = monthly_value / aiops_monthly_cost if aiops_monthly_cost > 0 else float("inf")
    payback_months = aiops_monthly_cost / monthly_value if monthly_value > 0 else float("inf")

    # Verdict
    if roi > 1.5:
        verdict = "worth_it"
    elif roi > 1.0:
        verdict = "marginal"
    else:
        verdict = "not_worth_it"

    return {
        "monthly_value": round(monthly_value, 2),
        "monthly_cost": round(aiops_monthly_cost, 2),
        "roi": round(roi, 2),
        "payback_months": round(payback_months, 2) if payback_months != float("inf") else float("inf"),
        "verdict": verdict,
    }


if __name__ == "__main__":
    # ================================================================
    # Scenario 1: Small e-commerce, few incidents
    # 20 services, 2 incidents/mo x 1h each, $10k/h downtime
    # Expected: NOT worth it — too few incidents to justify $15k/mo
    # ================================================================
    result1 = is_worth_it(
        num_services=20,
        incidents_per_month=2,
        avg_incident_duration_hours=1,
        downtime_cost_per_hour=10_000,
        aiops_monthly_cost=15_000,
    )
    print("Scenario 1 — Small e-commerce (20 services, 2 inc/mo, $10k/h):")
    print(f"  Value: ${result1['monthly_value']:,.0f}/mo | Cost: ${result1['monthly_cost']:,.0f}/mo")
    print(f"  ROI: {result1['roi']} | Payback: {result1['payback_months']} months")
    print(f"  Verdict: {result1['verdict']}")
    print()

    # ================================================================
    # Scenario 2: Mid-size SaaS, moderate incidents
    # 100 services, 5 incidents/mo x 2h each, $20k/h downtime
    # Expected: WORTH IT — enough volume and cost to justify
    # ================================================================
    result2 = is_worth_it(
        num_services=100,
        incidents_per_month=5,
        avg_incident_duration_hours=2,
        downtime_cost_per_hour=20_000,
        aiops_monthly_cost=25_000,
    )
    print("Scenario 2 — Mid-size SaaS (100 services, 5 inc/mo, $20k/h):")
    print(f"  Value: ${result2['monthly_value']:,.0f}/mo | Cost: ${result2['monthly_cost']:,.0f}/mo")
    print(f"  ROI: {result2['roi']} | Payback: {result2['payback_months']} months")
    print(f"  Verdict: {result2['verdict']}")
    print()

    # ================================================================
    # Scenario 3 (custom): Vietnamese fintech startup
    #
    # Industry: Digital payment / e-wallet (similar to MoMo, ZaloPay)
    # Why this downtime cost:
    #   - Vietnam digital payment market: $15B+ transaction volume/year (2024)
    #   - Mid-tier fintech processes ~$50M/month in transactions
    #   - Even 1 hour downtime blocks transactions, causes user churn,
    #     regulatory reporting obligations (State Bank of Vietnam Circular 09)
    #   - Estimated $30k/hour: $15k direct transaction loss +
    #     $10k user churn/trust damage + $5k regulatory/compliance cost
    #
    # 60 services (payment gateway, KYC, ledger, notification, fraud detection...)
    # 4 incidents/month (common for fast-growing startups with frequent deploys)
    # 1.5h average duration (typical for teams with basic monitoring)
    # AIOps cost: $12k/mo (self-hosted Prometheus + Grafana + custom ML pipeline)
    # ================================================================
    result3 = is_worth_it(
        num_services=60,
        incidents_per_month=4,
        avg_incident_duration_hours=1.5,
        downtime_cost_per_hour=30_000,
        aiops_monthly_cost=12_000,
    )
    print("Scenario 3 — Vietnamese fintech (60 services, 4 inc/mo, $30k/h):")
    print(f"  Value: ${result3['monthly_value']:,.0f}/mo | Cost: ${result3['monthly_cost']:,.0f}/mo")
    print(f"  ROI: {result3['roi']} | Payback: {result3['payback_months']} months")
    print(f"  Verdict: {result3['verdict']}")
    print()
    print("  Justification: Vietnamese fintech with 60 microservices serving")
    print("  digital payment flows. $30k/h downtime cost reflects direct")
    print("  transaction loss ($15k), user trust/churn ($10k), and regulatory")
    print("  compliance cost ($5k) per SBV Circular 09. Self-hosted AIOps at")
    print("  $12k/mo makes strong ROI case at 6.0x return.")
