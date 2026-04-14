"""Entrypoint for CDMX weather ingestor service."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .db import WeatherRepository
from .ingestor import WeatherIngestor
from .sources import CsvSimulationSource, OpenMeteoSource


def configure_logging() -> None:
    """Configure human-readable logs to stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        stream=sys.stdout,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CDMX weather ingestion service")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single ingestion iteration and exit",
    )
    return parser.parse_args()


def build_ingestor() -> tuple[WeatherIngestor, int]:
    config = load_config()
    repository = WeatherRepository(config.database_url)

    source = (
        CsvSimulationSource(config.csv_path)
        if config.csv_simulation
        else OpenMeteoSource()
    )

    logging.getLogger(__name__).info(
        "Configured weather source: %s",
        "csv" if config.csv_simulation else "open-meteo",
    )

    return WeatherIngestor(source=source, repository=repository), config.poll_seconds


def main() -> int:
    configure_logging()
    args = parse_args()

    try:
        ingestor, poll_seconds = build_ingestor()
        ingestor.bootstrap()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("Failed during weather ingestor startup")
        return 1

    if args.once:
        try:
            ingestor.ingest_once()
            return 0
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("Single ingestion run failed")
            return 1

    ingestor.run_forever(poll_seconds=poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
