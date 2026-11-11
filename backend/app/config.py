"""App settings, read from backend/.env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"

    # used when the receipt's currency is one PayPal can't settle
    default_currency: str = "USD"
    database_path: Path = BACKEND_DIR / "evensteven.db"
    # public address of the app, used to build the pay links shared with friends
    public_url: str = "http://localhost:8090"
    # set by Render on every web service; used as the public address when PUBLIC_URL is not given
    render_external_url: str = ""

    # limits on the two endpoints that call Claude, so a public demo can't run up the API bill
    ai_calls_per_ip_per_hour: int = 15
    ai_calls_per_day: int = 300


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.render_external_url and settings.public_url == "http://localhost:8090":
        settings.public_url = settings.render_external_url.rstrip("/")
    return settings
