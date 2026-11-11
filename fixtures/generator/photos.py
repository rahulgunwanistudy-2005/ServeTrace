"""Camera-roll photos with known metadata, for the v1.1 photo parser. Bible §13.

Every image is an 8x8 flat colour: the parser never reads a pixel, so the picture is
irrelevant and small files keep the repo small. What matters is the EXIF block, written
here with `piexif` (a dev-only dependency) and, for the HEIC variants, embedded by
`pillow-heif` exactly as an iPhone would carry it.

`expected.json` beside the photos is the answer key the vitest parser tests read. It is
written from the same values the EXIF was written from, never by running a parser, for
the same reason the corpus labels never come from the engine.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.photos

Places are public landmarks used only as geography; nobody is depicted or named.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import piexif
import pillow_heif
from PIL import Image

NY = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[1]
PHOTOS = ROOT / "photos"
MARIA = ROOT / "demo_cases" / "maria_contradicted"

MARIA_WORK = (40.7836227, -73.9527563)
"""Where Maria's Timeline places her all day: ~10.5 km from the door on her affidavit."""

PHILADELPHIA = (39.9526, -75.1652)
"""~130 km from the Bronx. Far enough that even an hour's allowance cannot explain it."""

BRONX_DOOR = (40.853454, -73.867397)


@dataclass(frozen=True, slots=True)
class Photo:
    name: str
    local: datetime | None
    """Wall-clock time the camera wrote into DateTimeOriginal, New York, or None."""
    gps: tuple[float, float] | None = None
    gps_stamp: bool = False
    """Write GPSDateStamp/GPSTimeStamp (UTC) as phones with GPS on do."""
    offset: str | None = None
    """OffsetTimeOriginal, e.g. "-04:00"."""
    h_error_m: float | None = None
    heic: bool = False
    colour: tuple[int, int, int] = (90, 110, 130)


def _rational(value: float, scale: int = 10_000) -> tuple[int, int]:
    return (round(value * scale), scale)


def _dms(degrees: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    value = abs(degrees)
    d = int(value)
    m = int((value - d) * 60)
    s = (value - d - m / 60) * 3600
    return ((d, 1), (m, 1), _rational(s, 1000))


def exif_bytes(photo: Photo) -> bytes:
    zeroth: dict[int, object] = {
        piexif.ImageIFD.Make: b"Synthetic",
        piexif.ImageIFD.Model: b"Fixture",
    }
    exif: dict[int, object] = {}
    gps: dict[int, object] = {}
    if photo.local is not None:
        exif[piexif.ExifIFD.DateTimeOriginal] = photo.local.strftime("%Y:%m:%d %H:%M:%S").encode()
        if photo.offset is not None:
            exif[piexif.ExifIFD.OffsetTimeOriginal] = photo.offset.encode()
    if photo.gps is not None:
        lat, lng = photo.gps
        gps[piexif.GPSIFD.GPSVersionID] = (2, 3, 0, 0)
        gps[piexif.GPSIFD.GPSLatitudeRef] = b"N" if lat >= 0 else b"S"
        gps[piexif.GPSIFD.GPSLatitude] = _dms(lat)
        gps[piexif.GPSIFD.GPSLongitudeRef] = b"E" if lng >= 0 else b"W"
        gps[piexif.GPSIFD.GPSLongitude] = _dms(lng)
        if photo.h_error_m is not None:
            gps[piexif.GPSIFD.GPSHPositioningError] = _rational(photo.h_error_m, 100)
        if photo.gps_stamp and photo.local is not None:
            utc = photo.local.replace(tzinfo=NY).astimezone(UTC)
            gps[piexif.GPSIFD.GPSDateStamp] = utc.strftime("%Y:%m:%d").encode()
            gps[piexif.GPSIFD.GPSTimeStamp] = ((utc.hour, 1), (utc.minute, 1), (utc.second, 1))
    return bytes(piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps, "1st": {}}))


