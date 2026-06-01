#!/usr/bin/env python3

import argparse
import html
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from agrandiz_i18n import i18n_js, language_switcher_html
from agrandiz_shell import APP_NAV_CSS, app_nav_html

try:
    from PIL import Image
    import imagehash
except Exception:
    Image = None
    imagehash = None


WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)?", re.IGNORECASE)


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


def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def tokenize_text(value):
    return set(WORD_RE.findall(normalize(value)))


def phrase_in_text(phrase, text):
    """
    Safe phrase matching.
    Avoids bugs like keyword 'cat' matching 'fortification'.
    """
    phrase = normalize(phrase)
    text = normalize(text)

    if not phrase:
        return False

    if " " in phrase or "-" in phrase:
        return phrase in text

    return phrase in tokenize_text(text)


def labels_match_any(labels, terms):
    labels_set = {normalize(x) for x in labels}
    for term in terms:
        term = normalize(term)
        if term in labels_set:
            return True
    return False


def evidence_matches(labels, caption, filename, album, terms):
    labels = [normalize(x) for x in labels]
    caption = normalize(caption)
    filename = normalize(filename)
    album = normalize(album)

    searchable_text = " ".join([caption, filename, album])

    for term in terms:
        term = normalize(term)

        if term in labels:
            return True

        # Phrase / exact token match for caption, filename, album.
        if phrase_in_text(term, searchable_text):
            return True

    return False


def extension_for(path):
    suffix = path.suffix.lower()
    if suffix in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        return suffix
    return ".jpg"


def choose_source_path(row):
    for key in ["path_preview", "path"]:
        value = row[key]
        if value and value != "None":
            p = Path(value)
            if p.exists() and p.is_file():
                return p
    return None


def copy_preview(src, uuid, thumbs_dir):
    ext = extension_for(src)
    dst = thumbs_dir / f"{uuid}{ext}"
    if not dst.exists():
        shutil.copy2(src, dst)
    return f"thumbs/{quote(dst.name)}"


def compute_phash(path):
    if Image is None or imagehash is None:
        return None
    try:
        with Image.open(path) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def hamming_hash(a, b):
    if not a or not b or len(a) != len(b):
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 999


def item_event_signature(item):
    """
    Groups near burst / same-moment visual variants even if captions differ.
    This catches cases like three costume photos with same timestamp, dimensions, labels.
    """
    date_key = (item.get("date") or "")[:19]
    labels_key = tuple(sorted(item.get("labels") or []))
    width = item.get("width")
    height = item.get("height")
    album = normalize(item.get("album"))
    return (date_key, album, width, height, labels_key)


def item_soft_signature(item):
    """
    Fallback near-duplicate signature when imagehash is not available.
    More aggressive than UUID but less aggressive than caption-only.
    """
    caption_tokens = tokenize_text(item.get("caption") or "")
    reduced_caption = tuple(sorted(t for t in caption_tokens if len(t) > 3))
    return (
        (item.get("date") or "")[:19],
        item.get("width"),
        item.get("height"),
        tuple(sorted(item.get("labels") or [])),
        reduced_caption[:8],
    )


def is_near_duplicate(item, selected, threshold):
    """
    Prefer perceptual hash if available. Fall back to event/signature logic.
    """
    if item.get("phash"):
        for other in selected:
            if other.get("phash") and hamming_hash(item["phash"], other["phash"]) <= threshold:
                return True

    event_sig = item_event_signature(item)
    soft_sig = item_soft_signature(item)

    for other in selected:
        if item_event_signature(other) == event_sig:
            return True
        if item_soft_signature(other) == soft_sig:
            return True

    return False


def item_visual_key(item):
    """
    Used for cross-story reuse.
    If phash exists, use it. Otherwise use event/soft signatures.
    """
    if item.get("phash"):
        return ("phash", item["phash"])
    return ("event", item_event_signature(item), item_soft_signature(item))


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


