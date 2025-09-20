import secrets
from typing import List, Optional
from pathlib import Path
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env",
                                      env_file_encoding="utf-8",
                                      env_ignore_empty=True,
                                      case_sensitive=True,
                                      extra="ignore")
    # App
    VERSION: str = "0.1.0"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 5233
    LOG_LEVEL: str = "info"
    APP_RELOAD: bool = True

    # Security
    # openssl rand -hex 32
    ACCESS_TOKEN_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 12
    REFRESH_TOKEN_EXPIRE_HOURS: int = 120
    ACCESS_TOKEN_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32))
    REFRESH_TOKEN_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32))
    SESSION_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32))

    # Files
    UPLOAD_DIR: str = "static/images"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://127.0.0.1:5233",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Frontend
    FRONTEND_CALLBACK_URL: Optional[str] = None

    # Environment - determines database type
    ENVIRONMENT: str = "development"  # development or production

    # SQLite (development)
    SQLITE_FILE: str = "database.db"

    # MySQL (production)
    MYSQL_HOST: Optional[str] = None
    MYSQL_PORT: int = 3306
    MYSQL_USER: Optional[str] = None
    MYSQL_PASSWORD: Optional[str] = None
    MYSQL_DATABASE: Optional[str] = None

    @computed_field
    @property
    def database_url(self) -> str:
        if self.ENVIRONMENT == "production":
            if not all([
                    self.MYSQL_HOST,
                    self.MYSQL_USER,
                    self.MYSQL_PASSWORD,
                    self.MYSQL_DATABASE,
            ]):
                raise ValueError("MySQL settings required for production")
            return (
                f"mysql+mysqlconnector://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
                f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}")
        else:
            # Development/testing uses SQLite
            return f"sqlite:///{BASE_DIR / self.SQLITE_FILE}"


settings = Settings()
