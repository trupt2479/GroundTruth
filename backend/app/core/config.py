import logging
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "GroundTruth"
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "INFO"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "groundtruth"
    POSTGRES_PASSWORD: str = "groundtruth_dev_secret"
    POSTGRES_DB: str = "groundtruth"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # Ingestion Configuration
    MOCK_INGESTION: bool = True
    AERODATABOX_API_KEY: str = "mock-rapidapi-key"
    AERODATABOX_API_HOST: str = "aerodatabox.p.rapidapi.com"
    AERODATABOX_TIMEOUT: float = 5.0
    OPENSKY_TIMEOUT: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()


def setup_logging():
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
