#!/usr/bin/env python3

import argparse
import html
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import quote


TRANSLATIONS = {
    "tr": {
        "title": "Bu Mac’te orijinali hazır anılar",
        "subtitle": "Orijinal dosyası veya güvenli preview kopyası lokal olarak erişilebilen fotoğraflardan oluşturulan ilk agrandiz galerisi.",
        "brand_tag": "lokal galeri",
        "available": "lokal fotoğraf",
        "shown": "gösteriliyor",
        "score": "Skor",
        "album": "Albüm",
        "caption": "AI açıklaması",
        "labels": "Etiketler",
        "no_caption": "Açıklama yok",
        "no_album": "Albüm yok",
        "source_note": "Bu sayfa yalnızca bu Mac üzerinde erişilebilen görsellerden üretildi. iCloud-only fotoğraflar daha sonra ayrı bir keşif/download akışına alınacak.",
        "open_dashboard": "Dashboard’a dön",
    },
    "en": {
        "title": "Originals ready on this Mac",
        "subtitle": "First agrandiz gallery built from photos whose original files or safe preview copies are locally available.",
        "brand_tag": "local gallery",
        "available": "local photos",
        "shown": "shown",
        "score": "Score",
        "album": "Album",
        "caption": "AI caption",
        "labels": "Labels",
        "no_caption": "No caption",
        "no_album": "No album",
        "source_note": "This page is generated only from images available on this Mac. iCloud-only photos will later move into a separate discovery/download flow.",
        "open_dashboard": "Back to dashboard",
    },
}


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def num(n):
    return f"{n:,}".replace(",", ".")


def load_json(raw, default=None):
    if default is None:
        default = []
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default




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


def pick_source_file(row):
    """
    Prefer path_preview because it is smaller and safer for static gallery.
    Fall back to original path if preview is missing.
    """
    preview = row["path_preview"]
    original = row["path"]

    for candidate in [preview, original]:
        if candidate and candidate != "None":
            p = Path(candidate)
            if p.exists() and p.is_file():
                return p

    return None


def extension_for(path):
    suffix = path.suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        return suffix
    return ".jpg"


def materialize_thumb(src, uuid, thumbs_dir):
    """
    Copy preview/original image into cache/thumbs with a stable filename.
    This avoids fragile absolute file:// references in generated HTML.
    """
    ext = extension_for(src)
    dst = thumbs_dir / f"{uuid}{ext}"

    if not dst.exists():
        shutil.copy2(src, dst)

    return dst


def fetch_local_photos(conn, limit):
    conn.row_factory = sqlite3.Row

    sql = """
    SELECT
        uuid,
        original_filename,
        date,
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
    WHERE is_missing = 0
      AND is_photo = 1
      AND (
        path_preview IS NOT NULL
        OR path IS NOT NULL
      )
    ORDER BY
      score_overall DESC,
      date DESC
    LIMIT ?
    """

    return conn.execute(sql, (limit,)).fetchall()


def build_gallery_items(rows, thumbs_dir):
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


def render_item(item, t):
    labels_html = "".join(f'<span class="chip">{esc(label)}</span>' for label in item["labels"])
    score = f"{item['score']:.3f}" if item["score"] is not None else "-"
    caption = item["caption"] or t["no_caption"]
    album = item["album"] or t["no_album"]
    date = item["date"] or ""
    filename = item["filename"] or ""
    dimensions = ""

    if item["width"] and item["height"]:
        dimensions = f"{item['width']}×{item['height']}"

    badges = []
    if item["favorite"]:
        badges.append("★")
    if item["live_photo"]:
        badges.append("Live")
    if item["screenshot"]:
        badges.append("Screenshot")

    badges_html = "".join(f'<span class="mini-badge">{esc(b)}</span>' for b in badges)

    return f"""
    <article class="gallery-card">
      <div class="image-wrap">
        <img src="{esc(item['thumb'])}" alt="{esc(caption)}" loading="lazy">
      </div>
      <div class="gallery-meta">
        <div class="topline">
          <span class="score-pill">{t['score']}: {score}</span>
          <span class="dim">{esc(dimensions)}</span>
        </div>
        <div class="caption">{esc(caption)}</div>
        <div class="submeta">{esc(filename)} · {esc(date)}</div>
        <div class="submeta">{t['album']}: {esc(album)}</div>
        <div class="badges">{badges_html}</div>
        <div class="chips">{labels_html}</div>
      </div>
    </article>
    """


