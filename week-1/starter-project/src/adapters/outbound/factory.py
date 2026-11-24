"""Fábrica de repositorios (composition root de persistencia vía DATABASE_URL)."""

import os
from typing import Optional

from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def _parse_sqlite_path(database_url: str) -> str:
    """Extrae la ruta de archivo o ':memory:' a partir de una URL sqlite:///."""
    if not database_url.startswith("sqlite:///"):
        raise ValueError(
            f"Esquema de DATABASE_URL no soportado: '{database_url}'. "
            "Se espera el prefijo 'sqlite:///'."
        )
    db_path = database_url[len("sqlite:///") :]
    return db_path if db_path else ":memory:"


def create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort:
    """Construye el adaptador de persistencia a partir de DATABASE_URL."""
    resolved_url = (
        database_url
        if database_url is not None
        else os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    db_path = _parse_sqlite_path(resolved_url)
    return SQLiteIncidentRepository(db_path=db_path)
