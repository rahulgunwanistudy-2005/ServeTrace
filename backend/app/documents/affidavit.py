"""The Draft Supporting Affidavit. Bible §15.

This attaches to the Order to Show Cause form the court provides; it does not replace it.

**The whole module is a selection problem.** Every sentence lives in `documents/copy.py`.
What happens here is deciding which of them belong in this person's document, in what
order, and with which numbers — and, more importantly, which do not. Three rules govern
that, and they are the reason the code below is a table rather than a narrative:

1. **A paragraph exists only if something the user confirmed supports it.** The three
   first-person statements — that no papers arrived, that the address is not their home,
   that notice never reached them in time — are ticks on a form. Unticked, the paragraph
   is *absent*, never softened into "I do not recall being served". A hedged sworn
   statement is worse for the person signing it than a shorter affidavit.
2. **Only STRONG and MODERATE findings become paragraphs.** An INFO finding is context for
   somebody reading their own result; it is not a fact worth swearing to.
3. **A finding code with no paragraph in the table below produces no paragraph.** New
   codes appear as the engine grows, and the failure mode to design against is a rule
   added in some later session quietly writing prose into a document somebody signs under
   oath. Silence is the safe default here, and `test_affidavit.py` asserts that every
   code the engine can emit at STRONG or MODERATE is either in the table or listed as
   deliberately excluded.

No LLM. Ever (bible §15).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from app.documents import copy
from app.documents.deadlines import effective_deadline
from app.documents.render import render_pdf
from app.domain.models import (
    AffiantStatement,
    Affidavit,
    CaseAnalysis,
    ClaimVerdict,
    Finding,
    LocationFix,
    ServiceMethod,
    Severity,
)
from app.geo.distance import haversine_km

TEMPLATE: Final = "affidavit.html.j2"

MAIN_CLAIM: Final = "served_at"

PARAGRAPH_SEVERITIES: Final = (Severity.STRONG, Severity.MODERATE)

HANDLED_CODES: Final = frozenset(
    {"F-VISIT", "F-PRISM", "F-DESC", "R-T1", "R-T2", "R-T3", "R-D1", "R-D2"}
)
"""The codes `_paragraph_for` writes a paragraph for. Declared as well as matched on,
because a `match` statement cannot be asked what it covers, and a test that cannot ask is
a test that cannot notice a new rule arriving."""

INFO_ONLY_CODES: Final = frozenset({"F-NEAR", "F-NODATA", "F-CLOCK", "F-NOGEO", "R-M1"})
"""Codes the engine only ever raises at INFO. They are context for somebody reading their
own result and are filtered out before `_paragraph_for` is ever reached; they are listed
so that one of them being promoted to MODERATE shows up as a failing test rather than as a
new sentence in a sworn document.

`R-M1` is the interesting one: the affidavit does not say clearly which kind of service
this was. There is no paragraph for it because there is nothing to swear to — the person
cannot testify about what the server meant to write — and because the timing rules that
depend on the method were skipped, so the document has nothing to say about them either."""

EXCLUDED_CODES: Final = frozenset({"F-CONFLICT", "R-L1", "R-L2", "R-L3"})
"""Codes that reach STRONG or MODERATE and still get no paragraph, on purpose.

`F-CONFLICT` is the engine saying the person's own data disagrees with itself. It is INFO
today and would be a strange thing to swear to at any severity, so it is named here rather
than left to the "unknown code" path — the difference between a decision and an oversight
is whether it is written down.

