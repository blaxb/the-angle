import os
from pydantic_settings import BaseSettings

def resolve_db_url() -> str:
    explicit_path = os.getenv("THEANGLE_DB_PATH") or os.getenv("RENDER_DISK_PATH")
    if explicit_path:
        return f"sqlite:///{explicit_path.rstrip('/')}/theangle.db"
    if os.path.isdir("/var/data"):
        return "sqlite:////var/data/theangle.db"
    return "sqlite:///./theangle.db"

DEFAULT_DB_URL = resolve_db_url()

class Settings(BaseSettings):
    app_secret: str
    db_url: str = DEFAULT_DB_URL
    base_url: str = "http://127.0.0.1:8000"

    openai_api_key: str = ""

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    x_bearer_token: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
