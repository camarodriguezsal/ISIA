"""Pruebas de aceptación BDD para Spec 003: Ciclo de Vida, Duplicados y Auditoría de SLA."""

from datetime import datetime
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app
from src.adapters.inbound.cli import app as cli_app
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort
from src.application.services import IncidentService

INCIDENT_ID_PATTERN = re.compile(r"^INC-[0-9A-F]{8}$")


def _build_client_with_repo() -> tuple[TestClient, SQLiteIncidentRepository]:
    repo = SQLiteIncidentRepository(":memory:")
    service = IncidentService(repository=repo)
    return TestClient(create_app(service=service)), repo


def test_sqlite_repository_has_dup_key_index_and_fulfills_port() -> None:
    """Verifica el índice compuesto idx_incidents_dup_key y el contrato del puerto."""
    repo = SQLiteIncidentRepository(":memory:")
    assert isinstance(repo, IncidentRepositoryPort)

    indexes = {
        row["name"]
        for row in repo.conn.execute("PRAGMA index_list(incidents)").fetchall()
    }
    assert "idx_incidents_dup_key" in indexes


def test_bdd_scenario_1_create_incident_without_duplicates() -> None:
    """Escenario 1: Registro inicial 201 sin duplicados previos con defaults INC-<HEX8> y OPEN."""
    client, repo = _build_client_with_repo()

    response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Latencia elevada en reporte de órdenes",
            "raw_text": (
                "El servicio reporting-api presenta lentitud intermitente al generar "
                "reportes de órdenes para algunos usuarios internos."
            ),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert INCIDENT_ID_PATTERN.match(body["incident_id"])
    assert body["title"] == "Latencia elevada en reporte de órdenes"
    assert body["status"] == "OPEN"
    assert datetime.fromisoformat(body["created_at"]) is not None
    assert body["severity"] in {"P0", "P1", "P2", "P3"}
    assert body["component"]
    assert body["recommended_team"] in {
        "Backend-Core",
        "Platform-SRE",
        "Data-DBA",
        "Security-IAM",
    }
    assert ":" in body["duplicate_group_key"]
    assert body["rationale"]
    assert body["is_duplicate"] is False
    assert body["duplicate_of"] == []

    persisted = repo.get_incident(body["incident_id"])
    assert persisted is not None
    assert persisted.duplicate_group_key == body["duplicate_group_key"]
    assert persisted.recommended_team == body["recommended_team"]


def test_bdd_scenario_2_detect_open_duplicates_ignoring_resolved_and_self() -> None:
    """Escenario 2: Detección de duplicado abierto 201 ignorando RESOLVED y al propio ID."""
    client, _ = _build_client_with_repo()
    shared_raw_text = (
        "Caída total en payments-gateway: 100% de los pagos fallan con error 503."
    )

    # Incidente previo abierto
    res_open = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-A0000001",
            "title": "Caída pagos 1",
            "raw_text": shared_raw_text,
            "status": "OPEN",
        },
    )
    assert res_open.status_code == 201
    assert res_open.json()["is_duplicate"] is False

    # Incidente previo en ESCALATION_REQUIRED (también cuenta como abierto)
    res_esc = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-E0000001",
            "title": "Caída pagos escalada",
            "raw_text": shared_raw_text,
            "status": "ESCALATION_REQUIRED",
        },
    )
    assert res_esc.status_code == 201

    # Incidente previo RESOLVED (debe excluirse)
    res_resolved = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-R0000001",
            "title": "Caída pagos resuelta",
            "raw_text": shared_raw_text,
            "status": "RESOLVED",
        },
    )
    assert res_resolved.status_code == 201

    # Nuevo incidente equivalente
    res_new = client.post(
        "/api/v1/incidents",
        json={
            "title": "Nuevo reporte caída pagos",
            "raw_text": shared_raw_text,
        },
    )
    assert res_new.status_code == 201
    body = res_new.json()
    assert body["is_duplicate"] is True
    assert set(body["duplicate_of"]) == {"INC-A0000001", "INC-E0000001"}
    assert "INC-R0000001" not in body["duplicate_of"]
    assert body["incident_id"] not in body["duplicate_of"]


