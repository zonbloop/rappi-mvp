"""Database access helpers for weather ingestor."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection

from .models import WeatherObservation


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_observations (
    observed_at timestamptz PRIMARY KEY,
    temperature_c numeric NOT NULL,
    precipitation_mm numeric NOT NULL,
    precip_interval_seconds int NOT NULL,
    source text NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now()
);
"""


# Dummy forecast view for the dashboard.
# Persistence model: repeats the latest observed values for the next hour.
CREATE_DUMMY_FORECAST_VIEW_SQL = """
CREATE OR REPLACE VIEW weather_forecast_dummy AS
WITH last_obs AS (
    SELECT
        observed_at,
        temperature_c,
        precipitation_mm
    FROM weather_observations
    ORDER BY observed_at DESC
    LIMIT 1
)
SELECT
    gs.observed_at,
    lo.temperature_c,
    lo.precipitation_mm,
    300::int AS forecast_step_seconds,
    'persistence'::text AS model,
    now() AS generated_at
FROM last_obs lo
CROSS JOIN LATERAL generate_series(
    lo.observed_at + interval '5 minutes',
    lo.observed_at + interval '60 minutes',
    interval '5 minutes'
) AS gs(observed_at);
"""


UPSERT_SQL = """
INSERT INTO weather_observations (
    observed_at,
    temperature_c,
    precipitation_mm,
    precip_interval_seconds,
    source
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (observed_at)
DO UPDATE SET
    temperature_c = EXCLUDED.temperature_c,
    precipitation_mm = EXCLUDED.precipitation_mm,
    precip_interval_seconds = EXCLUDED.precip_interval_seconds,
    source = EXCLUDED.source,
    fetched_at = now();
"""


class WeatherRepository:
    """Encapsulates PostgreSQL operations for weather observations."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def _connection(self) -> Iterator[PgConnection]:
        conn = psycopg2.connect(self._database_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)
                cursor.execute(CREATE_DUMMY_FORECAST_VIEW_SQL)

    def upsert_observation(self, observation: WeatherObservation) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    UPSERT_SQL,
                    (
                        observation.observed_at,
                        observation.temperature_c,
                        observation.precipitation_mm,
                        observation.precip_interval_seconds,
                        observation.source,
                    ),
                )
