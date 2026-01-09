from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Main configuration class. Loads values from .env files and environment variables."""

    # 1. App & API Configuration
    APP_NAME: str = "Central Data API"
    APP_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # 2. Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 3. Database Configuration
    DATABASE_URL: str = "sqlite:///db.sqlite"
    # For PostgreSQL e.g.: "postgresql://user:password@localhost/vessimdb"

    # Pydantic Configuration
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = "utf-8"
        extra = "allow"  # Optional: Allow additional fields


settings = Settings()
