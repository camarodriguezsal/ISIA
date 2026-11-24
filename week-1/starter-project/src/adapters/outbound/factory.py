"""Fábrica de repositorios (composition root de persistencia vía DATABASE_URL)."""

import os
from typing import Optional

from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

DEFAULT_DATABASE_URL = "sqlite:///:memory:"
POSTGRES_SCHEMES: tuple[str, ...] = ("postgresql://", "postgres://")


def _parse_sqlite_path(database_url: str) -> str:
    """Extrae la ruta de archivo o ':memory:' a partir de una URL sqlite:///."""
    db_path = database_url[len("sqlite:///") :]
    return db_path if db_path else ":memory:"


def create_repository(database_url: Optional[str] = None) -> IncidentRepositoryPort:
    """Construye el adaptador de persistencia (SQLite o PostgreSQL) según DATABASE_URL."""
    raw_url = (
        database_url
        if database_url is not None
        else os.getenv("DATABASE_URL")
    )
    if raw_url is None:
        resolved_url = DEFAULT_DATABASE_URL
    else:
        resolved_url = raw_url.strip()
        if not resolved_url:
            raise ValueError(
                "DATABASE_URL no puede estar vacía. "
                "Esquemas soportados: 'sqlite:///', 'postgresql://' o 'postgres://'."
            )

    if resolved_url.startswith(POSTGRES_SCHEMES):
        return PostgresIncidentRepository(dsn=resolved_url)

    if resolved_url.startswith("sqlite:///"):
        db_path = _parse_sqlite_path(resolved_url)
        return SQLiteIncidentRepository(db_path=db_path)

    raise ValueError(
        f"Esquema de DATABASE_URL no soportado: '{resolved_url}'. "
        "Esquemas soportados: 'sqlite:///', 'postgresql://' o 'postgres://'."
    )
