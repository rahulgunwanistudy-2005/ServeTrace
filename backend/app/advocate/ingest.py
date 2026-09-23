"""CSV/XLSX service records into `ServiceRecord`. Bible §11.4. Session 4."""

from app.domain.models import ServiceRecord


def parse_records(data: bytes, filename: str, column_map: dict[str, str]) -> list[ServiceRecord]:
    raise NotImplementedError("Session 4")
