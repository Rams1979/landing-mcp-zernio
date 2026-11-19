"""Configuración leída solo desde variables de entorno (nunca claves en el código)."""
import os
from datetime import datetime, timedelta, timezone

# Costa Rica no tiene horario de verano: UTC-6 fijo todo el año.
TZ_CR = timezone(timedelta(hours=-6))


def hoy():
    return datetime.now(TZ_CR).date()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
    # Railway entrega postgres:// o postgresql://; SQLAlchemy necesita el driver psycopg.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url
