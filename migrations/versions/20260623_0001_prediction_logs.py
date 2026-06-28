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

TABLE = "prediction_logs"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
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
    op.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS request_id TEXT;")
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_timestamp
            ON {TABLE} (timestamp DESC);
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_prediction
            ON {TABLE} (prediction);
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_prediction_logs_request_id
            ON {TABLE} (request_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_prediction_logs_request_id;")
    op.execute("DROP INDEX IF EXISTS idx_prediction_logs_prediction;")
    op.execute("DROP INDEX IF EXISTS idx_prediction_logs_timestamp;")
    op.execute(f"DROP TABLE IF EXISTS {TABLE};")
