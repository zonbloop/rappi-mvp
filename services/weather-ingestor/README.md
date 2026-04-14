# weather-ingestor (MVP)

Ingesta clima de CDMX cada `POLL_SECONDS` (default `300`) desde Open-Meteo y hace UPSERT en PostgreSQL.

## Variables de entorno

- `DATABASE_URL` **(requerida)**
- `POLL_SECONDS` (opcional, default `300`)
- `CSV_SIMULATION=1` (opcional, usa `data/cdmx_weather_seed.csv` en vez de Open-Meteo)
- `CSV_FILE_PATH` (opcional, default `data/cdmx_weather_seed.csv`)

## Ejecutar local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r services/weather-ingestor/requirements.txt

export DATABASE_URL='postgresql://user:pass@localhost:5432/rappi'
python -m app.main --once
```

> Ejecuta desde `services/weather-ingestor/` para que `python -m app.main` resuelva bien.

## Docker

Construir desde la raíz del repo:

```bash
docker build -f services/weather-ingestor/Dockerfile -t weather-ingestor .
docker run --rm \
  -e DATABASE_URL='postgresql://user:pass@host.docker.internal:5432/rappi' \
  weather-ingestor
```

## Tabla objetivo

La app asegura `weather_observations` con:

- `observed_at timestamptz primary key`
- `temperature_c numeric not null`
- `precipitation_mm numeric not null`
- `precip_interval_seconds int not null`
- `source text not null`
- `fetched_at timestamptz not null default now()`
