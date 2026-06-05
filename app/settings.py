from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./nutricoach.db",
        alias="DATABASE_URL",
    )
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    coach_model: str = Field(
        default="claude-haiku-4-5-20251001",
        alias="COACH_MODEL",
    )
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    jwt_refresh_secret: str = Field(default="", alias="JWT_REFRESH_SECRET")
    coach_rate_limit_per_hour: int = Field(
        default=30, alias="COACH_RATE_LIMIT_PER_HOUR"
    )
    coach_max_tokens: int = Field(default=1024, alias="COACH_MAX_TOKENS")
    coach_timeout_seconds: float = Field(
        default=30.0, alias="COACH_TIMEOUT_SECONDS"
    )
    auth_login_rate_limit_per_15min: int = Field(
        default=10, alias="AUTH_LOGIN_RATE_LIMIT_PER_15MIN"
    )
    auth_register_rate_limit_per_15min: int = Field(
        default=5, alias="AUTH_REGISTER_RATE_LIMIT_PER_15MIN"
    )


def get_settings() -> Settings:
    return Settings()
