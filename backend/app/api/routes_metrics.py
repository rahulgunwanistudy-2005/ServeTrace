"""`GET /api/stats` and `POST /api/leads`. Build prompt §8.2.

The contact form is the only route in the product that keeps what someone sends, and it
keeps only what the form asks for, with the person's explicit consent. Its body is never
logged; the request log line carries the route and the status like every other route.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.errors import ContactUnavailableError
from app.api.rate_limit import enforce_leads_rate_limit
from app.domain.models import LeadAccepted, LeadIn, UsageStats
from app.metrics.events import usage_stats
from app.metrics.store import StoreError, get_store

router = APIRouter(tags=["metrics"])


@router.get("/stats", response_model=UsageStats)
async def stats() -> UsageStats:
    return await usage_stats()


@router.post("/leads", response_model=LeadAccepted)
async def leads(lead: LeadIn, request: Request) -> LeadAccepted:
    # The honeypot: a field no person sees. A bot that fills it is told it succeeded,
    # so it has no reason to try again, and nothing is kept. It is checked before the
    # rate limit so a bot cannot spend a real person's hourly allowance on that address.
    if lead.website.strip():
        return LeadAccepted()
    enforce_leads_rate_limit(request)
    store = get_store()
    if not store.available:
        raise ContactUnavailableError(
            "The contact form is not switched on in this deployment, so nothing was sent."
        )
    try:
        await store.insert_lead(lead)
    except StoreError:
        raise ContactUnavailableError(
            "We could not save your message just now. Nothing was kept; please try again later."
        ) from None
    return LeadAccepted()
