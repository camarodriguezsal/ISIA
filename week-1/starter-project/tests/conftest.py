"""Fixtures compartidos para las pruebas de aceptación BDD de IncidentOps."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.adapters.inbound.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    """Cliente HTTP de pruebas contra una instancia limpia de FastAPI."""
    return TestClient(create_app())


@pytest.fixture
def cli_runner() -> CliRunner:
    """Ejecutor de pruebas para la aplicación CLI de Typer."""
    return CliRunner()
