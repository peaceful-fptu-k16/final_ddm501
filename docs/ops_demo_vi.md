# Kich ban demo Ops/MLOps

Tai lieu nay dung de demo nhanh pipeline Server Log Anomaly Detection theo huong Ops.

## 1. Train va register model

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.pipeline
```

Ket qua mong doi:

- Tao raw data tai `data/raw/server_metrics.csv`
- Tao processed data va feature table tai `data/processed/`
- Train Isolation Forest
- Log MLflow run neu MLflow kha dung
- Register model vao `models/registry/v1`
- Tao drift report tai `reports/drift/latest_report.json`

## 2. Chay API serving

```powershell
uvicorn api.main:app --reload
```

Mo:

- Swagger UI: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics

## 3. Sinh prediction log production

Mo terminal khac:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/send_demo_requests.py --rounds 30
```

FastAPI se ghi prediction log vao `data/production/predictions.csv`.

## 4. Check drift tren production logs

```powershell
python scripts/check_production_drift.py
```

Bao cao duoc ghi vao `reports/drift/latest_production_report.json`.

Co the goi qua API:

```powershell
curl -X POST http://localhost:8000/drift
```

## 5. Chay monitoring stack nhe

```powershell
docker compose up --build fastapi streamlit prometheus grafana
```

Mo:

- FastAPI: http://localhost:8000/docs
- Streamlit: http://localhost:8501
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana login: `admin` / `admin`.

## 6. Chay stack day du

```powershell
docker compose up --build
```

Stack day du co them Airflow, MLflow, PostgreSQL va MinIO:

- Airflow: http://localhost:8080
- MLflow: http://localhost:5000
- MinIO Console: http://localhost:9001

Airflow login: `admin` / `admin`.

## 7. Noi dung thuyet trinh ngan

Pipeline nay the hien day du cac phan:

- DataOps: validate schema, clean data, feature engineering, drift detection
- MLOps: train model, track experiment, registry, promotion gate
- DevOps: Docker, CI, API deployment
- Ops: Prometheus metrics, Grafana dashboard, alert rules, retraining DAG
