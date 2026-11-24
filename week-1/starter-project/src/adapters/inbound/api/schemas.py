"""Esquemas Pydantic v2 para el adaptador HTTP de IncidentOps."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

from src.application.services import ActiveIncidentsSummary, CreateIncidentResult
from src.domain.models import (
    IncidentStatus,
    SLAEvaluation,
    SeverityLevel,
    TeamName,
    TriageResult,
)


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


class CreateIncidentRequest(BaseModel):
    """Contrato de entrada para POST /api/v1/incidents."""

    title: str
    raw_text: str
    incident_id: Optional[str] = None
    created_at: Optional[datetime] = None
    status: IncidentStatus = "OPEN"

    @field_validator("title", "raw_text")
    @classmethod
    def required_fields_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "El campo no puede estar vacío ni contener solo espacios en blanco."
            )
        return value

    @field_validator("incident_id")
    @classmethod
    def optional_incident_id_must_not_be_blank(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError(
                "El campo 'incident_id' no puede estar vacío ni contener solo espacios en blanco."
            )
        return value


class IncidentCreatedResponse(BaseModel):
    """Contrato de salida para POST /api/v1/incidents."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    recommended_team: TeamName
    duplicate_group_key: str
    rationale: str
    is_duplicate: bool
    duplicate_of: list[str]

    @classmethod
    def from_result(cls, result: CreateIncidentResult) -> "IncidentCreatedResponse":
        return cls(
            incident_id=result.incident_id,
            title=result.title,
            component=result.component,
            severity=result.severity,
            status=result.status,
            created_at=result.created_at,
            recommended_team=result.recommended_team,
            duplicate_group_key=result.duplicate_group_key,
            rationale=result.rationale,
            is_duplicate=result.is_duplicate,
            duplicate_of=result.duplicate_of,
        )


class SLAEvaluationResponse(BaseModel):
    """Contrato de salida espejo de SLAEvaluation para GET /api/v1/incidents/{id}/sla."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

    @classmethod
    def from_domain(cls, evaluation: SLAEvaluation) -> "SLAEvaluationResponse":
        return cls(
            incident_id=evaluation.incident_id,
            severity=evaluation.severity,
            elapsed_minutes=evaluation.elapsed_minutes,
            allowed_minutes=evaluation.allowed_minutes,
            remaining_minutes=evaluation.remaining_minutes,
            is_breached=evaluation.is_breached,
            requires_escalation=evaluation.requires_escalation,
        )


class HealthResponse(BaseModel):
    """Contrato de salida para GET /health."""

    status: Literal["ok", "error"]
    database: Literal["connected", "unavailable"]
