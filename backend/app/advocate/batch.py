"""A batch of confirmed affidavits in, servers and agencies ranked out. Build prompt §6.3.

Advocate mode v1.0 read a spreadsheet of service records. The attorney edition reads the
affidavits themselves — a folder of them, read in the browser one at a time, each confirmed
by a person — and asks two more questions of them:

- **How often does each New York rule fire?** R-T1, R-T2, R-T3, R-D1 and R-M1 are run per
  affidavit exactly as the defendant flow runs them (`engine/rules_ny.py`, unchanged), and
  counted as *flagged out of applicable*. A rate over every affidavit would be meaningless:
  a missing mailing cannot be flagged on a personal service, which needs none. R-D2 is
  left out: it needs a defendant's own location data, which a batch does not have.
- **Which agency?** Servers work for agencies, and an agency is what a complaint names.
  Affidavits are grouped by the agency's licence number where it was printed, else its
  normalised name, else "unknown"; each agency gets the server patterns of its own
  filings and its own rule rates.

Nothing here is new physics or new law. The server patterns are `patterns.py`'s and the
rules are `rules_ny.py`'s; this module only groups and counts.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from app.advocate.ingest import records_from_affidavits
from app.advocate.patterns import analyze_servers, repeated_descriptions
from app.config import APP_VERSION, ENGINE_VERSION
from app.domain.models import (
    Affidavit,
    AffidavitRuleFlag,
    AgencyReport,
    BatchRejection,
    BatchReport,
    RuleRate,
    ServiceMethod,
    ServiceRecord,
)
from app.engine.params import PARAMS_VERSION, EngineParams
from app.engine.rules_ny import MAILING_METHODS, check_rules
from app.extraction.validators import agency_key as name_key
from app.licences.registry import normalise as licence_key

UNKNOWN_AGENCY: Final = "unknown"


def _mails(a: Affidavit) -> bool:
    return a.method in MAILING_METHODS


APPLICABLE: Final[dict[str, Callable[[Affidavit], bool]]] = {
    "R-T1": _mails,
    "R-T2": lambda a: _mails(a) and a.mailing_date is not None,
    "R-T3": lambda a: _mails(a) and a.proof_filed_date is not None,
    "R-D1": lambda a: a.method is ServiceMethod.AFFIX_AND_MAIL,
    "R-M1": lambda a: True,
}
"""When each rule *can* fire, mirroring the guard at the top of each rule in `rules_ny.py`.

