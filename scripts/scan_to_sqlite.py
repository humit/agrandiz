#!/usr/bin/env python3

import json
import sqlite3
from pathlib import Path
from datetime import datetime



DB_PATH = Path("cache/agrandiz.sqlite")


def dt_to_iso(value):
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def score_value(score, name):
    if score is None:
        return None
    return getattr(score, name, None)


def first_or_none(values):
    if not values:
        return None
    return values[0]


def safe_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return None


def create_schema(conn):
    conn.executescript(
        """
        DROP TABLE IF EXISTS photos;

        CREATE TABLE photos (
            uuid TEXT PRIMARY KEY,
            original_filename TEXT,
            filename TEXT,
            date TEXT,
            date_added TEXT,
            date_original TEXT,

            is_photo INTEGER,
            is_movie INTEGER,
            favorite INTEGER,
            hidden INTEGER,
            intrash INTEGER,
            visible INTEGER,

            is_missing INTEGER,
            in_cloud INTEGER,
            is_cloud_asset INTEGER,

            path TEXT,
            path_preview TEXT,
            path_derivatives_json TEXT,

            width INTEGER,
            height INTEGER,
            original_width INTEGER,
            original_height INTEGER,
            original_filesize INTEGER,
            uti TEXT,
            uti_original TEXT,

            albums_json TEXT,
            persons_json TEXT,
            labels_json TEXT,
            labels_normalized_json TEXT,
            keywords_json TEXT,

            ai_caption TEXT,

            screenshot INTEGER,
            selfie INTEGER,
            live_photo INTEGER,
            burst INTEGER,
            hdr INTEGER,
            panorama INTEGER,
            slow_mo INTEGER,
            time_lapse INTEGER,

            latitude REAL,
            longitude REAL,
            place TEXT,

            score_overall REAL,
            score_curation REAL,
            score_behavioral REAL,
            score_harmonious_color REAL,
            score_interesting_subject REAL,
            score_lively_color REAL,
            score_pleasant_composition REAL,
            score_sharply_focused_subject REAL,
            score_tastefully_blurred REAL,
            score_well_chosen_subject REAL,
            score_well_framed_subject REAL,
            score_well_timed_shot REAL,

            created_at TEXT
        );

        CREATE INDEX idx_photos_date ON photos(date);
        CREATE INDEX idx_photos_missing ON photos(is_missing);
        CREATE INDEX idx_photos_favorite ON photos(favorite);
        CREATE INDEX idx_photos_screenshot ON photos(screenshot);
        CREATE INDEX idx_photos_score_overall ON photos(score_overall);
        """
    )


def insert_photo(conn, p):
    score = getattr(p, "score", None)
    path_derivatives = getattr(p, "path_derivatives", None) or []

    conn.execute(
        """
        INSERT OR REPLACE INTO photos (
            uuid,
            original_filename,
            filename,
            date,
            date_added,
            date_original,

            is_photo,
            is_movie,
            favorite,
            hidden,
            intrash,
            visible,

            is_missing,
            in_cloud,
            is_cloud_asset,

            path,
            path_preview,
            path_derivatives_json,

            width,
            height,
            original_width,
            original_height,
            original_filesize,
            uti,
            uti_original,

            albums_json,
            persons_json,
            labels_json,
            labels_normalized_json,
            keywords_json,

            ai_caption,

            screenshot,
            selfie,
            live_photo,
            burst,
            hdr,
            panorama,
            slow_mo,
            time_lapse,

            latitude,
            longitude,
            place,

            score_overall,
            score_curation,
            score_behavioral,
            score_harmonious_color,
            score_interesting_subject,
            score_lively_color,
            score_pleasant_composition,
            score_sharply_focused_subject,
            score_tastefully_blurred,
            score_well_chosen_subject,
            score_well_framed_subject,
            score_well_timed_shot,

            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?
        )
        """,
        (
            getattr(p, "uuid", None),
            getattr(p, "original_filename", None),
            getattr(p, "filename", None),
            dt_to_iso(getattr(p, "date", None)),
            dt_to_iso(getattr(p, "date_added", None)),
            dt_to_iso(getattr(p, "date_original", None)),

            int(bool(getattr(p, "isphoto", False))),
            int(bool(getattr(p, "ismovie", False))),
            int(bool(getattr(p, "favorite", False))),
            int(bool(getattr(p, "hidden", False))),
            int(bool(getattr(p, "intrash", False))),
            int(bool(getattr(p, "visible", False))),

            int(bool(getattr(p, "ismissing", False))),
            int(bool(getattr(p, "incloud", False))),
            int(bool(getattr(p, "iscloudasset", False))),

            getattr(p, "path", None),
            first_or_none(path_derivatives),
            safe_json(path_derivatives),

            getattr(p, "width", None),
            getattr(p, "height", None),
            getattr(p, "original_width", None),
            getattr(p, "original_height", None),
            getattr(p, "original_filesize", None),
            getattr(p, "uti", None),
            getattr(p, "uti_original", None),

            safe_json(getattr(p, "albums", [])),
            safe_json(getattr(p, "persons", [])),
            safe_json(getattr(p, "labels", [])),
            safe_json(getattr(p, "labels_normalized", [])),
            safe_json(getattr(p, "keywords", [])),

            getattr(p, "ai_caption", None),

            int(bool(getattr(p, "screenshot", False))),
            int(bool(getattr(p, "selfie", False))),
            int(bool(getattr(p, "live_photo", False))),
            int(bool(getattr(p, "burst", False))),
            int(bool(getattr(p, "hdr", False))),
            int(bool(getattr(p, "panorama", False))),
            int(bool(getattr(p, "slow_mo", False))),
            int(bool(getattr(p, "time_lapse", False))),

            getattr(p, "latitude", None),
            getattr(p, "longitude", None),
            str(getattr(p, "place", None)) if getattr(p, "place", None) else None,

            score_value(score, "overall"),
            score_value(score, "curation"),
            score_value(score, "behavioral"),
            score_value(score, "harmonious_color"),
            score_value(score, "interesting_subject"),
            score_value(score, "lively_color"),
            score_value(score, "pleasant_composition"),
            score_value(score, "sharply_focused_subject"),
            score_value(score, "tastefully_blurred"),
            score_value(score, "well_chosen_subject"),
            score_value(score, "well_framed_subject"),
            score_value(score, "well_timed_shot"),

            datetime.now().isoformat(timespec="seconds"),
        ),
    )


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("Starting Photos Library scan...", flush=True)
    print("Loading osxphotos module...", flush=True)

    import osxphotos

    print("Opening Photos library database...", flush=True)
    photosdb = osxphotos.PhotosDB()

    print("Reading Photos assets. This may take a little while on first run...", flush=True)
    photos = photosdb.photos()

    print(f"Found {len(photos)} assets", flush=True)

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    for idx, photo in enumerate(photos, start=1):
        insert_photo(conn, photo)

        if idx % 500 == 0:
            conn.commit()
            print(f"Indexed {idx}/{len(photos)}")

    conn.commit()
    conn.close()

    print(f"Done. Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
