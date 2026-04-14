from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


@pytest.fixture
def sample_open_meteo_payload():
    return {
        "latitude": 19.4326,
        "longitude": -99.1332,
        "timezone": "America/Mexico_City",
        "current": {
            "time": "2026-01-01T10:00",
            "interval": 900,
            "temperature_2m": 22.4,
            "precipitation": 1.5,
        },
    }


@pytest.fixture
def test_database_url():
    return os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
