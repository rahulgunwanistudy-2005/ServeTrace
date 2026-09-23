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


# --- Extraction (bible §12) -------------------------------------------------------------
#
# The extractor never produces an `Affidavit`. It produces a *draft*: every field optional,
# dates, times and method left as the strings the model returned, and one verbatim
# `evidence_quote` per field. `extraction/validators.py` normalises the strings
# deterministically; the user confirms the result; only then does an `Affidavit` exist.


class AttemptDraft(BaseModel):
    """A prior service attempt as extracted, before normalisation."""

    at_date: str | None = None
    at_time: str | None = None
    at: AwareDatetime | None = None
    """Filled by the validators from `at_date` + `at_time`."""
    address: str | None = None
    location: LatLng | None = None
    outcome: str | None = None


class AffidavitDraft(BaseModel):
    """What came off the document. Nothing here is trusted until the user confirms it.

    Dates, times and `method` stay as free text on purpose. A model that writes
    "June 12, 2025" has to produce a note the user can act on, not a validation failure
    that throws the whole extraction away.
    """

    index_number: str | None = None
    court: str | None = None
    plaintiff: str | None = None
    defendant_name: str | None = None
    server_name: str | None = None
    server_license: str | None = None
    agency_license: str | None = None
    method: str | None = None
    served_date: str | None = None
    served_time: str | None = None
    served_at: AwareDatetime | None = None
    """Filled by the validators: `served_date` + `served_time` localised to America/New_York."""
    served_at_ambiguous: bool = False
    """The local time falls in a DST fold and means two different instants. Bible §11.1."""
    served_address: str | None = None
    served_location: LatLng | None = None
    recipient_name: str | None = None
    recipient_relationship: str | None = None
    recipient_description: PersonDescription | None = None
    attempts: list[AttemptDraft] = []
    mailing_date: str | None = None
    mailing_address: str | None = None
    proof_filed_date: str | None = None
    field_confidence: dict[str, float] = {}
    """0..1 per field name. A missing entry means the extractor offered no opinion."""
    evidence_quotes: dict[str, str] = {}
    """Per field, the verbatim span the value was read from. Also the "exactly as written"
    form of every date and time: the field holds the normalised value, the quote holds the
    words on the page, and the grounding check scores that quote against the text layer."""


class ValidationNote(BaseModel):
    """One deterministic observation about a draft field, shown next to that field."""

    field: str
    level: Literal["info", "warning", "error"]
    message: str


class ExtractionResult(BaseModel):
    """The response of `POST /api/extract`."""

    draft: AffidavitDraft
    notes: list[ValidationNote] = []
    provider: str
    source_sha256: str
    n_pages: int
    has_text_layer: bool
    used_vision: bool
    """True when the pages were sent as images because there was no usable text layer."""


class GeocodeRequest(BaseModel):
    address: str = Field(min_length=3, max_length=200)


class GeocodeResult(BaseModel):
    """A resolved NYC address. `label` is GeoSearch's normalised form of the input."""

    location: LatLng
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["geosearch", "cache"]


class GeocodeResponse(BaseModel):
    """`result` is null when the address could not be resolved inside New York City."""

    result: GeocodeResult | None = None


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
