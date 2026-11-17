from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    app_name: str = 'Lighting Panel API'
    environment: str = 'development'
    api_prefix: str = '/api/v1'
    secret_key: str
    database_url: str = 'sqlite:///./lighting_panel.db'
    access_token_minutes: int = 20
    cors_origins: str = 'http://localhost:5173'

    @field_validator('secret_key')
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value.encode()) < 32 or value == 'REPLACE_WITH_AT_LEAST_32_RANDOM_BYTES':
            raise ValueError('SECRET_KEY must be a unique random value of at least 32 bytes')
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
