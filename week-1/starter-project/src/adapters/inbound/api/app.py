"""Adaptador primario HTTP (FastAPI) y composition root de la API REST."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    CreateIncidentRequest,
    HealthResponse,
    IncidentCreatedResponse,
    SLAEvaluationResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import (
    DuplicateIncidentIdError,
    IncidentNotFoundError,
    IncidentService,
    ValidationError,
)


def create_app(service: Optional[IncidentService] = None) -> FastAPI:
    """Construye la aplicación FastAPI inyectando el servicio de aplicación."""
    incident_service = service or IncidentService(repository=create_repository())
    application = FastAPI(title="IncidentOps API", version="0.1.0")

    @application.get(
        "/health",
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse}},
    )
    def health_endpoint() -> JSONResponse:
        if incident_service.check_health():
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "database": "connected"},
            )
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )

    @application.post("/api/v1/incidents/triage", response_model=TriageResponse)
    def triage_incident_endpoint(payload: TriageRequest) -> TriageResponse:
        try:
            result = incident_service.triage_incident(
                incident_id=payload.incident_id,
                raw_text=payload.raw_text,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return TriageResponse.from_domain(result)

    @application.get(
        "/api/v1/incidents/summary", response_model=ActiveIncidentsSummaryResponse
    )
    def active_incidents_summary_endpoint(
        component: Optional[str] = Query(default=None),
        reference_time: Optional[datetime] = Query(default=None),
    ) -> ActiveIncidentsSummaryResponse:
        try:
            summary = incident_service.get_active_incidents_summary(
                component_filter=component,
                reference_time=reference_time,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return ActiveIncidentsSummaryResponse.from_summary(summary)

    @application.post(
        "/api/v1/incidents",
        status_code=201,
        response_model=IncidentCreatedResponse,
    )
    def create_incident_endpoint(
        payload: CreateIncidentRequest,
    ) -> IncidentCreatedResponse:
        try:
            result = incident_service.create_incident(
                title=payload.title,
                raw_text=payload.raw_text,
                incident_id=payload.incident_id,
                created_at=payload.created_at,
                status=payload.status,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except DuplicateIncidentIdError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return IncidentCreatedResponse.from_result(result)

    @application.get(
        "/api/v1/incidents/{incident_id}/sla",
        response_model=SLAEvaluationResponse,
    )
    def evaluate_incident_sla_endpoint(
        incident_id: str,
        reference_time: Optional[datetime] = Query(default=None),
    ) -> SLAEvaluationResponse:
        try:
            evaluation = incident_service.evaluate_incident_sla(
                incident_id=incident_id,
                reference_time=reference_time,
            )
        except IncidentNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return SLAEvaluationResponse.from_domain(evaluation)

    return application


app = create_app()
