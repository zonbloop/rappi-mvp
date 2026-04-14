"""Configuration management for weather ingestor."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .constants import DEFAULT_CSV_PATH, DEFAULT_POLL_SECONDS


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    database_url: str
    poll_seconds: int
    csv_simulation: bool
    csv_path: str


def _parse_poll_seconds(raw_value: str) -> int:
    try:
        poll_seconds = int(raw_value)
    except ValueError as exc:
        raise ValueError("POLL_SECONDS must be a valid integer") from exc

    if poll_seconds <= 0:
        raise ValueError("POLL_SECONDS must be greater than 0")

    return poll_seconds


def load_config() -> AppConfig:
    """Load and validate service configuration from environment variables."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL is required")

    raw_poll_seconds = os.getenv("POLL_SECONDS", str(DEFAULT_POLL_SECONDS)).strip()
    poll_seconds = _parse_poll_seconds(raw_poll_seconds)

    csv_simulation = os.getenv("CSV_SIMULATION", "0").strip() == "1"
    csv_path = os.getenv("CSV_FILE_PATH", DEFAULT_CSV_PATH).strip() or DEFAULT_CSV_PATH

    return AppConfig(
        database_url=database_url,
        poll_seconds=poll_seconds,
        csv_simulation=csv_simulation,
        csv_path=csv_path,
    )
