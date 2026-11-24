"""Pruebas de aceptación BDD para Spec 001 — Triaje Multi-Interfaz (HTTP + CLI)."""

import json

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.cli import app as cli_app


def test_scenario_1_http_502_payments_outage_p0(client: TestClient) -> None:
    """Escenario 1: Caída crítica HTTP 502 en pasarela de pagos vía HTTP."""
    response = client.post(
        "/api/v1/incidents/triage",
        json={
            "incident_id": "INC-1001",
            "raw_text": "HTTP 502 Bad Gateway en pasarela de pagos",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == "INC-1001"
    assert body["severity"] == "P0"
    assert body["component"] == "payments-gateway"
    assert body["recommended_team"] == "Backend-Core"
    assert body["duplicate_group_key"] == "payments-gateway:http-502-outage"
    assert isinstance(body["rationale"], str) and body["rationale"]
    assert body["consistency_ratio"] == 1.0


def test_scenario_2_http_individual_account_lockout_with_hoy_no_p0(client: TestClient) -> None:
    """Escenario 2: Cuenta individual bloqueada mencionando 'hoy' (sin falso positivo P0)."""
    response = client.post(
        "/api/v1/incidents/triage",
        json={
            "incident_id": "INC-1002",
            "raw_text": "Mi cuenta está bloqueada y no puedo ingresar hoy",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == "INC-1002"
    assert body["severity"] == "P2"
    assert body["severity"] != "P0"
    assert body["recommended_team"] == "Security-IAM"


@pytest.mark.parametrize(
    "payload",
    [
        {"incident_id": "INC-1003", "raw_text": "   "},
        {"incident_id": "", "raw_text": "Error en pasarela de pagos"},
        {"incident_id": "   ", "raw_text": "   "},
    ],
)
def test_scenario_3_http_rejects_empty_or_whitespace_inputs(
    client: TestClient, payload: dict[str, str]
) -> None:
    """Escenario 3: Rechazo de entradas vacías o con solo espacios en blanco vía HTTP."""
    response = client.post("/api/v1/incidents/triage", json=payload)

    assert response.status_code == 422


def test_scenario_4_cli_parity_with_json_stdout(
    client: TestClient, cli_runner: CliRunner
) -> None:
    """Escenario 4: Paridad funcional en CLI con salida JSON."""
    raw_text = "HTTP 502 Bad Gateway en pasarela de pagos"
    http_body = client.post(
        "/api/v1/incidents/triage",
        json={"incident_id": "INC-1001", "raw_text": raw_text},
    ).json()

    cli_result = cli_runner.invoke(
        cli_app,
        ["triage", "--incident-id", "INC-1001", "--raw-text", raw_text],
    )

    assert cli_result.exit_code == 0
    cli_body = json.loads(cli_result.stdout)
    assert cli_body == http_body
    assert cli_body["severity"] == "P0"
    assert cli_body["recommended_team"] == "Backend-Core"


@pytest.mark.parametrize(
    "args",
    [
        ["triage", "--incident-id", "", "--raw-text", "Fallo en pagos"],
        ["triage", "--incident-id", "INC-1005", "--raw-text", "   "],
    ],
)
def test_scenario_5_cli_rejects_empty_or_whitespace_inputs(
    cli_runner: CliRunner, args: list[str]
) -> None:
    """Escenario 5: Rechazo de entradas vacías en CLI."""
    cli_result = cli_runner.invoke(cli_app, args)

    assert cli_result.exit_code == 1
    assert cli_result.output.strip() != ""
