"""Adaptador primario CLI (Typer) para IncidentOps."""

from dataclasses import asdict
from datetime import datetime
import json
from typing import Optional

import typer

from src.adapters.outbound.factory import create_repository
from src.application.services import (
    DuplicateIncidentIdError,
    IncidentNotFoundError,
    IncidentService,
    ValidationError,
)

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


@app.command("create")
def create_command(
    title: str = typer.Option(
        ..., "--title", help="Título descriptivo del incidente."
    ),
    raw_text: str = typer.Option(
        ..., "--raw-text", help="Descripción textual del reporte del incidente."
    ),
    incident_id: Optional[str] = typer.Option(
        None,
        "--incident-id",
        help="Identificador opcional del incidente (autogenerado INC-<HEX8> si se omite).",
    ),
    created_at: Optional[str] = typer.Option(
        None,
        "--created-at",
        help="Fecha/hora ISO-8601 de creación del incidente.",
    ),
    status: str = typer.Option(
        "OPEN",
        "--status",
        help="Estado inicial del incidente (OPEN, IN_PROGRESS, ESCALATION_REQUIRED, RESOLVED).",
    ),
) -> None:
    """Registra, clasifica y persiste un incidente imprimiendo el resultado en JSON por stdout."""
    parsed_created_at: Optional[datetime] = None
    if created_at is not None:
        try:
            parsed_created_at = datetime.fromisoformat(created_at)
        except ValueError as exc:
            typer.echo(
                f"Error de validación: formato inválido para '--created-at': '{created_at}'.",
                err=True,
            )
            raise typer.Exit(code=1) from exc

    service = IncidentService(repository=create_repository())
    try:
        result = service.create_incident(
            title=title,
            raw_text=raw_text,
            incident_id=incident_id,
            created_at=parsed_created_at,
            status=status,  # type: ignore[arg-type]
        )
    except (ValidationError, DuplicateIncidentIdError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    payload = asdict(result)
    payload["created_at"] = result.created_at.isoformat()
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command("sla")
def sla_command(
    incident_id: str = typer.Option(
        ..., "--incident-id", help="Identificador único del incidente a auditar."
    ),
    reference_time: Optional[str] = typer.Option(
        None,
        "--reference-time",
        help="Fecha/hora ISO-8601 de referencia para evaluación determinista de SLA.",
    ),
) -> None:
    """Audita el estado de SLA de un incidente persistido en JSON por stdout."""
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
        evaluation = service.evaluate_incident_sla(
            incident_id=incident_id,
            reference_time=parsed_ref_time,
        )
    except (IncidentNotFoundError, ValidationError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(json.dumps(asdict(evaluation), ensure_ascii=False))


@app.command("health")
def health_command() -> None:
    """Verifica conectividad real contra la base de datos configurada (SELECT 1)."""
    service = IncidentService(repository=create_repository())
    if service.check_health():
        typer.echo(
            json.dumps({"status": "ok", "database": "connected"}, ensure_ascii=False)
        )
        return

    typer.echo(
        json.dumps({"status": "error", "database": "unavailable"}, ensure_ascii=False)
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
