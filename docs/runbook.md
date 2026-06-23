# Operations Runbook

This runbook is written for the local Docker Compose environment, but the checks map directly to staging or production.

## Service URLs

| Service | URL | Default credential |
| --- | --- | --- |
| Airflow | http://localhost:8080 | `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` |
| MLflow | http://localhost:5000 | none |
| FastAPI | http://localhost:8000/docs | `X-API-Key: API_KEY` for `/detect` and `/drift` |
| Streamlit | http://localhost:8501 | uses `API_KEY` when calling FastAPI |
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

- `postgres`, `db-migrate`, `mlflow`, `fastapi`, `streamlit`, `prometheus`, `alertmanager`, and `grafana` are healthy or completed.
- `GET /health` on FastAPI returns `model_loaded: true` after a model has been trained.
- Prometheus target `fastapi:8000` is up.
- Airflow DAG runs finish with all tasks successful.

Authenticated smoke test:

```powershell
$headers = @{ "X-API-Key" = "local-dev-api-key" }
$body = @{
  server_id = "srv-01"
  cpu_usage = 92.5
  memory_usage = 88.1
  request_count = 420
  error_rate = 0.27
  avg_latency_ms = 1600
  p95_latency_ms = 2400
} | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/detect -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

## Database Migrations

Migrations are applied automatically by the `db-migrate` service before FastAPI starts.

Manual migration:

```powershell
docker compose run --rm db-migrate
```

Verify the audit table:

```powershell
docker compose exec -T postgres psql -U airflow -d airflow -c "select timestamp, request_id, prediction, model_version from prediction_logs order by timestamp desc limit 5;"
```

## Common Incidents

### API returns heuristic model

Cause: no model artifact is mounted or the registry state is missing.

Actions:

```powershell
python -m src.pipeline
docker compose restart fastapi
```

Verify `models/registry/registry_state.json` exists and `/health` shows `model_source: local_registry` or `mlflow`.

Use the registry CLI for controlled rollback:

```powershell
python scripts/model_registry.py status
python scripts/model_registry.py rollback v1
docker compose restart fastapi
```

### Prediction logs are missing

Cause: PostgreSQL URL is wrong, database is unavailable, or no traffic has hit `/detect`.

Actions:

```powershell
docker compose logs --tail 100 postgres
python scripts/send_demo_requests.py --rounds 20 --api-key local-dev-api-key
```

The API falls back to `data/production/predictions.csv` if PostgreSQL logging fails.

### Drift report is skipped

Cause: no prediction log or no training reference data.

Actions:

```powershell
python -m src.pipeline
python scripts/send_demo_requests.py --rounds 30 --api-key local-dev-api-key
python scripts/check_production_drift.py
```

### Alerts are not delivered

Cause: Alertmanager is healthy, but the local webhook endpoint is still a placeholder.

Actions:

```powershell
docker compose logs --tail 100 alertmanager
docker compose exec -T prometheus wget -qO- http://alertmanager:9093/-/ready
```

Replace `monitoring/alertmanager.yml` or use `monitoring/alertmanager.webhook.example.yml` as a template for Slack, Discord, PagerDuty, or an incident bridge.

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
$env:API_KEY="local-dev-api-key"
locust -f loadtests/locustfile.py --host http://localhost:8000
```

Recommended demo target: 10-25 users, 2 users/second spawn rate.

## Reset Local State

This removes Docker volumes and should only be used when you want a clean local environment.

```powershell
docker compose down -v
docker compose up --build
```
