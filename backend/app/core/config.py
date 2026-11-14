"""Runtime configuration, loaded from environment variables and an optional `.env` file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "orbitvitals-api"
API_V1_PREFIX = "/api/v1"


class Settings(BaseSettings):
    """Backend settings. Every environment variable is prefixed with `ORBITVITALS_`."""

    model_config = SettingsConfigDict(
        env_prefix="ORBITVITALS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    # Browsers enforce CORS, so the Flutter Web client must be allowed explicitly.
    # The default regex accepts any localhost port because `flutter run -d chrome`
    # picks a random one. Deployed frontend origins go in `cors_allow_origins`.
    cors_allow_origins: list[str] = []
    cors_allow_origin_regex: str | None = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
