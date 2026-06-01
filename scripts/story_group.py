#!/usr/bin/env python3

"""Story grouping helpers.

This module groups neutral story candidate items into timeline/story moments.
It should stay independent from any specific dashboard renderer.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime


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


def milestone_terms(item):
    return useful_terms(item) & MILESTONE_TERMS

def month_label(item, lang):
    dt = parse_dt(item.get("date"))
    if not dt:
        return "Unknown"

    if lang == "tr":
        months = [
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
        ]
    else:
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

    return f"{months[dt.month - 1]} {dt.year}"

def parse_dt(value):
    if not value:
        return None

    raw = value.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(raw)
    except Exception:
        try:
            return datetime.fromisoformat(raw[:19])
        except Exception:
            return None

def representative_score(item):
    score = float(item.get("score") or 0)
    milestone_bonus = min(len(item.get("milestone_terms") or []) * 0.03, 0.12)
    favorite_bonus = 0.08 if item.get("favorite") else 0
    local_bonus = 0.01 if item.get("original_status") == "local" else 0
    return score + milestone_bonus + favorite_bonus + local_bonus

def useful_terms(item):
    all_terms = set()

    for label in item.get("labels") or []:
        all_terms |= tokens(label)

    all_terms |= tokens(item.get("caption") or "")
    all_terms |= tokens(item.get("album") or "")

    return {
        t for t in all_terms
        if len(t) >= 3 and t not in GENERIC_TERMS
    }

def year_of(item):
    dt = parse_dt(item.get("date"))
    if not dt:
        return "Unknown"
    return str(dt.year)

def tokens(value):
    return set(WORD_RE.findall(normalize(value)))

def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()

def hamming_hash(a, b):
    if not a or not b or len(a) != len(b):
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 999


def seconds_between(a, b):
    da = parse_dt(a.get("date"))
    db = parse_dt(b.get("date"))

    if da is None or db is None:
        return 999999

    try:
        return abs((da - db).total_seconds())
    except Exception:
        return abs((da.replace(tzinfo=None) - db.replace(tzinfo=None)).total_seconds())

def same_moment(a, b, config):
    dt = seconds_between(a, b)
    phash_distance = hamming_hash(a.get("phash"), b.get("phash"))

    terms_a = useful_terms(a)
    terms_b = useful_terms(b)

    shared = terms_a & terms_b
    shared_milestones = milestone_terms(a) & milestone_terms(b)

    if phash_distance <= 5:
        return True

    if dt <= int(config.get("burst_seconds", 5)):
        if shared_milestones:
            return True
        if len(shared) >= 3:
            return True

    if dt <= int(config.get("moment_seconds", 90)):
        if len(shared_milestones) >= 1 and len(shared) >= 2:
            return True

    return False


def cluster_items(items, config):
    clusters = []

    for item in sorted(items, key=lambda x: x.get("date") or ""):
        assigned = False

        for cluster in clusters:
            if any(same_moment(item, existing, config) for existing in cluster["items"]):
                cluster["items"].append(item)
                assigned = True
                break

        if not assigned:
            clusters.append({"items": [item]})

    moments = []

    for idx, cluster in enumerate(clusters, start=1):
        cluster_items_sorted = sorted(cluster["items"], key=representative_score, reverse=True)
        rep = cluster_items_sorted[0]

        dates = [parse_dt(i.get("date")) for i in cluster_items_sorted if parse_dt(i.get("date"))]
        if dates:
            start = min(dates).isoformat()
            end = max(dates).isoformat()
        else:
            start = rep.get("date")
            end = rep.get("date")

        all_terms = set()
        all_milestones = set()

        for item in cluster_items_sorted:
            all_terms |= useful_terms(item)
            all_milestones |= milestone_terms(item)

        moments.append(
            {
                "moment_id": f"family_moment_{idx:04d}",
                "representative": rep,
                "variants": cluster_items_sorted,
                "variant_count": len(cluster_items_sorted),
                "date_start": start,
                "date_end": end,
                "year": year_of(rep),
                "month_label_tr": month_label(rep, "tr"),
                "month_label_en": month_label(rep, "en"),
                "terms": sorted(all_terms)[:20],
                "milestone_terms": sorted(all_milestones),
                "moment_score": round(representative_score(rep), 4)
            }
        )

    return moments


def select_year_moments(moments, config):
    by_year = defaultdict(list)

    for moment in moments:
        by_year[moment["year"]].append(moment)

    max_per_year = int(config.get("max_moments_per_year", 16))
    max_total = int(config.get("max_total_moments", 160))

    selected_by_year = {}

    for year, items in by_year.items():
        # Within each year, prefer milestone-rich and high-scoring items,
        # but output chronologically after selection.
        ranked = sorted(
            items,
            key=lambda m: (
                len(m.get("milestone_terms") or []),
                m.get("moment_score") or 0,
                m.get("variant_count") or 1
            ),
            reverse=True
        )

        selected = ranked[:max_per_year]
        selected = sorted(selected, key=lambda m: m.get("date_start") or "")

        selected_by_year[year] = selected

    # Enforce global max if needed.
    all_selected = []
    for year in sorted(selected_by_year.keys()):
        for moment in selected_by_year[year]:
            all_selected.append((year, moment))

    if len(all_selected) > max_total:
        all_selected = sorted(
            all_selected,
            key=lambda ym: (ym[1].get("moment_score") or 0, len(ym[1].get("milestone_terms") or [])),
            reverse=True
        )[:max_total]

        new_by_year = defaultdict(list)
        for year, moment in all_selected:
            new_by_year[year].append(moment)

        selected_by_year = {
            year: sorted(items, key=lambda m: m.get("date_start") or "")
            for year, items in new_by_year.items()
        }

    return dict(sorted(selected_by_year.items()))

