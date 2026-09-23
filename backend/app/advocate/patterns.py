"""Impossible travel, throughput and repeated descriptions. Bible §11.4. Session 4."""

from app.domain.models import ServerReport, ServiceRecord
from app.engine.params import EngineParams


def analyze_servers(records: list[ServiceRecord], params: EngineParams) -> list[ServerReport]:
    """O(n log n) per server. Must handle 50k rows in under three seconds."""
    raise NotImplementedError("Session 4")
