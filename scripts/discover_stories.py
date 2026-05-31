#!/usr/bin/env python3

import argparse
import html
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


STORY_DEFS = [
    {
        "id": "childhood_moments",
        "emoji": "🧒",
        "title_tr": "Çocukluk Anları",
        "title_en": "Childhood Moments",
        "desc_tr": "Çocuk etiketli karelerden aile albümü veya kısa büyüme hikâyesi.",
        "desc_en": "Child-labeled moments suitable for a family album or short growing-up story.",
        "keywords": ["child", "children", "kid", "baby", "boy", "girl", "school", "playground"],
        "min_score": 0.45,
        "max_items": 36,
        "output_types": ["web_gallery", "family_album", "short_reel"],
    },
    {
        "id": "whatsapp_highlights",
        "emoji": "💬",
        "title_tr": "WhatsApp’tan Gelen Güçlü Anılar",
        "title_en": "WhatsApp Highlights",
        "desc_tr": "Mesaj geçmişinin içinde kaybolmuş, albüme veya hediye seçkisine dönüşebilecek kareler.",
        "desc_en": "Strong memories hidden in chat history, suitable for a gift album or highlight gallery.",
        "album_like": "WhatsApp",
        "min_score": 0.55,
        "max_items": 36,
        "output_types": ["web_gallery", "gift_album", "short_reel"],
    },
    {
        "id": "fishing_and_sea",
        "emoji": "🎣",
        "title_tr": "Balık, Deniz ve Su Hikâyeleri",
        "title_en": "Fishing, Sea & Water Stories",
        "desc_tr": "Balık, deniz, su, tekne ve sahil temalı hediye albümü veya reel adayı.",
        "desc_en": "Fish, sea, water, boat and coast themed candidates for a gift album or reel.",
        "keywords": ["fish", "fishing", "sea", "water", "boat", "coast", "beach", "lake", "ocean", "shark"],
        "min_score": 0.45,
        "max_items": 36,
        "output_types": ["gift_album", "short_reel", "web_gallery"],
    },
    {
        "id": "outdoor_and_camping",
        "emoji": "🏕️",
        "title_tr": "Açık Hava, Kamp ve Yol",
        "title_en": "Outdoor, Camping & Roads",
        "desc_tr": "Kamp, yürüyüş, doğa, yol ve açık hava anılarından kısa hikâye adayları.",
        "desc_en": "Camping, walking, nature, roads and outdoor memories suitable for short stories.",
        "keywords": ["camping", "tent", "tree", "forest", "mountain", "desert", "road", "outdoor", "grass", "plant", "sky"],
        "min_score": 0.45,
        "max_items": 36,
        "output_types": ["short_reel", "web_gallery", "travel_album"],
    },
    {
        "id": "tables_and_gatherings",
        "emoji": "🍽️",
        "title_tr": "Sofralar ve Buluşmalar",
        "title_en": "Tables & Gatherings",
        "desc_tr": "Yemek, masa, aile ve arkadaş buluşmalarından ritüel/hafıza albümü adayı.",
        "desc_en": "Food, table, family and friend gatherings suitable for ritual/memory albums.",
        "keywords": ["food", "meal", "table", "restaurant", "plate", "drink", "brunch", "dinner", "people"],
        "min_score": 0.42,
        "max_items": 36,
        "output_types": ["web_gallery", "family_album", "short_reel"],
    },
    {
        "id": "pets_and_animals",
        "emoji": "🐾",
        "title_tr": "Patili ve Hayvanlı Anılar",
        "title_en": "Pets & Animal Moments",
        "desc_tr": "Kedi, köpek ve diğer hayvan temalı eğlenceli hediye/reel adayları.",
        "desc_en": "Cat, dog and animal-themed candidates for playful gift albums or reels.",
        "keywords": ["animal", "dog", "cat", "canine", "puppy", "pet", "bird", "horse"],
        "min_score": 0.45,
        "max_items": 36,
        "output_types": ["gift_album", "short_reel", "web_gallery"],
    },
    {
        "id": "travel_and_places",
        "emoji": "🧳",
        "title_tr": "Seyahat ve Yer Hafızası",
        "title_en": "Travel & Place Memory",
        "desc_tr": "Yolculuk, şehir, manzara, yapı ve uzak yerlerden seyahat hikâyesi adayı.",
        "desc_en": "Travel, city, landscape, architecture and far-away place story candidates.",
        "keywords": ["building", "land", "sky", "mountain", "city", "road", "beach", "desert", "water", "aircraft", "hotel"],
        "min_score": 0.50,
        "max_items": 36,
        "output_types": ["travel_album", "short_reel", "web_gallery"],
    },
    {
        "id": "pandemic_days",
        "emoji": "🏠",
        "title_tr": "Pandemi Günleri",
        "title_en": "Pandemic Days",
        "desc_tr": "2020–2021 döneminden ev, ekran, çocuk, yemek ve gündelik hayat hafızası.",
        "desc_en": "Home, screens, children, food and daily life memories from 2020–2021.",
        "from_date": "2020-03-01",
        "to_date": "2021-12-31",
        "keywords": ["home", "interior room", "food", "table", "child", "people", "mask", "computer", "screen"],
        "min_score": 0.35,
        "max_items": 36,
        "output_types": ["period_album", "web_gallery", "short_reel"],
    },
    {
        "id": "surprisingly_beautiful",
        "emoji": "✨",
        "title_tr": "Beklenmedik Güzel Kareler",
        "title_en": "Surprisingly Beautiful",
        "desc_tr": "Apple Photos analizine göre yüksek estetik skorlu, muhtemelen unutulmuş kareler.",
        "desc_en": "High-scoring images according to Apple Photos analysis, probably forgotten.",
        "min_score": 0.70,
        "max_items": 36,
        "output_types": ["short_reel", "web_gallery", "cover_candidates"],
    },
]


