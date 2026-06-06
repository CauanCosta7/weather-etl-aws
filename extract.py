import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import Config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    reraise=True,
)
def _fetch_city(city: str, api_key: str) -> dict[str, Any]:
    """Busca clima de uma cidade com retry automático e backoff."""
    response = requests.get(
        BASE_URL,
        params={"q": city, "appid": api_key, "units": "metric"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _save_bronze(records: list[dict], config: Config) -> str:
    """Salva JSON bruto no S3 Bronze com partição por data."""
    now = datetime.now(timezone.utc)
    key = f"bronze/weather/{now.strftime('%Y/%m/%d')}/raw_{now.strftime('%Y%m%d_%H%M%S')}.json"

    s3 = boto3.client("s3", region_name=config.aws_region)
    s3.put_object(
        Bucket=config.s3_bucket,
        Key=key,
        Body=json.dumps(records, ensure_ascii=False),
        ContentType="application/json",
    )
    logger.info("bronze_saved bucket=%s key=%s records=%d", config.s3_bucket, key, len(records))
    return key


def extract(config: Config) -> str:
    """
    Extrai dados da OpenWeatherMap API e salva no S3 Bronze.
    Retorna a S3 key do arquivo criado.
    """
    logger.info("extract_start cities=%s", config.owm_cities)
    start = datetime.now(timezone.utc)

    records: list[dict] = []
    errors: list[str] = []

    for city in config.owm_cities:
        try:
            data = _fetch_city(city.strip(), config.owm_api_key)
            data["_extracted_at"] = datetime.now(timezone.utc).isoformat()
            records.append(data)
            logger.info("city_extracted city=%s", city)
        except requests.exceptions.RequestException as exc:
            logger.error("city_failed city=%s error=%s", city, exc)
            errors.append(city)

    if not records:
        raise RuntimeError(f"Nenhum dado extraído. Cidades com erro: {errors}")

    if errors:
        logger.warning("extract_partial_failure failed_cities=%s", errors)

    bronze_key = _save_bronze(records, config)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        "extract_done records=%d errors=%d elapsed_s=%.2f",
        len(records), len(errors), elapsed,
    )
    return bronze_key
