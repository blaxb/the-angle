from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_secret: str
    db_url: str = "sqlite:///./theangle.db"
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

