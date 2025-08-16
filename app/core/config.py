from pydantic_settings import BaseSettings
from pydantic import HttpUrl

class Settings(BaseSettings):
    INSIGHTS_USER_AGENT: str = "ShopifyInsightsBot/1.0 (+https://example.com)"
    INSIGHTS_TIMEOUT: float = 20.0
    INSIGHTS_MAX_CONCURRENCY: int = 8
    INSIGHTS_MAX_PRODUCTS: int = 2000  # safety cap
    class Config:
        env_file = ".env"

settings = Settings()
