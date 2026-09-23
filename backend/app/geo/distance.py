"""Great-circle distance. The only distance function in the codebase."""

from math import asin, cos, radians, sin, sqrt

from app.domain.models import LatLng

EARTH_RADIUS_KM = 6371.0088
"""IUGG mean radius. Over NYC distances the spherical error is well under the GPS noise."""


def haversine_km(a: LatLng, b: LatLng) -> float:
    lat1, lng1, lat2, lng2 = (radians(v) for v in (a.lat, a.lng, b.lat, b.lng))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, h)))
