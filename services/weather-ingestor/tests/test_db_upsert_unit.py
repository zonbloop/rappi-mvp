from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.db import WeatherRepository
from app.models import WeatherObservation


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closed = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


def test_should_execute_upsert_statement_with_on_conflict(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.db.psycopg2.connect", lambda *_args, **_kwargs: fake_conn)

    repo = WeatherRepository("postgresql://example")
    repo.ensure_schema()
    repo.upsert_observation(
        WeatherObservation(
            observed_at=datetime.fromisoformat("2026-01-01T10:00:00-06:00"),
            temperature_c=Decimal("21.2"),
            precipitation_mm=Decimal("3.5"),
            precip_interval_seconds=900,
            source="open-meteo",
        )
    )

    assert len(fake_conn.cursor_obj.executed) == 2

    _create_sql, _ = fake_conn.cursor_obj.executed[0]
    upsert_sql, params = fake_conn.cursor_obj.executed[1]

    normalized = " ".join(str(upsert_sql).split()).upper()
    assert "INSERT INTO WEATHER_OBSERVATIONS" in normalized
    assert "ON CONFLICT (OBSERVED_AT)" in normalized
    assert "DO UPDATE" in normalized

    assert params[0].isoformat() == "2026-01-01T10:00:00-06:00"
    assert str(params[1]) == "21.2"
    assert str(params[2]) == "3.5"
    assert params[3] == 900
    assert params[4] == "open-meteo"

    assert fake_conn.commits == 2
    assert fake_conn.rollbacks == 0
    assert fake_conn.closed == 2
