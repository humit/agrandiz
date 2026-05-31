#!/usr/bin/env python3

import argparse
import sqlite3
import json
import html
import shutil
from pathlib import Path
from collections import Counter
from datetime import datetime
from urllib.parse import quote


TRANSLATIONS = {
    "tr": {
        "brand_tag": "Aile arşivinizi görünür hale getirin",
        "hero_title": "agrandiz arşivinizdeki hikâyeleri buldu",
        "hero_subtitle": "Mac + Photos/iCloud arşivinizden keşfedilen ilk özet ve albüm adayları.",
        "memories_found": "anı bulundu",
        "available_local": "Bu Mac üzerinde erişilebilir",
        "icloud_only": "Yalnızca iCloud’da",
        "whatsapp_memories": "WhatsApp anısı",
        "child_moments": "Çocuk anı etiketi",
        "favorites": "Favori",
        "screenshots": "Ekran görüntüsü",
        "live_photos": "Live Photo",
        "people_photos": "İnsan içeren fotoğraf",
        "top_labels": "Öne çıkan etiketler",
        "suggested_stories": "Önerilen Hikâyeler",
        "top_scored": "Apple analizine göre öne çıkan kareler",
        "top_local": "Bu Mac’te hazır güçlü kareler",
        "cloud_only_highlights": "iCloud’da duran güçlü kareler",
        "story_whatsapp_title": "WhatsApp Anıları",
        "story_whatsapp_desc": "Dağınık mesaj geçmişinin içinden sürpriz albüm adayları.",
        "story_child_title": "Çocukluk Anları",
        "story_child_desc": "Çocuk etiketli kareler aile albümü için güçlü bir başlangıç.",
        "story_food_title": "Sofralar ve Buluşmalar",
        "story_food_desc": "Yemek, masa ve buluşma temalı anılar.",
        "story_nature_title": "Ağaçlar ve Açık Hava",
        "story_nature_desc": "Doğa, yürüyüş ve kamp hikâyeleri için adaylar.",
        "story_beautiful_title": "Beklenmedik Güzel Kareler",
        "story_beautiful_desc": "Apple’ın estetik olarak yüksek puanladığı unutulmuş fotoğraflar.",
        "story_people_title": "İnsanlar ve Yakın Çevre",
        "story_people_desc": "İnsan içeren anılar daha sonra kişi bazlı albümlere dönüşebilir.",
        "ready_now": "Orijinal hazır",
        "needs_download": "Orijinal iCloud’da",
        "score": "Skor",
        "album": "Albüm",
        "caption": "AI açıklaması",
        "no_caption": "Açıklama yok",
        "generated": "Oluşturuldu",
        "theme": "Tema",
        "platform": "Kaynak profili",
        "apple_note": "Bu ilk sürüm Apple Photos/iCloud arşivine göre tasarlanmıştır. Görseller güvenli lokal preview kopyalarından gösterilir.",
    },
    "en": {
        "brand_tag": "Make your family archive visible",
        "hero_title": "agrandiz found stories in your archive",
        "hero_subtitle": "First summary and album candidates discovered from your Mac + Photos/iCloud archive.",
        "memories_found": "memories found",
        "available_local": "Available on this Mac",
        "icloud_only": "Stored only in iCloud",
        "whatsapp_memories": "WhatsApp memories",
        "child_moments": "Child-labeled moments",
        "favorites": "Favorites",
        "screenshots": "Screenshots",
        "live_photos": "Live Photos",
        "people_photos": "People photos",
        "top_labels": "Top labels",
        "suggested_stories": "Suggested Stories",
        "top_scored": "Top memories according to Apple analysis",
        "top_local": "Strong local memories ready now",
        "cloud_only_highlights": "Strong memories still in iCloud",
        "story_whatsapp_title": "WhatsApp Highlights",
        "story_whatsapp_desc": "Surprising album candidates discovered inside chat history.",
        "story_child_title": "Childhood Moments",
        "story_child_desc": "Child-labeled images form a strong starting point for family albums.",
        "story_food_title": "Tables & Gatherings",
        "story_food_desc": "Food, table and gathering memories ready for ritual/family stories.",
        "story_nature_title": "Trees & Outdoor Days",
        "story_nature_desc": "Candidates for nature, walks and camping stories.",
        "story_beautiful_title": "Surprisingly Beautiful",
        "story_beautiful_desc": "Forgotten photos Apple rated highly.",
        "story_people_title": "People & Inner Circle",
        "story_people_desc": "People-rich memories that can later evolve into person-based albums.",
        "ready_now": "Original ready",
        "needs_download": "Original in iCloud",
        "score": "Score",
        "album": "Album",
        "caption": "AI caption",
        "no_caption": "No caption",
        "generated": "Generated",
        "theme": "Theme",
        "platform": "Source profile",
        "apple_note": "This first version is designed around Apple Photos/iCloud archives. Images are rendered from safe local preview copies.",
    },
}


