# Tóm tắt slide

## 1. Mục tiêu
- Xây dựng stack MLOps cho phát hiện anomaly trên server metrics.
- Không làm concept drift vì chưa có actual label production.

## 2. Kiến trúc
- Data validation -> preprocessing -> feature engineering -> Isolation Forest.
- MLflow tracking/registry, FastAPI serving, PostgreSQL audit log.
- Prometheus/Grafana monitoring, Alertmanager -> Airflow retraining DAG.

## 3. Kết quả model
- Precision: 0.973684
- Recall: 0.973684
- F1-score: 0.973684
- Training rows: 720

## 4. Production runtime
- Requests logged: 400
- Anomaly count: 108
- API p95 latency: 0.05 seconds
- Error count: 0
- Load test RPS: 7.19846
- Load test p95/failure: 210 ms / 0

## 5. Observability
- Prometheus scrape FastAPI metrics.
- Grafana dashboard hiển thị request rate, p95 latency, anomaly rate.
- Alertmanager route warning/critical alert sang bridge.

## 6. Explainability và fairness
- Explainability method: shap_tree_explainer
- Fairness group: server_id
- Max anomaly-rate gap: 1

## 7. Retraining
- API `/retrain` có check drift và force retraining.
- Alertmanager bridge tạo Airflow DAG run khi `DataDriftDetected` hoặc `HighAnomalyRate` firing.

## 8. CI/CD
- GitHub Actions chạy Ruff, pytest, Docker build, Trivy scan và compose integration.
- Latest run: queued
