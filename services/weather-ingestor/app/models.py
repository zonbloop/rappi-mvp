"""Shared domain models for weather ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class WeatherObservation:
    """A normalized weather observation ready for persistence."""

    observed_at: datetime
    temperature_c: Decimal
    precipitation_mm: Decimal
    precip_interval_seconds: int
    source: str
