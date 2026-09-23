"""NYC GeoSearch lookups with an on-disk cache. Bible §8. Session 2."""

from app.domain.models import LatLng


async def geocode(address: str) -> LatLng | None:
    """Resolve a NYC street address. Only the address is ever sent upstream."""
    raise NotImplementedError("Session 2")
