<div align="center">

# final_ddm501

### Production-style MLOps for Server Log Anomaly Detection

[![CI](https://github.com/peaceful-fptu-k16/final_ddm501/actions/workflows/ci.yml/badge.svg)](https://github.com/peaceful-fptu-k16/final_ddm501/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Secured%20Serving-009688?logo=fastapi&logoColor=white)
![Airflow](https://img.shields.io/badge/Airflow-Orchestration-017CEE?logo=apacheairflow&logoColor=white)
![MLflow](https://img.shields.io/badge/MLflow-Registry%20%26%20Tracking-0194E2?logo=mlflow&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Audit%20Trail-4169E1?logo=postgresql&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-Metrics-E6522C?logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?logo=grafana&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose%20%2B%20GHCR-2496ED?logo=docker&logoColor=white)

</div>

`final_ddm501` is an end-to-end MLOps reference stack for detecting anomalies in server logs and infrastructure metrics. It is intentionally runnable on a laptop with Docker Compose, while still demonstrating production concerns: authenticated model serving, JSON request logs, database migrations, prediction audit trails, orchestration, model registry operations, observability, alert routing, drift checks, CI quality gates, image publishing, and security scanning.

## Production Capabilities

| Capability | Implementation |
| --- | --- |
| Authenticated inference | FastAPI protects `/detect` and `/drift` with `X-API-Key` |
| Structured observability | JSON request logs with `request_id`, latency, status, prediction, and model version |
| Database audit trail | PostgreSQL `prediction_logs` table with Alembic migration and CSV fallback |
| Model lifecycle | Local registry promotion gates, rollback CLI, optional MLflow alias sync |
| Experiment tracking | MLflow server backed by PostgreSQL and MinIO artifact storage |
| Orchestration | Airflow DAGs for training, validation, drift, and retraining |
| Explainability | `/explain` endpoint writes feature impact reports with SHAP when available and permutation fallback |
| Fairness monitoring | `/fairness` endpoint measures anomaly-rate parity by configurable operational segment |
| API retraining | `/retrain` endpoint checks drift-triggered retraining or runs a forced retraining job |
| Monitoring | Prometheus metrics, Grafana dashboard provisioning, Alertmanager routing |
| Alert-to-retrain bridge | Alertmanager webhook can trigger the Airflow retraining DAG through the Airflow REST API |
| CI/CD | Ruff, pytest, Compose validation, Trivy scans, GHCR image publish, Compose integration test |
| Load testing | Locust scenario for normal and anomalous prediction traffic |

## Tech Stack

| Layer | Tools |
| --- | --- |
| Serving | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white) ![Uvicorn](https://img.shields.io/badge/Uvicorn-111111?logo=gunicorn&logoColor=white) |
| Machine learning | ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white) ![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikitlearn&logoColor=white) ![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white) |
| Orchestration | ![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-017CEE?logo=apacheairflow&logoColor=white) |
| Tracking and artifacts | ![MLflow](https://img.shields.io/badge/MLflow-0194E2?logo=mlflow&logoColor=white) ![MinIO](https://img.shields.io/badge/MinIO-C72E49?logo=minio&logoColor=white) |
| App dashboard | ![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white) |
| Storage | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white) ![Alembic](https://img.shields.io/badge/Alembic-Migrations-6BA539) |
| Observability | ![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus&logoColor=white) ![Grafana](https://img.shields.io/badge/Grafana-F46800?logo=grafana&logoColor=white) ![Alertmanager](https://img.shields.io/badge/Alertmanager-E6522C?logo=prometheus&logoColor=white) |
| Delivery | ![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white) ![Trivy](https://img.shields.io/badge/Trivy-Security%20Scan-1904DA) |

## Architecture

```mermaid
flowchart LR
    A["Raw server metrics"] --> B["Data validation"]
    B --> C["Preprocessing"]
    C --> D["Feature engineering"]
    D --> E["Isolation Forest training"]
    E --> F["MLflow tracking"]
    E --> G["Promotion gates"]
    G --> H["Local / MLflow registry"]
    H --> I["FastAPI serving"]
    I --> J["PostgreSQL audit logs"]
    I --> K["Prometheus metrics"]
    K --> L["Grafana dashboards"]
    K --> M["Alertmanager"]
    M --> P["Alertmanager Airflow bridge"]
    P --> O["Retraining workflow"]
    J --> N["Production drift detection"]
    N --> O["Retraining workflow"]
```

## Services

| Service | URL | Purpose |
| --- | --- | --- |
| Airflow | http://localhost:8080 | Pipeline orchestration |
| MLflow | http://localhost:5000 | Experiment tracking and model registry |
| FastAPI | http://localhost:8000/docs | Authenticated model serving |
| Streamlit | http://localhost:8501 | Operations dashboard |
| Prometheus | http://localhost:9090 | Metrics and alert rules |
| Alertmanager | http://localhost:9093 | Alert routing and webhook delivery |
| Alertmanager bridge | http://localhost:9099/health | Webhook receiver that triggers Airflow DAG runs |
| Grafana | http://localhost:3000 | Monitoring dashboards |
| MinIO | http://localhost:9001 | S3-compatible artifact storage |
| PostgreSQL | localhost:5432 | Metadata and prediction audit trail |

Credentials, API keys, and ports are controlled through `.env`. Start from `.env.example` and replace all `change-me` values before sharing or deploying.

## Quick Start

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

Train or refresh the local model:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.pipeline
```

Run database migrations manually when needed:

```powershell
python scripts/migrate_db.py
```

Send an authenticated prediction:

```powershell
curl -X POST http://localhost:8000/detect `
  -H "Content-Type: application/json" `
  -H "X-API-Key: local-dev-api-key" `
  -d "{\"server_id\":\"srv-01\",\"cpu_usage\":92.5,\"memory_usage\":88.1,\"request_count\":420,\"error_rate\":0.27,\"avg_latency_ms\":1600,\"p95_latency_ms\":2400}"
```

Example response:

```json
{
  "prediction": "anomaly",
  "anomaly_score": -0.61,
  "risk_level": "high",
  "model_version": "v1"
}
```

## Model Registry Operations

Inspect local registry state:

```powershell
python scripts/model_registry.py status
```

Promote or rollback a model version:

```powershell
python scripts/model_registry.py promote v2
python scripts/model_registry.py rollback v1
```

Point an MLflow alias to a registered model version:

```powershell
python scripts/model_registry.py set-mlflow-alias 3 --alias production
```

## Operations Checks

```powershell
docker compose ps
docker compose logs --tail 100 fastapi
docker compose logs --tail 100 airflow-scheduler
```

Smoke-test health and monitoring:

```powershell
Invoke-WebRequest http://localhost:8000/health
Invoke-WebRequest http://localhost:9090/-/ready
Invoke-WebRequest http://localhost:9093/-/ready
Invoke-WebRequest http://localhost:3000/api/health
```

Reload the currently configured MLflow production model without restarting FastAPI:

```powershell
Invoke-RestMethod http://localhost:8000/model/reload -Method Post -Headers @{ "X-API-Key" = "local-dev-api-key" }
```

Explain an individual prediction:

```powershell
Invoke-RestMethod http://localhost:8000/explain -Method Post `
  -Headers @{ "X-API-Key" = "local-dev-api-key" } `
  -ContentType "application/json" `
  -Body '{"server_id":"srv-01","cpu_usage":94,"memory_usage":91,"request_count":520,"error_rate":0.32,"avg_latency_ms":1700,"p95_latency_ms":2600}'
```

Run production drift, fairness, and retraining checks:

```powershell
Invoke-RestMethod http://localhost:8000/drift -Method Post -Headers @{ "X-API-Key" = "local-dev-api-key" }
Invoke-RestMethod http://localhost:8000/fairness -Method Post -Headers @{ "X-API-Key" = "local-dev-api-key" }
Invoke-RestMethod http://localhost:8000/retrain -Method Post `
  -Headers @{ "X-API-Key" = "local-dev-api-key" } `
  -ContentType "application/json" `
  -Body '{"force":false,"reload_after_train":false}'
```

Check prediction audit logs:

```powershell
docker compose exec -T postgres psql -U airflow -d mlops -c "select timestamp, request_id, prediction, model_version from prediction_logs order by timestamp desc limit 5;"
```

## CI/CD

GitHub Actions runs a production-oriented gate:

- Ruff linting
- Pytest suite
- Docker Compose validation
- FastAPI and Streamlit Docker image builds
- Trivy critical vulnerability scans
- GHCR publish on `main`
- Compose integration test for API, migration, PostgreSQL audit logs, Prometheus, Alertmanager, and Grafana

Published image names:

```text
ghcr.io/peaceful-fptu-k16/final-ddm501-fastapi
ghcr.io/peaceful-fptu-k16/final-ddm501-streamlit
```

Dependency upgrades are reviewed manually for this final demo because Airflow, MLflow, NumPy, pandas, and base images have tight compatibility constraints.

## Load Testing

```powershell
pip install -r requirements-loadtest.txt
$env:API_KEY="local-dev-api-key"
locust -f loadtests/locustfile.py --host http://localhost:8000
```

Open http://localhost:8089 and start with 10-25 local users for a smoke test.

Headless smoke run for report evidence:

```powershell
$env:API_KEY="local-dev-api-key"
locust -f loadtests/locustfile.py --host http://localhost:8000 `
  --headless -u 15 -r 5 -t 45s --csv reports/demo_evidence/loadtest
```

## Demo Evidence and Reports

After the stack is running, generate real evidence from FastAPI, MLflow, Airflow, Prometheus, Grafana, PostgreSQL, Docker, and GitHub:

```powershell
python scripts/send_demo_requests.py --api-key local-dev-api-key --rounds 120 --delay-seconds 0.02 --anomaly-probability 0.25 --seed 42
python scripts/collect_demo_evidence.py
```

Generated report artifacts:

- [Vietnamese evidence report](docs/evidence_report_vi.md)
- [Slide summary](docs/slide_summary_vi.md)
- `reports/demo_evidence/latest_metrics.json`
- `reports/demo_evidence/metrics_table.csv`
- `reports/demo_evidence/*.svg`

Concept drift is intentionally out of scope for this demo because production traffic does not include ground-truth labels. The stack still monitors production data drift, prediction distribution drift, explainability, fairness by configured group, runtime health, and retraining triggers.

## Repository Layout

```text
api/                    FastAPI serving, security, schemas
dashboard/              Streamlit operations dashboard
dags/                   Airflow DAGs
data/raw/               Sample input data
docker/postgres/        PostgreSQL initialization
docs/                   Architecture, demo notes, and runbook
loadtests/              Locust scenarios
migrations/             Alembic database migrations
monitoring/             Prometheus, Alertmanager, and Grafana config
scripts/                Demo, migration, drift, and registry helpers
src/                    Data, feature, model, monitoring, storage, utilities
tests/                  Pytest suite
```

## Documentation

- [Architecture notes](docs/architecture.md)
- [Vietnamese demo guide](docs/ops_demo_vi.md)
- [Operations runbook](docs/runbook.md)
- [Evidence report](docs/evidence_report_vi.md)
- [Slide summary](docs/slide_summary_vi.md)

## Production Notes

- Replace default local credentials and `API_KEY` in `.env`.
- Store secrets in GitHub Secrets, Docker secrets, Vault, or a cloud secret manager.
- Keep MLflow host/CORS settings strict outside localhost.
- Use managed PostgreSQL and S3-compatible storage for persistent environments.
- Put FastAPI behind an authenticated gateway or internal ingress.
- Replace the sample Alertmanager webhook with a real Slack, Discord, PagerDuty, or incident bridge.
- Persist model artifacts and registry metadata outside application containers.
