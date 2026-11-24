"""Pruebas de aceptación BDD y contrato de puerto para el Hito 002 (Resumen de Incidentes Activos)."""

from datetime import datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.factory import create_repository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService
from src.domain.models import Incident


def _seed_sample_incidents(repo: SQLiteIncidentRepository) -> None:
    """Inserta un conjunto determinista de incidentes OPEN, IN_PROGRESS y RESOLVED."""
    incidents = [
        # P0 (60m 24/7): creado 90m antes -> breached=True, requires_escalation=True
        Incident(
            incident_id="INC-2001",
            title="Caída total en pasarela de pagos",
            component="payments-gateway",
            severity="P0",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 10, 30, 0),
        ),
        # P1 (240m 24/7): creado 190m antes -> 79% (>= 75%), breached=False, requires_escalation=True
        Incident(
            incident_id="INC-2002",
            title="Latencia elevada en checkout",
            component="payments-gateway",
            severity="P1",
            status="IN_PROGRESS",
            created_at=datetime(2026, 11, 20, 8, 50, 0),
        ),
        # P2 (480m horario hábil): creado sábado 10:00, ref lunes 10:00 -> 120m hábiles, breached=False
        Incident(
            incident_id="INC-2003",
            title="Error intermitente en tokens OAuth",
            component="auth-service",
            severity="P2",
            status="OPEN",
            created_at=datetime(2026, 11, 20, 11, 0, 0),
        ),
        # RESOLVED: debe excluirse del resumen
        Incident(
            incident_id="INC-2004",
            title="Incidente resuelto en pasarela de pagos",
            component="payments-gateway",
            severity="P0",
            status="RESOLVED",
            created_at=datetime(2026, 11, 20, 9, 0, 0),
            resolved_at=datetime(2026, 11, 20, 9, 20, 0),
        ),
    ]
    for incident in incidents:
        repo.save_incident(incident)


def test_sqlite_repository_fulfills_incident_repository_port() -> None:
    """Verifica el cumplimiento estructural de IncidentRepositoryPort sobre SQLiteIncidentRepository."""
    repo = SQLiteIncidentRepository(db_path=":memory:")
    assert isinstance(repo, IncidentRepositoryPort)
    assert repo.check_health() is True

    incident = Incident(
        incident_id="INC-PORT-1",
        title="Timeout en base de datos",
        component="database-cluster",
        severity="P1",
        status="OPEN",
        created_at=datetime(2026, 11, 20, 10, 0, 0),
        duplicate_group_key="database-cluster:pool-exhaustion",
    )
    repo.save_incident(incident)

    fetched = repo.get_incident("INC-PORT-1")
    assert fetched is not None
    assert fetched.incident_id == "INC-PORT-1"

    duplicates = repo.find_open_duplicates("database-cluster:pool-exhaustion")
    assert len(duplicates) == 1
    assert duplicates[0].incident_id == "INC-PORT-1"


