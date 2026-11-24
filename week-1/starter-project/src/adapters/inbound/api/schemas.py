"""Esquemas Pydantic v2 para el adaptador HTTP de IncidentOps."""

from pydantic import BaseModel, field_validator

from src.application.services import ActiveIncidentsSummary
from src.domain.models import IncidentStatus, SeverityLevel, TeamName, TriageResult


class TriageRequest(BaseModel):
    """Contrato de entrada para POST /api/v1/incidents/triage."""

    incident_id: str
    raw_text: str

    @field_validator("incident_id", "raw_text")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "El campo no puede estar vacío ni contener solo espacios en blanco."
            )
        return value


class TriageResponse(BaseModel):
    """Contrato de salida espejo de TriageResult."""

    incident_id: str
    severity: SeverityLevel
    component: str
    recommended_team: TeamName
    duplicate_group_key: str
    rationale: str
    consistency_ratio: float

    @classmethod
    def from_domain(cls, result: TriageResult) -> "TriageResponse":
        return cls(
            incident_id=result.incident_id,
            severity=result.severity,
            component=result.component,
            recommended_team=result.recommended_team,
            duplicate_group_key=result.duplicate_group_key,
            rationale=result.rationale,
            consistency_ratio=result.consistency_ratio,
        )


class ActiveIncidentItem(BaseModel):
    """Detalle de un incidente activo en GET /api/v1/incidents/summary."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int
    requires_escalation: bool


class ActiveIncidentsSummaryResponse(BaseModel):
    """Contrato de salida para GET /api/v1/incidents/summary."""

    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentItem]

    @classmethod
    def from_summary(
        cls, summary: ActiveIncidentsSummary
    ) -> "ActiveIncidentsSummaryResponse":
        return cls(
            total_active=summary.total_active,
            breached_count=summary.breached_count,
            incidents=[
                ActiveIncidentItem(
                    incident_id=item.incident_id,
                    title=item.title,
                    component=item.component,
                    severity=item.severity,
                    status=item.status,
                    elapsed_minutes=item.elapsed_minutes,
                    requires_escalation=item.requires_escalation,
                )
                for item in summary.incidents
            ],
        )
