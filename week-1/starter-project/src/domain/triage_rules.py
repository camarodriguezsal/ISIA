"""Motor determinista de clasificación y enrutamiento de incidentes (IncidentOps)."""

import json
from pathlib import Path
from typing import Dict, List

from src.domain.models import SeverityLevel, TeamName, TriageResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_incidents.json"


def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente evaluando impacto real, seguridad y radio de afectación."""
    text_lower = raw_text.lower()

    # 1. Brechas de seguridad multi-tenant o fuga de datos -> P0 / Security-IAM
    if "company_id" in text_lower or "otra organización" in text_lower or "fuga" in text_lower:
        severity: SeverityLevel = "P0"
        component = "reporting-api"
        recommended_team: TeamName = "Security-IAM"
        symptom_category = "idor-data-leak"
        rationale = "Brecha crítica multi-tenant: exposición de datos entre organizaciones."

    # 2. Caída global de pagos (HTTP 502) -> P0 / Backend-Core
    elif "502" in text_lower and ("pago" in text_lower or "cobro" in text_lower or "pasarela" in text_lower):
        severity = "P0"
        component = "payments-gateway"
        recommended_team = "Backend-Core"
        symptom_category = "http-502-outage"
        rationale = "Indisponibilidad global de servicio crítico de pagos (HTTP 502)."

    # 3. Degradación severa de infraestructura compartida -> P1 / Data-DBA
    elif "94%" in text_lower or ("postgresql" in text_lower and "pool" in text_lower):
        severity = "P1"
        component = "database-cluster"
        recommended_team = "Data-DBA"
        symptom_category = "pool-exhaustion"
        rationale = "Saturación crítica del pool de conexiones PostgreSQL con riesgo inminente de caída."

    # 4. Consultas históricas lentas (>3s / 10,000 registros) -> P2 / Data-DBA
    elif "10,000" in text_lower and ("segundos" in text_lower or "tarda" in text_lower):
        severity = "P2"
        component = "reporting-api"
        recommended_team = "Data-DBA"
        symptom_category = "slow-query-10k"
        rationale = "Degradación moderada de consulta histórica (>3s) para volúmenes >10k registros."

    # 5. Bloqueo de cuenta individual (neutraliza trampa léxica "hoy") -> P2 / Security-IAM
    elif "cuenta" in text_lower and ("bloqueada" in text_lower or "ingresar" in text_lower):
        severity = "P2"
        component = "auth-identity"
        recommended_team = "Security-IAM"
        symptom_category = "account-lockout"
        rationale = "Bloqueo operativo de cuenta individual sin afectación global del servicio."

    # 6. Exportación lenta pero funcional -> P2 / Backend-Core
    elif "exportación" in text_lower and ("segundos" in text_lower or "lenta" in text_lower):
        severity = "P2"
        component = "reporting-api"
        recommended_team = "Backend-Core"
        symptom_category = "slow-excel-export"
        rationale = "Degradación de rendimiento en exportación sin pérdida de disponibilidad."

    # 7. Mantenimiento preventivo en staging -> P3 / Platform-SRE
    elif "certificado" in text_lower or "tls" in text_lower:
        severity = "P3"
        component = "infra-certificates"
        recommended_team = "Platform-SRE"
        symptom_category = "tls-rotation"
        rationale = "Tarea preventiva de rotación de certificado TLS en entorno no productivo (staging)."

    # 8. Ajustes cosméticos de interfaz -> P3 / Backend-Core
    else:
        severity = "P3"
        component = "frontend-ui"
        recommended_team = "Backend-Core"
        symptom_category = "cosmetic-color"
        rationale = "Solicitud visual/cosmética sin impacto funcional."

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        recommended_team=recommended_team,
        duplicate_group_key=f"{component}:{symptom_category}",
        rationale=rationale,
    )


def _run_triage_audit() -> None:
    """Ejecuta el motor determinista sobre los incidentes de ejemplo."""
    incidents: List[Dict[str, str]] = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))

    print("=== Auditoría del Motor de Triaje (`src/domain/triage_rules.py`) ===")
    print(f"{'ID':<10} | {'Sev.':<5} | {'Equipo':<14} | {'Componente':<20} | {'Extracto del Reporte'}")
    print("-" * 105)
    for item in incidents:
        result = classify_incident_report(item["id"], item["raw_text"])
        snippet = item["raw_text"][:40] + "..." if len(item["raw_text"]) > 40 else item["raw_text"]
        print(
            f"{result.incident_id:<10} | {result.severity:<5} | {result.recommended_team:<14} "
            f"| {result.component:<20} | {snippet}"
        )
    print("-" * 105)


if __name__ == "__main__":
    _run_triage_audit()
