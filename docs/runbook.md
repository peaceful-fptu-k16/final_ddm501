# Operations Runbook

This runbook is written for the local Docker Compose environment, but the checks map directly to staging or production.

## Service URLs

| Service | URL | Default credential |
| --- | --- | --- |
| Airflow | http://localhost:8080 | `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` |
| MLflow | http://localhost:5000 | none |
| FastAPI | http://localhost:8000/docs | none |
| Streamlit | http://localhost:8501 | none |
| Prometheus | http://localhost:9090 | none |
| Alertmanager | http://localhost:9093 | none |
| Grafana | http://localhost:3000 | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` |
| MinIO | http://localhost:9001 | `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` |

## Daily Health Check

```powershell
docker compose ps
docker compose logs --tail 100 fastapi
docker compose logs --tail 100 airflow-scheduler
docker compose logs --tail 100 mlflow
```

Expected state:

- `postgres`, `mlflow`, `fastapi`, `streamlit`, `prometheus`, `alertmanager`, and `grafana` are running.
- `GET /health` on FastAPI returns `model_loaded: true` after a model has been trained.
- Prometheus target `fastapi:8000` is up.
- Airflow DAG runs finish with all tasks successful.

## Common Incidents

### API returns heuristic model

Cause: no model artifact is mounted or the registry state is missing.

Actions:

```powershell
python -m src.pipeline
docker compose restart fastapi
```

Verify `models/registry/registry_state.json` exists and `/health` shows `model_source: local_registry` or `mlflow`.

### Prediction logs are missing

Cause: PostgreSQL URL is wrong, database is unavailable, or no traffic has hit `/detect`.

Actions:

```powershell
docker compose logs --tail 100 postgres
python scripts/send_demo_requests.py --rounds 20
```

The API falls back to `data/production/predictions.csv` if PostgreSQL logging fails.

### Drift report is skipped

Cause: no prediction log or no training reference data.

Actions:

```powershell
python -m src.pipeline
python scripts/send_demo_requests.py --rounds 30
python scripts/check_production_drift.py
```

### MLflow is unreachable from Airflow

Cause: MLflow is not healthy, MinIO artifact bucket was not created, or host/CORS settings are too strict.

Actions:

```powershell
docker compose ps mlflow minio minio-init
docker compose logs --tail 100 mlflow
docker compose restart mlflow airflow-webserver airflow-scheduler
```

For local development, `.env.example` keeps permissive MLflow host settings. Tighten them before deploying outside localhost.

## Load Test

```powershell
pip install -r requirements-loadtest.txt
locust -f loadtests/locustfile.py --host http://localhost:8000
```

Recommended demo target: 10-25 users, 2 users/second spawn rate.

## Reset Local State

This removes Docker volumes and should only be used when you want a clean local environment.

```powershell
docker compose down -v
docker compose up --build
```
