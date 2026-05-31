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

try:
    from PIL import Image
    import imagehash
except Exception:
    Image = None
    imagehash = None


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


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def esc_attr(value):
    return html.escape(str(value), quote=True) if value is not None else ""


def num(n):
    return f"{n:,}".replace(",", ".")


def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def tokens(value):
    return set(WORD_RE.findall(normalize(value)))


def load_json(raw, default=None):
    if default is None:
        default = []
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def load_config(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return json.loads(p.read_text())


def phrase_or_token_match(term, text):
    term = normalize(term)
    text = normalize(text)

    if not term:
        return False

    if " " in term or "-" in term:
        return term in text

    return term in tokens(text)


def evidence_matches(labels, caption, filename, album, terms):
    labels_normalized = {normalize(x) for x in labels}
    searchable = " ".join([caption or "", filename or "", album or ""]).lower()

    for term in terms:
        term = normalize(term)
        if term in labels_normalized:
            return True
        if phrase_or_token_match(term, searchable):
            return True

    return False


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


def milestone_terms(item):
    return useful_terms(item) & MILESTONE_TERMS


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


def year_of(item):
    dt = parse_dt(item.get("date"))
    if not dt:
        return "Unknown"
    return str(dt.year)


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


def seconds_between(a, b):
    da = parse_dt(a.get("date"))
    db = parse_dt(b.get("date"))

    if da is None or db is None:
        return 999999

    try:
        return abs((da - db).total_seconds())
    except Exception:
        return abs((da.replace(tzinfo=None) - db.replace(tzinfo=None)).total_seconds())


def hamming_hash(a, b):
    if not a or not b or len(a) != len(b):
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 999


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
        ORDER BY date ASC, score_overall DESC
        """
    ).fetchall()


def row_matches(row, config):
    score = row["score_overall"]
    if score is None or float(score) < float(config.get("min_score", 0.0)):
        return False

    date = row["date"] or ""

    if config.get("from_date") and date[:10] < config["from_date"]:
        return False

    if config.get("to_date") and date[:10] > config["to_date"]:
        return False

    labels = load_json(row["labels_normalized_json"])
    albums = load_json(row["albums_json"])
    album = " ".join(albums)
    caption = row["ai_caption"] or ""
    filename = row["original_filename"] or ""

    if evidence_matches(labels, caption, filename, album, config.get("exclude_any", [])):
        return False

    return evidence_matches(labels, caption, filename, album, config.get("include_any", []))


def build_item(row, thumbs_dir, use_phash):
    src = choose_source_path(row)
    if not src:
        return None

    thumb = copy_preview(src, row["uuid"], thumbs_dir)

    albums = load_json(row["albums_json"])
    labels = load_json(row["labels_normalized_json"])

    item = {
        "uuid": row["uuid"],
        "filename": row["original_filename"],
        "date": row["date"],
        "caption": row["ai_caption"],
        "score": row["score_overall"],
        "album": albums[0] if albums else "",
        "labels": labels[:10],
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

    if use_phash:
        thumb_path = thumbs_dir.parent / thumb
        item["phash"] = compute_phash(thumb_path)

    item["terms"] = sorted(useful_terms(item))[:20]
    item["milestone_terms"] = sorted(milestone_terms(item))

    return item


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


def representative_score(item):
    score = float(item.get("score") or 0)
    milestone_bonus = min(len(item.get("milestone_terms") or []) * 0.03, 0.12)
    favorite_bonus = 0.08 if item.get("favorite") else 0
    local_bonus = 0.01 if item.get("original_status") == "local" else 0
    return score + milestone_bonus + favorite_bonus + local_bonus


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


def build_timeline(rows, config, thumbs_dir):
    use_phash = Image is not None and imagehash is not None and not config.get("disable_phash", False)

    items = []

    for row in rows:
        if not row_matches(row, config):
            continue

        item = build_item(row, thumbs_dir, use_phash)
        if item:
            items.append(item)

        max_candidates = config.get("max_candidates")
        if max_candidates and len(items) >= int(max_candidates):
            break

    moments = cluster_items(items, config)
    by_year = select_year_moments(moments, config)

    total_selected = sum(len(v) for v in by_year.values())
    grouped_variants = sum(
        max(moment.get("variant_count", 1) - 1, 0)
        for year_items in by_year.values()
        for moment in year_items
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "phash_enabled": use_phash,
        "source_item_count": len(items),
        "moment_count": len(moments),
        "selected_moment_count": total_selected,
        "grouped_variant_count": grouped_variants,
        "years": [
            {
                "year": year,
                "moment_count": len(moments_for_year),
                "moments": moments_for_year
            }
            for year, moments_for_year in by_year.items()
        ]
    }


def frames_for_moment(moment):
    frames = []
    seen = set()

    rep = moment.get("representative", {})
    if rep.get("thumb"):
        frames.append(rep["thumb"])
        seen.add(rep["thumb"])

    for item in moment.get("variants", []):
        thumb = item.get("thumb")
        if thumb and thumb not in seen:
            frames.append(thumb)
            seen.add(thumb)

    return frames[:10]


def render_moment(moment, lang):
    item = moment["representative"]
    caption = item.get("caption") or ("Açıklama yok" if lang == "tr" else "No caption")
    score = f"{float(item.get('score') or 0):.3f}"

    labels = "".join(f'<span class="chip">{esc(label)}</span>' for label in (item.get("labels") or [])[:6])
    milestones = "".join(f'<span class="chip matched">{esc(term)}</span>' for term in (moment.get("milestone_terms") or [])[:4])

    if lang == "tr":
        original = "Orijinal iCloud’da" if item.get("original_status") == "icloud" else "Orijinal lokal"
        album_label = "Albüm"
        similar_label = "benzer kare"
        variant_label = "Moment"
        month = moment.get("month_label_tr", "")
    else:
        original = "Original in iCloud" if item.get("original_status") == "icloud" else "Original local"
        album_label = "Album"
        similar_label = "similar shots"
        variant_label = "Moment"
        month = moment.get("month_label_en", "")

    frames = frames_for_moment(moment)
    frames_json = esc_attr(json.dumps(frames, ensure_ascii=False))

    variant_badge = ""
    if moment.get("variant_count", 1) > 1:
        variant_badge = f'<span class="mini-badge moment-badge">{variant_label} · {moment["variant_count"]} {similar_label}</span>'

    return f"""
    <article class="timeline-card" data-frames="{frames_json}">
      <div class="timeline-image">
        <img src="{esc(item.get('thumb'))}" alt="{esc(caption)}" loading="lazy">
        <div class="sequence-hint">micro sequence</div>
      </div>
      <div class="timeline-meta">
        <div class="timeline-badges">
          <span class="mini-badge">{esc(month)}</span>
          <span class="mini-badge">{esc(original)}</span>
          <span class="mini-badge">Score {score}</span>
          {variant_badge}
        </div>
        <div class="caption">{esc(caption)}</div>
        <div class="submeta">{album_label}: {esc(item.get('album') or '-')} · {esc(item.get('date') or '')}</div>
        <div class="chips">{milestones}{labels}</div>
      </div>
    </article>
    """


def render_html(timeline, config, lang):
    title = config["title_tr"] if lang == "tr" else config["title_en"]
    subtitle = config["subtitle_tr"] if lang == "tr" else config["subtitle_en"]

    if lang == "tr":
        story_label = "aile zaman çizelgesi"
        source_label = "aday fotoğraf"
        moment_label = "seçili moment"
        grouped_label = "gruplanan varyant"
        years_label = "yıl"
        note = "Bu sayfa orijinalleri indirmeden, mevcut preview cache üzerinden oluşturuldu."
    else:
        story_label = "family timeline"
        source_label = "candidate photos"
        moment_label = "selected moments"
        grouped_label = "grouped variants"
        years_label = "years"
        note = "This page was generated from the preview cache without downloading originals."

    year_sections = []

    for year in timeline["years"]:
        cards = "\n".join(render_moment(moment, lang) for moment in year["moments"])
        year_sections.append(
            f"""
            <section class="year-section">
              <div class="year-head">
                <h2>{esc(year['year'])}</h2>
                <span>{year['moment_count']} {moment_label}</span>
              </div>
              <div class="timeline-grid">
                {cards}
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="../themes/apple.css">
  <style>
    .timeline-summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}
    .summary-card, .year-section {{
      background: rgba(255,255,255,0.78);
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }}
    .summary-card {{
      padding: 22px;
    }}
    .summary-card .value {{
      font-size: 38px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }}
    .summary-card .label {{
      color: #6e6e73;
      margin-top: 6px;
    }}
    .year-section {{
      padding: 24px;
      margin: 24px 0;
    }}
    .year-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .year-head h2 {{
      margin: 0;
      font-size: 42px;
      letter-spacing: -0.05em;
    }}
    .year-head span {{
      color: #6e6e73;
      font-weight: 650;
    }}
    .timeline-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .timeline-card {{
      overflow: hidden;
      background: #fff;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 22px;
    }}
    .timeline-image {{
      position: relative;
      height: clamp(210px, 22vw, 330px);
      background:
        linear-gradient(45deg, #f2f2f4 25%, transparent 25%),
        linear-gradient(-45deg, #f2f2f4 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #f2f2f4 75%),
        linear-gradient(-45deg, transparent 75%, #f2f2f4 75%);
      background-size: 20px 20px;
      background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
      background-color: #fafafa;
      overflow: hidden;
    }}
    .timeline-image img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }}
    .sequence-hint {{
      position: absolute;
      right: 10px;
      bottom: 10px;
      opacity: 0;
      transition: opacity .16s ease;
      font-size: 11px;
      padding: 5px 8px;
      border-radius: 999px;
      background: rgba(0,0,0,.62);
      color: #fff;
    }}
    .timeline-card:hover .sequence-hint {{
      opacity: 1;
    }}
    .timeline-meta {{
      padding: 12px;
    }}
    .timeline-badges, .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }}
    .mini-badge, .chip {{
      font-size: 11px;
      padding: 5px 8px;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.08);
      background: #f3f4f6;
      color: #3a3a3c;
    }}
    .moment-badge, .chip.matched {{
      background: rgba(0,113,227,0.10);
      color: #0071e3;
    }}
    .caption {{
      font-size: 13px;
      line-height: 1.4;
      min-height: 38px;
    }}
    .submeta {{
      font-size: 11px;
      color: #6e6e73;
      margin: 8px 0;
    }}
    @media (max-width: 1200px) {{
      .timeline-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 900px) {{
      .timeline-grid, .timeline-summary {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 620px) {{
      .timeline-grid, .timeline-summary {{
        grid-template-columns: 1fr;
      }}
      .year-head {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body class="theme-apple profile-apple_icloud">
  <div class="shell">
    <header class="hero">
      <div class="brand">agrandiz <span>{esc(story_label)}</span></div>
      <div class="hero-copy">
        <h1>{esc(title)}</h1>
        <p>{esc(subtitle)}</p>
        <div class="meta-line">{esc(note)}</div>
      </div>
    </header>

    <section class="timeline-summary">
      <article class="summary-card">
        <div class="value">{num(len(timeline['years']))}</div>
        <div class="label">{esc(years_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(timeline['source_item_count'])}</div>
        <div class="label">{esc(source_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(timeline['selected_moment_count'])}</div>
        <div class="label">{esc(moment_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(timeline['grouped_variant_count'])}</div>
        <div class="label">{esc(grouped_label)}</div>
      </article>
    </section>

    {''.join(year_sections)}
  </div>

  <script>
    document.querySelectorAll(".timeline-card").forEach(card => {{
      let frames = [];
      try {{
        frames = JSON.parse(card.dataset.frames || "[]");
      }} catch (e) {{
        frames = [];
      }}

      if (!frames || frames.length < 2) return;

      const img = card.querySelector("img");
      if (!img) return;

      let timer = null;
      let idx = 0;
      const original = frames[0];

      function start() {{
        if (timer) return;
        idx = 0;
        timer = setInterval(() => {{
          idx = (idx + 1) % frames.length;
          img.src = frames[idx];
        }}, 420);
      }}

      function stop() {{
        if (timer) {{
          clearInterval(timer);
          timer = null;
        }}
        img.src = original;
      }}

      card.addEventListener("mouseenter", start);
      card.addEventListener("mouseleave", stop);

      card.querySelector(".timeline-image").addEventListener("click", () => {{
        if (timer) stop();
        else start();
      }});
    }});
  </script>
</body>
</html>
"""


def patch_portal_index(outdir):
    index = outdir / "index.html"
    if not index.exists():
        return

    text = index.read_text()

    if "family-timeline.apple.apple_icloud.html" in text:
        return

    insert = """
      <a class="portal-card" href="family-timeline.apple.apple_icloud.html">
        <div class="eyebrow">Türkçe · Family Timeline</div>
        <h2>Çocukların Büyüme Hikâyesi</h2>
        <p>Çocuk, aile, doğum günü, okul ve gündelik hayat anılarından yıllara yayılan zaman çizelgesi.</p>
      </a>

      <a class="portal-card" href="family-timeline.apple.apple_icloud.html">
        <div class="eyebrow">English · Family Timeline</div>
        <h2>Children's Growing-Up Story</h2>
        <p>A year-by-year timeline from child, family, birthday, school and everyday-life memories.</p>
      </a>
"""

    needle = '    </section>'
    pos = text.find(needle)
    if pos != -1:
        text = text[:pos] + insert + "\n" + text[pos:]
        index.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--config", default="config/family_timeline.json")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    parser.add_argument("--fast", action="store_true", help="Use faster beta/test settings")
    parser.add_argument("--max-candidates", type=int, default=None, help="Limit matched candidate photos")
    parser.add_argument("--max-total-moments", type=int, default=None, help="Limit selected timeline moments")
    parser.add_argument("--no-phash", action="store_true", help="Disable perceptual hash computation")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)

    if args.fast:
        config["disable_phash"] = True
        config["max_candidates"] = min(int(config.get("max_candidates", 700)), 700)
        config["max_total_moments"] = min(int(config.get("max_total_moments", 60)), 60)
        config["max_moments_per_year"] = min(int(config.get("max_moments_per_year", 8)), 8)

    if args.no_phash:
        config["disable_phash"] = True

    if args.max_candidates is not None:
        config["max_candidates"] = args.max_candidates

    if args.max_total_moments is not None:
        config["max_total_moments"] = args.max_total_moments

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = fetch_rows(conn)
    conn.close()

    timeline = build_timeline(rows, config, thumbs_dir)

    json_path = outdir / "family_timeline.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "config": args.config,
                "timeline": timeline
            },
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"Wrote {json_path}")
    print("source_item_count:", timeline["source_item_count"])
    print("moment_count:", timeline["moment_count"])
    print("selected_moment_count:", timeline["selected_moment_count"])
    print("grouped_variant_count:", timeline["grouped_variant_count"])

    langs = ["tr", "en"] if args.lang == "both" else [args.lang]

    for lang in langs:
        html_text = render_html(timeline, config, lang)
        html_path = outdir / "family-timeline.apple.apple_icloud.html"
        html_path.write_text(html_text, encoding="utf-8")
        print(f"Wrote {html_path}")

    patch_portal_index(outdir)


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
