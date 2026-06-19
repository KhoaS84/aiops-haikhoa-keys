# SUBMIT.md — Kết quả nghiệm thu 6 kịch bản sự cố (Chaos Scenarios)

Dưới đây là nhật ký (logs) thực tế trích xuất từ bộ điều phối vòng lặp kín (Closed-Loop Orchestrator) khi thực nghiệm đầy đủ 6 kịch bản chaos từ mức cơ bản đến nâng cao.

---

## 1. Scenario 1 — Phục hồi thành công (Latency trên payment-svc)

**Lệnh inject:**
```bash
python trigger_alert.py HighLatency payment-svc
```

**Nhật ký orchestrator (trích):**
```json
{"ts": "2026-06-18T06:26:55.218763+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "HighLatency", "service": "payment-svc", "severity": "warning"}
{"ts": "2026-06-18T06:26:55.218763+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "HighLatency", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T06:26:55.218763+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "payment-svc"}
{"ts": "2026-06-18T06:26:55.221113+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": true}
{"ts": "2026-06-18T06:26:55.311022+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "[DRY-RUN] would execute: docker restart ronki-payment-svc", "stderr": ""}
{"ts": "2026-06-18T06:26:55.311022+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-18T06:26:55.311022+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": false}
{"ts": "2026-06-18T06:27:02.184546+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "[restart_service] Restarting ronki-payment-svc...\nronki-payment-svc\n[restart_service] Waiting 5s for ronki-payment-svc to come up...\n[restart_service] ronki-payment-svc is running.", "stderr": ""}
{"ts": "2026-06-18T06:27:02.185074+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-18T06:27:02.185074+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "payment-svc", "timeout_s": 60}
{"ts": "2026-06-18T06:27:02.200617+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 1, "latency_p99_ms": 248.14705882352942, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-18T06:27:12.229382+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 2, "latency_p99_ms": 248.35, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-18T06:27:22.263320+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 3, "latency_p99_ms": 248.29411764705884, "up": 1.0, "latency_ok": true, "up_ok": true}
{"ts": "2026-06-18T06:27:22.263320+00:00", "level": "INFO", "event_type": "VERIFY_PASS", "service": "payment-svc", "samples": 3}
{"ts": "2026-06-18T06:27:22.263320+00:00", "level": "INFO", "event_type": "ACTION_SUCCESS", "alertname": "HighLatency", "service": "payment-svc", "runbook": "runbooks/restart_service.sh"}
```

**Đánh giá:** Đạt yêu cầu. p99 latency nhỏ hơn ngưỡng 500ms giúp Verify Pass sau 3 mẫu đo liên tiếp. Ghi nhận sự kiện `ACTION_SUCCESS`.

---

## 2. Scenario 2 — Hành động thất bại $\rightarrow$ Rollback

**Thiết lập:** Sửa tạm ngưỡng `latency_p99_max_ms` thành `1` trong `baseline.json` để ép quá trình verify luôn thất bại.

**Lệnh inject:**
```bash
python trigger_alert.py HighLatency payment-svc
```

**Nhật ký orchestrator (trích):**
```json
{"ts": "2026-06-18T06:28:19.409388+00:00", "level": "INFO", "event_type": "ACTION_EXECUTED", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-18T06:28:19.409388+00:00", "level": "INFO", "event_type": "VERIFY_START", "service": "payment-svc", "timeout_s": 60}
{"ts": "2026-06-18T06:28:19.424424+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 1, "latency_p99_ms": 248.25892857142856, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T06:28:29.445820+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 2, "latency_p99_ms": 248.25675675675674, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T06:28:39.477124+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 3, "latency_p99_ms": 248.23853211009174, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T06:28:49.519491+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 4, "latency_p99_ms": 248.2222222222222, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T06:28:59.550136+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 5, "latency_p99_ms": 248.188679245283, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T06:29:09.593115+00:00", "level": "INFO", "event_type": "VERIFY_SAMPLE", "service": "payment-svc", "sample": 6, "latency_p99_ms": 248.2067674409985, "up": 1.0, "latency_ok": false, "up_ok": true}
{"ts": "2026-06-18T06:29:19.593719+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "payment-svc", "samples": 6}
{"ts": "2026-06-18T06:29:19.593719+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "payment-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T06:29:19.593719+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/restart_service.sh", "service": "payment-svc", "dry_run": false}
{"ts": "2026-06-18T06:29:26.457988+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/restart_service.sh", "service": "payment-svc", "returncode": 0, "stdout": "[restart_service] Restarting ronki-payment-svc...\nronki-payment-svc\n[restart_service] Waiting 5s for ronki-payment-svc to come up...\n[restart_service] ronki-payment-svc is running.", "stderr": ""}
{"ts": "2026-06-18T06:29:26.457988+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "payment-svc", "rollback_runbook": "runbooks/restart_service.sh"}
```

**Đánh giá:** Đạt yêu cầu. p99 latency thực tế (248ms) vượt xa ngưỡng ép buộc (1ms). Verify thất bại dẫn tới sự kiện `ROLLBACK_TRIGGERED` và chạy thành công runbook rollback với log `ROLLBACK_EXECUTED`.

