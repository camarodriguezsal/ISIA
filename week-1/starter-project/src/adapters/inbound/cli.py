"""Adaptador primario CLI (Typer) para IncidentOps."""

from dataclasses import asdict
from datetime import datetime
import json
from typing import Optional

import typer

from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService, ValidationError

app = typer.Typer(help="CLI de soporte y triaje determinista para IncidentOps.")


@app.callback()
def main_callback() -> None:
    """Comandos de operación de IncidentOps."""


@app.command("triage")
def triage_command(
    incident_id: str = typer.Option(
        ..., "--incident-id", help="Identificador único del incidente."
    ),
    raw_text: str = typer.Option(
        ..., "--raw-text", help="Descripción textual del reporte del incidente."
    ),
) -> None:
    """Clasifica y enruta un incidente imprimiendo el TriageResult en JSON por stdout."""
    service = IncidentService()
    try:
        result = service.triage_incident(incident_id=incident_id, raw_text=raw_text)
    except ValidationError as exc:
        typer.echo(f"Error de validación: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(asdict(result), ensure_ascii=False))


@app.command("summary")
def summary_command(
    component: Optional[str] = typer.Option(
        None, "--component", help="Filtra incidentes activos por componente exacto."
    ),
    reference_time: Optional[str] = typer.Option(
        None,
        "--reference-time",
        help="Fecha/hora ISO-8601 de referencia para evaluación determinista de SLA.",
    ),
) -> None:
    """Consulta el resumen de incidentes activos en JSON por stdout."""
    parsed_ref_time: Optional[datetime] = None
    if reference_time is not None:
        try:
            parsed_ref_time = datetime.fromisoformat(reference_time)
        except ValueError as exc:
            typer.echo(
                f"Error de validación: formato inválido para '--reference-time': '{reference_time}'.",
                err=True,
            )
            raise typer.Exit(code=1) from exc

    service = IncidentService(repository=create_repository())
    try:
        summary = service.get_active_incidents_summary(
            component_filter=component,
            reference_time=parsed_ref_time,
        )
    except ValidationError as exc:
        typer.echo(f"Error de validación: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(asdict(summary), ensure_ascii=False))


if __name__ == "__main__":
    app()
