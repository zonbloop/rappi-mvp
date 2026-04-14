from __future__ import annotations

import pytest
import psycopg2

from app.db import WeatherRepository
from app.ingestor import WeatherIngestor
from app.sources import OpenMeteoSource


@pytest.mark.integration
def test_should_run_single_ingestion_iteration_against_postgres(test_database_url, monkeypatch):
    if not test_database_url:
        pytest.skip("TEST_DATABASE_URL/DATABASE_URL no definido; se omite integración")

    payload = {
        "current": {
            "time": "2026-01-01T10:00",
            "interval": 900,
            "temperature_2m": 20.0,
            "precipitation": 2.0,
        }
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    monkeypatch.setattr("app.sources.requests.get", lambda *args, **kwargs: FakeResponse())

    repository = WeatherRepository(test_database_url)
    source = OpenMeteoSource(timeout_seconds=5)
    ingestor = WeatherIngestor(source=source, repository=repository)

    ingestor.bootstrap()
    ingestor.ingest_once()

    with psycopg2.connect(test_database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT observed_at, temperature_c, precipitation_mm, precip_interval_seconds, source
                FROM weather_observations
                WHERE observed_at = %s
                """,
                ("2026-01-01T10:00:00-06:00",),
            )
            row = cur.fetchone()

    assert row is not None, "No se insertó la observación esperada en weather_observations"
    assert float(row[1]) == 20.0
    assert float(row[2]) == 2.0
    assert int(row[3]) == 900
    assert row[4] == "open-meteo"