def q1(conn, sql):
    return conn.execute(sql).fetchone()[0]


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


def extension_for(path):
    suffix = path.suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        return suffix
    return ".jpg"


def materialize_thumb(src_path, uuid, thumbs_dir):
    """
    Copy a Photos preview/original into cache/thumbs and return a relative HTML path.
    This avoids fragile file:// URLs and browser security/path issues.
    """
    if not src_path or src_path == "None":
        return None

    src = Path(src_path)
    if not src.exists() or not src.is_file():
        return None

    ext = extension_for(src)
    dst = thumbs_dir / f"{uuid}{ext}"

    if not dst.exists():
        shutil.copy2(src, dst)

    return f"thumbs/{quote(dst.name)}"


def choose_source_path(row):
    """
    Prefer path_preview. Fall back to original path.
    For iCloud-only items, path_preview is often still available.
    """
    preview = row["path_preview"]
    original = row["path"]

    for candidate in [preview, original]:
        if candidate and candidate != "None":
            p = Path(candidate)
            if p.exists() and p.is_file():
                return str(p)

    return None




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


def top_labels(conn, limit=12):
    rows = conn.execute(
        "SELECT labels_normalized_json FROM photos WHERE labels_normalized_json IS NOT NULL"
    ).fetchall()

    counter = Counter()

    for (raw,) in rows:
        for label in load_json(raw):
            if label and label != "_unknown_":
                counter[label] += 1

    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def top_photos(conn, thumbs_dir, where="1=1", limit=12):
    conn.row_factory = sqlite3.Row

    sql = f"""
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
    WHERE {where}
      AND score_overall IS NOT NULL
    ORDER BY score_overall DESC
    LIMIT ?
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


def build_data(conn, theme, profile, thumbs_dir):
    metrics = {
        "total": q1(conn, "SELECT COUNT(*) FROM photos"),
        "local": q1(conn, "SELECT COUNT(*) FROM photos WHERE is_missing = 0"),
        "icloud": q1(conn, "SELECT COUNT(*) FROM photos WHERE is_missing = 1"),
        "favorites": q1(conn, "SELECT COUNT(*) FROM photos WHERE favorite = 1"),
        "screenshots": q1(conn, "SELECT COUNT(*) FROM photos WHERE screenshot = 1"),
        "live_photos": q1(conn, "SELECT COUNT(*) FROM photos WHERE live_photo = 1"),
        "whatsapp": q1(conn, "SELECT COUNT(*) FROM photos WHERE albums_json LIKE '%WhatsApp%'"),
        "child": q1(conn, "SELECT COUNT(*) FROM photos WHERE labels_normalized_json LIKE '%child%'"),
        "people": q1(conn, "SELECT COUNT(*) FROM photos WHERE labels_normalized_json LIKE '%people%'"),
        "food": q1(conn, "SELECT COUNT(*) FROM photos WHERE labels_normalized_json LIKE '%food%'"),
        "tree": q1(conn, "SELECT COUNT(*) FROM photos WHERE labels_normalized_json LIKE '%tree%'"),
    }

    suggested_stories = [
        {"id": "whatsapp_highlights", "count": metrics["whatsapp"], "theme": "whatsapp", "confidence": "high"},
        {"id": "childhood_moments", "count": metrics["child"], "theme": "family", "confidence": "high"},
        {"id": "tables_and_gatherings", "count": metrics["food"], "theme": "rituals", "confidence": "medium"},
        {"id": "trees_and_outdoor_days", "count": metrics["tree"], "theme": "nature", "confidence": "medium"},
        {"id": "surprisingly_beautiful", "count": 12, "theme": "aesthetic", "confidence": "medium"},
        {"id": "people_and_inner_circle", "count": metrics["people"], "theme": "people", "confidence": "medium"},
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "product": "agrandiz",
        "theme": theme,
        "profile": profile,
        "source": {
            "type": "apple_photos_icloud",
            "cache": "cache/agrandiz.sqlite",
            "thumbs": "cache/thumbs",
        },
        "metrics": metrics,
        "top_labels": top_labels(conn),
        "suggested_stories": suggested_stories,
        "photo_sets": {
            "top_scored": top_photos(conn, thumbs_dir, "1=1", 12),
            "top_local": top_photos(conn, thumbs_dir, "is_missing = 0", 8),
            "top_cloud": top_photos(conn, thumbs_dir, "is_missing = 1", 8),
            "whatsapp_highlights": top_photos(conn, thumbs_dir, "albums_json LIKE '%WhatsApp%'", 12),
            "childhood_moments": top_photos(conn, thumbs_dir, "labels_normalized_json LIKE '%child%'", 12),
        },
    }


def write_dashboard_data(outdir, data):
    out_file = outdir / "dashboard_data.json"
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_file}")


def render_photo_card(photo, t):
    chips = "".join(f'<span class="chip">{esc(label)}</span>' for label in photo["labels"])

    availability = t["needs_download"] if photo["is_missing"] else t["ready_now"]
    availability_class = "icloud" if photo["is_missing"] else "local"

    caption = esc(photo["caption"] or t["no_caption"])
    album = esc(photo["album"] or "-")
    filename = esc(photo["filename"] or "")
    date = esc(photo["date"] or "")
    score = f"{photo['score']:.3f}" if photo["score"] is not None else "-"

    if photo.get("thumb"):
        image_html = f'<img src="{esc(photo["thumb"])}" alt="{caption}" loading="lazy">'
    else:
        image_html = '<div class="thumb-placeholder"></div>'

    badges = []
    if photo.get("favorite"):
        badges.append("★")
    if photo.get("live_photo"):
        badges.append("Live")
    if photo.get("screenshot"):
        badges.append("Screenshot")

    badges_html = "".join(f'<span class="chip">{esc(badge)}</span>' for badge in badges)

    return f"""
    <article class="photo-card">
      <div class="thumb-wrap">{image_html}</div>
      <div class="photo-meta">
        <div class="row top">
          <span class="availability {availability_class}">{availability}</span>
          <span class="score">{t['score']}: {score}</span>
        </div>
        <div class="filename">{filename}</div>
        <div class="caption">{caption}</div>
        <div class="submeta">{t['album']}: {album} · {date}</div>
        <div class="chips">{badges_html}{chips}</div>
      </div>
    </article>
    """


def render_dashboard(theme, lang, profile, data):
    t = TRANSLATIONS[lang]
    m = data["metrics"]

    labels_html = "".join(
        f'<span class="label-pill">{esc(item["label"])} <strong>{item["count"]}</strong></span>'
        for item in data["top_labels"]
    )

    story_defs = [
        ("whatsapp_highlights", t["story_whatsapp_title"], t["story_whatsapp_desc"]),
        ("childhood_moments", t["story_child_title"], t["story_child_desc"]),
        ("tables_and_gatherings", t["story_food_title"], t["story_food_desc"]),
        ("trees_and_outdoor_days", t["story_nature_title"], t["story_nature_desc"]),
        ("surprisingly_beautiful", t["story_beautiful_title"], t["story_beautiful_desc"]),
        ("people_and_inner_circle", t["story_people_title"], t["story_people_desc"]),
    ]

    story_map = {story["id"]: story for story in data["suggested_stories"]}

    story_cards = ""
    for story_id, title, desc in story_defs:
        count = story_map.get(story_id, {}).get("count", 0)
        story_cards += f"""
        <article class="story-card">
          <div class="story-count">{num(count)}</div>
          <h3>{esc(title)}</h3>
          <p>{esc(desc)}</p>
        </article>
        """

    top_scored_html = "".join(render_photo_card(p, t) for p in data["photo_sets"]["top_scored"])
    top_local_html = "".join(render_photo_card(p, t) for p in data["photo_sets"]["top_local"])
    top_cloud_html = "".join(render_photo_card(p, t) for p in data["photo_sets"]["top_cloud"])

    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>agrandiz dashboard</title>
  <link rel="stylesheet" href="../themes/{theme}.css">
</head>
<body class="theme-{theme} profile-{profile}">
  <div class="shell">
    <header class="hero">
      <div class="brand">agrandiz <span>{esc(t['brand_tag'])}</span></div>
      <div class="hero-copy">
        <h1>{esc(t['hero_title'])}</h1>
        <p>{esc(t['hero_subtitle'])}</p>
        <div class="meta-line">
          {t['theme']}: <strong>{theme}</strong> ·
          {t['platform']}: <strong>{profile}</strong> ·
          {t['generated']}: <strong>{esc(data["generated_at"])}</strong>
        </div>
      </div>
    </header>

    <section class="metrics-grid">
      <article class="metric-card metric-primary">
        <div class="metric-value">{num(m['total'])}</div>
        <div class="metric-label">{t['memories_found']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['local'])}</div>
        <div class="metric-label">{t['available_local']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['icloud'])}</div>
        <div class="metric-label">{t['icloud_only']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['whatsapp'])}</div>
        <div class="metric-label">{t['whatsapp_memories']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['child'])}</div>
        <div class="metric-label">{t['child_moments']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['people'])}</div>
        <div class="metric-label">{t['people_photos']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['favorites'])}</div>
        <div class="metric-label">{t['favorites']}</div>
      </article>

      <article class="metric-card">
        <div class="metric-value">{num(m['screenshots'])}</div>
        <div class="metric-label">{t['screenshots']}</div>
      </article>
    </section>

    <section class="info-strip">
      <div class="panel">
        <h2>{esc(t['top_labels'])}</h2>
        <div class="label-pills">{labels_html}</div>
      </div>
      <div class="panel small-note">{esc(t['apple_note'])}</div>
    </section>

    <section>
      <h2 class="section-title">{esc(t['suggested_stories'])}</h2>
      <div class="stories-grid">{story_cards}</div>
    </section>

    <section>
      <h2 class="section-title">{esc(t['top_scored'])}</h2>
      <div class="photo-grid">{top_scored_html}</div>
    </section>

    <section>
      <h2 class="section-title">{esc(t['top_local'])}</h2>
      <div class="photo-grid compact">{top_local_html}</div>
    </section>

    <section>
      <h2 class="section-title">{esc(t['cloud_only_highlights'])}</h2>
      <div class="photo-grid compact">{top_cloud_html}</div>
    </section>
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--theme", default="apple", choices=["apple", "google", "windows"])
    parser.add_argument(
        "--profile",
        default="apple_icloud",
        choices=["apple_icloud", "google_photos", "windows_local"],
    )
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    data = build_data(conn, args.theme, args.profile, thumbs_dir)
    conn.close()

    write_dashboard_data(outdir, data)

    # Canonical dashboard output. UI language is handled client-side via i18n.
    html = render_dashboard(args.theme, "en", args.profile, data)
    out_file = outdir / f"dashboard.{args.theme}.{args.profile}.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
