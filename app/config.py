from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os
from pathlib import Path


class Settings(BaseSettings):
    # MongoDB URIs
    REGWATCH_MONGODB_URI: str
    ECOSYSTEM_MONGODB_URI: str
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"  # Default version
    
    # RegComply Webhook Configuration
    REGCOMPLY_WEBHOOK_URL: str = ""
    REGCOMPLY_WEBHOOK_SECRET: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings():
    return Settings()
