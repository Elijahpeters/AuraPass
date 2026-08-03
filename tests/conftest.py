import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    from aurapass import database

    database_path = tmp_path / "aurapass-test.db"
    monkeypatch.setattr(database, "DATABASE_PATH", database_path)
    monkeypatch.setattr(database, "ensure_directories", lambda: tmp_path.mkdir(exist_ok=True))
    database.init_db()
    return database
