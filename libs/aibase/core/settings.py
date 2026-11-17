from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseModel):
    """Selects an adapter by name; `options` is passed to its constructor."""

    provider: str
    model: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class PHISettings(BaseModel):
    enabled: bool = True
    redactor: str = "regex"
    fail_closed: bool = True


class AuthSettings(BaseModel):
    enabled: bool = False
    issuer: str | None = None
    audience: str | None = None
    public_key: str | None = None
    algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    tenant_claim: str = "tenant_id"
    scope_claim: str = "scope"


class OtelSettings(BaseModel):
    endpoint: str | None = None


class AuditSettings(BaseModel):
    path: str = "./data/audit/audit.jsonl"


class LimitSettings(BaseModel):
    max_body_bytes: int = 25 * 1024 * 1024
    rate_limit_per_minute: int = 600
    request_timeout_s: float = 60.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIBASE_", env_nested_delimiter="__", env_file=".env", extra="ignore"
    )

    env: Literal["local", "test", "staging", "production"] = "local"
    service_name: str = "aibase"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)

    llm: ProviderSettings = ProviderSettings(provider="fake")
    embeddings: ProviderSettings = ProviderSettings(provider="fake")
    vectorstore: ProviderSettings = ProviderSettings(provider="memory")
    stt: ProviderSettings = ProviderSettings(provider="fake")
    diarization: ProviderSettings = ProviderSettings(provider="fake")
    storage: ProviderSettings = ProviderSettings(provider="local")
    queue: ProviderSettings = ProviderSettings(provider="memory")
    cache: ProviderSettings = ProviderSettings(provider="memory")

    phi: PHISettings = PHISettings()
    auth: AuthSettings = AuthSettings()
    otel: OtelSettings = OtelSettings()
    audit: AuditSettings = AuditSettings()
    limits: LimitSettings = LimitSettings()

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        # Fail at startup, not at the first request, when a safety control is off.
        if self.env in ("staging", "production"):
            if not self.auth.enabled:
                raise ValueError("auth.enabled must be true in staging/production")
            if not (self.phi.enabled and self.phi.fail_closed):
                raise ValueError("phi must be enabled and fail_closed in staging/production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
