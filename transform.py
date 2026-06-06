import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3
import pandas as pd

from config import Config

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["name", "main", "wind", "weather", "coord", "sys", "dt"]
REQUIRED_MAIN  = ["temp", "humidity", "pressure"]


def _validate_record(record: dict[str, Any]) -> bool:
    """Valida schema do registro bruto. Retorna False se inválido."""
    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        logger.warning("schema_invalid city=%s missing_fields=%s", record.get("name"), missing)
        return False

    missing_main = [f for f in REQUIRED_MAIN if f not in record.get("main", {})]
    if missing_main:
        logger.warning("schema_invalid_main city=%s missing=%s", record.get("name"), missing_main)
        return False

    return True


def _flatten(record: dict[str, Any]) -> dict[str, Any]:
    """Achata registro JSON aninhado em linha tabular."""
    return {
        "city":                record["name"],
        "country":             record["sys"].get("country"),
        "lat":                 record["coord"].get("lat"),
        "lon":                 record["coord"].get("lon"),
        "temp_celsius":        record["main"]["temp"],
        "feels_like":          record["main"].get("feels_like"),
        "temp_min":            record["main"].get("temp_min"),
        "temp_max":            record["main"].get("temp_max"),
        "humidity_pct":        record["main"]["humidity"],
        "pressure_hpa":        record["main"]["pressure"],
        "wind_speed_ms":       record["wind"].get("speed"),
        "wind_deg":            record["wind"].get("deg"),
        "weather_main":        record["weather"][0].get("main") if record.get("weather") else None,
        "weather_description": record["weather"][0].get("description") if record.get("weather") else None,
        "cloudiness_pct":      record.get("clouds", {}).get("all"),
        "visibility_m":        record.get("visibility"),
        "measurement_ts":      pd.Timestamp(record["dt"], unit="s", tz="UTC"),
        "extracted_at":        pd.Timestamp(record.get("_extracted_at")),
    }


def _load_bronze(bronze_key: str, config: Config) -> list[dict]:
    """Lê arquivo JSON do S3 Bronze."""
    s3 = boto3.client("s3", region_name=config.aws_region)
    obj = s3.get_object(Bucket=config.s3_bucket, Key=bronze_key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def _save_silver(df: pd.DataFrame, config: Config) -> str:
    """Salva DataFrame como Parquet no S3 Silver."""
    now = datetime.now(timezone.utc)
    key = f"silver/weather/{now.strftime('%Y/%m/%d')}/clean_{now.strftime('%Y%m%d_%H%M%S')}.parquet"

    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)

    s3 = boto3.client("s3", region_name=config.aws_region)
    s3.put_object(
        Bucket=config.s3_bucket,
        Key=key,
        Body=buffer.getvalue(),
        ContentType="application/octet-stream",
    )
    logger.info("silver_saved key=%s records=%d", key, len(df))
    return key


def transform(bronze_key: str, config: Config) -> str:
    """
    Transforma Bronze → Silver.
    Retorna a S3 key do arquivo Parquet criado.
    """
    logger.info("transform_start bronze_key=%s", bronze_key)
    start = datetime.now(timezone.utc)

    records = _load_bronze(bronze_key, config)
    logger.info("bronze_loaded raw_records=%d", len(records))

    valid = [r for r in records if _validate_record(r)]
    invalid_count = len(records) - len(valid)
    if invalid_count:
        logger.warning("schema_invalid_dropped count=%d", invalid_count)

    if not valid:
        raise RuntimeError("Nenhum registro válido após validação de schema.")

    df = pd.DataFrame([_flatten(r) for r in valid])

    # Checar nulos em colunas críticas
    critical_cols = ["city", "temp_celsius", "humidity_pct", "measurement_ts"]
    for col in critical_cols:
        null_count = int(df[col].isna().sum())
        if null_count:
            logger.warning("nulls_in_critical_col col=%s count=%d", col, null_count)

    df = df.dropna(subset=["city", "measurement_ts"])

    # Remover duplicatas por chave de negócio
    dupes = int(df.duplicated(subset=["city", "measurement_ts"]).sum())
    if dupes:
        logger.warning("duplicates_removed count=%d", dupes)
        df = df.drop_duplicates(subset=["city", "measurement_ts"])

    silver_key = _save_silver(df, config)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("transform_done records=%d elapsed_s=%.2f", len(df), elapsed)
    return silver_key
