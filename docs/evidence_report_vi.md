# Báo cáo evidence vận hành MLOps

Thời điểm thu thập: `2026-07-01T20:52:31+07:00`.

Phạm vi: báo cáo này không triển khai concept drift vì production chưa có ground-truth label.
Các phần còn lại được chạy và ghi nhận qua API, MLflow, Airflow, Prometheus/Grafana,
Alertmanager bridge, PostgreSQL và GitHub.

## Bảng số liệu chính

| Chỉ số | Giá trị | Nguồn |
| --- | --- | --- |
| Model precision | 0.973684 | models/latest/metrics.json |
| Model recall | 0.973684 | models/latest/metrics.json |
| Model f1_score | 0.973684 | models/latest/metrics.json |
| False positive rate | 0.001466 | models/latest/metrics.json |
| Training rows | 720 | models/latest/metrics.json |
| Production requests | 400 | PostgreSQL prediction_logs |
| Production anomaly count | 108 | PostgreSQL prediction_logs |
| Rolling anomaly rate | 0.375 | Prometheus |
| API p95 latency seconds | 0.05 | Prometheus |
| API error count | 0 | Prometheus |
| Load test RPS | 7.19846 | Locust CSV |
| Load test p95 ms | 210 | Locust CSV |
| Load test p99 ms | 360 | Locust CSV |
| Load test failure rate | 0 | Locust CSV |
| Model source loaded | local_registry | FastAPI /health |
| Latest drift score | 9.23221 | FastAPI /drift |
| Fairness max gap | 1 | FastAPI /fairness |
| Explainability method | shap_tree_explainer | FastAPI /explain |

## Evidence theo hệ thống

| Nhóm | Kết quả | Nguồn/ghi chú |
| --- | --- | --- |
| MLflow | 8e3073c2a8db4621b97861bf425d6465 | Experiment server-log-anomaly |
| Airflow | healthy | Health API |
| Grafana | ok | Grafana /api/health |
| Alertmanager bridge | ok | Bridge /health |
| GitHub Actions | queued | https://github.com/peaceful-fptu-k16/final_ddm501/actions/runs/28459915531 |
| Git branch | main | 10d697a |

## Data quality

| Metric | Giá trị |
| --- | --- |
| Valid | True |
| Rows after validation | 720 |
| Errors | 0 |
| Warnings | 0 |

## Production prediction

| Metric | Giá trị |
| --- | --- |
| Total requests | 400 |
| Normal | 292 |
| Anomaly | 108 |
| Average anomaly score | 0.132085 |
| Risk distribution | {"low": 292, "medium": 108} |

## Load test

| Metric | Giá trị |
| --- | --- |
| Requests | 273 |
| RPS | 7.19846 |
| p50 ms | 76 |
| p95 ms | 210 |
| p99 ms | 360 |
| Failure rate | 0 |

## Explainability và fairness

Explainability dùng `shap_tree_explainer`. Top feature hiện tại:

| Feature | Impact | Direction |
| --- | --- | --- |
| error_rate | 0.833543 | raises_anomaly_risk |
| traffic_error_pressure | 0.828311 | raises_anomaly_risk |
| request_count | 0.820555 | raises_anomaly_risk |
| p95_latency_ms_roll_mean_3 | 0.790517 | raises_anomaly_risk |
| error_rate_roll_mean_3 | 0.788234 | raises_anomaly_risk |
| p95_latency_ms | 0.750149 | raises_anomaly_risk |
| avg_latency_ms | 0.720553 | raises_anomaly_risk |
| avg_latency_ms_roll_mean_3 | 0.687806 | raises_anomaly_risk |

Fairness dùng `fairlearn_metricframe` theo nhóm `server_id`.

| Group | Requests | Anomaly rate | High risk rate |
| --- | --- | --- | --- |
| srv-01 | 87 | 0.298851 | 0 |
| srv-02 | 47 | 0 | 0 |
| srv-03 | 26 | 1 | 0 |
| srv-load-01 | 184 | 0 | 0 |
| srv-load-02 | 56 | 1 | 0 |

## Biểu đồ sinh tự động

| Tên | File |
| --- | --- |
| prediction_distribution | reports/demo_evidence/prediction_distribution.svg |
| explainability_top_features | reports/demo_evidence/explainability_top_features.svg |
| fairness_group_rates | reports/demo_evidence/fairness_group_rates.svg |

## Ảnh chụp màn hình

| Ảnh | Đường dẫn |
| --- | --- |
| airflow_retraining_dag.png | docs/assets/screenshots/airflow_retraining_dag.png |
| fastapi_docs.png | docs/assets/screenshots/fastapi_docs.png |
| grafana_dashboard.png | docs/assets/screenshots/grafana_dashboard.png |
| mlflow_experiment.png | docs/assets/screenshots/mlflow_experiment.png |
| streamlit_dashboard.png | docs/assets/screenshots/streamlit_dashboard.png |

## Ghi chú CI/CD

Workflow GitHub gồm lint, pytest, docker build, Trivy critical scan, GHCR publish trên `main`
và compose integration test. Latest run lấy từ GitHub API:

| Metric | Giá trị |
| --- | --- |
| Run number | 34 |
| Status | queued |
| Conclusion | n/a |
| Event | push |
| Started | 2026-06-30T16:28:57Z |
| Updated | 2026-06-30T16:32:17Z |
| Commit | 10d697af18f352f9446fb6142f05aa10cd426795 |
| URL | https://github.com/peaceful-fptu-k16/final_ddm501/actions/runs/28459915531 |

| Job | Status | Conclusion | Started | Completed |
| --- | --- | --- | --- | --- |
| Python quality gate | completed | success | 2026-06-30T16:29:00Z | 2026-06-30T16:29:50Z |
| Docker build, scan, and publish | completed | success | 2026-06-30T16:29:52Z | 2026-06-30T16:32:17Z |
| Compose integration test | completed | success | 2026-06-30T16:29:52Z | 2026-06-30T16:31:14Z |
| Local CD deploy | queued | n/a | 2026-06-30T16:32:17Z | n/a |

| Job | Step | Status | Conclusion | Started | Completed |
| --- | --- | --- | --- | --- | --- |
| Docker build, scan, and publish | Scan FastAPI image | completed | success | 2026-06-30T16:30:49Z | 2026-06-30T16:31:04Z |
| Docker build, scan, and publish | Scan Streamlit image | completed | success | 2026-06-30T16:31:04Z | 2026-06-30T16:31:22Z |
| Docker build, scan, and publish | Post Scan Streamlit image | completed | success | 2026-06-30T16:32:11Z | 2026-06-30T16:32:14Z |
| Docker build, scan, and publish | Post Scan FastAPI image | completed | success | 2026-06-30T16:32:14Z | 2026-06-30T16:32:16Z |