`R-L1`, `R-L2` and `R-L3` are the licence checks against the City's register. They are
useful to a person and to the Help Center, and they do not belong in a sworn document.
The register is a snapshot of today and carries no status history, so it cannot establish
what a licence's standing was on the day of the service; the findings say so in as many
words, and one of them turns on a number that could as easily be a typo. Swearing to
"the server was not licensed" on the strength of a lookup is the overclaim this whole
module is built to refuse. The person can raise it; they should not attest to it.
"""


@dataclass(frozen=True, slots=True)
class Paragraph:
    """One numbered paragraph, and where its authority comes from.

    `source` is an L-id from bible §5, a finding code, or `"user"` for something only the
    person signing can state. It is not printed — a court document does not carry our
    rule codes — but it is what the tests assert on, so that "every paragraph traces to
    §5 or to a finding" is a property the suite checks rather than a claim in a docstring.
    """

    text: str
    source: str


def _verdict_for(analysis: CaseAnalysis, claim_ref: str) -> ClaimVerdict | None:
    return next((v for v in analysis.verdicts if v.claim_ref == claim_ref), None)


def _claim_address(affidavit: Affidavit, claim_ref: str) -> str:
    if claim_ref == MAIN_CLAIM:
        return affidavit.served_address
    try:
        return affidavit.attempts[int(claim_ref.removeprefix("attempt[").removesuffix("]"))].address
    except (ValueError, IndexError):  # pragma: no cover - claim_ref comes from the engine
        return affidavit.served_address


def _anchor_fix(verdict: ClaimVerdict, distance_km: float) -> LocationFix | None:
    """Which of the fixes the engine used is the one a finding's distance refers to.

    The distance is on the finding; the timestamp behind it is not, and a paragraph that
    quotes a distance without the time it was recorded is not a fact anybody can check.
    Rather than widen the engine's output for this document's convenience, the fix is
    identified by the number it produced: among the fixes that verdict used, the one whose
    distance from the claimed point is closest to the distance quoted.
    """
    if not verdict.fixes_used:
        return None
    point = verdict.claimed_location
    return min(
        verdict.fixes_used,
        key=lambda fix: abs(haversine_km(point, fix.loc) - distance_km),
    )


def _location_paragraph(analysis: CaseAnalysis, finding: Finding, builder: str) -> Paragraph | None:
    """F-VISIT and F-PRISM, in the first person, with the numbers the engine measured."""
    claim_ref = str(finding.numbers.get("claim", MAIN_CLAIM))
    verdict = _verdict_for(analysis, claim_ref)
    distance = finding.numbers.get("distance_km")
    if verdict is None or not isinstance(distance, int | float):
        return None

    address = _claim_address(analysis.affidavit, claim_ref)
    when = verdict.claimed_at

    # An attempt is a different assertion from the service, and reads as one. It gets the
    # plain form: the affidavit records an attempt at this time, my records say this.
    if claim_ref != MAIN_CLAIM:
        return Paragraph(copy.para_attempt(when, float(distance), address), finding.code)

    anchor = _anchor_fix(verdict, float(distance))
    if builder == "visit" and anchor is not None and anchor.t_end is not None:
        return Paragraph(
            copy.para_visit(when, float(distance), address, anchor.t, anchor.t_end),
            finding.code,
        )

    speed = finding.numbers.get("required_speed_kmh")
    minutes = finding.numbers.get("minutes")
    if isinstance(speed, int | float) and isinstance(minutes, int | float) and anchor is not None:
        return Paragraph(
            copy.para_prism(when, float(distance), address, anchor.t, float(minutes), float(speed)),
            finding.code,
        )

    # No usable gap: the record and the sworn moment are inside the same minute, so there
    # is no journey to describe and none is described.
    return Paragraph(copy.para_simultaneous(when, float(distance), address), finding.code)


def _paragraph_for(analysis: CaseAnalysis, finding: Finding) -> Paragraph | None:
    method = analysis.affidavit.method.value
    numbers = finding.numbers

    match finding.code:
        case "F-VISIT":
            return _location_paragraph(analysis, finding, "visit")
        case "F-PRISM":
            return _location_paragraph(analysis, finding, "prism")
        case "F-DESC":
            described = numbers.get("described")
            if not isinstance(described, str):
                return None
            return Paragraph(copy.para_description(described, method), finding.code)
        case "R-T1":
            return Paragraph(copy.para_mailing_missing(method), finding.code)
        case "R-T2":
            return Paragraph(
                copy.para_mailing_late(_int(numbers, "days"), _int(numbers, "limit_days")),
                finding.code,
            )
        case "R-T3":
            return Paragraph(
                copy.para_proof_late(_int(numbers, "days"), _int(numbers, "limit_days")),
                finding.code,
            )
        case "R-D1":
            return Paragraph(
                copy.para_diligence(_int(numbers, "attempts"), _int(numbers, "distinct_days")),
                finding.code,
            )
        case "R-D2":
            return Paragraph(
                copy.para_attempts_contradicted(_int(numbers, "attempts_contradicted")),
                finding.code,
            )
        case _:
            return None


def _int(numbers: dict[str, float | str], key: str) -> int:
    value = numbers.get(key, 0)
    return int(float(value)) if isinstance(value, int | float) else 0


def cplr_317_eligible(analysis: CaseAnalysis, affiant: AffiantStatement, today: date) -> bool:
    """Bible §5 L6, all three conditions, and never on arithmetic alone.

    L6 is available to someone served *other than by personal delivery*, who did not
    personally receive notice in time to defend, within one year of learning of the
    judgment and five years of its entry. The first is a fact about the affidavit, the
    second is a statement only they can make, and the third is arithmetic.

    An unknown deadline is not a passed one: when neither date was given there is nothing
    to be out of time against, and dropping the ground because a form field was blank
    would cost the person a statutory route over a missing input.
    """
    if analysis.affidavit.method is ServiceMethod.PERSONAL:
        return False
    if not affiant.states_no_notice_in_time:
        return False
    deadline = effective_deadline(analysis.deadlines)
    return deadline is None or deadline >= today


def build_paragraphs(
    analysis: CaseAnalysis, affiant: AffiantStatement, today: date | None = None
) -> list[Paragraph]:
    affidavit = analysis.affidavit
    method = affidavit.method
    when = today or copy.local(analysis.generated_at).date()
    paragraphs: list[Paragraph] = [
        Paragraph(copy.para_identity(affiant.name, affiant.residence_address), "user")
    ]

    if affiant.name.strip() != affidavit.defendant_name.strip():
        paragraphs.append(Paragraph(copy.para_named_differently(affidavit.defendant_name), "user"))

    paragraphs.append(
        Paragraph(
            copy.para_affidavit_of_service(
                affidavit.served_at,
                affidavit.served_address,
                method.value,
                affidavit.server_name,
            ),
            _method_ref(method),
        )
    )

    if affiant.states_not_served:
        paragraphs.append(Paragraph(copy.para_not_served(affidavit.served_at), "user"))

    # Only 308(2) and 308(4) turn on the address being the person's dwelling (L2, L3).
    # After personal delivery the statement is true and does no work, and a sworn
    # paragraph that does no work is noise in a document a judge has to read.
    if affiant.states_not_my_address and method is not ServiceMethod.PERSONAL:
        paragraphs.append(
            Paragraph(copy.para_not_my_address(affidavit.served_address), _method_ref(method))
        )

    from_findings: list[Paragraph] = []
    for finding in analysis.findings:
        if finding.severity not in PARAGRAPH_SEVERITIES or finding.code in EXCLUDED_CODES:
            continue
        paragraph = _paragraph_for(analysis, finding)
        if paragraph is not None:
            from_findings.append(paragraph)

    # The records paragraph introduces the location history as support, so it is written
    # only where the location history *is* support. Where the records place this person at
    # the address at the time sworn to, annexing them and pointing a judge at them would
    # hand the other side its own exhibit. Bible §6 says report a consistent result
    # honestly; honestly does not mean filing it against yourself.
    sources = _sources_sentence(analysis) if _has_location_paragraph(from_findings) else None
    if sources is not None:
        paragraphs.append(Paragraph(copy.para_records_intro(sources), "user"))

    paragraphs.extend(from_findings)

    if from_findings:
        paragraphs.append(Paragraph(copy.PARA_PACKET, "user"))
    paragraphs.append(Paragraph(copy.PARA_RELIEF_5015, "L5"))

    if cplr_317_eligible(analysis, affiant, when):
        paragraphs.append(Paragraph(copy.para_317(method.value, affiant.defense_summary), "L6"))
        deadline = effective_deadline(analysis.deadlines)
        if deadline is not None:
            paragraphs.append(Paragraph(copy.para_317_deadline(deadline), "L6"))

    paragraphs.append(Paragraph(copy.PARA_TRAVERSE, "L5"))
    paragraphs.append(Paragraph(copy.PARA_STAY, "L5"))
    paragraphs.append(Paragraph(copy.PARA_GPS, "L7"))
    return paragraphs


LOCATION_CODES: Final = frozenset({"F-VISIT", "F-PRISM"})


def _has_location_paragraph(paragraphs: list[Paragraph]) -> bool:
    return any(p.source in LOCATION_CODES for p in paragraphs)


def annexes_packet(
    analysis: CaseAnalysis, affiant: AffiantStatement, today: date | None = None
) -> bool:
    """Whether this document annexes the Evidence Packet as Exhibit B.

    The exhibit list has to agree with the paragraphs: a document that lists an exhibit no
    paragraph refers to is a document somebody has to explain at a hearing.
    """
    return any(
        p.source.startswith(("F-", "R-")) for p in build_paragraphs(analysis, affiant, today)
    )


def _method_ref(method: ServiceMethod) -> str:
    return {
        ServiceMethod.PERSONAL: "L1",
        ServiceMethod.SUBSTITUTE: "L2",
        ServiceMethod.AFFIX_AND_MAIL: "L3",
    }.get(method, "L1")


def _sources_sentence(analysis: CaseAnalysis) -> str | None:
    """Which kinds of record the person's data actually contained, named plainly."""
    kinds = {
        copy.FIX_KIND_IN_SENTENCE[fix.kind.value]
        for verdict in analysis.verdicts
        for fix in verdict.fixes_used
    }
    return copy.fmt_list(sorted(kinds)) if kinds else None


