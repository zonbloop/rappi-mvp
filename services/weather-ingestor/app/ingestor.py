"""Core weather ingestion loop."""

from __future__ import annotations

import logging
import time

from .db import WeatherRepository
from .sources import ObservationSource

logger = logging.getLogger(__name__)


class WeatherIngestor:
    """Coordinates data source reads and PostgreSQL upserts."""

    def __init__(self, source: ObservationSource, repository: WeatherRepository) -> None:
        self._source = source
        self._repository = repository

    def bootstrap(self) -> None:
        """Ensure required database schema exists."""
        self._repository.ensure_schema()
        logger.info("Database schema ready (weather_observations)")

    def ingest_once(self) -> None:
        """Fetch one observation and persist it with idempotent upsert."""
        observation = self._source.fetch_observation()
        self._repository.upsert_observation(observation)
        logger.info(
            (
                "Upserted weather observation "
                "observed_at=%s temperature_c=%s precipitation_mm=%s "
                "precip_interval_seconds=%s source=%s"
            ),
            observation.observed_at.isoformat(),
            observation.temperature_c,
            observation.precipitation_mm,
            observation.precip_interval_seconds,
            observation.source,
        )

    def run_forever(self, poll_seconds: int) -> None:
        """Run the ingestion loop at a fixed polling interval."""
        while True:
            start = time.monotonic()
            try:
                self.ingest_once()
            except Exception:  # noqa: BLE001
                logger.exception("Weather ingestion iteration failed")

            elapsed = time.monotonic() - start
            sleep_seconds = max(0, poll_seconds - int(elapsed))
            logger.info("Sleeping %s seconds before next poll", sleep_seconds)
            time.sleep(sleep_seconds)
