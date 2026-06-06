import io
import logging
from datetime import datetime, timezone

import boto3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import Config

logger = logging.getLogger(__name__)

# DDL da tabela Gold — criada automaticamente se não existir
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS fact_weather (
    id                  SERIAL PRIMARY KEY,
    city                VARCHAR(100)   NOT NULL,
    country             VARCHAR(10),
    lat                 NUMERIC(9,6),
    lon                 NUMERIC(9,6),
    temp_celsius        NUMERIC(5,2),
    feels_like          NUMERIC(5,2),
    temp_min            NUMERIC(5,2),
    temp_max            NUMERIC(5,2),
    humidity_pct        INTEGER,
    pressure_hpa        INTEGER,
    wind_speed_ms       NUMERIC(6,2),
    wind_deg            INTEGER,
    weather_main        VARCHAR(50),
    weather_description VARCHAR(100),
    cloudiness_pct      INTEGER,
    visibility_m        INTEGER,
    measurement_ts      TIMESTAMPTZ    NOT NULL,
    extracted_at        TIMESTAMPTZ,
    loaded_at           TIMESTAMPTZ    DEFAULT NOW(),
    UNIQUE (city, measurement_ts)
);
"""

# Upsert idempotente — rodar 2x não duplica dados
_UPSERT = """
INSERT INTO fact_weather (
    city, country, lat, lon,
    temp_celsius, feels_like, temp_min, temp_max,
    humidity_pct, pressure_hpa,
    wind_speed_ms, wind_deg,
    weather_main, weather_description,
    cloudiness_pct, visibility_m,
    measurement_ts, extracted_at
) VALUES %s
ON CONFLICT (city, measurement_ts) DO UPDATE SET
    temp_celsius        = EXCLUDED.temp_celsius,
    humidity_pct        = EXCLUDED.humidity_pct,
    pressure_hpa        = EXCLUDED.pressure_hpa,
    wind_speed_ms       = EXCLUDED.wind_speed_ms,
    weather_description = EXCLUDED.weather_description,
    loaded_at           = NOW();
"""

_COLS = [
    "city", "country", "lat", "lon",
    "temp_celsius", "feels_like", "temp_min", "temp_max",
    "humidity_pct", "pressure_hpa",
    "wind_speed_ms", "wind_deg",
    "weather_main", "weather_description",
    "cloudiness_pct", "visibility_m",
    "measurement_ts", "extracted_at",
]


def _load_silver(silver_key: str, config: Config) -> pd.DataFrame:
    """Lê arquivo Parquet do S3 Silver."""
    s3 = boto3.client("s3", region_name=config.aws_region)
    obj = s3.get_object(Bucket=config.s3_bucket, Key=silver_key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def load(silver_key: str, config: Config) -> int:
    """
    Carrega Silver → RDS Gold via upsert idempotente.
    Retorna número de registros processados.
    """
    logger.info("load_start silver_key=%s", silver_key)
    start = datetime.now(timezone.utc)

    df = _load_silver(silver_key, config)
    logger.info("silver_loaded records=%d", len(df))

    # Converter para lista de tuplas — None para valores nulos
    records = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df[_COLS].itertuples(index=False, name=None)
    ]

    # Context manager garante fechamento de conexão e rollback em falha
    with psycopg2.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password,
        connect_timeout=10,
	sslmode="require",
    ) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(_CREATE_TABLE)
                execute_values(cur, _UPSERT, records)
                conn.commit()
                logger.info("load_committed records=%d", len(records))
            except Exception as exc:
                conn.rollback()
                logger.error("load_failed rollback_executed error=%s", exc)
                raise

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("load_done records=%d elapsed_s=%.2f", len(records), elapsed)
    return len(records)
