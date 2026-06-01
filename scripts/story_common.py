#!/usr/bin/env python3

"""Common helpers for Agrandiz story discovery, grouping and rendering.

This module intentionally contains low-risk utility code only. It should not
know about a specific dashboard such as family timeline, vacation, wedding or
school stories.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


def read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any, *, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def esc_attr(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def compact_list(values: Iterable[Any]) -> list[Any]:
    return [v for v in values if v is not None and v != ""]


def normalize_text(value: Any) -> str:
    """Return a lowercase, accent-normalized text string for loose matching."""

    if value is None:
        return ""

    text = str(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9çğıöşüİıĞğÜüŞşÖöÇç]+", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def phrase_in_text(phrase: str, text: str) -> bool:
    phrase_n = normalize_text(phrase)
    text_n = normalize_text(text)
    if not phrase_n or not text_n:
        return False
    return phrase_n in text_n


def join_text_fields(*values: Any) -> str:
    return " ".join(str(v) for v in values if v is not None and str(v).strip())


def profile_filter_terms(profile: dict[str, Any], bucket: str) -> list[str]:
    """Extract tag/label/term values from generic profile filters.

    bucket is usually "any", "all" or "none".
    This intentionally ignores person/place filters because those need entity
    resolution and source metadata support in a later step.
    """

    filters = profile.get("filters") or {}
    terms: list[str] = []

    for item in filters.get(bucket, []) or []:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        value = item.get("value")
        if item_type in {"tag", "label", "term"} and value:
            terms.append(str(value))

    return terms


def profile_output_path(outdir: str | Path, filename: str) -> Path:
    return Path(outdir) / filename


def stable_slug(value: Any, *, default: str = "story") -> str:
    text = normalize_text(value)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or default


def source_identity(profile: dict[str, Any]) -> str:
    source = profile.get("source") or {}
    if isinstance(source, dict):
        return str(source.get("id") or source.get("provider") or "unknown")
    return str(source or "unknown")
