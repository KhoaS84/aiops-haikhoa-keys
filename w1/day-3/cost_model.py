import pandas as pd

def estimate_cost():
    tiers = {
        "Small" : {"Services": 10, "log_gb": 50, "metric_eps": 100_000},
        "Medium": {"Services": 20, "log_gb": 100, "metric_eps": 1_000_000},
        "Large" : {"Services": 50, "log_gb": 200, "metric_eps": 2_000_000}
    }

    # Định mức giá
    COST_LOG_STORAGE_PER_GB = 0.5
    COST_KAFKA_PER_100K_EPS = 300
    COST_COMPUTE_FLINK_BASE = 500
    DATADOG_LOG_PER_GB = 1.5
    DATADOG_HOST_PER_MONTH = 15

    results = []
    for tier, data in tiers.items():
        # Tự xây dựng
        storage_cost = data["log_gb"] * COST_LOG_STORAGE_PER_GB
        network_kafka_cost = (data["metric_eps"] / 100_000) * COST_KAFKA_PER_100K_EPS
        compute_cost = COST_COMPUTE_FLINK_BASE * (data["Services"] / 10)
        build_cost = storage_cost + network_kafka_cost + compute_cost

        # Sử dụng Datadog
        buy_log = data["log_gb"] * 30 * DATADOG_LOG_PER_GB
        buy_host = data["Services"] * 2 * DATADOG_HOST_PER_MONTH
        buy_total = buy_log + buy_host

        results.append({
            "Tier": tier,
            "Build_Storage Cost": storage_cost,
            "Build_Kafka/Network Cost": network_kafka_cost,
            "Build_Compute Cost": compute_cost,
            "Total_Build": build_cost,
            "Total_Buy_Saas": buy_total
        })

    df = pd.DataFrame(results)
    print(df.to_markdown(index=False))

if __name__ == "__main__":
    estimate_cost()