def build_item(row, thumbs_dir, use_phash):
    src = choose_source_path(row)
    if not src:
        return None

    thumb = copy_preview(src, row["uuid"], thumbs_dir)
    albums = load_json(row["albums_json"])
    labels = load_json(row["labels_normalized_json"])
    album = albums[0] if albums else ""

    item = {
        "uuid": row["uuid"],
        "filename": row["original_filename"],
        "date": row["date"],
        "caption": row["ai_caption"],
        "score": row["score_overall"],
        "album": album,
        "labels": labels[:8],
        "is_missing": bool(row["is_missing"]),
        "original_status": "icloud" if row["is_missing"] else "local",
        "preview_status": "ready",
        "thumb": thumb,
        "favorite": bool(row["favorite"]),
        "screenshot": bool(row["screenshot"]),
        "live_photo": bool(row["live_photo"]),
        "width": row["width"],
        "height": row["height"],
        "phash": None
    }

    if use_phash and imagehash is not None:
        thumb_path = thumbs_dir.parent / thumb
        item["phash"] = compute_phash(thumb_path)

    return item


def row_matches_story(row, story):
    score = row["score_overall"]
    min_score = story.get("min_score")
    if min_score is not None:
        if score is None or float(score) < float(min_score):
            return False

    date = row["date"] or ""
    if story.get("from_date") and date[:10] < story["from_date"]:
        return False
    if story.get("to_date") and date[:10] > story["to_date"]:
        return False

    labels = load_json(row["labels_normalized_json"])
    caption = row["ai_caption"] or ""
    filename = row["original_filename"] or ""
    albums = load_json(row["albums_json"])
    album = " ".join(albums)

    album_like = story.get("album_like")
    if album_like and normalize(album_like) not in normalize(album):
        return False

    exclude_any = story.get("exclude_any") or []
    if evidence_matches(labels, caption, filename, album, exclude_any):
        return False

    include_any = story.get("include_any") or []
    if include_any:
        return evidence_matches(labels, caption, filename, album, include_any)

    # Generic score-based story.
    return True


def item_match_strength(item, story):
    labels = item.get("labels") or []
    caption = item.get("caption") or ""
    filename = item.get("filename") or ""
    album = item.get("album") or ""

    include_any = story.get("include_any") or []
    score = float(item.get("score") or 0)

    evidence = 0
    matched_terms = []

    for term in include_any:
        if evidence_matches(labels, caption, filename, album, [term]):
            evidence += 1
            matched_terms.append(term)

    if story.get("album_like") and normalize(story["album_like"]) in normalize(album):
        evidence += 1
        matched_terms.append(f"album:{story['album_like']}")

    return {
        "evidence": evidence,
        "matched_terms": matched_terms,
        "rank_score": (evidence * 10) + score
    }


def build_story(rows, story, thumbs_dir, globally_used, config):
    max_items = story.get("max_items") or config["global"].get("max_items_per_story", 28)
    threshold = config["global"].get("near_duplicate_hamming_threshold", 5)
    avoid_cross = config["global"].get("avoid_cross_story_reuse", True)
    use_phash = Image is not None and imagehash is not None

    candidates = []

    for row in rows:
        if not row_matches_story(row, story):
            continue

        item = build_item(row, thumbs_dir, use_phash)
        if not item:
            continue

        strength = item_match_strength(item, story)
        item["matched_terms"] = strength["matched_terms"]
        item["_rank_score"] = strength["rank_score"]

        visual_key = item_visual_key(item)
        if avoid_cross and visual_key in globally_used and not story.get("allow_reuse"):
            continue

        candidates.append(item)

    # Prefer thematic evidence first, then aesthetic score.
    candidates.sort(key=lambda x: (x["_rank_score"], float(x.get("score") or 0)), reverse=True)

    selected = []
    event_counts = defaultdict(int)
    max_per_event = config["global"].get("max_per_event_signature", 2)

    for item in candidates:
        if is_near_duplicate(item, selected, threshold):
            continue

        event_sig = item_event_signature(item)
        if event_counts[event_sig] >= max_per_event:
            continue

        selected.append(item)
        event_counts[event_sig] += 1

        if len(selected) >= max_items:
            break

    for item in selected:
        globally_used.add(item_visual_key(item))
        item.pop("_rank_score", None)

    return selected


def score_story(items, story):
    if not items:
        return 0

    avg_score = sum(float(i.get("score") or 0) for i in items) / len(items)
    count_score = min(len(items) / 20, 1.0)
    preview_ratio = sum(1 for i in items if i.get("preview_status") == "ready") / len(items)
    local_ratio = sum(1 for i in items if i.get("original_status") == "local") / len(items)
    evidence_avg = sum(len(i.get("matched_terms") or []) for i in items) / len(items)
    evidence_score = min(evidence_avg / 3, 1.0)

    readiness = (
        avg_score * 0.35
        + count_score * 0.25
        + preview_ratio * 0.15
        + evidence_score * 0.20
        + local_ratio * 0.05
    )

    return round(readiness * 100, 1)