def affidavit_context(
    analysis: CaseAnalysis, affiant: AffiantStatement, today: date | None = None
) -> dict[str, Any]:
    affidavit = analysis.affidavit
    return {
        "title": copy.AFFIDAVIT_TITLE,
        "draft_mark": copy.DRAFT_MARK,
        "disclaimer": copy.DISCLAIMER,
        "note": copy.AFFIDAVIT_NOTE,
        "preamble": copy.AFFIDAVIT_PREAMBLE,
        "state_county": copy.STATE_COUNTY,
        "case": {
            "court": affidavit.court,
            "index_number": affidavit.index_number,
            "plaintiff": affidavit.plaintiff,
            "defendant": affidavit.defendant_name,
        },
        "affiant_name": affiant.name,
        "paragraphs": [p.text for p in build_paragraphs(analysis, affiant, today)],
        "wherefore": copy.PARA_WHEREFORE,
        "exhibits": [
            {"letter": letter, "text": text}
            for letter, text in copy.EXHIBITS
            if letter != "B" or annexes_packet(analysis, affiant, today)
        ],
        "signature_label": copy.SIGNATURE_LABEL,
        "notary_block": copy.NOTARY_BLOCK,
        "notary_label": copy.NOTARY_LABEL,
        "generated": copy.generated_line(
            analysis.generated_at, analysis.engine_version, analysis.params_version
        ),
        "generated_iso": copy.local(analysis.generated_at).isoformat(),
        "product": copy.PRODUCT,
    }


def build_draft_affidavit(
    analysis: CaseAnalysis, affiant: AffiantStatement, today: date | None = None
) -> bytes:
    return render_pdf(TEMPLATE, affidavit_context(analysis, affiant, today))


__all__ = [
    "EXCLUDED_CODES",
    "HANDLED_CODES",
    "INFO_ONLY_CODES",
    "LOCATION_CODES",
    "Paragraph",
    "affidavit_context",
    "annexes_packet",
    "build_draft_affidavit",
    "build_paragraphs",
    "cplr_317_eligible",
]