def test_bdd_scenario_1_global_summary_excludes_resolved_and_evaluates_sla() -> None:
    """Escenario 1: Resumen global excluyendo RESOLVED, con cálculo SLA y umbral preventivo 75%."""
    repo = SQLiteIncidentRepository(db_path=":memory:")
    _seed_sample_incidents(repo)
    client = TestClient(create_app(service=IncidentService(repository=repo)))

    response = client.get(
        "/api/v1/incidents/summary",
        params={"reference_time": "2026-11-20T12:00:00"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_active"] == 3
    assert payload["breached_count"] == 1

    by_id = {item["incident_id"]: item for item in payload["incidents"]}
    assert "INC-2004" not in by_id

    # INC-2001: P0 90m -> breached y requires_escalation=True
    assert by_id["INC-2001"]["elapsed_minutes"] == 90
    assert by_id["INC-2001"]["requires_escalation"] is True

    # INC-2002: P1 190m (79% de 240m) -> requires_escalation=True pero NO incrementa breached_count
    assert by_id["INC-2002"]["elapsed_minutes"] == 190
    assert by_id["INC-2002"]["requires_escalation"] is True

    # INC-2003: P2 60m hábiles (viernes 11:00 a 12:00) -> dentro de SLA
    assert by_id["INC-2003"]["elapsed_minutes"] == 60
    assert by_id["INC-2003"]["requires_escalation"] is False


def test_p2_business_hours_weekend_calculation() -> None:
    """Caso borde: incidente P2 creado en fin de semana solo contabiliza minutos hábiles."""
    repo = SQLiteIncidentRepository(db_path=":memory:")
    repo.save_incident(
        Incident(
            incident_id="INC-WKND",
            title="Reporte diferido de facturación",
            component="reporting-api",
            severity="P2",
            status="OPEN",
            created_at=datetime(2026, 11, 21, 10, 0, 0),  # Sábado
        )
    )
    client = TestClient(create_app(service=IncidentService(repository=repo)))

    response = client.get(
        "/api/v1/incidents/summary",
        params={"reference_time": "2026-11-23T10:00:00"},  # Lunes 10:00 -> 120m hábiles
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_active"] == 1
    assert payload["breached_count"] == 0
    assert payload["incidents"][0]["elapsed_minutes"] == 120


def test_bdd_scenario_2_summary_filtered_by_component() -> None:
    """Escenario 2: Resumen filtrado por componente retorna únicamente incidentes de ese componente."""
    repo = SQLiteIncidentRepository(db_path=":memory:")
    _seed_sample_incidents(repo)
    client = TestClient(create_app(service=IncidentService(repository=repo)))

    response = client.get(
        "/api/v1/incidents/summary",
        params={
            "component": "payments-gateway",
            "reference_time": "2026-11-20T12:00:00",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_active"] == 2
    assert payload["breached_count"] == 1
    assert all(item["component"] == "payments-gateway" for item in payload["incidents"])


def test_bdd_scenario_3_empty_state_returns_valid_zero_summary() -> None:
    """Escenario 3: Sin incidentes activos o sin coincidencias retorna 200 OK con totales en 0."""
    repo = SQLiteIncidentRepository(db_path=":memory:")
    client = TestClient(create_app(service=IncidentService(repository=repo)))

    empty_resp = client.get("/api/v1/incidents/summary")
    assert empty_resp.status_code == 200
    assert empty_resp.json() == {"total_active": 0, "breached_count": 0, "incidents": []}

    _seed_sample_incidents(repo)
    no_match_resp = client.get(
        "/api/v1/incidents/summary",
        params={"component": "non-existent-service"},
    )
    assert no_match_resp.status_code == 200
    assert no_match_resp.json() == {"total_active": 0, "breached_count": 0, "incidents": []}


def test_http_validation_errors_for_blank_component_and_invalid_reference_time() -> None:
    """FR-009: Rechaza component en blanco y reference_time inválido con 422."""
    repo = SQLiteIncidentRepository(db_path=":memory:")
    client = TestClient(create_app(service=IncidentService(repository=repo)))

    blank_resp = client.get("/api/v1/incidents/summary", params={"component": "   "})
    assert blank_resp.status_code == 422

    bad_time_resp = client.get(
        "/api/v1/incidents/summary", params={"reference_time": "not-a-timestamp"}
    )
    assert bad_time_resp.status_code == 422


def test_bdd_scenario_4_cli_summary_parity_with_http(
    tmp_path: Path, monkeypatch, cli_runner: CliRunner
) -> None:
    """Escenario 4: La CLI `summary` produce la misma salida JSON que GET /api/v1/incidents/summary."""
    db_file = tmp_path / "incidents.db"
    database_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    repo = create_repository()
    assert isinstance(repo, SQLiteIncidentRepository)
    _seed_sample_incidents(repo)

    client = TestClient(create_app(service=IncidentService(repository=repo)))
    http_resp = client.get(
        "/api/v1/incidents/summary",
        params={
            "component": "payments-gateway",
            "reference_time": "2026-11-20T12:00:00",
        },
    )
    assert http_resp.status_code == 200

    cli_result = cli_runner.invoke(
        cli_app,
        [
            "summary",
            "--component",
            "payments-gateway",
            "--reference-time",
            "2026-11-20T12:00:00",
        ],
    )
    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout) == http_resp.json()

    # Validaciones de error en CLI (exit code 1)
    bad_comp = cli_runner.invoke(cli_app, ["summary", "--component", "   "])
    assert bad_comp.exit_code == 1

    bad_time = cli_runner.invoke(cli_app, ["summary", "--reference-time", "invalid-date"])
    assert bad_time.exit_code == 1
