"""/api/geocode: turn a New York City address into a point.

The address is the entire request. Bible §13: when a bank statement is the source of a
location, only the address ever leaves the browser, never the amount or the merchant.
"""

from fastapi import APIRouter, Depends

from app.api.rate_limit import enforce_rate_limit
from app.domain.models import GeocodeRequest, GeocodeResponse
from app.geo.geocode import geocode

router = APIRouter(tags=["geocode"])


@router.post("/geocode", response_model=GeocodeResponse, dependencies=[Depends(enforce_rate_limit)])
async def geocode_address(body: GeocodeRequest) -> GeocodeResponse:
    return GeocodeResponse(result=await geocode(body.address))
