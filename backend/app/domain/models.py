"""Every data contract in ServeTrace. Bible §10.

Nothing outside this module may define a shape that crosses a module boundary.
All datetimes are timezone-aware; naive datetimes are rejected at the boundary.
"""

import re
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator


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


class PageType(StrEnum):
    """What a page of an uploaded court file is. v1.1, bible §12."""

    AFFIDAVIT_OF_SERVICE = "affidavit_of_service"
    SUMMONS_COMPLAINT = "summons_complaint"
    JUDGMENT = "judgment"
    NOTICE = "notice"
    OTHER = "other"


class FieldEvidence(BaseModel):
    """Where a value was read: the words, the page, and on a text-layer PDF the box."""

    quote: str | None = None
    page: int | None = None
    """0-based page index in the uploaded file."""
    bbox: tuple[float, float, float, float] | None = None
    """PDF points (x0, top, x1, bottom), text-layer documents only."""


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
    agency_name: str | None = None
    """The process serving agency, if the affidavit names one. v1.1: advocate rollups."""
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
    evidence: dict[str, FieldEvidence] = {}
    """v1.1: where on the uploaded file each field was read. Provenance only; nothing in
    the engine reads it. `field_confidence` stays the confidence channel."""


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
    agency_name: str | None = None
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
    evidence: dict[str, FieldEvidence] = {}
    """v1.1: the same quotes with the page they came from and, when the file has a text
    layer, the box around them, so the review screen can point at the words."""
    method_checkbox: str | None = None
    """v1.1: on a form that prints a box per method, the box the extractor saw ticked
    ("308_1", "308_2", "308_4"), or None when the form has no boxes. Only ever compared with
    `method`; never a source of the method by itself."""


class ValidationNote(BaseModel):
    """One deterministic observation about a draft field, shown next to that field."""

    field: str
    level: Literal["info", "warning", "error"]
    message: str


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
    PHOTO = "photo"
    """v1.1: where and when a camera says a photo was taken. Read on the device."""


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
    time_uncertainty_s: int = Field(default=0, ge=0, le=86_400)
    """v1.1: 0 when the time is exact; above 0 when a time zone or clock was assumed.
    The engine only ever widens what the fix could mean by this, never narrows it."""
    tz_assumed: bool = False
    """v1.1: true when the source had no offset and no UTC reading, so the time zone was
    assumed. A contradiction resting only on such fixes is never STRONG (bible §11.1.7)."""


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


# --- Documents (bible §15) ----------------------------------------------------------------
#
# Both documents are built from a `CaseAnalysis` the client already holds. Nothing is
# stored, so there is no case id to hand back for: the analysis travels with the request
# exactly as the fixes travelled with the one that produced it.


class AffiantStatement(BaseModel):
    """What the person signing the draft affidavit has told us, and what they will swear to.

    The three booleans are ticks, not inferences. Each one gates a paragraph that only
    that person is in a position to state — whether papers reached them, whether an
    address is their home, whether notice arrived in time to defend. A paragraph whose
    tick is off is left out of the document entirely rather than hedged, because a sworn
    statement hedged into vagueness is worse for them than a shorter affidavit.
    """

    name: str = Field(min_length=1, max_length=120)
    residence_address: str | None = Field(default=None, max_length=200)
    states_not_served: bool = False
    states_not_my_address: bool = False
    states_no_notice_in_time: bool = False
    """CPLR 317 (L6) turns on this and cannot be offered without it."""
    defense_summary: str | None = Field(default=None, max_length=1000)
    """The meritorious defence L6 also requires, in the person's own words. Never ours."""


class PacketRequest(BaseModel):
    analysis: CaseAnalysis
    fixes: list[LocationFix] = []
    """The windowed fixes that were sent to `/api/analyze`, so the packet can print the
    whole exhibit rather than only the two points the engine leaned on. A packet that
    showed just the decisive records would invite exactly the question it exists to
    answer."""
    map_png_base64: str | None = None
    """The result map, captured in the browser. Validated as a PNG before it is embedded."""
    affiant_name: str | None = Field(default=None, max_length=120)


