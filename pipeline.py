import logging
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from config import Config
from extract import extract
from transform import transform
from load import load

# Logging estruturado em JSON — compatível com CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("pipeline")


def run() -> None:
    load_dotenv()

    logger.info("pipeline_start")
    start = datetime.now(timezone.utc)

    try:
        config = Config.from_env()

        bronze_key = extract(config)
        silver_key = transform(bronze_key, config)
        loaded     = load(silver_key, config)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(
            "pipeline_success records_loaded=%d elapsed_total_s=%.2f",
            loaded, elapsed,
        )

    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.error("pipeline_failed error=%s elapsed_s=%.2f", exc, elapsed)
        sys.exit(1)


if __name__ == "__main__":
    run()
