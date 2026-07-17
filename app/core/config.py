from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Payment API"
    debug: bool = True

    database_url: str

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "payment_db"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    frontend_success_url: str = (
        "http://localhost:3000/payment/success"
    )
    frontend_cancel_url: str = (
        "http://localhost:3000/payment/cancel"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()