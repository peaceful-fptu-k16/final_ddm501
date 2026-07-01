from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Request as FastAPIRequest

app = FastAPI(title="Alertmanager Airflow Bridge", version="0.1.0")


def _env_list(name: str, default: str = "") -> set[str]:
    return {item.strip() for item in os.getenv(name, default).split(",") if item.strip()}


def _settings() -> dict[str, Any]:
    return {
        "airflow_api_url": os.getenv("AIRFLOW_API_URL", "http://airflow-webserver:8080").rstrip("/"),
        "airflow_username": os.getenv("AIRFLOW_USERNAME", "admin"),
        "airflow_password": os.getenv("AIRFLOW_PASSWORD", "admin"),
        "dag_id": os.getenv("AIRFLOW_RETRAINING_DAG_ID", "server_log_anomaly_retraining"),
        "trigger_alert_names": _env_list("ALERT_TRIGGER_NAMES", "DataDriftDetected,HighAnomalyRate"),
        "timeout_seconds": float(os.getenv("AIRFLOW_TRIGGER_TIMEOUT_SECONDS", "10")),
    }


def _alert_name(alert: dict[str, Any]) -> str:
    return str(alert.get("labels", {}).get("alertname", "unknown"))


def _matching_firing_alerts(payload: dict[str, Any], trigger_alert_names: set[str]) -> list[dict[str, Any]]:
    alerts = payload.get("alerts", [])
    if not isinstance(alerts, list):
        return []
    firing = [alert for alert in alerts if isinstance(alert, dict) and alert.get("status") == "firing"]
    if not trigger_alert_names:
        return firing
    return [alert for alert in firing if _alert_name(alert) in trigger_alert_names]


def _auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def _dag_run_id(alert: dict[str, Any]) -> str:
    alert_name = "".join(character if character.isalnum() else "_" for character in _alert_name(alert))
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"alertmanager__{alert_name}__{timestamp}"


def _post_airflow_dag_run(alert: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    endpoint = f"{settings['airflow_api_url']}/api/v1/dags/{settings['dag_id']}/dagRuns"
    body = {
        "dag_run_id": _dag_run_id(alert),
        "conf": {
            "source": "alertmanager",
            "alert": alert,
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": _auth_header(settings["airflow_username"], settings["airflow_password"]),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=settings["timeout_seconds"]) as response:
        response_body = response.read().decode("utf-8")
        return {
            "ok": 200 <= response.status < 300,
            "status_code": response.status,
            "body": json.loads(response_body) if response_body else {},
        }


@app.get("/health")
def health() -> dict[str, object]:
    settings = _settings()
    return {
        "status": "ok",
        "airflow_api_url": settings["airflow_api_url"],
        "dag_id": settings["dag_id"],
        "trigger_alert_names": sorted(settings["trigger_alert_names"]),
    }


@app.post("/alertmanager")
async def alertmanager_webhook(request: FastAPIRequest) -> dict[str, Any]:
    payload = await request.json()
    settings = _settings()
    alerts = _matching_firing_alerts(payload, settings["trigger_alert_names"])
    results = []

    for alert in alerts:
        try:
            result = _post_airflow_dag_run(alert, settings)
        except HTTPError as exc:
            result = {
                "ok": False,
                "status_code": exc.code,
                "error": exc.read().decode("utf-8", errors="replace"),
            }
        except (TimeoutError, URLError) as exc:
            result = {
                "ok": False,
                "status_code": None,
                "error": str(exc),
            }
        results.append(
            {
                "alertname": _alert_name(alert),
                "fingerprint": alert.get("fingerprint"),
                "airflow": result,
            }
        )

    return {
        "status": "processed",
        "received_alerts": len(payload.get("alerts", [])) if isinstance(payload.get("alerts", []), list) else 0,
        "matched_firing_alerts": len(alerts),
        "triggered_dag_runs": sum(1 for result in results if result["airflow"].get("ok")),
        "results": results,
    }