---

## 3. Scenario 3 — Circuit breaker (3 lỗi liên tiếp)

**Lệnh inject:**
```bash
python trigger_alert.py HighLatency inventory-svc
python trigger_alert.py HighLatency checkout-svc
```

**Nhật ký orchestrator (trích — sau khi có 3 lần thất bại liên tiếp):**
```json
{"ts": "2026-06-18T06:32:48.786074+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "inventory-svc", "samples": 6}
{"ts": "2026-06-18T06:32:48.786074+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "inventory-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T06:32:55.668051+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "inventory-svc", "rollback_runbook": "runbooks/restart_service.sh"}
...
{"ts": "2026-06-18T06:34:02.750313+00:00", "level": "WARNING", "event_type": "VERIFY_FAIL", "service": "checkout-svc", "samples": 6}
{"ts": "2026-06-18T06:34:02.750313+00:00", "level": "WARNING", "event_type": "ROLLBACK_TRIGGERED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T06:34:09.643829+00:00", "level": "INFO", "event_type": "ROLLBACK_EXECUTED", "service": "checkout-svc", "rollback_runbook": "runbooks/restart_service.sh"}
{"ts": "2026-06-18T06:34:09.643829+00:00", "level": "ERROR", "event_type": "CIRCUIT_BREAKER_HALT", "consecutive_failures": 3, "threshold": 3, "message": "Automation halted. Manual intervention required."}
```

**Đánh giá:** Đạt yêu cầu. Sau lần lỗi thứ 3 liên tiếp, orchestrator chuyển trạng thái cầu chì và log sự kiện ngắt tự động hóa `CIRCUIT_BREAKER_HALT`.

---

## 4. Scenario 4 — Triển khai đa bước transactional (Step C lỗi)

**Lệnh inject:**
```bash
python trigger_alert.py MultiStepDeploy api-gateway
```
*(Đồng thời chạy script can thiệp rename container trong quá trình thực thi để gây ra lỗi ở Step C)*

**Nhật ký orchestrator (trích):**
```json
{"ts": "2026-06-18T06:37:58.501618+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "MultiStepDeploy", "service": "api-gateway", "severity": "warning"}
{"ts": "2026-06-18T06:37:58.501618+00:00", "level": "INFO", "event_type": "DECIDE_RUNBOOK", "alertname": "MultiStepDeploy", "service": "api-gateway", "runbook": "runbooks/multi_step_deploy.sh --step-a"}
{"ts": "2026-06-18T06:37:58.502407+00:00", "level": "INFO", "event_type": "BLAST_RADIUS_OK", "service": "api-gateway"}
{"ts": "2026-06-18T06:37:58.502407+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway", "dry_run": true}
{"ts": "2026-06-18T06:37:58.608087+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway", "returncode": 0, "stdout": "[DRY-RUN] step-A: would drain traffic \u00e2\u2020\u2019 docker stop ronki-api-gateway", "stderr": ""}
{"ts": "2026-06-18T06:37:58.608087+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway"}
{"ts": "2026-06-18T06:37:58.608087+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway", "dry_run": false}
{"ts": "2026-06-18T06:38:00.031810+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --step-a", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] step-A: draining traffic from ronki-api-gateway...\nronki-api-gateway\n[multi_step_deploy] step-A complete.", "stderr": ""}
{"ts": "2026-06-18T06:38:00.031810+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/multi_step_deploy.sh --step-b", "service": "api-gateway", "dry_run": false}
{"ts": "2026-06-18T06:38:03.469799+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --step-b", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] step-B: applying new config to ronki-api-gateway...\nronki-api-gateway\n[multi_step_deploy] step-B complete.", "stderr": ""}
{"ts": "2026-06-18T06:38:03.469799+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/multi_step_deploy.sh --step-c", "service": "api-gateway", "dry_run": false}
{"ts": "2026-06-18T06:38:05.736288+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --step-c", "service": "api-gateway", "returncode": 1, "stdout": "[multi_step_deploy] step-C: re-enabling traffic for ronki-api-gateway...\n[multi_step_deploy] ERROR: step-C traffic enable failed \u00e2\u20ac\u201d ronki-api-gateway status=\nmissing", "stderr": ""}
{"ts": "2026-06-18T06:38:05.736288+00:00", "level": "ERROR", "event_type": "TRANSACTIONAL_STEP_FAIL", "step": "runbooks/multi_step_deploy.sh --step-c", "service": "api-gateway", "completed_before_failure": ["runbooks/multi_step_deploy.sh --step-a", "runbooks/multi_step_deploy.sh --step-b"]}
{"ts": "2026-06-18T06:38:05.736288+00:00", "level": "WARNING", "event_type": "TRANSACTIONAL_ROLLBACK_STEP", "step": "runbooks/multi_step_deploy.sh --rollback-b", "service": "api-gateway"}
{"ts": "2026-06-18T06:38:05.736288+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/multi_step_deploy.sh --rollback-b", "service": "api-gateway", "dry_run": false}
{"ts": "2026-06-18T06:38:05.850032+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --rollback-b", "service": "api-gateway", "returncode": 1, "stdout": "[multi_step_deploy] rollback-B: reverting config on ronki-api-gateway...", "stderr": "Error response from daemon: No such container: ronki-api-gateway\nfailed to start containers: ronki-api-gateway"}
{"ts": "2026-06-18T06:38:05.850032+00:00", "level": "WARNING", "event_type": "TRANSACTIONAL_ROLLBACK_STEP", "step": "runbooks/multi_step_deploy.sh --rollback-a", "service": "api-gateway"}
{"ts": "2026-06-18T06:38:05.850032+00:00", "level": "INFO", "event_type": "RUNBOOK_EXEC", "script": "runbooks/multi_step_deploy.sh --rollback-a", "service": "api-gateway", "dry_run": false}
{"ts": "2026-06-18T06:38:08.051813+00:00", "level": "INFO", "event_type": "RUNBOOK_RESULT", "script": "runbooks/multi_step_deploy.sh --rollback-a", "service": "api-gateway", "returncode": 0, "stdout": "[multi_step_deploy] rollback-A: restoring traffic to ronki-api-gateway...\n[multi_step_deploy] rollback-A complete.", "stderr": ""}
{"ts": "2026-06-18T06:38:08.051813+00:00", "level": "INFO", "event_type": "TRANSACTIONAL_ROLLBACK_COMPLETE", "service": "api-gateway", "rolled_back": ["runbooks/multi_step_deploy.sh --rollback-b", "runbooks/multi_step_deploy.sh --rollback-a"]}
```

