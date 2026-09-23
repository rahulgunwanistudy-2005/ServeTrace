"""Haversine sanity. Ranges, not exact values: the point is the order of magnitude."""

import pytest

from app.domain.models import LatLng
from app.geo.distance import haversine_km

TIMES_SQUARE = LatLng(lat=40.7580, lng=-73.9855)
GRAND_CENTRAL = LatLng(lat=40.7527, lng=-73.9772)
BRONX_ZOO = LatLng(lat=40.8506, lng=-73.8769)
JFK = LatLng(lat=40.6413, lng=-73.7781)


def test_times_square_to_grand_central() -> None:
    # Roughly four short blocks plus two long ones. The bible estimates 0.6-0.8 km, but the
    # true straight line between these two landmarks is 0.91 km, so the range brackets that.
    assert 0.7 <= haversine_km(TIMES_SQUARE, GRAND_CENTRAL) <= 1.1


def test_bronx_zoo_to_jfk() -> None:
    assert 20.0 <= haversine_km(BRONX_ZOO, JFK) <= 30.0


def test_identical_points_are_zero() -> None:
    assert haversine_km(TIMES_SQUARE, TIMES_SQUARE) == pytest.approx(0.0, abs=1e-9)


def test_symmetric() -> None:
    assert haversine_km(BRONX_ZOO, JFK) == pytest.approx(haversine_km(JFK, BRONX_ZOO))


def test_antipodal_does_not_blow_up_on_domain_error() -> None:
    """The asin argument is clamped, so floating point cannot push it past 1.0."""
    d = haversine_km(LatLng(lat=0.0, lng=0.0), LatLng(lat=0.0, lng=180.0))
    assert d == pytest.approx(20015.0, abs=5.0)


def test_meridian_wrap_is_a_short_hop_not_a_world_tour() -> None:
    d = haversine_km(LatLng(lat=40.0, lng=179.99), LatLng(lat=40.0, lng=-179.99))
    assert d < 2.0
