"""Pruebas de aceptación BDD para Spec 004: Persistencia PostgreSQL, Salud y Runtime en Contenedores."""

import json
from pathlib import Path
from typing import Optional

import psycopg
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _FailingHealthRepository:
    """Doble de repositorio que simula fallo de conectividad (check_health -> False)."""

    def save_incident(self, incident: Incident) -> None:
        raise NotImplementedError

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return None

    def find_open_duplicates(
        self,
        duplicate_group_key: str,
        exclude_incident_id: Optional[str] = None,
    ) -> list[Incident]:
        return []

    def list_active_incidents(
        self, component_filter: Optional[str] = None
    ) -> list[Incident]:
        return []

    def check_health(self) -> bool:
        return False


class _SpySQLiteRepository(SQLiteIncidentRepository):
    """Subclase espía para confirmar invocación real de check_health()."""

    def __init__(self) -> None:
        super().__init__(db_path=":memory:")
        self.health_checks_called = 0

    def check_health(self) -> bool:
        self.health_checks_called += 1
        return super().check_health()


# --- Escenario 1: GET /health operativo (200 OK) y comando CLI health ---


def test_bdd_scenario_1_http_health_ok_executes_real_select_1() -> None:
    """Given base operativa, When GET /health, Then 200 OK con status=ok y database=connected."""
    repo = _SpySQLiteRepository()
    client = TestClient(create_app(service=IncidentService(repository=repo)))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    assert repo.health_checks_called == 1


def test_bdd_scenario_1_cli_health_ok_returns_exit_0_and_json(
    monkeypatch: pytest.MonkeyPatch, cli_runner: CliRunner
) -> None:
    """Given DATABASE_URL SQLite operativa, When CLI health, Then exit 0 y JSON equivalente."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    result = cli_runner.invoke(cli_app, ["health"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "ok", "database": "connected"}


# --- Escenario 2: GET /health ante fallo de conectividad (503 Service Unavailable) ---


def test_bdd_scenario_2_http_health_unavailable_returns_503() -> None:
    """Given fallo de conectividad (check_health=False), When GET /health, Then 503 y JSON error."""
    failing_repo = _FailingHealthRepository()
    assert isinstance(failing_repo, IncidentRepositoryPort)
    client = TestClient(create_app(service=IncidentService(repository=failing_repo)))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_bdd_scenario_2_cli_health_unavailable_returns_exit_1_and_json(
    monkeypatch: pytest.MonkeyPatch, cli_runner: CliRunner
) -> None:
    """Given fallo de conectividad en repositorio, When CLI health, Then exit 1 y JSON error en stdout."""
    monkeypatch.setattr(
        "src.adapters.inbound.cli.create_repository",
        lambda: _FailingHealthRepository(),
    )

    result = cli_runner.invoke(cli_app, ["health"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"status": "error", "database": "unavailable"}


def test_bdd_scenario_2_postgres_driver_error_returns_false_without_leaking_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When psycopg.connect falla con OperationalError, check_health retorna False y HTTP retorna 503 sin credenciales."""

    def _raise_operational_error(*args: object, **kwargs: object) -> object:
        raise psycopg.OperationalError(
            "connection failed for postgresql://secret_user:super_secret_pw@db:5432/incidentops"
        )

    monkeypatch.setattr(psycopg, "connect", _raise_operational_error)
    pg_repo = PostgresIncidentRepository(
        dsn="postgresql://secret_user:super_secret_pw@db:5432/incidentops",
        init_schema=False,
    )
    client = TestClient(create_app(service=IncidentService(repository=pg_repo)))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
    assert "super_secret_pw" not in response.text
    assert "secret_user" not in response.text


def test_incident_service_check_health_without_repository_raises_runtime_error() -> None:
    """IncidentService sin repositorio lanza RuntimeError al invocar check_health()."""
    service = IncidentService()
    with pytest.raises(RuntimeError):
        service.check_health()


# --- Escenario 3: Selección transparente SQLite / PostgreSQL vía DATABASE_URL ---


def test_bdd_scenario_3_factory_defaults_to_sqlite_memory_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Given DATABASE_URL ausente, When create_repository(), Then SQLiteIncidentRepository(':memory:')."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    repo = create_repository()

    assert isinstance(repo, SQLiteIncidentRepository)
    assert isinstance(repo, IncidentRepositoryPort)
    assert repo.db_path == ":memory:"
    assert repo.check_health() is True


def test_bdd_scenario_3_factory_selects_sqlite_file(tmp_path: Path) -> None:
    """Given DATABASE_URL sqlite:///..., When create_repository(), Then SQLiteIncidentRepository en archivo."""
    db_file = tmp_path / "incidents.db"

    repo = create_repository(f"sqlite:///{db_file}")

    assert isinstance(repo, SQLiteIncidentRepository)
    assert repo.db_path == str(db_file)
    assert repo.check_health() is True


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://incidentops:incidentops@db:5432/incidentops",
        "postgres://incidentops:incidentops@db:5432/incidentops",
    ],
)
def test_bdd_scenario_3_factory_selects_postgres_for_pg_schemes(
    monkeypatch: pytest.MonkeyPatch, dsn: str
) -> None:
    """Given DATABASE_URL postgresql:// o postgres://, When create_repository(), Then PostgresIncidentRepository."""
    monkeypatch.setattr(PostgresIncidentRepository, "_try_init_schema", lambda self: None)

    repo = create_repository(dsn)

    assert isinstance(repo, PostgresIncidentRepository)
    assert isinstance(repo, IncidentRepositoryPort)
    assert repo.dsn == dsn


@pytest.mark.parametrize("invalid_url", ["", "   ", "mysql://user:pass@localhost/db"])
def test_bdd_scenario_3_factory_rejects_empty_or_unsupported_schemes(
    invalid_url: str,
) -> None:
    """Given esquema inválido o vacío, When create_repository(), Then ValueError."""
    with pytest.raises(ValueError):
        create_repository(invalid_url)


# --- Escenario 4: Orquestación reproducible en 2 contenedores (api + db) ---


def test_bdd_scenario_4_container_artifacts_meet_contract() -> None:
    """Verifica Dockerfile (python:3.12-slim + uv), .dockerignore y docker-compose.yml (api + db)."""
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    # Dockerfile: python:3.12-slim + uv + uvicorn en 8000
    assert "FROM python:3.12-slim" in dockerfile
    assert "uv" in dockerfile
    assert "uv.lock" in dockerfile
    assert "uvicorn" in dockerfile
    assert "8000" in dockerfile

    # .dockerignore limpio
    for excluded in (".venv/", ".git/", "**/__pycache__/", "*.db"):
        assert excluded in dockerignore

    # docker-compose.yml: db (postgres:16-alpine, volumen, pg_isready) + api (DATABASE_URL, service_healthy, /health)
    assert "postgres:16-alpine" in compose
    assert "/var/lib/postgresql/data" in compose
    assert "pg_isready" in compose
    assert "DATABASE_URL" in compose
    assert "@db:5432/" in compose
    assert "depends_on:" in compose
    assert "service_healthy" in compose
    assert "http://localhost:8000/health" in compose
    assert "urllib.request" in compose
