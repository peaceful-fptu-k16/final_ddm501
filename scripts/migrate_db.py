from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.config import settings


def run_migrations() -> None:
    if not settings.prediction_database_url:
        print("PREDICTION_DATABASE_URL is not set; skipping migrations")
        return

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.prediction_database_url)
    command.upgrade(config, "head")


if __name__ == "__main__":
    run_migrations()
