from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:password@localhost:5432/shopify_products"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    anthropic_api_key: str = ""

    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_store_domain: str = ""
    # Legacy: static access token (pre-2026 custom apps). Leave blank to use client credentials flow.
    shopify_access_token: str = ""

    storage_backend: str = "local"
    storage_path: str = "./uploads"

    shopify_webhook_secret: str = ""

    # Public-facing URLs (used for OAuth redirect_uri construction and frontend redirects)
    app_url: str = "http://localhost:8000"       # Backend URL reachable by Shopify
    frontend_url: str = "http://localhost:3000"  # Frontend URL for post-OAuth redirect

    secret_key: str = "change-this-in-production"
    cors_origins: List[str] = ["http://localhost:3000"]
    environment: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
