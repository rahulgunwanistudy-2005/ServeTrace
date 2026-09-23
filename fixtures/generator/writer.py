"""Canonical serialisation. Everything the generator emits goes through here.

Byte-identical output for a given seed is a hard requirement (S1 acceptance gate), so
nothing written here may depend on wall-clock time, dict insertion order, set iteration
or unrounded floats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _plain(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float):
        # Trailing float noise is the usual reason "same seed" stops meaning "same bytes".
        return round(value, 7)
    return value


def dumps(value: Any) -> str:
    return (
        json.dumps(
            _plain(value), indent=1, sort_keys=True, ensure_ascii=False, separators=(",", ": ")
        )
        + "\n"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(value), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
