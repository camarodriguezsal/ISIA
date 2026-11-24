"""Adaptador secundario PostgreSQL (psycopg sin ORM) que implementa IncidentRepositoryPort."""

from datetime import datetime
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row

from src.domain.models import Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE


class PostgresIncidentRepository:
    """Persistencia de incidentes y políticas SLA en PostgreSQL sin ORM (ADR-004)."""

    def __init__(
        self,
        dsn: str,
        connect_timeout: int = 3,
        init_schema: bool = True,
    ) -> None:
        self.dsn = dsn
        self.connect_timeout = connect_timeout
        self._schema_initialized = False
        if init_schema:
            self._try_init_schema()

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(
            self.dsn,
            connect_timeout=self.connect_timeout,
            row_factory=dict_row,
        )

    def _try_init_schema(self) -> None:
        """Inicializa el esquema de forma idempotente sin bloquear el arranque ante caída temporal."""
        try:
            self._init_schema()
        except psycopg.Error:
            self._schema_initialized = False

    def _ensure_schema(self) -> None:
        if not self._schema_initialized:
            self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sla_policies (
                        severity TEXT PRIMARY KEY,
                        max_resolution_minutes INTEGER NOT NULL,
                        operates_24x7 INTEGER NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS incidents (
                        incident_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        component TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        resolved_at TEXT,
                        recommended_team TEXT,
                        duplicate_group_key TEXT
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_incidents_component_status
                    ON incidents (component, status)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_incidents_dup_key
                    ON incidents (duplicate_group_key, status)
                    """
                )
                for rule in SLA_POLICY_TABLE.values():
                    cursor.execute(
                        """
                        INSERT INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (severity) DO UPDATE SET
                            max_resolution_minutes = EXCLUDED.max_resolution_minutes,
                            operates_24x7 = EXCLUDED.operates_24x7
                        """,
                        (
                            rule.severity,
                            rule.max_resolution_minutes,
                            1 if rule.operates_24x7 else 0,
                        ),
                    )
            conn.commit()
        self._schema_initialized = True

    @staticmethod
    def _row_to_incident(row: dict[str, Any]) -> Incident:
        return Incident(
            incident_id=row["incident_id"],
            title=row["title"],
            component=row["component"],
            severity=row["severity"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"])
                if row["resolved_at"]
                else None
            ),
            recommended_team=row["recommended_team"],
            duplicate_group_key=row["duplicate_group_key"],
        )

    def save_incident(self, incident: Incident) -> None:
        """Inserta o actualiza un incidente en la tabla incidents."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO incidents (
                        incident_id, title, component, severity, status,
                        created_at, resolved_at, recommended_team, duplicate_group_key
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (incident_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        component = EXCLUDED.component,
                        severity = EXCLUDED.severity,
                        status = EXCLUDED.status,
                        created_at = EXCLUDED.created_at,
                        resolved_at = EXCLUDED.resolved_at,
                        recommended_team = EXCLUDED.recommended_team,
                        duplicate_group_key = EXCLUDED.duplicate_group_key
                    """,
                    (
                        incident.incident_id,
                        incident.title,
                        incident.component,
                        incident.severity,
                        incident.status,
                        incident.created_at.isoformat(),
                        incident.resolved_at.isoformat()
                        if incident.resolved_at
                        else None,
                        incident.recommended_team,
                        incident.duplicate_group_key,
                    ),
                )
            conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Recupera un incidente por su ID o retorna None si no existe."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT incident_id, title, component, severity, status,
                           created_at, resolved_at, recommended_team, duplicate_group_key
                    FROM incidents
                    WHERE incident_id = %s
                    """,
                    (incident_id,),
                )
                row = cursor.fetchone()
        return self._row_to_incident(row) if row is not None else None

    def find_open_duplicates(
        self,
        duplicate_group_key: str,
        exclude_incident_id: Optional[str] = None,
    ) -> list[Incident]:
        """Busca incidentes abiertos con la misma duplicate_group_key."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if exclude_incident_id is not None:
                    cursor.execute(
                        """
                        SELECT incident_id, title, component, severity, status,
                               created_at, resolved_at, recommended_team, duplicate_group_key
                        FROM incidents
                        WHERE duplicate_group_key = %s
                          AND status IN ('OPEN', 'IN_PROGRESS', 'ESCALATION_REQUIRED')
                          AND incident_id != %s
                        ORDER BY created_at ASC, incident_id ASC
                        """,
                        (duplicate_group_key, exclude_incident_id),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT incident_id, title, component, severity, status,
                               created_at, resolved_at, recommended_team, duplicate_group_key
                        FROM incidents
                        WHERE duplicate_group_key = %s
                          AND status IN ('OPEN', 'IN_PROGRESS', 'ESCALATION_REQUIRED')
                        ORDER BY created_at ASC, incident_id ASC
                        """,
                        (duplicate_group_key,),
                    )
                rows = cursor.fetchall()
        return [self._row_to_incident(row) for row in rows]

    def list_active_incidents(
        self, component_filter: Optional[str] = None
    ) -> list[Incident]:
        """Lista incidentes activos (OPEN e IN_PROGRESS) usando INNER JOIN con sla_policies."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cursor:
                if component_filter is not None:
                    cursor.execute(
                        """
                        SELECT i.incident_id, i.title, i.component, i.severity, i.status,
                               i.created_at, i.resolved_at, i.recommended_team, i.duplicate_group_key
                        FROM incidents i
                        INNER JOIN sla_policies p ON i.severity = p.severity
                        WHERE i.component = %s
                          AND i.status IN ('OPEN', 'IN_PROGRESS')
                        ORDER BY i.created_at ASC, i.incident_id ASC
                        """,
                        (component_filter,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT i.incident_id, i.title, i.component, i.severity, i.status,
                               i.created_at, i.resolved_at, i.recommended_team, i.duplicate_group_key
                        FROM incidents i
                        INNER JOIN sla_policies p ON i.severity = p.severity
                        WHERE i.status IN ('OPEN', 'IN_PROGRESS')
                        ORDER BY i.created_at ASC, i.incident_id ASC
                        """
                    )
                rows = cursor.fetchall()
        return [self._row_to_incident(row) for row in rows]

    def check_health(self) -> bool:
        """Ejecuta una consulta real SELECT 1 para verificar conectividad con PostgreSQL."""
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return cursor.fetchone() is not None
        except psycopg.Error:
            return False