def encode(photo: Photo) -> bytes:
    image = Image.new("RGB", (8, 8), photo.colour)
    buffer = io.BytesIO()
    if photo.heic:
        pillow_heif.register_heif_opener()
        image.save(buffer, format="HEIF", exif=exif_bytes(photo), quality=50)
    else:
        image.save(buffer, format="JPEG", exif=exif_bytes(photo), quality=70)
    return buffer.getvalue()


def expected(photo: Photo) -> dict[str, object]:
    """What a correct parser must make of this file. Decided from the inputs above."""
    if photo.local is None:
        return {"skip": "no_original_time"}
    if photo.gps is None:
        return {"skip": "no_location"}
    if photo.gps_stamp:
        t, assumed = photo.local.replace(tzinfo=NY).astimezone(UTC), False
    elif photo.offset is not None:
        sign = -1 if photo.offset.startswith("-") else 1
        hh, mm = (int(x) for x in photo.offset[1:].split(":"))
        offset = timedelta(hours=hh, minutes=mm) * sign
        t, assumed = (photo.local - offset).replace(tzinfo=UTC), False
    else:
        t, assumed = photo.local.replace(tzinfo=NY).astimezone(UTC), True
    return {
        "t": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "lat": photo.gps[0],
        "lng": photo.gps[1],
        "accuracy_m": photo.h_error_m if photo.h_error_m is not None else 100.0,
        "tz_assumed": assumed,
        "time_uncertainty_s": 3600 if assumed else 0,
    }


def _at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2025, 6, 12, hour, minute, second)


VARIANTS: tuple[Photo, ...] = (
    Photo("gps_utc.jpg", _at(19, 38), MARIA_WORK, gps_stamp=True, h_error_m=12.0),
    Photo("gps_utc.heic", _at(19, 38), MARIA_WORK, gps_stamp=True, h_error_m=12.0, heic=True),
    Photo("offset.jpg", _at(19, 31), MARIA_WORK, offset="-04:00"),
    Photo("local_only.jpg", _at(19, 45), MARIA_WORK),
    Photo("local_only.heic", _at(19, 45), MARIA_WORK, heic=True),
    Photo("no_gps.jpg", _at(19, 40)),
    Photo("no_time.jpg", None, MARIA_WORK),
    Photo("burst_1.jpg", _at(19, 50, 0), MARIA_WORK, gps_stamp=True, h_error_m=8.0),
    Photo("burst_2.jpg", _at(19, 50, 20), (40.78365, -73.95280), gps_stamp=True, h_error_m=8.0),
    Photo("burst_3.jpg", _at(19, 50, 45), (40.78360, -73.95270), gps_stamp=True, h_error_m=8.0),
    Photo("far_local_only.jpg", _at(19, 42), PHILADELPHIA),
)
"""One file per branch of the parser's time-source ladder (bible §13), plus a burst."""

MARIA_EXACT: tuple[Photo, ...] = (
    Photo("IMG_0611.jpg", _at(19, 31), MARIA_WORK, gps_stamp=True, h_error_m=15.0),
    Photo("IMG_0612.jpg", _at(19, 38), MARIA_WORK, gps_stamp=True, h_error_m=15.0),
    Photo("IMG_0613.heic", _at(19, 52), MARIA_WORK, gps_stamp=True, h_error_m=15.0, heic=True),
)
"""Maria with no Timeline: three photos from work that evening, GPS on."""

MARIA_LOCAL: tuple[Photo, ...] = tuple(
    Photo(p.name, p.local, p.gps, heic=p.heic) for p in MARIA_EXACT
)
"""The same three after a messaging app stripped the GPS clock: time zone unknown."""


def write(directory: Path, photos: tuple[Photo, ...]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    answers: dict[str, object] = {}
    for photo in photos:
        (directory / photo.name).write_bytes(encode(photo))
        answers[photo.name] = expected(photo)
    (directory / "expected.json").write_text(json.dumps(answers, indent=2) + "\n")


def main() -> None:
    write(PHOTOS, VARIANTS)
    write(MARIA / "photos", MARIA_EXACT)
    write(MARIA / "photos_no_zone", MARIA_LOCAL)
    print(f"wrote {len(VARIANTS)} + {len(MARIA_EXACT)} + {len(MARIA_LOCAL)} photos")


if __name__ == "__main__":
    main()
