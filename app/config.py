import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = (
        "postgresql+asyncpg://wallet_user:wallet_pass@localhost:5432/wallet_db"
    )
    DATABASE_URL_SYNC: str = (
        "postgresql://wallet_user:wallet_pass@localhost:5432/wallet_db"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    APP_ENV: str = "development"

    MAX_TRANSACTION_HISTORY: int = 100
    DEFAULT_TRANSACTION_HISTORY: int = 10


settings = Settings()