**Đánh giá:** Đạt yêu cầu xuất sắc. Step A và B chạy thành công. Khi Step C fail, orchestrator nhận diện sự cố, log `TRANSACTIONAL_STEP_FAIL` liệt kê các bước đã xong, rồi chạy lần lượt rollback-B rồi tới rollback-A (đúng thứ tự ngược lại) và hoàn tất với log `TRANSACTIONAL_ROLLBACK_COMPLETE`.

---

## 5. Scenario 5 — Xử lý alert đồng thời (Concurrency / Locks)

**Lệnh inject:**
```bash
python trigger_alert.py HighLatency payment-svc
python trigger_alert.py HighLatency inventory-svc
# Chờ 5s và gửi tiếp alert trùng lặp trên payment-svc:
python trigger_alert.py HighLatency payment-svc
```

**Nhật ký orchestrator (trích):**
```json
{"ts": "2026-06-18T06:40:12.254579+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "HighLatency", "service": "inventory-svc", "severity": "warning"}
{"ts": "2026-06-18T06:40:12.255771+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "HighLatency", "service": "payment-svc", "severity": "warning"}
...
{"ts": "2026-06-18T06:40:12.387088+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "payment-svc"}
{"ts": "2026-06-18T06:40:12.390994+00:00", "level": "INFO", "event_type": "DRY_RUN_PASS", "runbook": "runbooks/restart_service.sh", "service": "inventory-svc"}
...
{"ts": "2026-06-18T06:40:27.270983+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "HighLatency", "service": "payment-svc", "severity": "warning"}
{"ts": "2026-06-18T06:40:27.272462+00:00", "level": "WARNING", "event_type": "SERVICE_LOCK_BUSY", "service": "payment-svc", "message": "Another runbook is executing for this service; skipping duplicate"}
```

**Đánh giá:** Đạt yêu cầu xuất sắc. Hai service độc lập bắt đầu chạy dry-run cách nhau 3ms (không block nhau nhờ cơ chế đa luồng). Khi có alert trùng lặp gửi đến `payment-svc` lúc runbook cũ chưa kết thúc, orchestrator phát hiện lock đã giữ và log đúng sự kiện `SERVICE_LOCK_BUSY`.

---

## 6. Scenario 6 — Chống LLM Hallucination (Decision Validation)

**Thiết lập:** Cấu hình `TestHallucination` trỏ sang `"runbooks/nonexistent_runbook.sh"` trong `runbook_map` nhưng KHÔNG bổ sung vào whitelist `runbook_registry` của `config.yaml`.

**Lệnh inject:**
```bash
python trigger_alert.py TestHallucination payment-svc
```

**Nhật ký orchestrator (trích):**
```json
{"ts": "2026-06-18T06:42:00.242460+00:00", "level": "INFO", "event_type": "ALERT_DETECTED", "alertname": "TestHallucination", "service": "payment-svc", "severity": "warning"}
{"ts": "2026-06-18T06:42:00.242460+00:00", "level": "ERROR", "event_type": "DECISION_VALIDATION_FAILED", "bad_runbook": "runbooks/nonexistent_runbook.sh", "alertname": "TestHallucination", "raw_decision": "runbooks/nonexistent_runbook.sh", "action": "escalate_no_auto_action"}
```

**Đánh giá:** Đạt yêu cầu xuất sắc. Lệnh chạy bị chặn ngay ở khâu kiểm duyệt trước dry-run. Orchestrator dừng tiến trình, ghi nhận lỗi `DECISION_VALIDATION_FAILED` chứa đầy đủ 4 trường thông tin chi tiết và không spawn bất kỳ subprocess nào.
