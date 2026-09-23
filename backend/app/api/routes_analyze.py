"""/api/analyze: the engine, behind one stateless POST.

Nothing is stored. The request carries everything the verdict depends on — the affidavit
the user confirmed, the fixes their browser already narrowed to the hours around the
claimed times (bible §13), the optional roster and the two dates — and the response
carries the whole analysis back. There is no session, no id and nothing to come back for.

The route itself only guards and delegates. Every decision in the response comes from
`engine/`, which is pure and has no idea it is behind HTTP.
"""

from fastapi import APIRouter, Depends

from app.api.errors import AffidavitNotConfirmedError, BadInputError
from app.api.rate_limit import enforce_rate_limit
from app.config import get_settings
from app.domain.models import AnalyzeRequest, CaseAnalysis
from app.engine.verdict import analyze

router = APIRouter(tags=["analyze"])


def _guard(body: AnalyzeRequest) -> None:
    """Bible §10: analysis refuses unconfirmed affidavits. Bible §16: bounded input."""
    if not body.affidavit.user_confirmed:
        raise AffidavitNotConfirmedError(
            "Please confirm that the details we read off your papers are right before we "
            "analyse them. Every number in the result is built from those details."
        )

    settings = get_settings()
    if len(body.fixes) > settings.max_fixes:
        raise BadInputError(
            f"That is more than {settings.max_fixes:,} location points. Only the hours "
            f"around the times on the affidavit need to be sent."
        )
    if len(body.household) > settings.max_household:
        raise BadInputError(f"That is more than {settings.max_household} people in one household.")


@router.post("/analyze", response_model=CaseAnalysis, dependencies=[Depends(enforce_rate_limit)])
async def analyze_case(body: AnalyzeRequest) -> CaseAnalysis:
    _guard(body)
    return analyze(body)
