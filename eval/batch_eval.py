"""The attorney-edition batch, scored against the generator's answer key. Build prompt §7.

`fixtures/advocate_batch/` holds 60 synthetic affidavits with patterns injected on purpose
and an answer key (`expected.json`) written by the generator, never by the code under
test. This scores `analyze_batch` against it:

- **Rule flags**, per rule: which affidavits were flagged, against which ones the generator
  built to trip it. Precision and recall over affidavit positions.
- **Impossible pairs**, per server, counted against the key.
- **The repeated description**: the right server, at the right number of addresses.
- **The clean agency** has no flags of any kind and ranks last.
- **Rule-rate correctness.** Each rate is flagged out of *applicable*, and the denominator is
  the part a reader can most easily get wrong. It is recomputed here independently, from
  the raw JSON and bible §11.3's table, without importing the batch module's own
  `APPLICABLE`, and the flagged count comes from the answer key, not from the engine. Every
  rate the report prints has to equal that.

Deterministic: the fixture is committed and nothing here reads a clock or a random source.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from app.advocate.batch import analyze_batch
from app.domain.models import Affidavit, BatchReport
from app.engine.params import PARAMS

FIXTURE: Final = Path(__file__).resolve().parents[1] / "fixtures" / "advocate_batch"

MAILING: Final = ("308_2", "308_4")


def independent_applicable(row: dict[str, Any]) -> list[str]:
    """Bible §11.3, read straight off the table, for one affidavit as raw JSON.

    R-T1 applies to every mailing method. R-T2 measures a gap, so it needs a mailing date;
    R-T3 measures a filing, so it needs a filing date. R-D1 is affix-and-mail only. R-M1
    applies to everything. R-D2 needs the defendant's own data, which a batch has none of.
    """
    method = row.get("method")
    mails = method in MAILING
    rules = []
    if mails:
        rules.append("R-T1")
    if mails and row.get("mailing_date"):
        rules.append("R-T2")
    if mails and row.get("proof_filed_date"):
        rules.append("R-T3")
    if method == "308_4":
        rules.append("R-D1")
    rules.append("R-M1")
    return rules


@dataclass
class Scores:
    expected: int = 0
    predicted: int = 0
    true_positives: int = 0

    @property
    def precision(self) -> float | None:
        return round(self.true_positives / self.predicted, 4) if self.predicted else None

    @property
    def recall(self) -> float | None:
        return round(self.true_positives / self.expected, 4) if self.expected else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected": self.expected,
            "predicted": self.predicted,
            "true_positives": self.true_positives,
            "precision": self.precision,
            "recall": self.recall,
        }


@dataclass
class BatchEval:
    n_affidavits: int = 0
    rules: dict[str, Scores] = field(default_factory=dict)
    pairs: Scores = field(default_factory=Scores)
    repeated_description_found: bool = False
    clean_agency_clean: bool = False
    clean_agency_last: bool = False
    rates_checked: int = 0
    rates_wrong: list[dict[str, Any]] = field(default_factory=list)

    @property
    def all_flags_right(self) -> bool:
        return all(s.true_positives == s.expected == s.predicted for s in self.rules.values())


def _load() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = json.loads((FIXTURE / "affidavits.json").read_text(encoding="utf-8"))
    truth = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    return rows, truth


def score(rows: list[dict[str, Any]], truth: dict[str, Any], report: BatchReport) -> BatchEval:
    result = BatchEval(n_affidavits=len(rows))
    expected_flags: dict[str, set[int]] = {
        code: set(indexes) for code, indexes in truth["flagged"].items()
    }

    for code in sorted({f.rule_code for f in report.flags} | set(expected_flags)):
        predicted = {f.index for f in report.flags if f.rule_code == code and f.flagged}
        wanted = expected_flags.get(code, set())
        result.rules[code] = Scores(
            expected=len(wanted), predicted=len(predicted), true_positives=len(predicted & wanted)
        )

    name_of = {
        (row.get("server_license") or row.get("server_name") or "").strip(): row["server_name"]
        for row in rows
    }
    found_pairs = {
        name_of.get(s.server_id, s.server_id): len(s.impossible_pairs) for s in report.servers
    }
    wanted_pairs: dict[str, int] = truth["impossible_pairs"]
    for server in set(found_pairs) | set(wanted_pairs):
        got, want = found_pairs.get(server, 0), wanted_pairs.get(server, 0)
        result.pairs.expected += want
        result.pairs.predicted += got
        result.pairs.true_positives += min(got, want)

    repeated = truth["repeated_description"]
    result.repeated_description_found = any(
        name_of.get(s.server_id, s.server_id) == repeated["server"]
        and any(count == repeated["addresses"] for _, count in s.repeated_descriptions)
        for s in report.servers
    )

    clean = [a for a in report.agencies if a.agency_display == truth["clean_agency"]]
    if clean:
        agency = clean[0]
        result.clean_agency_clean = (
            agency.impossible_pairs == 0
            and not agency.repeated_descriptions
            and all(rate.flagged == 0 for rate in agency.rule_rates)
        )
        result.clean_agency_last = agency.risk_rank == max(a.risk_rank for a in report.agencies)

    applicable: dict[str, int] = {}
    for row in rows:
        for code in independent_applicable(row):
            applicable[code] = applicable.get(code, 0) + 1
    printed = {rate.rule_code: rate for rate in report.rule_rates}
    for code in sorted(set(applicable) | set(printed)):
        want_flagged = len(expected_flags.get(code, set()))
        want_applicable = applicable.get(code, 0)
        rate = printed.get(code)
        result.rates_checked += 1
        shown = (rate.flagged, rate.applicable) if rate else (0, 0)
        if shown != (want_flagged, want_applicable):
            result.rates_wrong.append(
                {"rule": code, "printed": list(shown), "expected": [want_flagged, want_applicable]}
            )
    return result


def run(out: Path | None = None) -> BatchEval:
    rows, truth = _load()
    report = analyze_batch([Affidavit.model_validate(r) for r in rows], PARAMS)
    result = score(rows, truth, report)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "advocate_batch.json").write_text(
            json.dumps(as_json(result), indent=1, sort_keys=True) + "\n"
        )
    return result


def published_figures(result: BatchEval) -> dict[str, Any]:
    return {
        "n_affidavits": result.n_affidavits,
        "rules": {code: s.as_dict() for code, s in result.rules.items()},
        "impossible_pairs": result.pairs.as_dict(),
        "repeated_description_found": result.repeated_description_found,
        "clean_agency_clean": result.clean_agency_clean,
        "clean_agency_last": result.clean_agency_last,
        "rates_checked": result.rates_checked,
        "rates_wrong": len(result.rates_wrong),
    }


def as_json(result: BatchEval) -> dict[str, Any]:
    return {**published_figures(result), "rates_wrong_detail": result.rates_wrong}


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def format_report(result: BatchEval) -> str:
    lines = [f"Advocate batch (v1.1), {result.n_affidavits} affidavits against the answer key"]
    for code, s in result.rules.items():
        lines.append(
            f"  {code:<6} flagged {s.predicted:<3} expected {s.expected:<3} "
            f"precision {_pct(s.precision):<5} recall {_pct(s.recall)}"
        )
    p = result.pairs
    lines += [
        f"  impossible pairs: {p.predicted} found, {p.expected} expected, "
        f"precision {_pct(p.precision)}, recall {_pct(p.recall)}",
        f"  repeated description found: {result.repeated_description_found}",
        f"  clean agency has no flags: {result.clean_agency_clean}, ranks last: "
        f"{result.clean_agency_last}",
        f"  rule rates checked independently: {result.rates_checked}, wrong: "
        f"{len(result.rates_wrong)}   <- gate, must be 0",
    ]
    return "\n".join(lines)