def render_gallery(lang, items, total_local):
    t = TRANSLATIONS[lang]

    cards = "\n".join(render_item(item, t) for item in items)

    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>agrandiz local gallery</title>
  <link rel="stylesheet" href="../themes/apple.css">
  <style>
    .gallery-hero {{
      margin-bottom: 24px;
    }}

    .gallery-summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}

    .summary-card {{
      background: rgba(255,255,255,0.78);
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 24px;
      padding: 22px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }}

    .summary-card .value {{
      font-size: 40px;
      font-weight: 700;
      letter-spacing: -0.04em;
    }}

    .summary-card .label {{
      color: #6e6e73;
      margin-top: 6px;
    }}

    .note-panel {{
      background: rgba(255,255,255,0.78);
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 24px;
      padding: 20px;
      color: #6e6e73;
      line-height: 1.5;
      margin-bottom: 24px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }}

    .gallery-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
    }}

    .gallery-card {{
      overflow: hidden;
      background: #fff;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }}

    .image-wrap {{
      aspect-ratio: 4 / 3;
      overflow: hidden;
      background: #eceff3;
    }}

    .image-wrap img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}

    .gallery-meta {{
      padding: 16px;
    }}

    .topline {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      margin-bottom: 10px;
    }}

    .score-pill {{
      font-size: 12px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(0,113,227,0.12);
      color: #0071e3;
      font-weight: 650;
    }}

    .dim {{
      color: #6e6e73;
      font-size: 12px;
    }}

    .caption {{
      font-size: 14px;
      line-height: 1.45;
      min-height: 42px;
      margin-bottom: 8px;
    }}

    .submeta {{
      color: #6e6e73;
      font-size: 12px;
      margin-bottom: 6px;
      line-height: 1.35;
      word-break: break-word;
    }}

    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }}

    .mini-badge {{
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #f3f4f6;
      color: #3a3a3c;
    }}

    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }}

    .chip {{
      font-size: 11px;
      padding: 5px 8px;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.08);
      background: #fff;
      color: #3a3a3c;
    }}

    .back-link {{
      display: inline-flex;
      align-items: center;
      text-decoration: none;
      color: #0071e3;
      font-weight: 650;
      margin-top: 20px;
    }}

    @media (max-width: 1200px) {{
      .gallery-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 900px) {{
      .gallery-summary,
      .gallery-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 620px) {{
      .gallery-summary,
      .gallery-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body class="theme-apple profile-apple_icloud">
  <div class="shell">
    <header class="hero gallery-hero">
      <div class="brand">agrandiz <span>{esc(t['brand_tag'])}</span></div>
      <div class="hero-copy">
        <h1>{esc(t['title'])}</h1>
        <p>{esc(t['subtitle'])}</p>
        <div class="meta-line">Mode: <strong>local preview gallery</strong></div>
      </div>
    </header>

    <section class="gallery-summary">
      <article class="summary-card">
        <div class="value">{num(total_local)}</div>
        <div class="label">{esc(t['available'])}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(len(items))}</div>
        <div class="label">{esc(t['shown'])}</div>
      </article>
      <article class="summary-card">
        <div class="value">0</div>
        <div class="label">uploads / deletes</div>
      </article>
    </section>

    <section class="note-panel">
      {esc(t['source_note'])}
    </section>

    <section class="gallery-grid">
      {cards}
    </section>

    <a class="back-link" href="index.html">← {esc(t['open_dashboard'])}</a>
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    total_local = conn.execute(
        "SELECT COUNT(*) FROM photos WHERE is_missing = 0 AND is_photo = 1"
    ).fetchone()[0]

    rows = fetch_local_photos(conn, args.limit)
    conn.close()

    items = build_gallery_items(rows, thumbs_dir)

    data_file = outdir / "local_gallery_data.json"
    data_file.write_text(
        json.dumps(
            {
                "total_local_photos": total_local,
                "shown": len(items),
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {data_file}")

    langs = ["tr", "en"] if args.lang == "both" else [args.lang]

    for lang in langs:
        html_text = render_gallery(lang, items, total_local)
        out_file = outdir / f"local-gallery.{lang}.apple.apple_icloud.html"
        out_file.write_text(html_text, encoding="utf-8")
        print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
