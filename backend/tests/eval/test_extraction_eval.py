"""The extraction eval's scoring, checked without a provider.

The eval itself needs an API key and is never part of this suite. Its arithmetic is what
would quietly publish a wrong number on the Methodology page, so that is tested here.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.models import AffidavitDraft, GeocodeResult, LatLng, PersonDescription
from eval import extraction_eval as ev

DEMO = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases" / "maria_contradicted"


@pytest.fixture(scope="module")
def truth() -> dict[str, Any]:
    return json.loads((DEMO / "affidavit.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def perfect_draft(truth: dict[str, Any]) -> AffidavitDraft:
    from datetime import datetime

    return AffidavitDraft(
        index_number=truth["index_number"],
        court=truth["court"],
        plaintiff=truth["plaintiff"],
        defendant_name=truth["defendant_name"],
        server_name=truth["server_name"],
        server_license=truth["server_license"],
        agency_license=truth["agency_license"],
        method=truth["method"],
        served_at=datetime.fromisoformat(truth["served_at"]),
        served_address=truth["served_address"],
        mailing_address=truth["mailing_address"],
        mailing_date=truth["mailing_date"],
        proof_filed_date=truth["proof_filed_date"],
        recipient_description=PersonDescription(**truth["recipient_description"]),
    )


@pytest.mark.asyncio
async def test_a_perfect_extraction_scores_every_field(
    perfect_draft: AffidavitDraft, truth: dict[str, Any]
) -> None:
    fields = await ev.score(perfect_draft, truth)
    assert fields
    assert all(fields.values()), [name for name, ok in fields.items() if not ok]


@pytest.mark.asyncio
async def test_an_empty_extraction_scores_the_fields_that_are_empty_anyway(
    truth: dict[str, Any],
) -> None:
    fields = await ev.score(AffidavitDraft(), truth)
    assert not fields["defendant_name"]
    assert not fields["served_at"]
    assert not fields["served_address"]
    assert not fields["recipient_description"]
    assert fields["attempts_count"]  # this case has no attempts, and neither does the draft


@pytest.mark.asyncio
async def test_the_time_is_compared_to_the_minute(
    perfect_draft: AffidavitDraft, truth: dict[str, Any]
) -> None:
    from datetime import timedelta

    off_by_a_second = perfect_draft.served_at
    assert off_by_a_second is not None
    near = perfect_draft.model_copy(update={"served_at": off_by_a_second + timedelta(seconds=30)})
    far = perfect_draft.model_copy(update={"served_at": off_by_a_second + timedelta(minutes=1)})

    assert (await ev.score(near, truth))["served_at"]
    assert not (await ev.score(far, truth))["served_at"]


def _stub_geocode(monkeypatch: pytest.MonkeyPatch, points: dict[str, LatLng]) -> None:
    async def fake_geocode(address: str, client: object | None = None) -> GeocodeResult | None:
        point = points.get(address)
        return (
            None
            if point is None
            else GeocodeResult(location=point, label=address, confidence=1.0, source="cache")
        )

    monkeypatch.setattr(ev, "geocode", fake_geocode)


@pytest.mark.asyncio
async def test_an_address_is_judged_by_geography_not_by_spelling(
    perfect_draft: AffidavitDraft, truth: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """S2 §9: 50 m of tolerance, so the eval measures whether the extractor found the
    right building rather than whether it punctuated it the way the generator did."""
    reworded = "2100 white plains rd., bronx ny 10462"
    _stub_geocode(
        monkeypatch,
        {
            reworded: LatLng(lat=40.853454, lng=-73.867397),
            truth["served_address"]: LatLng(lat=40.853650, lng=-73.867397),
        },
    )
    restyled = perfect_draft.model_copy(update={"served_address": reworded})

    assert (await ev.score(restyled, truth))["served_address"]


@pytest.mark.asyncio
async def test_a_different_building_is_wrong_however_similar_the_words(
    perfect_draft: AffidavitDraft, truth: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    other = "2200 white plains road, bronx ny 10462"
    _stub_geocode(
        monkeypatch,
        {
            other: LatLng(lat=40.858000, lng=-73.865000),
            truth["served_address"]: LatLng(lat=40.853454, lng=-73.867397),
        },
    )
    wrong = perfect_draft.model_copy(update={"served_address": other})

    assert not (await ev.score(wrong, truth))["served_address"]


@pytest.mark.asyncio
async def test_an_address_the_lookup_cannot_resolve_is_a_miss_not_a_crash(
    perfect_draft: AffidavitDraft, truth: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A whole eval run must not end because one address could not be looked up."""
    _stub_geocode(monkeypatch, {})
    wrong = perfect_draft.model_copy(update={"served_address": "somewhere else entirely"})

    assert not (await ev.score(wrong, truth))["served_address"]


def test_accuracy_is_reported_per_field_and_per_variant() -> None:
    results = [
        ev.Scored("case_0000", "clean", {"court": True, "served_at": True}),
        ev.Scored("case_0001", "clean", {"court": True, "served_at": False}),
        ev.Scored("case_0000", "scanned", {"court": False, "served_at": False}),
        ev.Scored("case_0002", "scanned", {}, error="ExtractionInvalidError"),
    ]
    report = ev.summarise(results)

    assert report["clean"]["per_field_accuracy"] == {"court": 1.0, "served_at": 0.5}
    assert report["clean"]["mean_field_accuracy"] == 0.75
    assert report["scanned"]["per_field_accuracy"] == {"court": 0.0, "served_at": 0.0}
    assert report["scanned"]["n_failed"] == 1
    assert report["scanned"]["n_documents"] == 2


def test_a_document_the_extractor_could_not_read_is_counted_not_hidden() -> None:
    """A run that quietly drops its failures reports a better number than it earned."""
    report = ev.summarise([ev.Scored("case_0000", "clean", {}, error="ExtractionUnavailableError")])
    assert report["clean"]["n_extracted"] == 0
    assert report["clean"]["n_failed"] == 1
