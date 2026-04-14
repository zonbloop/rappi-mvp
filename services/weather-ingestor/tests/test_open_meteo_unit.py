from __future__ import annotations

from app.constants import CDMX_LATITUDE, CDMX_LONGITUDE, CDMX_TIMEZONE, OPEN_METEO_URL
from app.sources import OpenMeteoSource


def test_should_call_open_meteo_with_expected_url_and_params(monkeypatch, sample_open_meteo_payload):
    called = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sample_open_meteo_payload

    def fake_get(url, *, params, timeout):
        called["url"] = url
        called["params"] = params
        called["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.sources.requests.get", fake_get)

    source = OpenMeteoSource(timeout_seconds=7)
    source.fetch_observation()

    assert called["url"] == OPEN_METEO_URL
    assert called["params"] == {
        "latitude": CDMX_LATITUDE,
        "longitude": CDMX_LONGITUDE,
        "timezone": CDMX_TIMEZONE,
        "current": "temperature_2m,precipitation",
    }
    assert called["timeout"] == 7


def test_should_parse_open_meteo_json_into_weather_observation(monkeypatch, sample_open_meteo_payload):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sample_open_meteo_payload

    monkeypatch.setattr("app.sources.requests.get", lambda *args, **kwargs: FakeResponse())

    source = OpenMeteoSource(timeout_seconds=5)
    result = source.fetch_observation()

    assert result.observed_at.isoformat().startswith("2026-01-01T10:00:00")
    assert float(result.temperature_c) == 22.4
    assert float(result.precipitation_mm) == 1.5
    assert result.precip_interval_seconds == 900
    assert result.source == "open-meteo"
