"""
Application settings module
환경 변수 및 설정을 중앙에서 관리합니다.
"""
import os
from pathlib import Path
from typing import Optional
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and config files"""

    # Application
    APP_NAME: str = "Docent AI Core API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Database
    DATABASE_PATH: str = "./data/docent.db"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10

    # Image Upload
    IMAGE_UPLOAD_PATH: str = "./data/uploads"

    # Google Cloud Storage (for images)
    GCS_BUCKET_NAME: Optional[str] = None
    GCS_PROJECT_ID: Optional[str] = None
    GCS_CREDENTIALS_PATH: Optional[str] = None

    # Gemini API
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL_NAME: str = "gemini-3-flash-preview"

    # Google Custom Search API (for video reference collection)
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_ENGINE_ID: Optional[str] = None
    GOOGLE_SEARCH_API_URL: str = "https://www.googleapis.com/customsearch/v1"
    GOOGLE_SEARCH_NUM_RESULTS: int = 1  # 검색 결과 개수 (기본값: 1 = 가장 정확도 높은 것만)

    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_DAYS: int = 7

    # Redis (optional, for future scaling)
    REDIS_URL: Optional[str] = None
    REDIS_ENABLED: bool = False

    # Logging
    LOG_LEVEL: str = "INFO"

    # Environment
    ENV: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance

    Returns:
        Settings: Application settings
    """
    return Settings()


def load_database_config() -> dict:
    """
    Load database configuration from YAML file

    Returns:
        dict: Database configuration
    """
    config_path = Path(__file__).parent / "database.yml"

    if not config_path.exists():
        # Return default config if file doesn't exist
        return {
            "database": {
                "path": "./data/docent.db",
                "echo": False,
                "pool_size": 5,
                "max_overflow": 10,
                "check_same_thread": False,
            }
        }

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_data_directory():
    """Ensure data directory exists for SQLite database"""
    settings = get_settings()
    db_path = Path(settings.DATABASE_PATH)
    db_dir = db_path.parent

    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created data directory: {db_dir}")
