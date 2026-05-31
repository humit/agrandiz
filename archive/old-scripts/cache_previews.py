#!/usr/bin/env python3

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import quote


def extension_for(path):
    suffix = path.suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        return suffix
    return ".jpg"


def copy_preview(src, uuid, thumbs_dir):
    ext = extension_for(src)
    dst = thumbs_dir / f"{uuid}{ext}"

    if not dst.exists():
        shutil.copy2(src, dst)

    return f"thumbs/{quote(dst.name)}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            uuid,
            is_missing,
            path,
            path_preview,
            score_overall,
            ai_caption,
            original_filename
        FROM photos
        ORDER BY
            score_overall DESC,
            date DESC
        """
    ).fetchall()

    stats = {
        "total_assets": 0,
        "original_local": 0,
        "original_icloud": 0,
        "preview_path_present": 0,
        "preview_file_exists": 0,
        "preview_cached": 0,
        "preview_missing": 0,
        "original_local_preview_cached": 0,
        "original_icloud_preview_cached": 0,
        "examples_cached": [],
        "examples_missing": [],
    }

    cached = []
    missing = []

    for row in rows:
        stats["total_assets"] += 1

        if row["is_missing"]:
            stats["original_icloud"] += 1
        else:
            stats["original_local"] += 1

        preview = row["path_preview"]

        if preview:
            stats["preview_path_present"] += 1

        src = None

        if preview and preview != "None":
            p = Path(preview)
            if p.exists() and p.is_file():
                src = p
                stats["preview_file_exists"] += 1

        # Fall back to original only for local originals.
        if src is None and not row["is_missing"] and row["path"] and row["path"] != "None":
            p = Path(row["path"])
            if p.exists() and p.is_file():
                src = p

        if src is None:
            stats["preview_missing"] += 1
            if len(missing) < 20:
                missing.append(
                    {
                        "uuid": row["uuid"],
                        "original_filename": row["original_filename"],
                        "is_missing": bool(row["is_missing"]),
                        "score": row["score_overall"],
                        "caption": row["ai_caption"],
                        "path_preview": row["path_preview"],
                    }
                )
            continue

        thumb = copy_preview(src, row["uuid"], thumbs_dir)

        stats["preview_cached"] += 1
        if row["is_missing"]:
            stats["original_icloud_preview_cached"] += 1
        else:
            stats["original_local_preview_cached"] += 1

        if len(cached) < 30:
            cached.append(
                {
                    "uuid": row["uuid"],
                    "original_filename": row["original_filename"],
                    "is_missing": bool(row["is_missing"]),
                    "score": row["score_overall"],
                    "caption": row["ai_caption"],
                    "thumb": thumb,
                }
            )

        if args.limit and stats["preview_cached"] >= args.limit:
            break

    stats["examples_cached"] = cached
    stats["examples_missing"] = missing

    report_path = outdir / "preview_report.json"
    report_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
