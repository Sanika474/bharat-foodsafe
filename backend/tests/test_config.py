from app.core.config import Settings, settings


def test_settings_default_values():
    assert settings.APP_NAME == "BharatFoodSafe"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.DEBUG is True
    assert settings.DATABASE_POOL_SIZE == 20
    assert settings.DATABASE_MAX_OVERFLOW == 10
    assert settings.DATABASE_POOL_TIMEOUT == 30
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_ACCESS_TTL_MINUTES == 15
    assert settings.JWT_REFRESH_TTL_DAYS == 7
    assert settings.BCRYPT_ROUNDS == 12
    assert settings.STORAGE_PROVIDER in ["local", "s3"]
    assert settings.MAX_UPLOAD_MB == 10
    assert settings.RATE_LIMIT_LOGIN_PER_MINUTE == 5
    assert settings.RATE_LIMIT_UPLOAD_PER_MINUTE == 20
    assert settings.RATE_LIMIT_API_PER_MINUTE == 100
    assert settings.TASK_GENERATION_LOOKAHEAD_DAYS == 1
    assert settings.ANOMALY_MIN_HISTORY == 30
    assert settings.ANOMALY_REVIEW_THRESHOLD == 0.70
    assert settings.AUDIT_RETENTION_DAYS == 2555
    assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR"]
    assert settings.LOG_FORMAT == "json"


def test_settings_custom_env_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("MAX_UPLOAD_MB", "25")
    custom_settings = Settings()
    assert custom_settings.APP_ENV == "staging"
    assert custom_settings.DEBUG is False
    assert custom_settings.MAX_UPLOAD_MB == 25
