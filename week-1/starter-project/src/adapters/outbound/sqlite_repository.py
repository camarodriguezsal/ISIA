"""Adaptador secundario SQLite que implementa IncidentRepositoryPort."""

from datetime import datetime
import sqlite3
from typing import Optional

from src.domain.models import Incident
from src.domain.sla_calculator import SLA_POLICY_TABLE


class SQLiteIncidentRepository:
    """Persistencia optimizada de incidentes y políticas SLA en SQLite (ADR-001)."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.conn.cursor()
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
        existing_columns = {
            row["name"]
            for row in cursor.execute("PRAGMA table_info(incidents)").fetchall()
        }
        if "recommended_team" not in existing_columns:
            cursor.execute("ALTER TABLE incidents ADD COLUMN recommended_team TEXT")
        if "duplicate_group_key" not in existing_columns:
            cursor.execute("ALTER TABLE incidents ADD COLUMN duplicate_group_key TEXT")
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
                INSERT OR REPLACE INTO sla_policies (severity, max_resolution_minutes, operates_24x7)
                VALUES (?, ?, ?)
                """,
                (rule.severity, rule.max_resolution_minutes, 1 if rule.operates_24x7 else 0),
            )
        self.conn.commit()

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> Incident:
        return Incident(
            incident_id=row["incident_id"],
            title=row["title"],
            component=row["component"],
            severity=row["severity"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None
            ),
            recommended_team=row["recommended_team"],
            duplicate_group_key=row["duplicate_group_key"],
        )

    def save_incident(self, incident: Incident) -> None:
        """Inserta o actualiza un incidente en la tabla incidents."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO incidents (
                incident_id, title, component, severity, status,
                created_at, resolved_at, recommended_team, duplicate_group_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident.incident_id,
                incident.title,
                incident.component,
                incident.severity,
                incident.status,
                incident.created_at.isoformat(),
                incident.resolved_at.isoformat() if incident.resolved_at else None,
                incident.recommended_team,
                incident.duplicate_group_key,
            ),
        )
        self.conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Recupera un incidente por su ID o retorna None si no existe."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT incident_id, title, component, severity, status,
                   created_at, resolved_at, recommended_team, duplicate_group_key
            FROM incidents
            WHERE incident_id = ?
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
        cursor = self.conn.cursor()
        if exclude_incident_id is not None:
            cursor.execute(
                """
                SELECT incident_id, title, component, severity, status,
                       created_at, resolved_at, recommended_team, duplicate_group_key
                FROM incidents
                WHERE duplicate_group_key = ?
                  AND status IN ('OPEN', 'IN_PROGRESS', 'ESCALATION_REQUIRED')
                  AND incident_id != ?
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
                WHERE duplicate_group_key = ?
                  AND status IN ('OPEN', 'IN_PROGRESS', 'ESCALATION_REQUIRED')
                ORDER BY created_at ASC, incident_id ASC
                """,
                (duplicate_group_key,),
            )
        return [self._row_to_incident(row) for row in cursor.fetchall()]

    def list_active_incidents(
        self, component_filter: Optional[str] = None
    ) -> list[Incident]:
        """Lista incidentes activos (OPEN e IN_PROGRESS) usando INNER JOIN con sla_policies."""
        cursor = self.conn.cursor()
        if component_filter is not None:
            cursor.execute(
                """
                SELECT i.incident_id, i.title, i.component, i.severity, i.status,
                       i.created_at, i.resolved_at, i.recommended_team, i.duplicate_group_key
                FROM incidents i
                INNER JOIN sla_policies p ON i.severity = p.severity
                WHERE i.component = ?
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
        return [self._row_to_incident(row) for row in cursor.fetchall()]

    def check_health(self) -> bool:
        """Ejecuta una consulta mínima para verificar la salud de la conexión SQLite."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
