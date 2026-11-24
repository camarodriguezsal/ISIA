"""Casos de uso compartidos de IncidentOps (agnósticos al transporte)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

from src.application.ports import IncidentRepositoryPort
from src.domain.models import (
    Incident,
    IncidentStatus,
    SLAEvaluation,
    SeverityLevel,
    TeamName,
    TriageResult,
)
from src.domain.sla_calculator import evaluate_sla_status
from src.domain.triage_rules import classify_incident_report

VALID_INCIDENT_STATUSES: tuple[str, ...] = (
    "OPEN",
    "IN_PROGRESS",
    "ESCALATION_REQUIRED",
    "RESOLVED",
)


class ValidationError(ValueError):
    """Error de validación de entrada en la capa de aplicación."""


class IncidentNotFoundError(LookupError):
    """Error lanzado cuando un incidente solicitado no existe en el repositorio."""


class DuplicateIncidentIdError(ValueError):
    """Error lanzado al intentar crear un incidente con un incident_id ya existente."""


@dataclass(frozen=True)
class CreateIncidentResult:
    """Resultado estructurado del caso de uso de creación de incidentes."""

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

    def create_incident(
        self,
        title: str,
        raw_text: str,
        incident_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        status: IncidentStatus = "OPEN",
    ) -> CreateIncidentResult:
        """Clasifica, persiste y verifica duplicados abiertos de un nuevo incidente."""
        if self._repository is None:
            raise RuntimeError(
                "IncidentService requiere un IncidentRepositoryPort configurado para crear incidentes."
            )

        cleaned_title = title.strip()
        cleaned_text = raw_text.strip()
        if not cleaned_title:
            raise ValidationError(
                "El campo 'title' no puede estar vacío ni contener solo espacios."
            )
        if not cleaned_text:
            raise ValidationError(
                "El campo 'raw_text' no puede estar vacío ni contener solo espacios."
            )

        if incident_id is not None:
            resolved_id = incident_id.strip()
            if not resolved_id:
                raise ValidationError(
                    "El campo 'incident_id' no puede estar vacío ni contener solo espacios."
                )
        else:
            resolved_id = f"INC-{uuid.uuid4().hex[:8].upper()}"

        if status not in VALID_INCIDENT_STATUSES:
            raise ValidationError(
                f"Estado no válido: '{status}'. Valores permitidos: {', '.join(VALID_INCIDENT_STATUSES)}."
            )

        if self._repository.get_incident(resolved_id) is not None:
            raise DuplicateIncidentIdError(
                f"Ya existe un incidente registrado con el identificador '{resolved_id}'."
            )

        effective_created_at = created_at or datetime.now()
        triage = classify_incident_report(
            incident_id=resolved_id,
            raw_text=cleaned_text,
        )

        incident = Incident(
            incident_id=resolved_id,
            title=cleaned_title,
            component=triage.component,
            severity=triage.severity,
            status=status,
            created_at=effective_created_at,
            recommended_team=triage.recommended_team,
            duplicate_group_key=triage.duplicate_group_key,
        )
        self._repository.save_incident(incident)

        open_duplicates = self._repository.find_open_duplicates(
            duplicate_group_key=triage.duplicate_group_key,
            exclude_incident_id=resolved_id,
        )
        duplicate_ids = [dup.incident_id for dup in open_duplicates]

        return CreateIncidentResult(
            incident_id=incident.incident_id,
            title=incident.title,
            component=incident.component,
            severity=incident.severity,
            status=incident.status,
            created_at=incident.created_at,
            recommended_team=triage.recommended_team,
            duplicate_group_key=triage.duplicate_group_key,
            rationale=triage.rationale,
            is_duplicate=bool(duplicate_ids),
            duplicate_of=duplicate_ids,
        )

    def evaluate_incident_sla(
        self,
        incident_id: str,
        reference_time: Optional[datetime] = None,
    ) -> SLAEvaluation:
        """Evalúa el estado de SLA de un incidente persistido delegando al dominio."""
        if self._repository is None:
            raise RuntimeError(
                "IncidentService requiere un IncidentRepositoryPort configurado para auditar SLA."
            )

        cleaned_id = incident_id.strip()
        if not cleaned_id:
            raise ValidationError(
                "El campo 'incident_id' no puede estar vacío ni contener solo espacios."
            )

        incident = self._repository.get_incident(cleaned_id)
        if incident is None:
            raise IncidentNotFoundError(
                f"No existe ningún incidente con el identificador '{cleaned_id}'."
            )

        effective_reference_time = reference_time or datetime.now()
        try:
            return evaluate_sla_status(
                incident, reference_time=effective_reference_time
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    def check_health(self) -> bool:
        """Verifica la conectividad real del repositorio configurado."""
        if self._repository is None:
            raise RuntimeError(
                "IncidentService requiere un IncidentRepositoryPort configurado para verificar salud."
            )
        return self._repository.check_health()
