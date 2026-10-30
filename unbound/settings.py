from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNBOUND_", env_file=".env", extra="ignore"
    )
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    base_url: str | None = None
    api_key: str | None = None
    db: str = "data/unbound.sqlite"
    checkpoint_db: str = "data/checkpoints.sqlite"
    call_timeout: float = 120
    attempts: int = 3
    worker_concurrency: int = 1
    owner_password: str | None = None
    public_origin: str | None = None

    def prepare(self):
        import os

        os.umask(0o077)
        if self.public_origin and (
            not self.public_origin.startswith("https://")
            or self.public_origin.endswith("/")
        ):
            raise ValueError(
                "UNBOUND_PUBLIC_ORIGIN must be an HTTPS origin without trailing slash"
            )
        if self.attempts < 1 or self.attempts > 5 or self.call_timeout <= 0:
            raise ValueError("Invalid timeout/attempt configuration")
        for p in (self.db, self.checkpoint_db):
            Path(p).parent.mkdir(parents=True, exist_ok=True)
