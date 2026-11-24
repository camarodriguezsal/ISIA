"""Casos de uso compartidos de IncidentOps (agnósticos al transporte)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.application.ports import IncidentRepositoryPort
from src.domain.models import IncidentStatus, SeverityLevel, TriageResult
from src.domain.sla_calculator import evaluate_sla_status
from src.domain.triage_rules import classify_incident_report


class ValidationError(ValueError):
    """Error de validación de entrada en la capa de aplicación."""


@dataclass(frozen=True)
class ActiveIncidentSummaryItem:
    """Detalle evaluado de un incidente activo en el resumen operativo."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int
    requires_escalation: bool


@dataclass(frozen=True)
class ActiveIncidentsSummary:
    """Vista consolidada de incidentes activos y cumplimiento de SLA."""

    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentSummaryItem]


class IncidentService:
    """Orquesta los casos de uso de IncidentOps reutilizables desde HTTP, CLI o MCP."""

    def __init__(self, repository: Optional[IncidentRepositoryPort] = None) -> None:
        self._repository = repository

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Ejecuta el triaje determinista stateless de un reporte de incidente."""
        cleaned_id = incident_id.strip()
        cleaned_text = raw_text.strip()

        if not cleaned_id:
            raise ValidationError(
                "El campo 'incident_id' no puede estar vacío ni contener solo espacios."
            )
        if not cleaned_text:
            raise ValidationError(
                "El campo 'raw_text' no puede estar vacío ni contener solo espacios."
            )

        return classify_incident_report(incident_id=cleaned_id, raw_text=cleaned_text)

    def get_active_incidents_summary(
        self,
        component_filter: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ActiveIncidentsSummary:
        """Calcula el resumen consolidado de incidentes activos delegando el SLA al dominio."""
        if self._repository is None:
            raise RuntimeError(
                "IncidentService requiere un IncidentRepositoryPort configurado para consultar incidentes."
            )

        cleaned_component: Optional[str] = None
        if component_filter is not None:
            cleaned_component = component_filter.strip()
            if not cleaned_component:
                raise ValidationError(
                    "El parámetro 'component' no puede estar vacío ni contener solo espacios."
                )

        effective_reference_time = reference_time or datetime.now()
        active_incidents = self._repository.list_active_incidents(
            component_filter=cleaned_component
        )

        items: list[ActiveIncidentSummaryItem] = []
        breached_count = 0

        for incident in active_incidents:
            sla_eval = evaluate_sla_status(
                incident, reference_time=effective_reference_time
            )
            if sla_eval.is_breached:
                breached_count += 1
            items.append(
                ActiveIncidentSummaryItem(
                    incident_id=incident.incident_id,
                    title=incident.title,
                    component=incident.component,
                    severity=incident.severity,
                    status=incident.status,
                    elapsed_minutes=sla_eval.elapsed_minutes,
                    requires_escalation=sla_eval.requires_escalation,
                )
            )

        return ActiveIncidentsSummary(
            total_active=len(items),
            breached_count=breached_count,
            incidents=items,
        )