TR_REEL_TEMPLATES = {
    "childhood_moments": "Çocukların büyüme hikâyesinden kısa ve duygusal bir reel.",
    "whatsapp_highlights": "WhatsApp’ın içinde kaybolmuş sürpriz anılardan hızlı bir highlight reel.",
    "fishing_and_sea": "Balık, deniz ve su kenarı anılarından hediye edilebilir kısa video.",
    "outdoor_and_camping": "Kamp, yürüyüş ve açık hava anılarından ritmik bir doğa reel’i.",
    "tables_and_gatherings": "Sofralar, arkadaşlar ve aile buluşmalarından sıcak bir kısa hikâye.",
    "pets_and_animals": "Hayvanlı, komik ve sevimli anlardan paylaşılabilir kısa video.",
    "travel_and_places": "Yol, manzara ve şehir karelerinden seyahat tadında kısa video.",
    "pandemic_days": "Evde geçen pandemi günlerinden dönem hafızası kısa filmi.",
    "surprisingly_beautiful": "Apple’ın yüksek puanladığı beklenmedik karelerden görsel bir seçki.",
}

EN_REEL_TEMPLATES = {
    "childhood_moments": "A short emotional reel from children’s growing-up moments.",
    "whatsapp_highlights": "A fast highlight reel from memories hidden inside WhatsApp.",
    "fishing_and_sea": "A giftable short video built from fishing, sea and water moments.",
    "outdoor_and_camping": "A rhythmic outdoor reel from camping, walking and nature memories.",
    "tables_and_gatherings": "A warm short story from tables, friends and family gatherings.",
    "pets_and_animals": "A playful short video from cute and funny animal moments.",
    "travel_and_places": "A travel-flavored short video from roads, places and landscapes.",
    "pandemic_days": "A period-memory short film from days spent at home during the pandemic.",
    "surprisingly_beautiful": "A visual selection from unexpectedly high-scoring images.",
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


def choose_source_path(row):
    for key in ["path_preview", "path"]:
        value = row[key]
        if value and value != "None":
            p = Path(value)
            if p.exists() and p.is_file():
                return p
    return None


def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def dedupe_key(item):
    filename = normalize(item.get("filename"))
    caption = normalize(item.get("caption"))
    album = normalize(item.get("album"))
    score = item.get("score")
    score_bucket = round(float(score), 3) if score is not None else ""
    if filename or caption:
        return (filename, caption, album, score_bucket)
    return (item.get("uuid"),)


def row_text(row):
    labels = " ".join(load_json(row["labels_normalized_json"]))
    caption = row["ai_caption"] or ""
    filename = row["original_filename"] or ""
    albums = " ".join(load_json(row["albums_json"]))
    return f"{labels} {caption} {filename} {albums}".lower()


def row_matches_story(row, story):
    text = row_text(row)

    score = row["score_overall"]
    if story.get("min_score") is not None:
        if score is None or float(score) < float(story["min_score"]):
            return False

    if story.get("album_like"):
        albums = " ".join(load_json(row["albums_json"])).lower()
        if story["album_like"].lower() not in albums:
            return False

    if story.get("from_date"):
        date = row["date"] or ""
        if date[:10] < story["from_date"]:
            return False

    if story.get("to_date"):
        date = row["date"] or ""
        if date[:10] > story["to_date"]:
            return False

    keywords = story.get("keywords") or []
    if keywords:
        return any(keyword.lower() in text for keyword in keywords)

    return True


def fetch_rows(conn):
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
        ORDER BY score_overall DESC, date DESC
        """
    ).fetchall()


def build_item(row, thumbs_dir):
    source = choose_source_path(row)
    if not source:
        return None

    thumb = copy_preview(source, row["uuid"], thumbs_dir)
    albums = load_json(row["albums_json"])
    labels = load_json(row["labels_normalized_json"])

    return {
        "uuid": row["uuid"],
        "filename": row["original_filename"],
        "date": row["date"],
        "caption": row["ai_caption"],
        "score": row["score_overall"],
        "album": albums[0] if albums else "",
        "labels": labels[:6],
        "is_missing": bool(row["is_missing"]),
        "original_status": "icloud" if row["is_missing"] else "local",
        "preview_status": "ready",
        "thumb": thumb,
        "favorite": bool(row["favorite"]),
        "screenshot": bool(row["screenshot"]),
        "live_photo": bool(row["live_photo"]),
        "width": row["width"],
        "height": row["height"],
    }


def score_story(items, story):
    if not items:
        return 0

    avg_score = sum(float(i["score"] or 0) for i in items) / len(items)
    count_score = min(len(items) / 24, 1.0)
    local_ratio = sum(1 for i in items if i["original_status"] == "local") / len(items)
    preview_ratio = sum(1 for i in items if i["preview_status"] == "ready") / len(items)

    # Story readiness: preview matters more than local original for first MVP.
    readiness = (avg_score * 0.45) + (count_score * 0.30) + (preview_ratio * 0.20) + (local_ratio * 0.05)
    return round(readiness * 100, 1)


def suggest_reel_structure(items, lang):
    n = len(items)
    if n >= 24:
        duration = "30–45s"
        pace = "fast"
    elif n >= 12:
        duration = "20–30s"
        pace = "medium"
    else:
        duration = "10–20s"
        pace = "short"

    return {
        "duration": duration,
        "pace": pace,
        "suggested_clip_count": min(n, 24),
        "format": "9:16",
    }


def build_stories(rows, thumbs_dir):
    stories = []

    for story in STORY_DEFS:
        items = []
        seen = set()

        for row in rows:
            if not row_matches_story(row, story):
                continue

            item = build_item(row, thumbs_dir)
            if not item:
                continue

            key = dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)

            items.append(item)

            if len(items) >= story["max_items"]:
                break

        if not items:
            continue

        score = score_story(items, story)

        # Only show stories that look somewhat meaningful.
        if len(items) < 4 and score < 45:
            continue

        stories.append(
            {
                "id": story["id"],
                "emoji": story["emoji"],
                "title_tr": story["title_tr"],
                "title_en": story["title_en"],
                "desc_tr": story["desc_tr"],
                "desc_en": story["desc_en"],
                "output_types": story["output_types"],
                "story_score": score,
                "item_count": len(items),
                "preview_ready_count": len(items),
                "original_local_count": sum(1 for i in items if i["original_status"] == "local"),
                "original_icloud_count": sum(1 for i in items if i["original_status"] == "icloud"),
                "reel_tr": TR_REEL_TEMPLATES.get(story["id"], ""),
                "reel_en": EN_REEL_TEMPLATES.get(story["id"], ""),
                "reel_structure": suggest_reel_structure(items, "tr"),
                "items": items,
            }
        )

    stories.sort(key=lambda s: (s["story_score"], s["item_count"]), reverse=True)
    return stories


def render_item(item, lang):
    labels = "".join(f'<span class="chip">{esc(label)}</span>' for label in item["labels"])
    score = f"{float(item['score']):.3f}" if item["score"] is not None else "-"
    caption = item["caption"] or ("Açıklama yok" if lang == "tr" else "No caption")
    album_label = "Albüm" if lang == "tr" else "Album"

    original = "Orijinal iCloud’da" if item["original_status"] == "icloud" else "Orijinal lokal"
    if lang == "en":
        original = "Original in iCloud" if item["original_status"] == "icloud" else "Original local"

    return f"""
    <article class="story-photo">
      <div class="story-photo-img">
        <img src="{esc(item['thumb'])}" alt="{esc(caption)}" loading="lazy">
      </div>
      <div class="story-photo-meta">
        <div class="photo-badges">
          <span class="mini-badge">Preview hazır</span>
          <span class="mini-badge">{esc(original)}</span>
          <span class="mini-badge">Score {score}</span>
        </div>
        <div class="photo-caption">{esc(caption)}</div>
        <div class="photo-sub">{album_label}: {esc(item['album'] or '-')} · {esc(item['date'] or '')}</div>
        <div class="chips">{labels}</div>
      </div>
    </article>
    """


def render_story_card(story, lang):
    title = story["title_tr"] if lang == "tr" else story["title_en"]
    desc = story["desc_tr"] if lang == "tr" else story["desc_en"]
    reel = story["reel_tr"] if lang == "tr" else story["reel_en"]

    score_label = "Hazırlık skoru" if lang == "tr" else "Readiness score"
    count_label = "kare" if lang == "tr" else "items"
    local_label = "orijinal lokal" if lang == "tr" else "original local"
    icloud_label = "orijinal iCloud’da" if lang == "tr" else "original in iCloud"
    output_label = "Çıktı adayları" if lang == "tr" else "Output candidates"
    reel_label = "Reel/Shorts fikri" if lang == "tr" else "Reel/Shorts idea"

    outputs = "".join(f'<span class="output-chip">{esc(o)}</span>' for o in story["output_types"])
    thumbs = "".join(render_item(item, lang) for item in story["items"][:12])

    return f"""
    <section class="story-section" id="{esc(story['id'])}">
      <div class="story-head">
        <div>
          <div class="story-emoji">{esc(story['emoji'])}</div>
          <h2>{esc(title)}</h2>
          <p>{esc(desc)}</p>
        </div>
        <div class="story-score">
          <div class="score-number">{story['story_score']}</div>
          <div class="score-label">{score_label}</div>
        </div>
      </div>

      <div class="story-stats">
        <span>{story['item_count']} {count_label}</span>
        <span>{story['original_local_count']} {local_label}</span>
        <span>{story['original_icloud_count']} {icloud_label}</span>
        <span>{story['reel_structure']['duration']} · {story['reel_structure']['format']}</span>
      </div>

      <div class="story-output">
        <strong>{output_label}:</strong>
        {outputs}
      </div>

      <div class="reel-idea">
        <strong>{reel_label}:</strong> {esc(reel)}
      </div>

      <div class="story-photo-grid">
        {thumbs}
      </div>
    </section>
    """


def render_page(stories, lang):
    if lang == "tr":
        title = "agrandiz hikâye keşfi"
        hero = "Albüm ve Reels/Shorts adayı hikâyeler"
        subtitle = "Photos/iCloud arşivindeki preview’ler, Apple AI etiketleri, caption’lar ve estetik skorlarla ilk çalıştırmada bulunan hikâye adayları."
        summary = "Bu sayfa orijinalleri indirmeden, mevcut preview cache üzerinden oluşturuldu."
        back = "Demo portalına dön"
    else:
        title = "agrandiz story discovery"
        hero = "Album and Reels/Shorts story candidates"
        subtitle = "Story candidates discovered on first run using Photos/iCloud previews, Apple AI labels, captions and aesthetic scores."
        summary = "This page was generated from the preview cache without downloading originals."
        back = "Back to demo portal"

    story_cards = "\n".join(render_story_card(story, lang) for story in stories)

    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="../themes/apple.css">
  <style>
    .story-summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}
    .summary-card, .story-section {{
      background: rgba(255,255,255,0.78);
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }}
    .summary-card {{
      padding: 22px;
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
    .story-section {{
      padding: 24px;
      margin: 24px 0;
    }}
    .story-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 16px;
    }}
    .story-emoji {{
      font-size: 36px;
      margin-bottom: 8px;
    }}
    .story-head h2 {{
      font-size: 34px;
      letter-spacing: -0.04em;
      margin: 0 0 8px;
    }}
    .story-head p {{
      color: #6e6e73;
      margin: 0;
      max-width: 760px;
      line-height: 1.5;
    }}
    .story-score {{
      min-width: 140px;
      text-align: center;
      background: linear-gradient(135deg,#0a84ff,#5ac8fa);
      color: #fff;
      border-radius: 24px;
      padding: 18px;
    }}
    .score-number {{
      font-size: 38px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }}
    .score-label {{
      font-size: 12px;
      opacity: .9;
    }}
    .story-stats, .story-output, .reel-idea {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 12px 0;
      color: #3a3a3c;
    }}
    .story-stats span, .output-chip, .mini-badge {{
      font-size: 12px;
      border-radius: 999px;
      padding: 7px 10px;
      background: #f3f4f6;
      color: #3a3a3c;
    }}
    .output-chip {{
      background: rgba(0,113,227,0.10);
      color: #0071e3;
    }}
    .reel-idea {{
      background: rgba(255,255,255,.72);
      border: 1px solid rgba(0,0,0,0.06);
      border-radius: 18px;
      padding: 14px;
      line-height: 1.45;
    }}
    .story-photo-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .story-photo {{
      overflow: hidden;
      background: #fff;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 22px;
    }}
    .story-photo-img {{
      aspect-ratio: 4 / 3;
      overflow: hidden;
      background: #eceff3;
    }}
    .story-photo-img img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .story-photo-meta {{
      padding: 12px;
    }}
    .photo-badges, .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }}
    .photo-caption {{
      font-size: 13px;
      line-height: 1.4;
      min-height: 38px;
    }}
    .photo-sub {{
      font-size: 11px;
      color: #6e6e73;
      margin: 8px 0;
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
      margin-top: 18px;
      color: #0071e3;
      text-decoration: none;
      font-weight: 650;
    }}
    @media (max-width: 1100px) {{
      .story-photo-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .story-summary {{
        grid-template-columns: 1fr;
      }}
      .story-head {{
        flex-direction: column;
      }}
    }}
    @media (max-width: 620px) {{
      .story-photo-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body class="theme-apple profile-apple_icloud">
  <div class="shell">
    <header class="hero">
      <div class="brand">agrandiz <span>story discovery</span></div>
      <div class="hero-copy">
        <h1>{esc(hero)}</h1>
        <p>{esc(subtitle)}</p>
        <div class="meta-line">{esc(summary)}</div>
      </div>
    </header>

    <section class="story-summary">
      <article class="summary-card">
        <div class="value">{num(len(stories))}</div>
        <div class="label">story candidates</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(sum(s['item_count'] for s in stories))}</div>
        <div class="label">selected preview items</div>
      </article>
      <article class="summary-card">
        <div class="value">0</div>
        <div class="label">originals downloaded</div>
      </article>
    </section>

    {story_cards}

    <a class="back-link" href="index.html">← {esc(back)}</a>
  </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = fetch_rows(conn)
    conn.close()

    stories = build_stories(rows, thumbs_dir)

    json_path = outdir / "story_candidates.json"
    json_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "story_count": len(stories),
        "stories": stories,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Discovered {len(stories)} story candidates")

    langs = ["tr", "en"] if args.lang == "both" else [args.lang]

    for lang in langs:
        html_text = render_page(stories, lang)
        out_file = outdir / f"stories.{lang}.apple.apple_icloud.html"
        out_file.write_text(html_text, encoding="utf-8")
        print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
