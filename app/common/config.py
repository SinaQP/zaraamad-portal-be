from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.version import VERSION as BUILD_VERSION

DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zaraamad_portal"


class Settings(BaseSettings):
    app_name: str = "Zaraamad Portal API"
    app_version: str = BUILD_VERSION
    app_env: str = "development"
    form_service_debug: bool = False
    database_url: str = DEFAULT_DATABASE_URL
    sqlserver_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SQLSERVER_URL", "CENTRAL_DATABASE_URL"),
    )
    jwt_signing_key: str = Field(
        default="change-me",
        validation_alias=AliasChoices("JWT_SIGNING_KEY", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "zaraamad-django"
    jwt_audience: str | None = None
    jwt_access_token_expire_minutes: int = 60
    otp_expire_seconds: int = 120
    otp_request_limit_count: int = 3
    otp_request_limit_window_seconds: int = 600
    otp_dev_mode: bool = True
    sms_api_url: str = "https://payamsms.com/services/rest/index.php"
    sms_request_timeout_seconds: int = 15
    bridge_request_timeout_seconds: int = 10
    bridge_api_key: str = "change-me-bridge-key"
    customer_connection_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CUSTOMER_CONNECTION_SECRET_KEY",
            "DATABASE_CONNECTION_SECRET_KEY",
        ),
    )
    sms_panel_organization: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMS_PANEL_ORGANIZATION", "API_ORGANIZATION"),
    )
    sms_panel_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMS_PANEL_USERNAME", "API_USERNAME"),
    )
    sms_panel_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMS_PANEL_PASSWORD", "API_PASSWORD"),
    )
    sms_panel_sender: str = "9820002739006"
    seed_admin_full_name: str = "System Admin"
    seed_admin_mobile: str = "09120000000"
    cors_allowed_origins: list[str] = []
    cors_allowed_origin_regex: str | None = (
        r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
    )
    cors_allow_credentials: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

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
