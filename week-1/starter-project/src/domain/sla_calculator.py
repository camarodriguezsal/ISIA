"""Módulo determinista para el cálculo y evaluación de acuerdos de nivel de servicio (SLA)."""

from datetime import datetime, time, timedelta, timezone
from typing import Dict

from src.domain.models import Incident, SLAEvaluation, SLARule, SeverityLevel

BUSINESS_START = time(8, 0, 0)
BUSINESS_END = time(18, 0, 0)

SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}


def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra la tabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]


def _calculate_business_minutes(start_dt: datetime, end_dt: datetime) -> int:
    """Calcula minutos hábiles (Lunes-Viernes 08:00-18:00) en complejidad O(D)."""
    total_seconds = 0.0
    current_day = start_dt.date()
    last_day = end_dt.date()

    while current_day <= last_day:
        if current_day.weekday() < 5:  # 0=Lunes ... 4=Viernes
            window_start = datetime.combine(current_day, BUSINESS_START)
            window_end = datetime.combine(current_day, BUSINESS_END)

            effective_start = max(start_dt, window_start)
            effective_end = min(end_dt, window_end)

            if effective_end > effective_start:
                total_seconds += (effective_end - effective_start).total_seconds()

        current_day += timedelta(days=1)

    return int(total_seconds // 60)


def _normalize_timestamp(dt: datetime) -> datetime:
    """Normaliza marcas temporales aware a UTC naive; mantiene las naive intactas."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    created_at = _normalize_timestamp(incident.created_at)
    end_time = _normalize_timestamp(incident.resolved_at or reference_time)

    if end_time < created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    if rule.operates_24x7:
        delta_seconds = (end_time - created_at).total_seconds()
        elapsed_minutes = int(delta_seconds // 60)
    else:
        elapsed_minutes = _calculate_business_minutes(created_at, end_time)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED"
        and (is_breached or elapsed_minutes >= escalation_limit)
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )


def _run_demo() -> None:
    """Ejecuta la demostración determinista y valida los casos borde de SLA."""
    print("=== Demostración y Validación Determinista de SLA ===")

    # Caso 1 (Original): P2 creado viernes 17:00 -> lunes 09:00 = 120 min hábiles (60m vie + 60m lun)
    inc_1 = Incident(
        incident_id="INC-2001",
        title="Latencia elevada en reporte de órdenes",
        component="reporting-api",
        severity="P2",
        status="OPEN",
        created_at=datetime(2026, 11, 6, 17, 0, 0),  # Viernes 17:00
    )
    ev_1 = evaluate_sla_status(inc_1, reference_time=datetime(2026, 11, 9, 9, 0, 0))
    assert ev_1.elapsed_minutes == 120 and not ev_1.is_breached and not ev_1.requires_escalation

    # Caso 2: P2 creado viernes 18:30 (fuera de horario) -> lunes 08:30 = 30 min hábiles
    inc_2 = Incident(
        incident_id="INC-2002",
        title="Ticket creado fuera de ventana hábil",
        component="reporting-api",
        severity="P2",
        status="OPEN",
        created_at=datetime(2026, 11, 6, 18, 30, 0),  # Viernes 18:30
    )
    ev_2 = evaluate_sla_status(inc_2, reference_time=datetime(2026, 11, 9, 8, 30, 0))
    assert ev_2.elapsed_minutes == 30 and ev_2.remaining_minutes == 450

    # Caso 3: P2 creado sábado -> evaluado domingo = 0 min hábiles
    inc_3 = Incident(
        incident_id="INC-2003",
        title="Bloqueo cuenta en fin de semana",
        component="auth-identity",
        severity="P2",
        status="OPEN",
        created_at=datetime(2026, 11, 7, 11, 0, 0),  # Sábado
    )
    ev_3 = evaluate_sla_status(inc_3, reference_time=datetime(2026, 11, 8, 17, 0, 0))
    assert ev_3.elapsed_minutes == 0 and not ev_3.requires_escalation

    # Caso 4: P2 alcanza exactamente el 75% del SLA (360 / 480 min) -> activa escalamiento preventivo
    inc_4 = Incident(
        incident_id="INC-2004",
        title="Cruce fin de semana al umbral 75%",
        component="reporting-api",
        severity="P2",
        status="IN_PROGRESS",
        created_at=datetime(2026, 11, 6, 16, 0, 0),  # Viernes 16:00 (120m)
    )
    ev_4 = evaluate_sla_status(inc_4, reference_time=datetime(2026, 11, 9, 12, 0, 0))  # Lunes 12:00 (+240m)
    assert ev_4.elapsed_minutes == 360 and ev_4.requires_escalation and not ev_4.is_breached

    # Caso 5: P2 vencido (500 > 480 min) mantiene requires_escalation=True mientras siga abierto
    ev_5 = evaluate_sla_status(inc_4, reference_time=datetime(2026, 11, 9, 14, 20, 0))
    assert ev_5.elapsed_minutes == 500 and ev_5.is_breached and ev_5.requires_escalation

    # Caso 6: P0 (operates_24x7=True) en madrugada de fin de semana corre 24/7
    inc_6 = Incident(
        incident_id="INC-2005",
        title="Caída pasarela de pagos en domingo",
        component="payments-gateway",
        severity="P0",
        status="OPEN",
        created_at=datetime(2026, 11, 7, 23, 30, 0),  # Sábado 23:30
    )
    ev_6 = evaluate_sla_status(inc_6, reference_time=datetime(2026, 11, 8, 0, 45, 0))  # Domingo 00:45 (75m)
    assert ev_6.elapsed_minutes == 75 and ev_6.is_breached and ev_6.requires_escalation

    for ev in (ev_1, ev_2, ev_3, ev_4, ev_5, ev_6):
        print(
            f"{ev.incident_id} ({ev.severity}) | Transcurrido: {ev.elapsed_minutes:3d}m / {ev.allowed_minutes:4d}m "
            f"| Restante: {ev.remaining_minutes:4d}m | Breached: {str(ev.is_breached):5s} | Escalar: {ev.requires_escalation}"
        )
    print("\nTodos los casos borde pasaron correctamente.")


if __name__ == "__main__":
    _run_demo()
