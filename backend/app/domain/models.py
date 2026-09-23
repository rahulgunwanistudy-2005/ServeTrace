"""Every data contract in ServeTrace. Bible §10.

Nothing outside this module may define a shape that crosses a module boundary.
All datetimes are timezone-aware; naive datetimes are rejected at the boundary.
"""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class ServiceMethod(StrEnum):
    PERSONAL = "308_1"
    SUBSTITUTE = "308_2"
    AFFIX_AND_MAIL = "308_4"
    UNKNOWN = "unknown"


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class PersonDescription(BaseModel):
    sex: Literal["male", "female", "unknown"] | None = None
    age_min: int | None = None
    age_max: int | None = None
    height_in_min: int | None = None
    height_in_max: int | None = None
    weight_lb_min: int | None = None
    weight_lb_max: int | None = None
    hair: str | None = None
    raw_text: str | None = None
    """Verbatim description block as extracted from the document."""


class ServiceAttempt(BaseModel):
    at: AwareDatetime
    address: str
    location: LatLng | None = None
    outcome: Literal["served", "affixed", "not_home", "refused", "other"]


class Affidavit(BaseModel):
    index_number: str | None = None
    court: str | None = None
    plaintiff: str | None = None
    defendant_name: str
    server_name: str | None = None
    server_license: str | None = None
    agency_license: str | None = None
    method: ServiceMethod
    served_at: AwareDatetime
    """The claimed completed service: delivery for 308(1)/308(2), affixing for 308(4)."""
    served_address: str
    served_location: LatLng | None = None
    recipient_name: str | None = None
    recipient_relationship: str | None = None
    recipient_description: PersonDescription | None = None
    attempts: list[ServiceAttempt] = []
    """Prior attempts, used for the 308(4) due-diligence check."""
    mailing_date: date | None = None
    mailing_address: str | None = None
    proof_filed_date: date | None = None
    source_sha256: str
    field_confidence: dict[str, float] = {}
    """0..1 per field, from the extractor."""
    user_confirmed: bool = False
    """Analysis refuses unconfirmed affidavits."""


class FixKind(StrEnum):
    VISIT = "visit"
    PATH = "path"
    TRANSACTION = "transaction"
    MANUAL = "manual"


class LocationFix(BaseModel):
    t: AwareDatetime
    t_end: AwareDatetime | None = None
    """Set for VISIT and MANUAL intervals."""
    loc: LatLng
    accuracy_m: float | None = None
    kind: FixKind
    source: str
    label: str | None = None
    """For example "Timeline visit: WORK"."""


class HouseholdMember(BaseModel):
    label: str
    sex: Literal["male", "female", "other"] | None = None
    age: int | None = None
    height_in: int | None = None
    is_defendant: bool = False


class Severity(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    INFO = "info"


class Finding(BaseModel):
    code: str
    """For example "F-PRISM", "F-VISIT", "F-DESC", "R-T1", "R-D1"."""
    severity: Severity
    title: str
    detail: str
    """Plain language, from copy templates."""
    numbers: dict[str, float | str] = {}
    legal_ref: str | None = None
    """An L-id from bible §5."""


class ClaimTier(StrEnum):
    CONTRADICTED = "contradicted"
    CONSISTENT = "consistent"
    NO_DATA = "no_data"
    INCONCLUSIVE = "inconclusive"


class ClaimVerdict(BaseModel):
    claim_ref: str
    """"served_at" or "attempt[i]"."""
    claimed_at: AwareDatetime
    claimed_location: LatLng
    tier: ClaimTier
    nearest_fix_km: float | None = None
    required_speed_kmh: float | None = None
    fixes_used: list[LocationFix] = []


class Deadlines(BaseModel):
    knowledge_date: date | None = None
    judgment_entry_date: date | None = None
    cplr_317_deadline: date | None = None
    cplr_317_outer_limit: date | None = None
    note: str


class AnalyzeRequest(BaseModel):
    affidavit: Affidavit
    fixes: list[LocationFix]
    household: list[HouseholdMember] = []
    knowledge_date: date | None = None
    judgment_entry_date: date | None = None


class CaseAnalysis(BaseModel):
    affidavit: Affidavit
    verdicts: list[ClaimVerdict]
    findings: list[Finding]
    overall: ClaimTier
    deadlines: Deadlines
    params_version: str
    engine_version: str
    generated_at: AwareDatetime


class ServiceRecord(BaseModel):
    server_id: str
    at: AwareDatetime
    loc: LatLng
    address: str | None = None
    case_ref: str | None = None
    outcome: str | None = None
    recipient_desc: str | None = None


class ImpossiblePair(BaseModel):
    a: ServiceRecord
    b: ServiceRecord
    distance_km: float
    minutes: float
    required_speed_kmh: float


class ServerReport(BaseModel):
    server_id: str
    n_records: int
    impossible_pairs: list[ImpossiblePair]
    max_services_per_hour: int
    repeated_descriptions: list[tuple[str, int]]
    risk_rank: int