class DraftAffidavitRequest(BaseModel):
    analysis: CaseAnalysis
    affiant: AffiantStatement


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


# --- Advocate mode I/O (bible §14.6) ------------------------------------------------------
#
# Bible §10 specifies the three shapes the batch engine computes over. These are the three
# it needs at the HTTP boundary: how a spreadsheet's own column names map onto them, what
# happened to a row that could not be used, and what the route answers with.


class AdvocateColumnMapping(BaseModel):
    """Which column of the uploaded file holds each field. Values are header names.

    Two things are required and each may be given two ways, because case-management
    systems export both: a time is either one column or a date column plus a time column,
    and a place is either a coordinate pair or an address to look up.
    """

    server_id: str
    at: str | None = None
    """One column holding the whole date and time."""
    date: str | None = None
    time: str | None = None
    """Or these two, used only when `at` is absent."""
    lat: str | None = None
    lng: str | None = None
    address: str | None = None
    case_ref: str | None = None
    outcome: str | None = None
    recipient_desc: str | None = None

    @property
    def has_time(self) -> bool:
        return bool(self.at) or bool(self.date and self.time)

    @property
    def has_place(self) -> bool:
        return bool(self.lat and self.lng) or bool(self.address)


class RejectedRow(BaseModel):
    """A row that could not be turned into a service record, and why.

    Rejections are part of the answer, not an error path. An advocate is assembling a
    complaint, and a parser that silently drops the eleven rows it could not read hands
    them a report whose denominator is wrong.
    """

    row: int
    """The row number as the spreadsheet shows it: the header is row 1."""
    code: str
    """For example "missing_time", "bad_coordinates", "address_not_found"."""
    reason: str
    """Plain language, naming the column at fault. Never echoes the cell's contents."""


class AdvocateStats(BaseModel):
    rows_read: int
    records: int
    rejected: int
    servers: int
    addresses_geocoded: int
    records_returned: int
    """How many filings came back for the map. Fewer than `records` on very large files."""
    params_version: str
    engine_version: str
    generated_at: AwareDatetime


class AdvocateAnalysis(BaseModel):
    reports: list[ServerReport]
    """In risk order, worst first."""
    rejected: list[RejectedRow]
    records: list[ServiceRecord] = []
    """The filings themselves, so the map can draw a server's whole week.

    A `ServerReport` carries only the pairs that do not fit, and a map of those alone
    would imply that four flagged steps were the server's entire output. The cluster of
    ordinary doors is what makes the outlier mean something, so the records come back too.

    Whole servers at a time, highest-ranked first, until the cap is reached — so any
    server the map can open, it can draw completely, and the rest keep their row in the
    table and say plainly that their day is not on the map.
    """
    mapping: AdvocateColumnMapping
    """Which column was read as which field, echoed back with the report.

    The same discipline as `params_version` on a `CaseAnalysis`: a number is only
    reproducible alongside what produced it, and "the times came out of the column headed
    `filed_on`" is exactly the kind of thing an advocate needs to be able to check when
    somebody disputes the report.
    """
    stats: AdvocateStats


# --- v1.1: court files, advocate batches, usage counts and leads --------------------------


class ExtractedAffidavit(BaseModel):
    """One affidavit of service found in an uploaded file, as a draft the user confirms.

    The spec for v1.1 sketched `ExtractionResult.affidavits` as confirmed `Affidavit`s.
    It is drafts here, deliberately: an `Affidavit` requires a service time, an address
    and a method, and a reader that could not find one must still hand back everything
    else it did find rather than fail the whole file. The user's confirmation is what
    turns a draft into an `Affidavit`, exactly as in v1.0.
    """

    draft: AffidavitDraft
    notes: list[ValidationNote] = []
    pages: list[int] = []
    """0-based pages of the uploaded file this affidavit was read from."""


class PagePreview(BaseModel):
    """A small picture of one page of the upload, handed back so the review screen can show
    the user their own document. Made in memory and never kept. `width` and `height` are
    in the same units as `FieldEvidence.bbox` (PDF points for a PDF, pixels for a photo)."""

    index: int
    width: float
    height: float
    image: str
    """`data:image/jpeg;base64,...`, at most 1000 px on the long edge."""


