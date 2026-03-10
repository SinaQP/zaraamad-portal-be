from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Zaraamad Portal API"
    app_version: str = "1.0.0"
    app_env: str = "development"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/zaraamad_portal"
    )
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    otp_expire_seconds: int = 120
    otp_request_limit_count: int = 3
    otp_request_limit_window_seconds: int = 600
    otp_dev_mode: bool = True
    seed_admin_full_name: str = "System Admin"
    seed_admin_mobile: str = "09120000000"
    cors_allowed_origins: list[str] = []
    cors_allowed_origin_regex: str | None = (
        r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    )
    cors_allow_credentials: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: Any) -> Any:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []
            if raw_value.startswith("["):
                return value
            return [
                origin.strip().rstrip("/")
                for origin in raw_value.split(",")
                if origin.strip()
            ]
        if isinstance(value, (list, tuple, set)):
            return [
                origin.strip().rstrip("/")
                for origin in value
                if isinstance(origin, str) and origin.strip()
            ]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
