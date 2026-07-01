from fastapi.testclient import TestClient

from scripts import alertmanager_airflow_bridge as bridge


def test_alertmanager_bridge_triggers_matching_firing_alert(monkeypatch) -> None:
    calls = []

    def fake_post_airflow_dag_run(alert, settings):
        calls.append((alert, settings))
        return {"ok": True, "status_code": 200, "body": {"dag_run_id": "demo"}}

    monkeypatch.setenv("ALERT_TRIGGER_NAMES", "DataDriftDetected")
    monkeypatch.setattr(bridge, "_post_airflow_dag_run", fake_post_airflow_dag_run)
    client = TestClient(bridge.app)

    response = client.post(
        "/alertmanager",
        json={
            "alerts": [
                {"status": "resolved", "labels": {"alertname": "DataDriftDetected"}},
                {"status": "firing", "labels": {"alertname": "PredictionApiLatencyHigh"}},
                {"status": "firing", "labels": {"alertname": "DataDriftDetected"}, "fingerprint": "abc"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["matched_firing_alerts"] == 1
    assert response.json()["triggered_dag_runs"] == 1
    assert calls[0][0]["fingerprint"] == "abc"
