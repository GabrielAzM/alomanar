import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _normalize_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql://", 1)
    return raw_url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.environ.get("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'alomana.db').as_posix()}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    QUICK_EXIT_URL = os.environ.get("QUICK_EXIT_URL", "https://www.google.com/")
    ADMIN_DEFAULT_USERNAME = os.environ.get("ADMIN_DEFAULT_USERNAME", "admin")
    ADMIN_DEFAULT_PASSWORD = os.environ.get("ADMIN_DEFAULT_PASSWORD", "admin123")
    USER_DEFAULT_USERNAME = os.environ.get("USER_DEFAULT_USERNAME", "usuario_demo")
    USER_DEFAULT_EMAIL = os.environ.get("USER_DEFAULT_EMAIL", "usuario@makemana.local")
    USER_DEFAULT_PASSWORD = os.environ.get("USER_DEFAULT_PASSWORD", "usuario123")

