# AGENTS.md

Este repo hoy solo contiene `req.md` (no hay implementación). Este archivo captura el **MVP acordado** y los **detalles que se pierden fácil** al retomar el trabajo.

## MVP (Fleet Connection Advisor, CDMX)

- Alcance: **CDMX solamente**.
- Fuente clima: **API pública sin API key/registro**.
- Variables a guardar: **precipitación** y **temperatura**.
- Cadencia: **guardar cada 5 minutos** en PostgreSQL.
- Frontend/BI: **Apache Superset** para histórico + KPIs.
- KPIs (solo 3 para MVP):
  - `Weather Severity Index (WSI)` (basado en lluvia alta)
  - `Degradación esperada` sobre `% órdenes atendidas` y `SLA pickup`
  - `Fleet Buffer requerido`

## Fuente de datos (preferida)

- API: **Open-Meteo** (no requiere key para el uso previsto en el MVP).
- Coordenadas CDMX: `lat=19.4326`, `lon=-99.1332`.
- Timezone: `America/Mexico_City` (guardar en DB como `timestamptz`).
- Endpoint recomendado (current):
  - `https://api.open-meteo.com/v1/forecast?latitude=19.4326&longitude=-99.1332&timezone=America%2FMexico_City&current=temperature_2m,precipitation`

Gotcha importante:
- `current.precipitation` en Open-Meteo es **acumulado en un intervalo** (ver `current.interval`, típicamente 900s = 15 min). El job corre cada 5 min pero la medida puede repetirse; por eso **UPSERT por `observed_at`**.

## Fallback si no hay API (o para demo offline)

- Permitir `CSV_SIMULATION=1` para leer datos simulados desde `data/cdmx_weather_seed.csv`.
- CSV recomendado (columnas):
  - `observed_at` (ISO8601 con tz)
  - `temperature_c`
  - `precipitation_mm`
  - `precip_interval_seconds`

## Modelo de datos (PostgreSQL)

Tabla mínima (CDMX): `weather_observations`

- `observed_at timestamptz primary key`
- `temperature_c numeric not null`
- `precipitation_mm numeric not null`
- `precip_interval_seconds int not null` (p.ej. 900)
- `source text not null` (`open-meteo` | `csv`)
- `fetched_at timestamptz not null default now()`

Idempotencia:
- Insertar con `ON CONFLICT (observed_at) DO UPDATE`.
- Usar como `observed_at` el timestamp provisto por la fuente (`current.time` o el CSV). No “inventar” el timestamp con `now()` truncado si la API devuelve su propia marca.

## KPIs (definiciones exactas del MVP)

El MVP no integra aún sistemas reales de órdenes/SLA. Los KPIs salen de clima + **baselines parametrizados**.

Parámetros (env sugeridos):
- `RAIN_HIGH_MM` (umbral de “lluvia alta”, en mm por el intervalo reportado)
- `BASE_ORDERS_ATTENDED_PCT` (0..1)
- `BASE_PICKUP_SLA_MIN` (minutos)
- `ALPHA_ATTENDED_DROP` (caída por `WSI=1`)
- `GAMMA_SLA_INCREASE_MIN` (incremento en minutos por `WSI=1`)
- `BUFFER_MAX_UNITS` (máximo buffer a exigir cuando `WSI=1`)

Fórmulas:
- KPI1: `WSI = LEAST(1, precipitation_mm / RAIN_HIGH_MM)`
- KPI2:
  - `% órdenes atendidas esperadas = BASE_ORDERS_ATTENDED_PCT - ALPHA_ATTENDED_DROP * WSI`
  - `SLA pickup esperado (min) = BASE_PICKUP_SLA_MIN + GAMMA_SLA_INCREASE_MIN * WSI`
- KPI3: `buffer_required = CEIL(BUFFER_MAX_UNITS * WSI)`

Implementación recomendada para Superset:
- Exponer KPIs vía una vista SQL (p.ej. `kpi_5m`) para que el dashboard no dependa de “calculated columns” frágiles.

## Docker Compose (servicios del MVP)

El compose debe separar servicios:
- `postgres`: persistente (volumen) + healthcheck.
- `weather-ingestor`: script en loop/scheduler cada 300s que llama Open‑Meteo (o CSV) y hace UPSERT.
- `superset`: UI conectada a Postgres.
- `superset-init` (one-shot): migraciones + creación de admin.

Decisión explícita del MVP:
- No meter Redis/Celery para ahorrar tiempo; usar Superset en modo básico.

Secretos/config:
- No hardcodear passwords en YAML; usar `.env` para `POSTGRES_PASSWORD`, `SUPERSET_SECRET_KEY`, credenciales admin de Superset.

## Dashboard (Superset)

- Dataset principal: `weather_observations` (y/o `kpi_5m`).
- Gráficas mínimas:
  - Serie temporal `precipitation_mm`
  - Serie temporal `temperature_c`
  - Cards: `WSI`, `% órdenes atendidas esperadas`, `SLA pickup esperado`, `buffer_required`

## Validaciones rápidas (para no “creerle” al dashboard)

- DB: confirmar que aparecen filas nuevas (o updates) cada 5 min.
- DB: verificar que no haya duplicados por timestamp (PK `observed_at`).
- Interpretación: no asumir que `precipitation_mm` es “mm/5min”; respetar `precip_interval_seconds`.
