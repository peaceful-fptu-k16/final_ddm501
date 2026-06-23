"""create prediction log audit table

Revision ID: 20260623_0001
Revises:
Create Date: 2026-06-23
"""

from __future__ import annotations

from alembic import op

revision = "20260623_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_logs (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            request_id TEXT,
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
        """
    )
    op.execute("ALTER TABLE prediction_logs ADD COLUMN IF NOT EXISTS request_id TEXT;")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_timestamp
            ON prediction_logs (timestamp DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_prediction
            ON prediction_logs (prediction);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_request_id
            ON prediction_logs (request_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_prediction_logs_request_id;")
    op.execute("DROP INDEX IF EXISTS idx_prediction_logs_prediction;")
    op.execute("DROP INDEX IF EXISTS idx_prediction_logs_timestamp;")
    op.execute("DROP TABLE IF EXISTS prediction_logs;")
