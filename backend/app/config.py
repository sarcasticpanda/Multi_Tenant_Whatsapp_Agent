from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongo_uri: str
    mongo_db_name: str = "whatsapp_agent"

    # Meta WhatsApp
    meta_phone_number_id: str
    meta_access_token: str
    meta_verify_token: str
    meta_app_secret: str

    # LLM
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"  # 200 req/day free vs 2.5-flash's 20/day
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # App
    app_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