def suggest_reel_structure(items):
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
        "format": "9:16"
    }


def build_stories(rows, config, thumbs_dir):
    story_defs = sorted(
        config["stories"],
        key=lambda s: s.get("specificity", 0),
        reverse=True
    )

    globally_used = set()
    stories = []

    for story in story_defs:
        items = build_story(rows, story, thumbs_dir, globally_used, config)

        if len(items) < 4:
            continue

        story_score = score_story(items, story)

        stories.append({
            "id": story["id"],
            "emoji": story.get("emoji", "•"),
            "specificity": story.get("specificity", 0),
            "generic": bool(story.get("generic", False)),
            "title_tr": story["title_tr"],
            "title_en": story["title_en"],
            "desc_tr": story["desc_tr"],
            "desc_en": story["desc_en"],
            "output_types": story.get("output_types", []),
            "story_score": story_score,
            "item_count": len(items),
            "preview_ready_count": len(items),
            "original_local_count": sum(1 for i in items if i["original_status"] == "local"),
            "original_icloud_count": sum(1 for i in items if i["original_status"] == "icloud"),
            "reel_tr": story.get("reel_tr", ""),
            "reel_en": story.get("reel_en", ""),
            "reel_structure": suggest_reel_structure(items),
            "items": items
        })

    # Keep specific stories first; score breaks ties.
    stories.sort(key=lambda s: (s["specificity"], s["story_score"], s["item_count"]), reverse=True)
    return stories


def render_item(item):
    labels = "".join(f'<span class="chip">{esc(label)}</span>' for label in item.get("labels", [])[:6])
    terms = "".join(f'<span class="chip matched">{esc(term)}</span>' for term in item.get("matched_terms", [])[:4])

    score = f"{float(item['score']):.3f}" if item.get("score") is not None else "-"
    caption_text = esc(item.get("caption") or "")
    caption_display = caption_text if caption_text else "<span data-i18n=\"common.no_caption\">No caption</span>"
    caption_alt = item.get("caption") or ""
    original_key = "common.original_icloud" if item["original_status"] == "icloud" else "common.original_local"
    original_fallback = "Original in iCloud" if item["original_status"] == "icloud" else "Original local"

    return f"""
    <article class="story-photo">
      <div class="story-photo-img">
        <img src="{esc(item['thumb'])}" alt="{esc(caption_alt)}" loading="lazy">
      </div>
      <div class="story-photo-meta">
        <div class="photo-badges">
          <span class="mini-badge" data-i18n="common.preview_ready">Preview ready</span>
          <span class="mini-badge" data-i18n="{original_key}">{original_fallback}</span>
          <span class="mini-badge">Score {score}</span>
        </div>
        <div class="photo-caption">{caption_display}</div>
        <div class="photo-sub"><span data-i18n="common.album">Album</span>: {esc(item.get('album') or '-')} · {esc(item.get('date') or '')}</div>
        <div class="chips">{terms}{labels}</div>
      </div>
    </article>
    """


def render_story_card(story):
    title = f'<span data-lang="tr">{esc(story["title_tr"])}</span><span data-lang="en">{esc(story["title_en"])}</span>'
    desc = f'<span data-lang="tr">{esc(story["desc_tr"])}</span><span data-lang="en">{esc(story["desc_en"])}</span>'
    reel = f'<span data-lang="tr">{esc(story["reel_tr"])}</span><span data-lang="en">{esc(story["reel_en"])}</span>'

    outputs = "".join(f'<span class="output-chip">{esc(o)}</span>' for o in story["output_types"])
    thumbs = "".join(render_item(item) for item in story["items"][:12])

    return f"""
    <section class="story-section" id="{esc(story['id'])}">
      <div class="story-head">
        <div>
          <div class="story-emoji">{esc(story['emoji'])}</div>
          <h2>{title}</h2>
          <p>{desc}</p>
        </div>
        <div class="story-score">
          <div class="score-number">{story['story_score']}</div>
          <div class="score-label" data-i18n="common.readiness_score">Readiness score</div>
        </div>
      </div>

      <div class="story-stats">
        <span>{story['item_count']} <span data-i18n="common.source_items">source items</span></span>
        <span>{story['original_local_count']} <span data-i18n="common.original_local">original local</span></span>
        <span>{story['original_icloud_count']} <span data-i18n="common.original_icloud">original in iCloud</span></span>
        <span>{story['reel_structure']['duration']} · {story['reel_structure']['format']}</span>
      </div>

      <div class="story-output">
        <strong data-i18n="common.output_candidates">Output candidates</strong>:
        {outputs}
      </div>

      <div class="reel-idea">
        <strong data-i18n="common.reel_idea">Reel/Shorts idea</strong>: {reel}
      </div>

      <div class="story-photo-grid">
        {thumbs}
      </div>
    </section>
    """


