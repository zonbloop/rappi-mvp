# Fleet Connection Advisor (MVP) - Docker Compose

Este MVP levanta servicios separados:

- `postgres`: base de datos principal (persistente, con healthcheck)
- `weather-ingestor`: ingesta de clima cada 5 minutos (build desde `services/weather-ingestor`)
- `superset-init`: inicialización one-shot de Superset (migraciones + creación de admin)
- `superset`: UI de Apache Superset
- `superset-bootstrap` (one-shot, opcional): crea conexión DB + dataset + charts + dashboard vía API

## Decisión de metadata DB para Superset

Para simplificar el MVP, **Superset usa el mismo PostgreSQL y la misma base de datos (`rappi_tec`)** que el ingestor.  
No se agrega Redis/Celery (modo básico, como se acordó).

## 1) Preparar variables de entorno

```bash
cp .env.example .env
```

Luego edita `.env` y define al menos:

- `POSTGRES_PASSWORD`
- `SUPERSET_SECRET_KEY`
- `SUPERSET_ADMIN_USERNAME`
- `SUPERSET_ADMIN_PASSWORD`
- `SUPERSET_ADMIN_EMAIL`

## 2) Levantar stack

```bash
docker compose up -d --build
```

Servicios expuestos en el host:

- Superset: `http://localhost:8088`
- Postgres: `localhost:5432` (si el puerto está ocupado, cambia el mapeo en `docker-compose.yml`)

## 2.1) (Opcional) Crear dashboard MVP automáticamente

Esto crea en Superset:

- Database connection: `Postgres (MVP)`
- Dataset: `public.weather_observations`
- Charts: precipitación, temperatura, tabla con últimos registros, y un **dummy forecast** (persistencia a 60 min)
- Dashboard: `Fleet Connection Advisor (CDMX)`

```bash
docker compose run --rm superset-bootstrap
```

Para ver logs:

```bash
docker compose logs -f
```

## 3) URL de Superset y credenciales

- URL: http://localhost:8088
- Usuario: `SUPERSET_ADMIN_USERNAME`
- Password: `SUPERSET_ADMIN_PASSWORD`

## 4) Ver tabla en PostgreSQL

Entrar a psql:

```bash
docker compose exec postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-rappi_tec}"
```

Dentro de `psql`:

```sql
\dt
SELECT * FROM weather_observations ORDER BY observed_at DESC LIMIT 10;
SELECT * FROM weather_forecast_dummy ORDER BY observed_at ASC LIMIT 10;
```

O directamente desde una sola línea:

```bash
docker compose exec postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-rappi_tec}" -c "SELECT * FROM weather_observations ORDER BY observed_at DESC LIMIT 10;"
```

## 5) Validación de compose

```bash
docker compose config
```

## Troubleshooting

- Si `superset-init` falla: mira logs con `docker compose logs --tail=200 superset-init`.
- Si Superset muestra error de grain (ej. `PT5M`): usa el bootstrap de este repo; los charts del MVP usan `PT1M`.
- Si el dashboard no aparece: re-ejecuta `docker compose run --rm superset-bootstrap`.
