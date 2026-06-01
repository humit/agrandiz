#!/usr/bin/env python3

"""Story profile loading and normalization.

A story profile is the stable contract between discovery, grouping and rendering.
The engine should not contain user-specific assumptions; those belong to generated
or user-edited profile files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from story_common import read_json


DEFAULT_SOURCE = "apple.apple_icloud"
DEFAULT_LAYOUT = "timeline"
DEFAULT_OUTPUT_JSON = "family_timeline.json"
DEFAULT_OUTPUT_HTML = "family-timeline.apple.apple_icloud.html"


def normalize_story_profile(raw: dict[str, Any], source_path: str | Path | None = None) -> dict[str, Any]:
    """Return a profile in the new generic shape.

    This accepts both the old family_timeline.json shape and the new story profile
    shape. The returned dict includes a `selection_legacy` key so the current
    the generic story builder can continue using the legacy matcher while the
    project migrates to generic filters.
    """

    is_new = "filters" in raw or "selection" in raw or "layout" in raw or "output" in raw

    if is_new:
        selection = raw.get("selection") or {}
        filters = raw.get("filters") or {}
        time = raw.get("time") or {}
        grouping = raw.get("grouping") or {}
        output = raw.get("output") or {}
        i18n = raw.get("i18n") or {}
        source = raw.get("source") or {}

        source_id = source.get("id") if isinstance(source, dict) else source
        source_id = source_id or DEFAULT_SOURCE

        include_any = selection.get("include_any") or _terms_from_filters(filters, "any")
        exclude_any = selection.get("exclude_any") or _terms_from_filters(filters, "none")

        profile = {
            "schema_version": raw.get("schema_version", 1),
            "id": raw.get("id", "family_timeline"),
            "template_id": raw.get("template_id", "people_timeline"),
            "kind": raw.get("kind", "story_dashboard"),
            "layout": raw.get("layout", DEFAULT_LAYOUT),
            "source": source if isinstance(source, dict) else {"id": source_id, "type": "photos_metadata"},
            "output": {
                "json": output.get("json", raw.get("output_json", DEFAULT_OUTPUT_JSON)),
                "html": output.get("html", raw.get("output_html", DEFAULT_OUTPUT_HTML)),
            },
            "i18n": {
                "title": i18n.get("title", "family.page_title"),
                "subtitle": i18n.get("subtitle", "family.subtitle"),
                "eyebrow": i18n.get("eyebrow", "family.timeline"),
            },
            "filters": filters,
            "selection": selection,
            "time": time,
            "grouping": grouping,
            "entities": raw.get("entities", {}),
            "user_semantics": raw.get("user_semantics", {}),
            "source_metadata_policy": raw.get(
                "source_metadata_policy",
                {
                    "prefer_source_people": True,
                    "prefer_source_places": True,
                    "prefer_source_labels": True,
                    "user_overrides_source": True,
                },
            ),
        }

        profile["selection_legacy"] = {
            "include_any": include_any,
            "exclude_any": exclude_any,
            "from_date": time.get("from"),
            "to_date": time.get("to"),
            "min_score": selection.get("min_score", raw.get("min_score", 0.0)),
            "max_moments_per_year": grouping.get("max_moments_per_year", raw.get("max_moments_per_year", 16)),
            "max_total_moments": grouping.get("max_total_moments", raw.get("max_total_moments", 160)),
            "moment_seconds": grouping.get("moment_seconds", raw.get("moment_seconds", 90)),
            "burst_seconds": grouping.get("burst_seconds", raw.get("burst_seconds", 5)),
        }

        return profile

    # Legacy family_timeline.json support.
    profile = {
        "schema_version": 1,
        "id": "family_timeline",
        "template_id": "people_timeline",
        "kind": "story_dashboard",
        "layout": DEFAULT_LAYOUT,
        "source": {
            "id": DEFAULT_SOURCE,
            "type": "photos_metadata",
            "provider": "apple_icloud"
        },
        "output": {
            "json": DEFAULT_OUTPUT_JSON,
            "html": DEFAULT_OUTPUT_HTML
        },
        "i18n": {
            "title": "family.page_title",
            "subtitle": "family.subtitle",
            "eyebrow": "family.timeline",
        },
        "filters": {
            "any": [{"type": "tag", "value": value} for value in raw.get("include_any", [])],
            "none": [{"type": "tag", "value": value} for value in raw.get("exclude_any", [])],
        },
        "selection": {
            "include_any": raw.get("include_any", []),
            "exclude_any": raw.get("exclude_any", []),
            "min_score": raw.get("min_score", 0.0),
        },
        "time": {
            "from": raw.get("from_date"),
            "to": raw.get("to_date"),
            "group_by": "year"
        },
        "grouping": {
            "mode": "timeline",
            "moment_seconds": raw.get("moment_seconds", 90),
            "burst_seconds": raw.get("burst_seconds", 5),
            "max_moments_per_year": raw.get("max_moments_per_year", 16),
            "max_total_moments": raw.get("max_total_moments", 160),
        },
        "entities": {},
        "user_semantics": {},
        "source_metadata_policy": {
            "prefer_source_people": True,
            "prefer_source_places": True,
            "prefer_source_labels": True,
            "user_overrides_source": True,
        },
        "legacy_titles": {
            "title_tr": raw.get("title_tr", "Çocukların Büyüme Hikâyesi"),
            "title_en": raw.get("title_en", "Children's Growing-Up Story"),
            "subtitle_tr": raw.get("subtitle_tr", ""),
            "subtitle_en": raw.get("subtitle_en", ""),
        },
    }

    profile["selection_legacy"] = dict(raw)
    return profile


def _terms_from_filters(filters: dict[str, Any], bucket: str) -> list[str]:
    terms: list[str] = []

    for item in filters.get(bucket, []) or []:
        if not isinstance(item, dict):
            continue

        if item.get("type") in {"tag", "label", "term"} and item.get("value"):
            terms.append(str(item["value"]))

    return terms


def load_story_profile(path: str | Path) -> dict[str, Any]:
    raw = read_json(path)
    profile = normalize_story_profile(raw, path)
    profile["profile_path"] = str(path)
    return profile


def legacy_selection_config(profile: dict[str, Any]) -> dict[str, Any]:
    return dict(profile.get("selection_legacy") or {})


def profile_output_json(profile: dict[str, Any]) -> str:
    return profile.get("output", {}).get("json") or DEFAULT_OUTPUT_JSON


def profile_output_html(profile: dict[str, Any]) -> str:
    return profile.get("output", {}).get("html") or DEFAULT_OUTPUT_HTML
