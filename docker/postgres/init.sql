CREATE DATABASE mlflow;

CREATE TABLE IF NOT EXISTS prediction_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    server_id TEXT NOT NULL,
    cpu_usage DOUBLE PRECISION NOT NULL,
    memory_usage DOUBLE PRECISION NOT NULL,
    request_count DOUBLE PRECISION NOT NULL,
    error_rate DOUBLE PRECISION NOT NULL,
    avg_latency_ms DOUBLE PRECISION NOT NULL,
    p95_latency_ms DOUBLE PRECISION NOT NULL,
    prediction TEXT NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    risk_level TEXT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_logs_timestamp
    ON prediction_logs (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_logs_prediction
    ON prediction_logs (prediction);
