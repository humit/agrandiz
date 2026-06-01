#!/usr/bin/env python3

"""Generic story discovery helpers.

This module converts photo database rows into neutral story candidate items.
It is source-aware but not dashboard-specific. Profile-specific selection still
comes from the normalized legacy config for this transition step.

Later steps will replace include_any/exclude_any matching with full entity-aware
filters: people, face clusters, places, date ranges and source metadata.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    from PIL import Image
    import imagehash
except Exception:
    Image = None
    imagehash = None


WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)?", re.IGNORECASE)

GENERIC_TERMS = {
    "a", "an", "the", "and", "or", "of", "on", "in", "at", "with", "to",
    "person", "people", "standing", "sitting", "holding", "wearing",
    "looking", "front", "background", "group", "photo", "image",
    "white", "black", "blue", "red", "green", "brown", "large", "small",
    "clothing", "shirt", "jacket"
}

MILESTONE_TERMS = {
    "baby",
    "birthday",
    "cake",
    "school",
    "student",
    "playground",
    "toy",
    "table",
    "pizza",
    "mask",
    "hospital",
    "balloon"
}


def normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def tokens(value: Any) -> set[str]:
    return set(WORD_RE.findall(normalize(value)))


def load_json(raw: Any, default: Any = None) -> Any:
    if default is None:
        default = []
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def phrase_or_token_match(term: str, text: str) -> bool:
    term = normalize(term)
    text = normalize(text)

    if not term:
        return False

    if " " in term or "-" in term:
        return term in text

    return term in tokens(text)


def evidence_matches(labels: list[str], caption: str, filename: str, album: str, terms: list[str]) -> bool:
    labels_normalized = {normalize(x) for x in labels}
    searchable = " ".join([caption or "", filename or "", album or ""]).lower()

    for term in terms:
        term = normalize(term)
        if term in labels_normalized:
            return True
        if phrase_or_token_match(term, searchable):
            return True

    return False


def useful_terms(item: dict[str, Any]) -> set[str]:
    all_terms: set[str] = set()

    for label in item.get("labels") or []:
        all_terms |= tokens(label)

    all_terms |= tokens(item.get("caption") or "")
    all_terms |= tokens(item.get("album") or "")

    return {
        term
        for term in all_terms
        if len(term) >= 3 and term not in GENERIC_TERMS
    }


def milestone_terms(item: dict[str, Any]) -> set[str]:
    terms = useful_terms(item)
    return terms & MILESTONE_TERMS


def extension_for(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        return suffix
    return ".jpg"


def choose_source_path(row: sqlite3.Row) -> str | None:
    preview = row["path_preview"]
    original = row["path"]

    if preview and Path(preview).exists():
        return preview

    if original and Path(original).exists():
        return original

    return None


def copy_preview(src: str | Path, uuid: str, thumbs_dir: str | Path) -> str:
    thumbs_dir = Path(thumbs_dir)
    ext = extension_for(src)
    dst = thumbs_dir / f"{uuid}{ext}"

    if not dst.exists():
        shutil.copy2(src, dst)

    return f"thumbs/{quote(dst.name)}"


def compute_phash(path: str | Path) -> str | None:
    if Image is None or imagehash is None:
        return None

    try:
        with Image.open(path) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def phash_available() -> bool:
    return Image is not None and imagehash is not None


def fetch_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT
            uuid,
            original_filename,
            date,
            is_missing,
            ai_caption,
            score_overall,
            path,
            path_preview,
            albums_json,
            labels_normalized_json,
            favorite,
            screenshot,
            live_photo,
            width,
            height
        FROM photos
        WHERE is_photo = 1
          AND score_overall IS NOT NULL
        ORDER BY date ASC, score_overall DESC
        """
    ).fetchall()


def row_matches(row: sqlite3.Row, config: dict[str, Any]) -> bool:
    score = row["score_overall"]
    if score is None or float(score) < float(config.get("min_score", 0.0)):
        return False

    date = row["date"] or ""

    if config.get("from_date") and date[:10] < config["from_date"]:
        return False

    if config.get("to_date") and date[:10] > config["to_date"]:
        return False

    labels = load_json(row["labels_normalized_json"])
    albums = load_json(row["albums_json"])
    album = " ".join(albums)
    caption = row["ai_caption"] or ""
    filename = row["original_filename"] or ""

    if evidence_matches(labels, caption, filename, album, config.get("exclude_any", [])):
        return False

    return evidence_matches(labels, caption, filename, album, config.get("include_any", []))


def build_item(row: sqlite3.Row, thumbs_dir: str | Path, use_phash: bool) -> dict[str, Any] | None:
    thumbs_dir = Path(thumbs_dir)
    src = choose_source_path(row)
    if not src:
        return None

    thumb = copy_preview(src, row["uuid"], thumbs_dir)

    albums = load_json(row["albums_json"])
    labels = load_json(row["labels_normalized_json"])

    item = {
        "uuid": row["uuid"],
        "filename": row["original_filename"],
        "date": row["date"],
        "caption": row["ai_caption"],
        "score": row["score_overall"],
        "album": albums[0] if albums else "",
        "labels": labels[:10],
        "is_missing": bool(row["is_missing"]),
        "original_status": "icloud" if row["is_missing"] else "local",
        "preview_status": "ready",
        "thumb": thumb,
        "favorite": bool(row["favorite"]),
        "screenshot": bool(row["screenshot"]),
        "live_photo": bool(row["live_photo"]),
        "width": row["width"],
        "height": row["height"],
        "phash": None,
        "source_metadata": {
            "source": "apple_icloud",
            "metadata_source": "photos_db",
            "albums": albums,
            "labels": labels,
        },
    }

    if use_phash:
        thumb_path = thumbs_dir.parent / thumb
        item["phash"] = compute_phash(thumb_path)

    item["terms"] = sorted(useful_terms(item))[:20]
    item["milestone_terms"] = sorted(milestone_terms(item))

    return item


def discover_items(
    rows: list[sqlite3.Row],
    config: dict[str, Any],
    thumbs_dir: str | Path,
    *,
    use_phash: bool | None = None,
) -> list[dict[str, Any]]:
    """Filter rows and return story candidate items."""

    if use_phash is None:
        use_phash = phash_available() and not config.get("disable_phash", False)

    items: list[dict[str, Any]] = []

    for row in rows:
        if not row_matches(row, config):
            continue

        item = build_item(row, thumbs_dir, use_phash)
        if item:
            items.append(item)

        max_candidates = config.get("max_candidates")
        if max_candidates and len(items) >= int(max_candidates):
            break

    return items
