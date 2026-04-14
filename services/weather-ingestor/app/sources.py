"""Weather data sources: Open-Meteo API and CSV simulation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import requests

from .constants import CDMX_LATITUDE, CDMX_LONGITUDE, CDMX_TIMEZONE, OPEN_METEO_URL
from .models import WeatherObservation


class ObservationSource(Protocol):
    """Interface for weather observation providers."""

    def fetch_observation(self) -> WeatherObservation:
        """Fetch a single normalized observation from the source."""


def _parse_observed_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(CDMX_TIMEZONE))
    return parsed


def _to_decimal(raw_value: object, field_name: str) -> Decimal:
    try:
        return Decimal(str(raw_value))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid decimal for {field_name}: {raw_value}") from exc


def _to_int(raw_value: object, field_name: str) -> int:
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer for {field_name}: {raw_value}") from exc

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0")
    return value


class OpenMeteoSource:
    """Fetch weather observations from Open-Meteo current weather endpoint."""

    def __init__(self, timeout_seconds: int = 15) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch_observation(self) -> WeatherObservation:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": CDMX_LATITUDE,
                "longitude": CDMX_LONGITUDE,
                "timezone": CDMX_TIMEZONE,
                "current": "temperature_2m,precipitation",
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        payload = response.json()
        current = payload.get("current")
        if not isinstance(current, dict):
            raise ValueError("Open-Meteo response missing 'current' object")

        observed_at_raw = current.get("time")
        temperature_raw = current.get("temperature_2m")
        precipitation_raw = current.get("precipitation")
        interval_raw = current.get("interval")

        if observed_at_raw is None:
            raise ValueError("Open-Meteo response missing current.time")

        observation = WeatherObservation(
            observed_at=_parse_observed_at(str(observed_at_raw)),
            temperature_c=_to_decimal(temperature_raw, "current.temperature_2m"),
            precipitation_mm=_to_decimal(precipitation_raw, "current.precipitation"),
            precip_interval_seconds=_to_int(interval_raw, "current.interval"),
            source="open-meteo",
        )

        return observation


@dataclass(frozen=True)
class CsvObservationRow:
    observed_at: datetime
    temperature_c: Decimal
    precipitation_mm: Decimal
    precip_interval_seconds: int


class CsvSimulationSource:
    """Read observations sequentially from CSV for offline/demo usage."""

    def __init__(self, csv_path: str) -> None:
        self._csv_path = Path(csv_path)
        self._rows = self._load_rows(self._csv_path)
        self._cursor = 0

    def fetch_observation(self) -> WeatherObservation:
        row = self._rows[self._cursor]
        self._cursor = (self._cursor + 1) % len(self._rows)

        return WeatherObservation(
            observed_at=row.observed_at,
            temperature_c=row.temperature_c,
            precipitation_mm=row.precipitation_mm,
            precip_interval_seconds=row.precip_interval_seconds,
            source="csv",
        )

    @staticmethod
    def _load_rows(csv_path: Path) -> list[CsvObservationRow]:
        ensure_csv_seed_file(csv_path)

        rows: list[CsvObservationRow] = []
        with csv_path.open("r", encoding="utf-8", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            required_fields = {
                "observed_at",
                "temperature_c",
                "precipitation_mm",
                "precip_interval_seconds",
            }
            found_fields = set(reader.fieldnames or [])
            if not required_fields.issubset(found_fields):
                missing = sorted(required_fields - found_fields)
                raise ValueError(
                    f"CSV missing required columns: {', '.join(missing)}"
                )

            for row in reader:
                rows.append(
                    CsvObservationRow(
                        observed_at=_parse_observed_at(str(row["observed_at"])),
                        temperature_c=_to_decimal(row["temperature_c"], "temperature_c"),
                        precipitation_mm=_to_decimal(
                            row["precipitation_mm"], "precipitation_mm"
                        ),
                        precip_interval_seconds=_to_int(
                            row["precip_interval_seconds"],
                            "precip_interval_seconds",
                        ),
                    )
                )

        if not rows:
            raise ValueError(f"CSV file has no data rows: {csv_path}")

        return rows


def ensure_csv_seed_file(csv_path: str | Path) -> None:
    """Create the default simulation CSV if it does not exist."""
    path = Path(csv_path)
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    seed_rows = [
        ("2026-01-01T10:00:00-06:00", "18.2", "0.0", "900"),
        ("2026-01-01T10:15:00-06:00", "18.0", "0.4", "900"),
        ("2026-01-01T10:30:00-06:00", "17.7", "1.2", "900"),
        ("2026-01-01T10:45:00-06:00", "17.5", "2.1", "900"),
        ("2026-01-01T11:00:00-06:00", "17.3", "0.7", "900"),
        ("2026-01-01T11:15:00-06:00", "17.1", "0.0", "900"),
    ]

    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(
            [
                "observed_at",
                "temperature_c",
                "precipitation_mm",
                "precip_interval_seconds",
            ]
        )
        writer.writerows(seed_rows)
