"""Puertos secundarios (Protocol) de la capa de aplicación de IncidentOps."""

from typing import Optional, Protocol, runtime_checkable

from src.domain.models import Incident


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Contrato estructural para repositorios de persistencia de incidentes."""

    def save_incident(self, incident: Incident) -> None:
        """Persiste o actualiza un incidente."""
        ...

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Recupera un incidente por su identificador o None si no existe."""
        ...

    def find_open_duplicates(
        self,
        duplicate_group_key: str,
        exclude_incident_id: Optional[str] = None,
    ) -> list[Incident]:
        """Busca incidentes abiertos con la misma clave de duplicado, excluyendo opcionalmente un ID."""
        ...

    def list_active_incidents(
        self, component_filter: Optional[str] = None
    ) -> list[Incident]:
        """Lista incidentes activos (OPEN e IN_PROGRESS), opcionalmente filtrados por componente."""
        ...

    def check_health(self) -> bool:
        """Verifica la disponibilidad del almacenamiento subyacente."""
        ...