Kept beside the rules' own guards rather than inferred from them, so that the denominator
of a rate is something a reader can check against the statute: R-T2 is about the gap
between delivery and mailing, so an affidavit with no mailing date is not in its
denominator (R-T1 is the rule that counts those)."""

BATCH_RULES: Final = tuple(APPLICABLE)


def agency_of(affidavit: Affidavit) -> tuple[str, str]:
    """(key, display) for the agency an affidavit names. Licence first, then name.

    The licence is the stronger identifier: the same agency is "Ironvale Attorney Service
    Corp." on one affidavit and "IRONVALE ATTORNEY SVC CORP" on another, but its licence
    number does not change. Keys are prefixed by kind so a licence can never collide with a
    name that happens to be digits.
    """
    display = (affidavit.agency_name or "").strip()
    number = licence_key(affidavit.agency_license)
    if number:
        return f"lic:{number}", display or f"Agency licence {number}"
    name = name_key(affidavit.agency_name)
    if name:
        return f"name:{name}", display
    return UNKNOWN_AGENCY, "Agency not named"


def rule_flags(index: int, affidavit: Affidavit, params: EngineParams) -> list[AffidavitRuleFlag]:
    """One row per batch rule that applies to this affidavit: flagged or not.

    `verdicts` is empty because a batch has no defendant's location data; that is exactly
    why R-D2 is not a batch rule.
    """
    fired = {finding.code for finding in check_rules(affidavit, [], params)}
    agency, _ = agency_of(affidavit)
    return [
        AffidavitRuleFlag(
            index=index,
            case_ref=affidavit.index_number,
            server_id=_server_id(affidavit),
            agency_key=agency,
            rule_code=code,
            flagged=code in fired,
        )
        for code, applies in APPLICABLE.items()
        if applies(affidavit)
    ]


def rates(flags: list[AffidavitRuleFlag]) -> list[RuleRate]:
    """Flagged out of applicable, per rule, in the rules' own order. Rules that applied to
    nothing are left out rather than reported as 0 of 0."""
    flagged: dict[str, int] = defaultdict(int)
    applicable: dict[str, int] = defaultdict(int)
    for flag in flags:
        applicable[flag.rule_code] += 1
        flagged[flag.rule_code] += int(flag.flagged)
    return [
        RuleRate(
            rule_code=code,
            flagged=flagged[code],
            applicable=applicable[code],
            rate=round(flagged[code] / applicable[code], 4),
        )
        for code in BATCH_RULES
        if applicable[code]
    ]


def _server_id(affidavit: Affidavit) -> str:
    """The same key `records_from_affidavits` groups by, so rows and records agree."""
    return (affidavit.server_license or affidavit.server_name or "").strip()


@dataclass(slots=True)
class _Agency:
    display: str
    affidavits: list[int]
    records: list[ServiceRecord]


def _rate_of(rule_rates: list[RuleRate], code: str) -> float:
    return next((r.rate for r in rule_rates if r.rule_code == code), 0.0)


def _agency_risk_key(report: AgencyReport) -> tuple[int, float, int, int, str]:
    """Build prompt §6.3: impossible pairs, then the R-T2 rate, then repeated descriptions.

    R-T2 is the one rate in the ranking because it is the strong timing rule: a mailing
    more than twenty days from delivery is outside what CPLR 308 allows, where a missing
    mailing (R-T1) may only be a page that was not uploaded. After those three, the total
    number of rule flags, so that an agency with flags never ranks below a clean one on
    the spelling of its name; the key is the last tiebreak, so a printed ranking is stable.
    """
    return (
        -report.impossible_pairs,
        -_rate_of(report.rule_rates, "R-T2"),
        -len(report.repeated_descriptions),
        -sum(rate.flagged for rate in report.rule_rates),
        report.agency_key,
    )


def analyze_batch(affidavits: list[Affidavit], params: EngineParams) -> BatchReport:
    """Every confirmed affidavit through the rules and the server patterns, rolled up."""
    rejected: list[BatchRejection] = []
    kept: list[tuple[int, Affidavit]] = []
    for index, affidavit in enumerate(affidavits):
        if not affidavit.user_confirmed:
            rejected.append(
                BatchRejection(
                    index=index,
                    code="unconfirmed",
                    reason="Nobody confirmed what was read off this affidavit, so it was left "
                    "out of the analysis.",
                )
            )
            continue
        if not _server_id(affidavit):
            rejected.append(
                BatchRejection(
                    index=index,
                    code="missing_server",
                    reason="This affidavit names no process server and no licence number, so "
                    "its filings cannot be grouped with anyone's.",
                )
            )
            continue
        kept.append((index, affidavit))

    flags = [flag for index, a in kept for flag in rule_flags(index, a, params)]
    records, _ = records_from_affidavits([a for _, a in kept])
    servers = analyze_servers(records, params)

    agencies: dict[str, _Agency] = {}
    for index, affidavit in kept:
        key, display = agency_of(affidavit)
        group = agencies.setdefault(key, _Agency(display=display, affidavits=[], records=[]))
        group.display = group.display or display
        group.affidavits.append(index)
        mine, _ = records_from_affidavits([affidavit])
        group.records.extend(mine)

    reports: list[AgencyReport] = []
    for key, group in agencies.items():
        own = analyze_servers(group.records, params)
        ordered = sorted(group.records, key=lambda r: (r.at, r.address or "", r.case_ref or ""))
        members = set(group.affidavits)
        reports.append(
            AgencyReport(
                agency_key=key,
                agency_display=group.display,
                n_affidavits=len(group.affidavits),
                servers=sorted({report.server_id for report in own}),
                impossible_pairs=sum(len(report.impossible_pairs) for report in own),
                max_services_per_hour=max(
                    (report.max_services_per_hour for report in own), default=0
                ),
                repeated_descriptions=repeated_descriptions(ordered, params),
                rule_rates=rates([f for f in flags if f.index in members]),
                risk_rank=0,
            )
        )
    reports.sort(key=_agency_risk_key)
    ranked = [r.model_copy(update={"risk_rank": rank}) for rank, r in enumerate(reports, 1)]

    return BatchReport(
        servers=servers,
        agencies=ranked,
        rule_rates=rates(flags),
        flags=flags,
        n_affidavits=len(affidavits),
        n_records=len(records),
        rejected=rejected,
        records=records,
        params_version=PARAMS_VERSION,
        engine_version=ENGINE_VERSION,
        app_version=APP_VERSION,
        generated_at=datetime.now(UTC),
    )
