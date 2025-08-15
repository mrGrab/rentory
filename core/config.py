from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env',
                                      env_file_encoding='utf-8',
                                      env_ignore_empty=True,
                                      case_sensitive=True,
                                      extra="ignore")
    VERSION: str = "0.1.0"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 5233
    LOG_LEVEL: str = "info"
    APP_API_VERSION: str = "v1"
    # openssl rand -hex 32
    ACCESS_TOKEN_SECRET_KEY: str | None = None
    ACCESS_TOKEN_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    SESSION_SECRET_KEY: str | None = None
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    UPLOAD_DIR: str = "static/images"
    APP_RELOAD: bool = True


settings = Settings()
