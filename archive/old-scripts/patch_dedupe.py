#!/usr/bin/env python3

from pathlib import Path


def patch_make_dashboard():
    path = Path("scripts/make_dashboard.py")
    text = path.read_text()

    backup = path.with_suffix(".py.bak")
    backup.write_text(text)

    helper = r'''

def normalize_for_dedupe(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def photo_dedupe_key(row):
    """
    Dedupe different Photos assets that likely point to the same visual item.

    Current heuristic:
    - Same original filename
    - Same AI caption
    - Same rounded score
    - Same first album

    This catches common WhatsApp / iCloud duplicate imports without collapsing
    same-event but genuinely different photos.
    """
    albums = load_json(row["albums_json"])
    first_album = albums[0] if albums else ""

    filename = normalize_for_dedupe(row["original_filename"])
    caption = normalize_for_dedupe(row["ai_caption"])
    album = normalize_for_dedupe(first_album)

    score = row["score_overall"]
    score_bucket = round(float(score), 3) if score is not None else ""

    if filename or caption:
        return ("visual", filename, caption, album, score_bucket)

    return ("uuid", row["uuid"])
'''

    if "def photo_dedupe_key(row):" not in text:
        marker = "def top_labels(conn, limit=12):"
        text = text.replace(marker, helper + "\n\n" + marker)

    old_sql = '''    LIMIT ?
    """

    photos = []

    for row in conn.execute(sql, (limit,)):
        source_path = choose_source_path(row)
        thumb = materialize_thumb(source_path, row["uuid"], thumbs_dir) if source_path else None

        albums = load_json(row["albums_json"])
        labels = load_json(row["labels_normalized_json"])

        photos.append(
            {
                "uuid": row["uuid"],
                "filename": row["original_filename"],
                "date": row["date"],
                "is_missing": bool(row["is_missing"]),
                "availability": "icloud_only" if row["is_missing"] else "local",
                "caption": row["ai_caption"],
                "score": row["score_overall"],
                "thumb": thumb,
                "source_path_available": bool(source_path),
                "album": albums[0] if albums else "",
                "labels": labels[:4],
                "favorite": bool(row["favorite"]),
                "screenshot": bool(row["screenshot"]),
                "live_photo": bool(row["live_photo"]),
                "width": row["width"],
                "height": row["height"],
            }
        )

    return photos
'''

    new_sql = '''    LIMIT ?
    """

    photos = []
    seen = set()

    # Fetch more rows than we need because duplicate rows may be removed.
    for row in conn.execute(sql, (limit * 5,)):
        key = photo_dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)

        source_path = choose_source_path(row)
        thumb = materialize_thumb(source_path, row["uuid"], thumbs_dir) if source_path else None

        albums = load_json(row["albums_json"])
        labels = load_json(row["labels_normalized_json"])

        photos.append(
            {
                "uuid": row["uuid"],
                "filename": row["original_filename"],
                "date": row["date"],
                "is_missing": bool(row["is_missing"]),
                "availability": "icloud_only" if row["is_missing"] else "local",
                "caption": row["ai_caption"],
                "score": row["score_overall"],
                "thumb": thumb,
                "source_path_available": bool(source_path),
                "album": albums[0] if albums else "",
                "labels": labels[:4],
                "favorite": bool(row["favorite"]),
                "screenshot": bool(row["screenshot"]),
                "live_photo": bool(row["live_photo"]),
                "width": row["width"],
                "height": row["height"],
            }
        )

        if len(photos) >= limit:
            break

    return photos
'''

    if old_sql not in text:
        raise SystemExit("Could not find expected top_photos block in scripts/make_dashboard.py")

    text = text.replace(old_sql, new_sql)

    # Fix SQL LIMIT parameter because we now pass limit * 5.
    text = text.replace("LIMIT ?\\n    \"\"\"", "LIMIT ?\\n    \"\"\"")

    path.write_text(text)
    print(f"Patched {path}, backup at {backup}")


def patch_make_local_gallery():
    path = Path("scripts/make_local_gallery.py")
    if not path.exists():
        print("scripts/make_local_gallery.py not found, skipping")
        return

    text = path.read_text()
    backup = path.with_suffix(".py.bak")
    backup.write_text(text)

    helper = r'''

def normalize_for_dedupe(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def row_dedupe_key(row):
    albums = load_json(row["albums_json"])
    first_album = albums[0] if albums else ""

    filename = normalize_for_dedupe(row["original_filename"])
    caption = normalize_for_dedupe(row["ai_caption"])
    album = normalize_for_dedupe(first_album)

    score = row["score_overall"]
    score_bucket = round(float(score), 3) if score is not None else ""

    if filename or caption:
        return ("visual", filename, caption, album, score_bucket)

    return ("uuid", row["uuid"])
'''

    if "def row_dedupe_key(row):" not in text:
        marker = "def pick_source_file(row):"
        text = text.replace(marker, helper + "\n\n" + marker)

    old = '''def build_gallery_items(rows, thumbs_dir):
    items = []

    for row in rows:
        src = pick_source_file(row)
        if not src:
            continue

        uuid = row["uuid"]
        thumb_path = materialize_thumb(src, uuid, thumbs_dir)
        labels = load_json(row["labels_normalized_json"])
        albums = load_json(row["albums_json"])

        items.append(
            {
                "uuid": uuid,
                "filename": row["original_filename"],
                "date": row["date"],
                "caption": row["ai_caption"],
                "score": row["score_overall"],
                "album": albums[0] if albums else "",
                "labels": labels[:5],
                "favorite": bool(row["favorite"]),
                "screenshot": bool(row["screenshot"]),
                "live_photo": bool(row["live_photo"]),
                "width": row["width"],
                "height": row["height"],
                "thumb": f"thumbs/{quote(thumb_path.name)}",
            }
        )

    return items
'''

    new = '''def build_gallery_items(rows, thumbs_dir):
    items = []
    seen = set()

    for row in rows:
        key = row_dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)

        src = pick_source_file(row)
        if not src:
            continue

        uuid = row["uuid"]
        thumb_path = materialize_thumb(src, uuid, thumbs_dir)
        labels = load_json(row["labels_normalized_json"])
        albums = load_json(row["albums_json"])

        items.append(
            {
                "uuid": uuid,
                "filename": row["original_filename"],
                "date": row["date"],
                "caption": row["ai_caption"],
                "score": row["score_overall"],
                "album": albums[0] if albums else "",
                "labels": labels[:5],
                "favorite": bool(row["favorite"]),
                "screenshot": bool(row["screenshot"]),
                "live_photo": bool(row["live_photo"]),
                "width": row["width"],
                "height": row["height"],
                "thumb": f"thumbs/{quote(thumb_path.name)}",
            }
        )

    return items
'''

    if old not in text:
        raise SystemExit("Could not find expected build_gallery_items block in scripts/make_local_gallery.py")

    text = text.replace(old, new)
    path.write_text(text)
    print(f"Patched {path}, backup at {backup}")


if __name__ == "__main__":
    patch_make_dashboard()
    patch_make_local_gallery()
