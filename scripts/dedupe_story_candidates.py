#!/usr/bin/env python3

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path


WORD_RE = re.compile(r"[a-z0-9çğıöşü]+", re.I)

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "with",
    "person", "people", "child", "children", "wearing", "standing",
    "sitting", "close", "front", "black", "red", "white", "blue",
    "photo", "image", "jpg", "jpeg"
}


def norm(value):
    return str(value or "").strip().lower()


def tokens(value):
    return {
        t for t in WORD_RE.findall(norm(value))
        if len(t) >= 3 and t not in STOPWORDS
    }


def get_first(d, keys, default=""):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in [None, ""]:
            return d.get(k)
    return default


def representative(item):
    if not isinstance(item, dict):
        return {}

    for key in ["representative", "photo", "item", "asset"]:
        if isinstance(item.get(key), dict):
            return item[key]

    return item


def caption_of(item):
    r = representative(item)
    return get_first(r, ["caption", "ai_caption", "description", "title"], "")


def date_of(item):
    r = representative(item)
    return get_first(r, ["date", "datetime", "created", "timestamp"], "")


def album_of(item):
    r = representative(item)
    album = get_first(r, ["album", "albums"], "")
    if isinstance(album, list):
        return " ".join(str(x) for x in album)
    return album


def filename_of(item):
    r = representative(item)
    return get_first(r, ["filename", "original_filename", "path", "thumb"], "")


def dimensions_of(item):
    r = representative(item)
    w = get_first(r, ["width", "w"], "")
    h = get_first(r, ["height", "h"], "")
    return f"{w}x{h}" if w or h else ""


def uuid_of(item):
    r = representative(item)
    return get_first(r, ["uuid", "id"], "")


def score_of(item):
    r = representative(item)
    try:
        return float(get_first(r, ["score", "score_overall", "moment_score"], 0) or 0)
    except Exception:
        return 0.0


def exact_second(value):
    value = str(value or "")
    if "T" in value and len(value) >= 19:
        return value[:19]
    return value[:19]


def minute_bucket(value):
    value = str(value or "")
    if "T" in value and len(value) >= 16:
        return value[:16]
    return value[:16]


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def duplicate_reason(a, b):
    da = exact_second(date_of(a))
    db = exact_second(date_of(b))
    ma = minute_bucket(date_of(a))
    mb = minute_bucket(date_of(b))

    album_a = norm(album_of(a))
    album_b = norm(album_of(b))

    dim_a = dimensions_of(a)
    dim_b = dimensions_of(b)

    cap_a = tokens(caption_of(a))
    cap_b = tokens(caption_of(b))
    sim = jaccard(cap_a, cap_b)

    # Strong case: exact same timestamp and same album.
    if da and da == db and album_a == album_b:
        return "same-second+album"

    # Strong case: same timestamp and same dimensions.
    if da and da == db and dim_a and dim_a == dim_b:
        return "same-second+shape"

    # Common WhatsApp case: same minute, same album, similar caption terms.
    if ma and ma == mb and album_a == album_b and sim >= 0.30:
        return "same-minute+album+caption"

    # Same timestamp with partial caption similarity.
    if da and da == db and sim >= 0.25:
        return "same-second+caption"

    return None


def merge_variants(target, source, reason):
    target = deepcopy(target)

    variants = []

    for k in ["variants", "items"]:
        if isinstance(target.get(k), list):
            variants.extend(target[k])

    variants.append(representative(target))
    variants.append(representative(source))

    seen = set()
    clean = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        key = uuid_of(v) or filename_of(v) or json.dumps(v, sort_keys=True, ensure_ascii=False)[:200]
        if key in seen:
            continue
        seen.add(key)
        clean.append(v)

    target["variants"] = clean
    target["variant_count"] = len(clean)
    reasons = set(target.get("dedupe_reasons") or [])
    reasons.add(reason)
    target["dedupe_reasons"] = sorted(reasons)

    return target


def dedupe_list(items):
    result = []

    for item in items:
        merged = False

        for idx, existing in enumerate(result):
            reason = duplicate_reason(existing, item)
            if reason:
                # Keep better-scored representative but merge variants.
                if score_of(item) > score_of(existing):
                    result[idx] = merge_variants(item, existing, reason)
                else:
                    result[idx] = merge_variants(existing, item, reason)
                merged = True
                break

        if not merged:
            result.append(item)

    return result


def dedupe_story_data(data):
    data = deepcopy(data)

    # Common structure: {"stories": [{"items": [...]}, ...]}
    if isinstance(data, dict) and isinstance(data.get("stories"), list):
        for story in data["stories"]:
            for key in ["moments", "items", "photos"]:
                if isinstance(story.get(key), list):
                    before = len(story[key])
                    story[key] = dedupe_list(story[key])
                    story["deduped_count"] = before - len(story[key])
                    break
        return data

    # Alternative structure: {"story_candidates": [...]}
    if isinstance(data, dict) and isinstance(data.get("story_candidates"), list):
        data["story_candidates"] = dedupe_list(data["story_candidates"])
        return data

    # Alternative: top-level list.
    if isinstance(data, list):
        return dedupe_list(data)

    raise ValueError("Unsupported story JSON structure. Inspect the JSON schema before deduping.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="cache/story_candidates_grouped.json")
    parser.add_argument("--output", default="cache/story_candidates_deduped.json")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    deduped = dedupe_story_data(data)

    Path(args.output).write_text(
        json.dumps(deduped, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
