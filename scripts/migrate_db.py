from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.config import settings


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def ensure_postgres_database(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql") or not url.database:
        return

    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
            {"database_name": url.database},
        ).scalar()
        if not exists:
            connection.execute(text(f"CREATE DATABASE {_quote_identifier(url.database)}"))


def run_migrations() -> None:
    if not settings.prediction_database_url:
        print("PREDICTION_DATABASE_URL is not set; skipping migrations")
        return

    ensure_postgres_database(settings.prediction_database_url)
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.prediction_database_url)
    command.upgrade(config, "head")


if __name__ == "__main__":
    run_migrations()
