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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()
