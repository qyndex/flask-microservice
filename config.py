"""Configuration classes for the Flask microservice."""
import os


class BaseConfig:
    """Base microservice configuration."""

    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    CELERY_BROKER_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Rate limiting
    RATELIMIT_STORAGE_URI: str = os.environ.get("REDIS_URL", "memory://")
    RATELIMIT_STRATEGY: str = "fixed-window"

    # CORS
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*")


class DevelopmentConfig(BaseConfig):
    """Development configuration."""

    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "sqlite:///dev.db")


class TestingConfig(BaseConfig):
    """Testing configuration."""

    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    CELERY_BROKER_URL: str = "memory://"
    CELERY_RESULT_BACKEND: str = "cache+memory://"
    CELERY_TASK_ALWAYS_EAGER: bool = True
    RATELIMIT_ENABLED: bool = False


class ProductionConfig(BaseConfig):
    """Production configuration."""

    DEBUG: bool = False
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    RATELIMIT_STORAGE_URI: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