def test_bdd_scenario_3_deterministic_sla_audit_business_hours_p2() -> None:
    """Escenario 3: Auditoría determinista de SLA en horario hábil (P2 vie 17:00 -> lun 09:00 = 120m)."""
    client, _ = _build_client_with_repo()

    create_res = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-2001",
            "title": "Latencia elevada en reporte de órdenes",
            "raw_text": (
                "La exportación de reportes en reporting-api está lenta y tarda "
                "varios segundos en completarse."
            ),
            "created_at": "2026-11-06T17:00:00",
            "status": "OPEN",
        },
    )
    assert create_res.status_code == 201
    assert create_res.json()["severity"] == "P2"

    sla_res = client.get(
        "/api/v1/incidents/INC-2001/sla",
        params={"reference_time": "2026-11-09T09:00:00"},
    )
    assert sla_res.status_code == 200
    assert sla_res.json() == {
        "incident_id": "INC-2001",
        "severity": "P2",
        "elapsed_minutes": 120,
        "allowed_minutes": 480,
        "remaining_minutes": 360,
        "is_breached": False,
        "requires_escalation": False,
    }

    # También valida normalización consistente de timestamp aware (Z) vs created_at naive
    sla_aware_res = client.get(
        "/api/v1/incidents/INC-2001/sla",
        params={"reference_time": "2026-11-09T09:00:00Z"},
    )
    assert sla_aware_res.status_code == 200
    assert sla_aware_res.json()["elapsed_minutes"] == 120


def test_bdd_scenario_4_sla_errors_404_and_422() -> None:
    """Escenario 4: 404 para incidente inexistente y 422 para reference_time < created_at."""
    client, _ = _build_client_with_repo()

    create_res = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-1001",
            "title": "Latencia en reporting-api",
            "raw_text": "Latencia degradada en reporting-api.",
            "created_at": "2026-11-06T17:00:00",
        },
    )
    assert create_res.status_code == 201

    not_found_res = client.get("/api/v1/incidents/INC-99999999/sla")
    assert not_found_res.status_code == 404

    invalid_time_res = client.get(
        "/api/v1/incidents/INC-1001/sla",
        params={"reference_time": "2026-11-06T16:00:00"},
    )
    assert invalid_time_res.status_code == 422


def test_bdd_scenario_5_cli_create_and_sla_parity(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch
) -> None:
    """Escenario 5: Paridad operativa mediante CLI create y sla con salida JSON y códigos 0/1."""
    db_file = tmp_path / "incidentops_cli.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    create_res = cli_runner.invoke(
        cli_app,
        [
            "create",
            "--incident-id",
            "INC-CLI00001",
            "--title",
            "Latencia en reporting-api",
            "--raw-text",
            "La exportación de reportes en reporting-api está lenta y tarda varios segundos.",
            "--created-at",
            "2026-11-06T17:00:00",
            "--status",
            "OPEN",
        ],
    )
    assert create_res.exit_code == 0, create_res.output
    created_payload = json.loads(create_res.stdout)
    assert created_payload["incident_id"] == "INC-CLI00001"
    assert created_payload["severity"] == "P2"
    assert created_payload["is_duplicate"] is False
    assert created_payload["duplicate_of"] == []

    sla_res = cli_runner.invoke(
        cli_app,
        [
            "sla",
            "--incident-id",
            "INC-CLI00001",
            "--reference-time",
            "2026-11-09T09:00:00",
        ],
    )
    assert sla_res.exit_code == 0, sla_res.output
    sla_payload = json.loads(sla_res.stdout)
    assert sla_payload == {
        "incident_id": "INC-CLI00001",
        "severity": "P2",
        "elapsed_minutes": 120,
        "allowed_minutes": 480,
        "remaining_minutes": 360,
        "is_breached": False,
        "requires_escalation": False,
    }

    # Errores CLI -> exit code 1
    not_found_cli = cli_runner.invoke(
        cli_app, ["sla", "--incident-id", "INC-NOEXISTE"]
    )
    assert not_found_cli.exit_code == 1

    bad_time_cli = cli_runner.invoke(
        cli_app,
        [
            "sla",
            "--incident-id",
            "INC-CLI00001",
            "--reference-time",
            "2026-11-06T16:00:00",
        ],
    )
    assert bad_time_cli.exit_code == 1


def test_edge_cases_validation_and_duplicate_id_conflict() -> None:
    """Casos borde: campos vacíos (422), status inválido (422) e incident_id duplicado (409)."""
    client, _ = _build_client_with_repo()

    blank_title = client.post(
        "/api/v1/incidents", json={"title": "   ", "raw_text": "Error en pagos"}
    )
    assert blank_title.status_code == 422

    invalid_status = client.post(
        "/api/v1/incidents",
        json={"title": "Error", "raw_text": "Error en pagos", "status": "CLOSED"},
    )
    assert invalid_status.status_code == 422

    first = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-DUP00001",
            "title": "Primer incidente",
            "raw_text": "Error en pagos",
        },
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/incidents",
        json={
            "incident_id": "INC-DUP00001",
            "title": "Segundo incidente mismo ID",
            "raw_text": "Error en pagos",
        },
    )
    assert conflict.status_code == 409
