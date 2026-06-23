# final_ddm501 - Server Log Anomaly Detection MLOps

`final_ddm501` is an end-to-end, Ops-oriented MLOps project for detecting anomalies in server metrics and logs. It is designed to be runnable on a laptop with Docker Compose while still showing the same operating concerns used in real systems: orchestration, experiment tracking, model promotion, API serving, observability, drift detection, alerting, and retraining.

## What This Project Delivers

- Airflow DAGs for training, validation, drift checks, and retraining orchestration
- Data quality checks for schema, ranges, timestamps, duplicate events, and latency consistency
- Feature engineering for rolling server pressure signals
- Isolation Forest anomaly model with MLflow experiment tracking
- Local model registry plus optional MLflow Model Registry URI loading
- FastAPI prediction service with Prometheus metrics
- PostgreSQL-backed prediction audit logs with CSV fallback for local development
- Streamlit dashboard for interactive predictions, recent logs, and drift reports
- Prometheus, Alertmanager, and Grafana monitoring stack
- MinIO-backed MLflow artifact storage
- GitHub Actions CI, Dependabot, and Locust load-test scaffold

## Architecture

```text
Raw server metrics
  -> Data validation
  -> Preprocessing
  -> Feature engineering
  -> Model training
  -> MLflow tracking and artifact storage
  -> Local or MLflow model registry
  -> FastAPI serving
  -> PostgreSQL prediction logs
  -> Prometheus metrics
  -> Grafana dashboards and Alertmanager
  -> Production drift detection
  -> Airflow retraining workflow
```

## Service Map

| Service | URL | Purpose |
| --- | --- | --- |
| Airflow | http://localhost:8080 | Pipeline orchestration |
| MLflow | http://localhost:5000 | Experiment tracking and model registry |
| FastAPI | http://localhost:8000/docs | Model serving and drift endpoint |
| Streamlit | http://localhost:8501 | Ops demo dashboard |
| Prometheus | http://localhost:9090 | Metrics and alert rules |
| Alertmanager | http://localhost:9093 | Alert routing |
| Grafana | http://localhost:3000 | Monitoring dashboard |
| MinIO | http://localhost:9001 | S3-compatible artifact storage |

Default local credentials are controlled through `.env`. Start from `.env.example` and replace all `change-me` values before sharing or deploying the stack.

## Repository Layout

```text
api/                    FastAPI serving layer
dashboard/              Streamlit operations dashboard
dags/                   Airflow DAGs
data/raw/               Sample raw data
docker/postgres/        PostgreSQL initialization
docs/                   Architecture, demo notes, and runbook
loadtests/              Locust load-test scenarios
monitoring/             Prometheus, Alertmanager, and Grafana config
scripts/                Demo and drift helper scripts
src/                    Data, feature, model, monitoring, and storage code
tests/                  Pytest suite
```

## Local Python Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.pipeline
uvicorn api.main:app --reload
```

In a second terminal:

```powershell
streamlit run dashboard/app.py
```

Useful local commands:

```powershell
python -m pytest
python scripts/send_demo_requests.py --rounds 30
python scripts/check_production_drift.py
```

## Docker Quick Start

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

Run the lightweight app stack:

```powershell
docker compose up --build fastapi streamlit prometheus alertmanager grafana
```

Run the full Ops stack:

```powershell
docker compose up --build
```

Check service state:

```powershell
docker compose ps
docker compose logs --tail 100 fastapi
```

## API Example

```powershell
curl -X POST http://localhost:8000/detect `
  -H "Content-Type: application/json" `
  -d "{\"server_id\":\"srv-01\",\"cpu_usage\":92.5,\"memory_usage\":88.1,\"request_count\":420,\"error_rate\":0.27,\"avg_latency_ms\":1600,\"p95_latency_ms\":2400}"
```

Expected response:

```json
{
  "prediction": "anomaly",
  "anomaly_score": -0.61,
  "risk_level": "high",
  "model_version": "v1"
}
```

## Model Lifecycle

1. Airflow or `python -m src.pipeline` extracts sample server metrics.
2. Validation writes a data-quality report under `reports/data_quality/`.
3. Preprocessing and feature engineering write processed features under `data/processed/`.
4. Training writes local artifacts under `models/latest/` and logs metrics/artifacts to MLflow when enabled.
5. Promotion gates compare candidate metrics with the current production model and update `models/registry/registry_state.json`.
6. FastAPI loads the promoted local registry model by default.
7. If `MLFLOW_MODEL_URI` is set, FastAPI attempts to load from MLflow first, for example `models:/server-log-anomaly@production`.

## Observability

FastAPI exposes `/metrics` for Prometheus. The stack includes alerts for:

- High anomaly rate
- High p95 API latency
- High API error rate
- Production drift score above threshold

Prediction requests are stored in PostgreSQL through `PREDICTION_DATABASE_URL`. If the database is unavailable, the API falls back to `data/production/predictions.csv` so demo traffic still works.

## Load Testing

```powershell
pip install -r requirements-loadtest.txt
locust -f loadtests/locustfile.py --host http://localhost:8000
```

Open http://localhost:8089 and start with 10-25 users for a local smoke test.

## CI/CD

GitHub Actions runs:

- Python dependency installation
- Ruff lint check
- Pytest test suite
- Docker Compose config validation
- FastAPI and Streamlit image smoke build

Dependabot is configured for Python packages, Docker images, and GitHub Actions.

## Production Notes

- Replace all default credentials in `.env`.
- Keep MLflow host/CORS settings strict outside local development.
- Use managed PostgreSQL/S3-compatible storage for real deployments.
- Put FastAPI behind an authenticated gateway or internal ingress.
- Add a real Alertmanager receiver such as Slack, PagerDuty, or an incident webhook.
- Persist model artifacts and registry metadata outside the application container.
- Run Locust or k6 before changing resource limits or scaling policy.

## Documentation

- Architecture notes: `docs/architecture.md`
- Vietnamese demo guide: `docs/ops_demo_vi.md`
- Operations runbook: `docs/runbook.md`
