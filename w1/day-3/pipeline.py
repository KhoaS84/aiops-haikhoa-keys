import pandas as pd
import queue
import threading
import time
import json

message_queue = queue.Queue(maxsize=1000)
stop_event = threading.Event()

def producer(file_path):
    """Đọc CSV và đẩy từng dòng vào queue"""
    print(f"[Producer] Bắt đầu đọc file {file_path}...")
    df = pd.read_csv(file_path)

    for index, row in df.iterrows():
        event = {
            "timestamp": row["timestamp"],
            "value": row["value"]
        }
        message_queue.put(event)

    print(f"[Producer] Đã nạp xong {len(df)} records vào Queue.")
    stop_event.set()  # Đánh dấu đã hoàn thành

def consumer(window_size=12):
    """Đọc queue, tính toán các đặc trưng và lưu ra file"""
    print("[Consumer] Bắt đầu lắng nghe dữ liệu...")
    data_buffer = []
    processed_features = []

    while not stop_event.is_set() or not message_queue.empty():
        try:
            #Lấy event từ queue
            event = message_queue.get(timeout=0.1)
            data_buffer.append(event)

            #Nếu đủ dữ liệu, tính toán đặc trưng
            if len(data_buffer) >= window_size:
                df_window = pd.DataFrame(data_buffer)

                #Trích xuất các đặc trưng
                latest_timestamp = df_window["timestamp"].iloc[-1]
                latest_value = df_window["value"].iloc[-1]
                rolling_mean = df_window["value"].mean()
                rolling_std = df_window["value"].std()
                rate_of_change = latest_value - df_window["value"].iloc[-2] if len(df_window) > 1 else 0

                processed_features.append({
                    "timestamp": latest_timestamp,
                    "value": latest_value,
                    "rolling_mean": rolling_mean,
                    "rolling_std": rolling_std,
                    "rate_of_change": rate_of_change
                })

                #Xóa dữ liệu cũ để tiết kiệm bộ nhớ
                data_buffer.pop(0)
            
            message_queue.task_done()
        except queue.Empty:
            continue
    
    print(f"[Consumer] Đã xử lý xong. Tiến hành lưu {len(processed_features)} records ra Parquet...")

    # Lưu ra Parquet file
    df_features = pd.DataFrame(processed_features)
    df_features.to_parquet("features.parquet", index=False)
    print("[Consumer] Lưu xong features.parquet.")

if __name__ == "__main__":
    csv_file = "/workspaces/aiops-haikhoa-keys/w1/day-3/data/machine_temperature_system_failure.csv"

    # Khởi tạo và chạy Thread
    t_producer = threading.Thread(target=producer, args=(csv_file,))
    t_consumer = threading.Thread(target=consumer)

    t_producer.start()
    t_consumer.start()

    t_producer.join()
    t_consumer.join()

    print("[Main] Pipeline đã hoàn thành.")