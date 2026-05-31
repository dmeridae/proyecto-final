from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    database_url: str = "sqlite+aiosqlite:///./callcenter.db"
    chroma_persist_dir: str = "./chroma_data"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    public_base_url: str = "http://localhost:8000"

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)

    @property
    def public_base_url_is_local(self) -> bool:
        url = self.public_base_url.lower().strip()
        return "localhost" in url or "127.0.0.1" in url

    @property
    def twilio_call_available(self) -> bool:
        """True si Twilio puede recibir llamadas (credenciales + URL pública para webhooks)."""
        return self.twilio_configured and not self.public_base_url_is_local

    @property
    def twilio_ready(self) -> bool:
        """Alias de twilio_call_available (compatibilidad)."""
        return self.twilio_call_available

    @property
    def twilio_voice_webhook_url(self) -> str:
        base = self.public_base_url.rstrip("/")
        return f"{base}/twilio/voice/incoming"


settings = Settings()
