import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Config:
    owm_api_key: str
    owm_cities: list[str]
    aws_region: str
    s3_bucket: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str

    @classmethod
    def from_env(cls) -> "Config":
        required = ["OWM_API_KEY", "S3_BUCKET", "DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise EnvironmentError(f"Variáveis de ambiente obrigatórias faltando: {missing}")

        return cls(
            owm_api_key=os.environ["OWM_API_KEY"],
            owm_cities=os.environ.get("OWM_CITIES", "Sao Paulo,Rio de Janeiro,Brasilia").split(","),
            aws_region=os.environ.get("AWS_REGION", "sa-east-1"),
            s3_bucket=os.environ["S3_BUCKET"],
            db_host=os.environ["DB_HOST"],
            db_port=int(os.environ.get("DB_PORT", "5432")),
            db_name=os.environ["DB_NAME"],
            db_user=os.environ["DB_USER"],
            db_password=os.environ["DB_PASSWORD"],
        )