class ExtractionResult(BaseModel):
    """The response of `POST /api/extract` (v1.1): every page classified, every affidavit
    found in the file as a draft, and the judgment's entry date when the file carries one.
    """

    page_types: list[PageType]
    affidavits: list[ExtractedAffidavit] = []
    judgment_entry_date: date | None = None
    """A draft like every other extracted value: shown to the user, never used unconfirmed."""
    judgment_evidence: FieldEvidence | None = None
    notes: list[ValidationNote] = []
    """File-level observations: pages skipped, classification fallbacks."""
    provider: str
    source_sha256: str
    n_pages: int
    has_text_layer: bool
    used_vision: bool
    previews: list[PagePreview] = []


class RuleRate(BaseModel):
    """How often one NY rule fired across a batch, out of the affidavits it applies to."""

    rule_code: str
    flagged: int
    applicable: int
    rate: float


class AgencyReport(BaseModel):
    agency_key: str
    """Normalized agency licence, else normalized agency name, else "unknown"."""
    agency_display: str
    n_affidavits: int
    servers: list[str]
    impossible_pairs: int
    max_services_per_hour: int
    repeated_descriptions: list[tuple[str, int]]
    rule_rates: list[RuleRate]
    risk_rank: int


class BatchRejection(BaseModel):
    """An affidavit that was in the batch but not analysed, and why. Never its contents."""

    index: int
    """Position in the submitted list, 0-based."""
    code: str
    reason: str


class AffidavitRuleFlag(BaseModel):
    """One batch rule against one affidavit it applies to: the row behind every rate."""

    index: int
    """Position of the affidavit in the submitted batch, 0-based."""
    case_ref: str | None
    server_id: str
    agency_key: str
    rule_code: str
    flagged: bool


class BatchReport(BaseModel):
    servers: list[ServerReport]
    agencies: list[AgencyReport]
    rule_rates: list[RuleRate]
    """Batch-wide."""
    n_affidavits: int
    n_records: int
    rejected: list[BatchRejection]
    records: list[ServiceRecord] = []
    """The service records the batch produced, so the map can draw a server's day."""
    flags: list[AffidavitRuleFlag] = []
    """Every (affidavit, applicable rule) pair, flagged or not. The rates are counts of these."""
    params_version: str
    engine_version: str
    app_version: str
    generated_at: AwareDatetime


class BatchReportRequest(BaseModel):
    """The advocate report PDF, rendered from a report the browser already holds."""

    report: BatchReport
    map_images: dict[str, str] = {}
    """Agency key to a PNG of that agency's day, captured in the browser. Optional."""
    unconfirmed: int = Field(default=0, ge=0)
    """Affidavits the person left unconfirmed in the queue; listed, never analysed."""
    failed: int = Field(default=0, ge=0)
    """Files that could not be read at all."""


class UsageEventKind(StrEnum):
    CHECK_COMPLETED = "check_completed"
    PACKET_DOWNLOADED = "packet_downloaded"
    ADVOCATE_BATCH = "advocate_batch"


_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
"""Strict enough to catch a typo, loose enough for any real address. `EmailStr` would need
`email-validator`, which is not an approved dependency."""


class LeadIn(BaseModel):
    """A contact request from the /attorneys page. Never carries case data."""

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    organization: str | None = Field(default=None, max_length=200)
    role: Literal["consumer_attorney", "legal_aid", "court_staff", "researcher", "other"]
    message: str | None = Field(default=None, max_length=2000)
    consent: Literal[True]
    website: str = Field(default="", max_length=200)
    """The honeypot. A person never sees it, so a person never fills it in."""

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        value = value.strip()
        if not _EMAIL.match(value):
            raise ValueError("not an email address")
        return value


class UsageTotals(BaseModel):
    kind: UsageEventKind
    real: int
    demo: int


class UsageStats(BaseModel):
    """Day-level counters only. No timestamps finer than a day exist to report."""

    enabled: bool
    since: date | None
    totals: list[UsageTotals]
