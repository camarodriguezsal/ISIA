"""Adaptador primario HTTP (FastAPI) y composition root de la API REST."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponse,
    TriageRequest,
    TriageResponse,
)
from src.adapters.outbound.factory import create_repository
from src.application.services import IncidentService, ValidationError


def create_app(service: Optional[IncidentService] = None) -> FastAPI:
    """Construye la aplicación FastAPI inyectando el servicio de aplicación."""
    incident_service = service or IncidentService(repository=create_repository())
    application = FastAPI(title="IncidentOps API", version="0.1.0")

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

    return application


app = create_app()