def render_page(stories, config_path):
    story_cards = "\n".join(render_story_card(story) for story in stories)

    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title data-i18n="raw.page_title">agrandiz raw story discovery</title>
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
    .summary-card {{ padding: 22px; }}
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
    .output-chip, .chip.matched {{
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
    .story-photo-meta {{ padding: 12px; }}
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
      .story-photo-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .story-summary {{ grid-template-columns: 1fr; }}
      .story-head {{ flex-direction: column; }}
    }}
    @media (max-width: 620px) {{
      .story-photo-grid {{ grid-template-columns: 1fr; }}
    }}
{APP_NAV_CSS}
  </style>
</head>
<body class="theme-apple profile-apple_icloud">
  <div class="shell">
    <header class="hero">
      <div class="brand">agrandiz <span data-i18n="raw.hero_title">raw story discovery</span></div>
      {language_switcher_html()}
      {app_nav_html()}
      <div class="hero-copy">
        <h1 data-i18n="raw.hero_title">Cleaner album and Reels/Shorts candidates</h1>
        <p data-i18n="raw.hero_subtitle">Second discovery output generated with config-driven story rules, exact token matching, near-duplicate cleanup and cross-story diversity.</p>
        <div class="meta-line"><span data-i18n="raw.note">This page was generated from the preview cache without downloading originals.</span> · Config: <strong>{esc(config_path)}</strong></div>
      </div>
    </header>

    <section class="story-summary">
      <article class="summary-card">
        <div class="value">{num(len(stories))}</div>
        <div class="label" data-i18n="raw.candidates">story candidates</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(sum(s['item_count'] for s in stories))}</div>
        <div class="label" data-i18n="raw.previews">selected previews</div>
      </article>
      <article class="summary-card">
        <div class="value">0</div>
        <div class="label" data-i18n="raw.downloaded">originals downloaded</div>
      </article>
    </section>

    {story_cards}

    <a class="back-link" href="dashboard.apple.apple_icloud.html">← <span data-i18n="raw.back">Back to demo portal</span></a>
  </div>
{i18n_js()}
</body>
</html>
"""


def write_index_links():
    p = Path("cache/index.html")
    if not p.exists():
        return

    text = p.read_text()

    insert = '''
      <a class="portal-card" href="stories-raw.apple.apple_icloud.html">
        <div class="eyebrow" data-i18n="portal.card.stories.eyebrow">Raw Story Discovery</div>
        <h2 data-i18n="raw.hero_title">Cleaner Story Candidates</h2>
        <p data-i18n="raw.hero_subtitle">Album/reel candidates generated with config-driven rules, stricter matching and duplicate cleanup.</p>
      </a>
'''

    if "stories-raw.apple.apple_icloud.html" in text:
        return

    needle = '''    </section>

    <section class="workflow">'''

    if needle in text:
        text = text.replace(needle, insert + "\n" + needle)
        p.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--config", default="config/story_profiles/apple_icloud_default.json")
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    config = json.loads(Path(args.config).read_text())

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = fetch_rows(conn)
    conn.close()

    stories = build_stories(rows, config, thumbs_dir)

    out_json = outdir / "story_candidates_raw.json"
    out_json.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "config": args.config,
        "phash_enabled": Image is not None and imagehash is not None,
        "story_count": len(stories),
        "stories": stories
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"phash_enabled: {Image is not None and imagehash is not None}")
    print(f"Discovered {len(stories)} story candidates")

    html_text = render_page(stories, args.config)
    out_file = outdir / "stories-raw.apple.apple_icloud.html"
    out_file.write_text(html_text, encoding="utf-8")
    print(f"Wrote {out_file}")

    write_index_links()


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
