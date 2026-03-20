from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration."""
    environment: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    database_url: str = "postgresql+asyncpg://mymind:mymind_secret@localhost:5432/mymind"
    redis_url: str = "redis://localhost:6379/0"
    
    gemini_api_key: str = ""
    gemini_model_pro: str = "gemini-3.1-pro-preview"
    gemini_model_flash: str = "gemini-3-flash-preview"
    fred_api_key: str = ""
    chroma_path: str = "./chroma_db"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
