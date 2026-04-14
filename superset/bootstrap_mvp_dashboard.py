"""Bootstrap Superset assets for the MVP.

This is intentionally minimal and idempotent:
- Creates a Postgres DB connection in Superset ("Postgres (MVP)") if missing
- Creates dataset for public.weather_observations if missing
- Creates 3 charts if missing
- Creates dashboard and basic layout if missing

It uses the Superset REST API (v1) and admin credentials provided via env.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import requests


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var {name}")
    return v


SUPERSET_URL = os.getenv("SUPERSET_URL", "http://superset:8088").rstrip("/")
ADMIN_USER = _env("SUPERSET_ADMIN_USERNAME")
ADMIN_PASS = _env("SUPERSET_ADMIN_PASSWORD")
DB_URI = _env("SUPERSET_MVP_SQLALCHEMY_URI")


def wait_for_superset(timeout_s: int = 180) -> None:
    deadline = time.time() + timeout_s
    last_err: Optional[str] = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{SUPERSET_URL}/health", timeout=5)
            if r.status_code == 200:
                return
            last_err = f"health status={r.status_code} body={r.text[:200]}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(2)
    raise RuntimeError(f"Superset not healthy after {timeout_s}s: {last_err}")


def login_and_csrf(session: requests.Session) -> tuple[str, str]:
    r = session.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS, "provider": "db", "refresh": True},
        timeout=15,
    )
    r.raise_for_status()
    token = r.json()["access_token"]

    r = session.get(
        f"{SUPERSET_URL}/api/v1/security/csrf_token/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    csrf = r.json()["result"]
    return token, csrf


def api(
    session: requests.Session,
    token: str,
    csrf: str,
    method: str,
    path: str,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    r = session.request(
        method,
        f"{SUPERSET_URL}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-CSRFToken": csrf,
            "Content-Type": "application/json",
        },
        json=json_body,
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def find_first_by_name(session: requests.Session, token: str, resource: str, name_key: str, name: str) -> Optional[Dict[str, Any]]:
    r = session.get(
        f"{SUPERSET_URL}/api/v1/{resource}/",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "(page:0,page_size:100)"},
        timeout=30,
    )
    r.raise_for_status()
    for item in r.json().get("result", []):
        if item.get(name_key) == name:
            return item
    return None


def main() -> None:
    wait_for_superset()

    session = requests.Session()
    token, csrf = login_and_csrf(session)

    # 1) Database connection
    db = find_first_by_name(session, token, "database", "database_name", "Postgres (MVP)")
    if db:
        db_id = db["id"]
    else:
        created = api(
            session,
            token,
            csrf,
            "POST",
            "/api/v1/database/",
            {
                "database_name": "Postgres (MVP)",
                "sqlalchemy_uri": DB_URI,
                "expose_in_sqllab": True,
            },
        )
        db_id = created["id"]

    # 2) Dataset
    dataset = find_first_by_name(session, token, "dataset", "table_name", "weather_observations")
    if dataset:
        dataset_id = dataset["id"]
    else:
        created = api(
            session,
            token,
            csrf,
            "POST",
            "/api/v1/dataset/",
            {"database": db_id, "schema": "public", "table_name": "weather_observations"},
        )
        dataset_id = created["id"]

    # 3) Charts (idempotent by slice_name)
    def ensure_chart(slice_name: str, viz_type: str, params: Dict[str, Any]) -> int:
        existing = find_first_by_name(session, token, "chart", "slice_name", slice_name)
        if existing:
            return existing["id"]

        payload = {
            "slice_name": slice_name,
            "viz_type": viz_type,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps(params),
        }
        created = api(session, token, csrf, "POST", "/api/v1/chart/", payload)
        return created["id"]

    chart_table = ensure_chart(
        "Weather Observations (Latest)",
        "table",
        {
            "datasource": f"{dataset_id}__table",
            "viz_type": "table",
            "all_columns": [
                "observed_at",
                "temperature_c",
                "precipitation_mm",
                "precip_interval_seconds",
                "source",
            ],
            "order_by_cols": ["[\"observed_at\", false]"],
            "row_limit": 100,
        },
    )

    chart_precip = ensure_chart(
        "Precipitation (mm)",
        "echarts_timeseries_line",
        {
            "datasource": f"{dataset_id}__table",
            "viz_type": "echarts_timeseries_line",
            "granularity_sqla": "observed_at",
            # Postgres default grain list in Superset doesn't include PT5M.
            "time_grain_sqla": "PT1M",
            "time_range": "No filter",
            "metrics": [
                {
                    "expressionType": "SIMPLE",
                    "column": {"column_name": "precipitation_mm"},
                    "aggregate": "SUM",
                    "label": "SUM(precipitation_mm)",
                }
            ],
            "groupby": [],
            "row_limit": 10000,
        },
    )

    chart_temp = ensure_chart(
        "Temperature (C)",
        "echarts_timeseries_line",
        {
            "datasource": f"{dataset_id}__table",
            "viz_type": "echarts_timeseries_line",
            "granularity_sqla": "observed_at",
            "time_grain_sqla": "PT1M",
            "time_range": "No filter",
            "metrics": [
                {
                    "expressionType": "SIMPLE",
                    "column": {"column_name": "temperature_c"},
                    "aggregate": "AVG",
                    "label": "AVG(temperature_c)",
                }
            ],
            "groupby": [],
            "row_limit": 10000,
        },
    )

    # 4) Dashboard
    dash = find_first_by_name(session, token, "dashboard", "slug", "fleet-connection-advisor-cdmx")
    if dash:
        dash_id = dash["id"]
    else:
        created = api(
            session,
            token,
            csrf,
            "POST",
            "/api/v1/dashboard/",
            {
                "dashboard_title": "Fleet Connection Advisor (CDMX)",
                "slug": "fleet-connection-advisor-cdmx",
                "published": True,
            },
        )
        dash_id = created["id"]

    # Attach charts to dashboard (so they show up in the dashboard's chart list)
    for cid in (chart_table, chart_precip, chart_temp):
        api(session, token, csrf, "PUT", f"/api/v1/chart/{cid}", {"dashboards": [dash_id]})

    # 5) Dummy forecast dataset + chart (view is created by the ingestor schema bootstrap)
    forecast_ds = find_first_by_name(session, token, "dataset", "table_name", "weather_forecast_dummy")
    if forecast_ds:
        forecast_ds_id = forecast_ds["id"]
    else:
        created = api(
            session,
            token,
            csrf,
            "POST",
            "/api/v1/dataset/",
            {"database": db_id, "schema": "public", "table_name": "weather_forecast_dummy"},
        )
        forecast_ds_id = created["id"]

    chart_forecast = ensure_chart(
        "Dummy Forecast (Next 60m)",
        "echarts_timeseries_line",
        {
            "datasource": f"{forecast_ds_id}__table",
            "viz_type": "echarts_timeseries_line",
            "granularity_sqla": "observed_at",
            "time_grain_sqla": "PT1M",
            "time_range": "No filter",
            "metrics": [
                {
                    "expressionType": "SIMPLE",
                    "column": {"column_name": "precipitation_mm"},
                    "aggregate": "AVG",
                    "label": "Forecast precipitation (mm)",
                }
            ],
            "groupby": [],
            "row_limit": 10000,
        },
    )
    api(session, token, csrf, "PUT", f"/api/v1/chart/{chart_forecast}", {"dashboards": [dash_id]})

    # Set a simple layout
    position = {
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW_1", "ROW_2"]},
        "ROW_1": {"type": "ROW", "id": "ROW_1", "children": ["COL_1", "COL_2"], "meta": {"background": "BACKGROUND_TRANSPARENT"}},
        "COL_1": {"type": "COLUMN", "id": "COL_1", "children": ["CHART_PREC"], "meta": {"width": 6, "background": "BACKGROUND_TRANSPARENT"}},
        "COL_2": {"type": "COLUMN", "id": "COL_2", "children": ["CHART_TEMP"], "meta": {"width": 6, "background": "BACKGROUND_TRANSPARENT"}},
        "ROW_2": {"type": "ROW", "id": "ROW_2", "children": ["COL_3", "COL_4"], "meta": {"background": "BACKGROUND_TRANSPARENT"}},
        "COL_3": {"type": "COLUMN", "id": "COL_3", "children": ["CHART_FORECAST"], "meta": {"width": 6, "background": "BACKGROUND_TRANSPARENT"}},
        "COL_4": {"type": "COLUMN", "id": "COL_4", "children": ["CHART_TABLE"], "meta": {"width": 6, "background": "BACKGROUND_TRANSPARENT"}},
        "CHART_PREC": {"type": "CHART", "id": "CHART_PREC", "children": [], "meta": {"chartId": chart_precip, "height": 50, "width": 6}},
        "CHART_TEMP": {"type": "CHART", "id": "CHART_TEMP", "children": [], "meta": {"chartId": chart_temp, "height": 50, "width": 6}},
        "CHART_FORECAST": {"type": "CHART", "id": "CHART_FORECAST", "children": [], "meta": {"chartId": chart_forecast, "height": 50, "width": 6}},
        "CHART_TABLE": {"type": "CHART", "id": "CHART_TABLE", "children": [], "meta": {"chartId": chart_table, "height": 50, "width": 6}},
    }
    api(session, token, csrf, "PUT", f"/api/v1/dashboard/{dash_id}", {"position_json": json.dumps(position)})

    print(f"Dashboard ready: {SUPERSET_URL}/superset/dashboard/fleet-connection-advisor-cdmx/")


if __name__ == "__main__":
    main()
