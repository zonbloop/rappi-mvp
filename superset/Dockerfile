FROM apache/superset:4.1.1

USER root

# Minimal Postgres driver for SQLAlchemy.
RUN pip install --no-cache-dir psycopg2-binary

USER superset
