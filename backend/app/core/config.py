import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Metadata
    APP_ENV: str = "development"
    APP_NAME: str = "BharatFoodSafe"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database Connection
    DATABASE_URL: str = "postgresql+psycopg://foodsafety:foodsafe_pass_2026@localhost:5432/bharat_foodsafe"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    # Security & Authentication
    JWT_SECRET: str = "super_secret_jwt_key_bharat_foodsafe_2026_change_in_prod_min_32_chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    # CORS Policy
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Object Storage Configuration
    STORAGE_PROVIDER: str = "local"
    LOCAL_STORAGE_PATH: str = "./uploads"
    S3_ENDPOINT: str = "https://s3.ap-south-1.amazonaws.com"
    S3_BUCKET: str = "bharat-foodsafe-evidence-dev"
    S3_REGION: str = "ap-south-1"
    S3_ACCESS_KEY: str = "AKIAIOSFODNN7EXAMPLE"
    S3_SECRET_KEY: str = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    MAX_UPLOAD_MB: int = 10

    # Security Rate Limits
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20
    RATE_LIMIT_API_PER_MINUTE: int = 100

    # Anomaly Engine & Operational Parameters
    TASK_GENERATION_LOOKAHEAD_DAYS: int = 1
    ANOMALY_MIN_HISTORY: int = 30
    ANOMALY_REVIEW_THRESHOLD: float = 0.70
    AUDIT_RETENTION_DAYS: int = 2555

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
