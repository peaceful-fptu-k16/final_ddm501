from __future__ import annotations

import json
import os

import pandas as pd
import requests
import streamlit as st

from src.storage.prediction_logs import load_prediction_logs

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY")


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY} if API_KEY else {}

st.set_page_config(page_title="Server Log Anomaly Ops", layout="wide")
st.title("Server Log Anomaly Ops Dashboard")

with st.sidebar:
    st.header("API")
    api_url = st.text_input("FastAPI URL", API_URL)
    health_clicked = st.button("Check health")
    if health_clicked:
        try:
            st.json(requests.get(f"{api_url}/health", timeout=5).json())
        except Exception as exc:
            st.error(f"Health check failed: {exc}")

    if st.button("Run drift check"):
        try:
            st.json(requests.post(f"{api_url}/drift", headers=_auth_headers(), timeout=30).json())
        except Exception as exc:
            st.error(f"Drift check failed: {exc}")

    if st.button("Run fairness report"):
        try:
            st.json(requests.post(f"{api_url}/fairness", headers=_auth_headers(), timeout=30).json())
        except Exception as exc:
            st.error(f"Fairness report failed: {exc}")

    if st.button("Check retraining trigger"):
        try:
            response = requests.post(
                f"{api_url}/retrain",
                json={"force": False},
                headers=_auth_headers(),
                timeout=120,
            )
            st.json(response.json())
        except Exception as exc:
            st.error(f"Retraining check failed: {exc}")

left, right = st.columns([1, 1])

with left:
    st.subheader("Prediction input")
    server_id = st.text_input("server_id", "srv-01")
    cpu_usage = st.slider("cpu_usage", 0.0, 100.0, 92.5)
    memory_usage = st.slider("memory_usage", 0.0, 100.0, 88.1)
    request_count = st.number_input("request_count", min_value=0.0, value=420.0)
    error_rate = st.slider("error_rate", 0.0, 1.0, 0.27)
    avg_latency_ms = st.number_input("avg_latency_ms", min_value=0.0, value=1600.0)
    p95_latency_ms = st.number_input("p95_latency_ms", min_value=0.0, value=2400.0)

    payload = {
        "server_id": server_id,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "request_count": request_count,
        "error_rate": error_rate,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
    }

    if st.button("Detect"):
        try:
            response = requests.post(f"{api_url}/detect", json=payload, headers=_auth_headers(), timeout=10)
            response.raise_for_status()
            st.json(response.json())
        except Exception as exc:
            st.error(f"Prediction failed: {exc}")

    if st.button("Explain"):
        try:
            response = requests.post(f"{api_url}/explain", json=payload, headers=_auth_headers(), timeout=30)
            response.raise_for_status()
            st.json(response.json())
        except Exception as exc:
            st.error(f"Explain failed: {exc}")

with right:
    st.subheader("Recent production predictions")
    production_log = os.getenv("PRODUCTION_LOG_PATH", "data/production/predictions.csv")
    try:
        df = load_prediction_logs(limit=50, fallback_path=production_log)
    except Exception as exc:
        st.warning(f"Could not load prediction log: {exc}")
        df = pd.DataFrame()

    if not df.empty:
        st.dataframe(df.tail(50), use_container_width=True)
        if "prediction" in df.columns:
            counts = df["prediction"].value_counts().rename_axis("prediction").reset_index(name="count")
            st.bar_chart(counts, x="prediction", y="count")
    else:
        st.info("No prediction log yet. Send a request to /detect first.")

    st.subheader("Latest drift report")
    drift_report = os.getenv("DRIFT_REPORT_PATH", "reports/drift/latest_production_report.json")
    if os.path.exists(drift_report):
        with open(drift_report, encoding="utf-8") as handle:
            st.json(json.load(handle))
    else:
        st.info("No production drift report yet. Run the drift check first.")

    st.subheader("Latest fairness report")
    fairness_report = os.getenv("FAIRNESS_REPORT_PATH", "reports/fairness/latest_report.json")
    if os.path.exists(fairness_report):
        with open(fairness_report, encoding="utf-8") as handle:
            st.json(json.load(handle))
    else:
        st.info("No fairness report yet. Run the fairness check first.")
