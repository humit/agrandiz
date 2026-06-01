#!/usr/bin/env python3

import argparse
import html
import json
import math
import re
from datetime import datetime
from pathlib import Path

from agrandiz_i18n import i18n_js, language_switcher_html
from agrandiz_shell import APP_NAV_CSS, app_nav_html


WORD_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)?", re.IGNORECASE)

# Terms that are too broad to decide whether two images are the same moment.
GENERIC_TERMS = {
    "a", "an", "the", "and", "or", "of", "on", "in", "at", "with", "to",
    "person", "people", "man", "woman", "child", "children", "boy", "girl",
    "standing", "sitting", "holding", "wearing", "looking", "close", "up",
    "photo", "image", "outdoor", "indoor", "clothing", "jacket", "shirt",
    "sky", "land", "water", "body", "background", "front", "group",
    "white", "black", "blue", "red", "green", "brown", "large", "small"
}

# Strong scene markers. If these overlap in a tight time window,
# we can group more confidently.
SCENE_TERMS = {
    "birthday", "cake", "balloon", "arch", "table",
    "beach", "sunset", "dusk", "afterglow", "lake", "ocean", "sea",
    "playground", "swing", "stroller", "toy",
    "fish", "fishing", "boat",
    "cat", "dog", "kitten", "puppy",
    "camping", "tent", "mountain", "desert", "road"
}


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def num(n):
    return f"{n:,}".replace(",", ".")


def normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def tokens(value):
    return set(WORD_RE.findall(normalize(value)))


def useful_terms(item):
    label_terms = set()
    for label in item.get("labels") or []:
        label_terms |= tokens(label)

    caption_terms = tokens(item.get("caption") or "")
    matched_terms = set()
    for term in item.get("matched_terms") or []:
        matched_terms |= tokens(term)

    all_terms = label_terms | caption_terms | matched_terms
    useful = {t for t in all_terms if len(t) >= 3 and t not in GENERIC_TERMS}

    return useful


def scene_terms(item):
    return useful_terms(item) & SCENE_TERMS


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


def seconds_between(a, b):
    da = parse_dt(a.get("date"))
    db = parse_dt(b.get("date"))
    if da is None or db is None:
        return None
    try:
        return abs((da - db).total_seconds())
    except Exception:
        # Offset-aware vs offset-naive fallback.
        return abs((da.replace(tzinfo=None) - db.replace(tzinfo=None)).total_seconds())


def hamming_hash(a, b):
    if not a or not b or len(a) != len(b):
        return 999
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 999


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def same_camera_burst_shape(a, b):
    """
    Many WhatsApp / Photos burst-like groups keep same dimensions.
    This is not enough by itself, but useful as supporting evidence.
    """
    return (
        a.get("width") == b.get("width")
        and a.get("height") == b.get("height")
        and a.get("album") == b.get("album")
    )


def same_moment(a, b, args):
    dt = seconds_between(a, b)

    if dt is None:
        dt = 999999

    phash_distance = hamming_hash(a.get("phash"), b.get("phash"))

    terms_a = useful_terms(a)
    terms_b = useful_terms(b)
    scene_a = scene_terms(a)
    scene_b = scene_terms(b)

    shared_terms = terms_a & terms_b
    shared_scene_terms = scene_a & scene_b
    term_jaccard = jaccard(terms_a, terms_b)

    # 1) True/near duplicate image.
    if phash_distance <= args.phash_duplicate_threshold:
        return True, f"phash≤{args.phash_duplicate_threshold}"

    # 2) Same burst / same scene within a very short interval.
    # Handles examples like balloon arch photos 1 second apart.
    if dt <= args.burst_seconds:
        if len(shared_scene_terms) >= 1:
            return True, f"burst≤{args.burst_seconds}s+scene"
        if same_camera_burst_shape(a, b) and len(shared_terms) >= args.min_shared_terms:
            return True, f"burst≤{args.burst_seconds}s+shape+terms"

    # 3) Same moment / stop-motion-like variants within a wider interval.
    # Handles beach/sunset photos 10–20 seconds apart.
    if dt <= args.moment_seconds:
        if len(shared_scene_terms) >= args.min_shared_scene_terms:
            return True, f"moment≤{args.moment_seconds}s+scene"
        if term_jaccard >= args.min_term_jaccard and len(shared_terms) >= args.min_shared_terms:
            return True, f"moment≤{args.moment_seconds}s+jaccard"

    # 4) Same location-like event with same dimensions and strong semantic overlap.
    if dt <= args.event_seconds and same_camera_burst_shape(a, b):
        if len(shared_scene_terms) >= args.min_shared_scene_terms:
            return True, f"event≤{args.event_seconds}s+shape+scene"

    return False, ""


def representative_score(item):
    score = float(item.get("score") or 0)
    favorite_bonus = 0.05 if item.get("favorite") else 0
    local_bonus = 0.01 if item.get("original_status") == "local" else 0
    evidence_bonus = min(len(item.get("matched_terms") or []) * 0.01, 0.04)
    return score + favorite_bonus + local_bonus + evidence_bonus


def choose_representative(items):
    return sorted(items, key=representative_score, reverse=True)[0]


def cluster_story_items(items, args):
    """
    Greedy moment clustering:
    - Process chronologically so burst-like photos meet each other.
    - Attach an item to the first compatible cluster.
    - Later pick best representative per cluster.
    """
    sortable = []
    for item in items:
        dt = parse_dt(item.get("date"))
        sortable.append((dt or datetime.max, item))

    sortable.sort(key=lambda x: x[0])

    clusters = []

    for _, item in sortable:
        assigned = False

        for cluster in clusters:
            compatible = False
            reasons = []

            # Compare against all items in the cluster, not only representative.
            for existing in cluster["items"]:
                ok, reason = same_moment(item, existing, args)
                if ok:
                    compatible = True
                    reasons.append(reason)

            if compatible:
                cluster["items"].append(item)
                cluster["reasons"].extend(reasons)
                assigned = True
                break

        if not assigned:
            clusters.append({
                "items": [item],
                "reasons": []
            })

    moments = []

    for idx, cluster in enumerate(clusters, start=1):
        items_sorted = sorted(cluster["items"], key=representative_score, reverse=True)
        rep = choose_representative(items_sorted)

        dates = [parse_dt(i.get("date")) for i in items_sorted if parse_dt(i.get("date"))]
        if dates:
            start = min(dates).isoformat()
            end = max(dates).isoformat()
            duration_seconds = int((max(dates).replace(tzinfo=None) - min(dates).replace(tzinfo=None)).total_seconds())
        else:
            start = rep.get("date")
            end = rep.get("date")
            duration_seconds = 0

        all_terms = set()
        for i in items_sorted:
            all_terms |= useful_terms(i)

        moments.append({
            "moment_id": f"moment_{idx:03d}",
            "representative": rep,
            "variant_count": len(items_sorted),
            "variants": items_sorted,
            "variant_uuids": [i.get("uuid") for i in items_sorted],
            "date_start": start,
            "date_end": end,
            "duration_seconds": duration_seconds,
            "terms": sorted(all_terms)[:16],
            "cluster_reasons": sorted(set(cluster["reasons"]))[:8],
            "moment_score": round(representative_score(rep), 4)
        })

    # Sort by representative quality, but keep moments diverse.
    moments.sort(key=lambda m: (m["moment_score"], m["variant_count"]), reverse=True)

    return moments


def process(data, args):
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": args.input,
        "mode": "moment_grouping",
        "settings": {
            "phash_duplicate_threshold": args.phash_duplicate_threshold,
            "burst_seconds": args.burst_seconds,
            "moment_seconds": args.moment_seconds,
            "event_seconds": args.event_seconds,
            "min_shared_terms": args.min_shared_terms,
            "min_shared_scene_terms": args.min_shared_scene_terms,
            "min_term_jaccard": args.min_term_jaccard,
            "max_moments_per_story": args.max_moments_per_story
        },
        "story_count": data.get("story_count"),
        "stories": []
    }

    for story in data.get("stories", []):
        moments = cluster_story_items(story.get("items", []), args)
        kept = moments[:args.max_moments_per_story]

        new_story = dict(story)
        new_story.pop("items", None)
        new_story["source_item_count"] = story.get("item_count", len(story.get("items", [])))
        new_story["moment_count"] = len(kept)
        new_story["hidden_variant_count"] = sum(max(m["variant_count"] - 1, 0) for m in kept)
        new_story["moments"] = kept

        # Keep representative items for old tooling compatibility.
        new_story["items"] = [m["representative"] for m in kept]
        new_story["item_count"] = len(kept)

        out["stories"].append(new_story)

    return out


def render_moment(moment, lang):
    item = moment["representative"]
    caption = item.get("caption") or ("Açıklama yok" if lang == "tr" else "No caption")

    score = f"{float(item.get('score') or 0):.3f}"
    labels = "".join(f'<span class="chip">{esc(label)}</span>' for label in (item.get("labels") or [])[:6])
    terms = "".join(f'<span class="chip matched">{esc(term)}</span>' for term in (item.get("matched_terms") or [])[:4])

    if lang == "tr":
        original = "Orijinal iCloud’da" if item.get("original_status") == "icloud" else "Orijinal lokal"
        album_label = "Albüm"
        moment_label = "Moment"
        similar_label = "benzer kare"
        variants_label = "Varyantlar"
    else:
        original = "Original in iCloud" if item.get("original_status") == "icloud" else "Original local"
        album_label = "Album"
        moment_label = "Moment"
        similar_label = "similar shots"
        variants_label = "Variants"

    variant_count = moment.get("variant_count", 1)
    variant_note = ""
    if variant_count > 1:
        variant_note = f'<span class="mini-badge moment-badge">{moment_label} · {variant_count} {similar_label}</span>'

    variant_list = ""
    if variant_count > 1:
        lines = []
        for v in moment.get("variants", [])[1:4]:
            v_caption = esc(v.get("caption") or "-")
            v_score = f"{float(v.get('score') or 0):.3f}"
            v_time = esc(v.get("date") or "")
            lines.append(f"<li>{v_caption} <small>Score {v_score} · {v_time}</small></li>")
        if lines:
            variant_list = f"""
            <details class="variants">
              <summary>{variants_label}</summary>
              <ul>{''.join(lines)}</ul>
            </details>
            """

    return f"""
    <article class="story-photo">
      <div class="story-photo-img">
        <img src="{esc(item.get('thumb'))}" alt="{esc(caption)}" loading="lazy">
      </div>
      <div class="story-photo-meta">
        <div class="photo-badges">
          <span class="mini-badge">Preview ready</span>
          <span class="mini-badge">{esc(original)}</span>
          <span class="mini-badge">Score {score}</span>
          {variant_note}
        </div>
        <div class="photo-caption">{esc(caption)}</div>
        <div class="photo-sub">{album_label}: {esc(item.get('album') or '-')} · {esc(item.get('date') or '')}</div>
        <div class="chips">{terms}{labels}</div>
        {variant_list}
      </div>
    </article>
    """


def render_story(story, lang):
    title = story["title_tr"] if lang == "tr" else story["title_en"]
    desc = story["desc_tr"] if lang == "tr" else story["desc_en"]
    reel = story["reel_tr"] if lang == "tr" else story["reel_en"]

    if lang == "tr":
        score_label = "Hazırlık skoru"
        moment_label = "moment"
        source_label = "kaynak kare"
        hidden_label = "gruplanan varyant"
        output_label = "Çıktı adayları"
        reel_label = "Reel/Shorts fikri"
    else:
        score_label = "Readiness score"
        moment_label = "moments"
        source_label = "source items"
        hidden_label = "grouped variants"
        output_label = "Output candidates"
        reel_label = "Reel/Shorts idea"

    outputs = "".join(f'<span class="output-chip">{esc(o)}</span>' for o in story.get("output_types", []))
    moments = "".join(render_moment(m, lang) for m in story.get("moments", [])[:12])

    return f"""
    <section class="story-section" id="{esc(story['id'])}">
      <div class="story-head">
        <div>
          <div class="story-emoji">{esc(story.get('emoji', '•'))}</div>
          <h2>{esc(title)}</h2>
          <p>{esc(desc)}</p>
        </div>
        <div class="story-score">
          <div class="score-number">{story.get('story_score')}</div>
          <div class="score-label">{score_label}</div>
        </div>
      </div>

      <div class="story-stats">
        <span>{story.get('moment_count', 0)} {moment_label}</span>
        <span>{story.get('source_item_count', 0)} {source_label}</span>
        <span>{story.get('hidden_variant_count', 0)} {hidden_label}</span>
        <span>{story.get('reel_structure', {}).get('duration', '')} · 9:16</span>
      </div>

      <div class="story-output">
        <strong>{output_label}:</strong>
        {outputs}
      </div>

      <div class="reel-idea">
        <strong>{reel_label}:</strong> {esc(reel)}
      </div>

      <div class="story-photo-grid">
        {moments}
      </div>
    </section>
    """


def render_page(data, lang):
    if lang == "tr":
        title = "agrandiz moment gruplama"
        hero = "Moment bazlı albüm ve Reels/Shorts adayları"
        subtitle = "Ardışık çekilmiş, gözle çok benzer kareler tek bir moment altında gruplanır; sadece en iyi temsilci gösterilir."
        candidates_label = "story adayı"
        moments_label = "seçili moment"
        grouped_label = "gruplanan varyant"
    else:
        title = "agrandiz moment grouping"
        hero = "Moment-based album and Reels/Shorts candidates"
        subtitle = "Near-burst and visually similar shots are grouped into moments; only the best representative is shown."
        candidates_label = "story candidates"
        moments_label = "selected moments"
        grouped_label = "grouped variants"

    stories = data.get("stories", [])
    total_moments = sum(s.get("moment_count", 0) for s in stories)
    total_grouped = sum(s.get("hidden_variant_count", 0) for s in stories)

    story_cards = "\n".join(render_story(story, lang) for story in stories)

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
    .moment-badge, .output-chip, .chip.matched {{
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
    .variants {{
      margin-top: 10px;
      font-size: 12px;
      color: #6e6e73;
    }}
    .variants summary {{
      cursor: pointer;
      color: #0071e3;
      font-weight: 650;
    }}
    .variants ul {{
      margin: 8px 0 0;
      padding-left: 18px;
    }}
    .variants small {{
      display: block;
      color: #8e8e93;
      margin-top: 2px;
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
      <div class="brand">agrandiz <span>moment grouping</span></div>
      {language_switcher_html()}
      {app_nav_html()}
      <div class="hero-copy">
        <h1>{esc(hero)}</h1>
        <p>{esc(subtitle)}</p>
      </div>
    </header>

    <section class="story-summary">
      <article class="summary-card">
        <div class="value">{num(len(stories))}</div>
        <div class="label">{esc(candidates_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(total_moments)}</div>
        <div class="label">{esc(moments_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(total_grouped)}</div>
        <div class="label">{esc(grouped_label)}</div>
      </article>
    </section>

    {story_cards}
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
      <a class="portal-card" href="stories-moments.tr.apple.apple_icloud.html">
        <div class="eyebrow">Türkçe · Moment Grouping</div>
        <h2>Moment Bazlı Hikâye Adayları</h2>
        <p>Ardışık ve benzer kareleri moment olarak gruplayan daha temiz albüm/reel adayları.</p>
      </a>

      <a class="portal-card" href="stories-moments.en.apple.apple_icloud.html">
        <div class="eyebrow">English · Moment Grouping</div>
        <h2>Moment-Based Story Candidates</h2>
        <p>Cleaner album/reel candidates with near-burst shots grouped into moments.</p>
      </a>
'''

    if "stories-moments.tr.apple.apple_icloud.html" in text:
        return

    needle = '''    </section>

    <section class="workflow">'''

    if needle in text:
        text = text.replace(needle, insert + "\n" + needle)
        p.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="cache/story_candidates_raw.json")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])

    parser.add_argument("--phash-duplicate-threshold", type=int, default=5)
    parser.add_argument("--burst-seconds", type=int, default=3)
    parser.add_argument("--moment-seconds", type=int, default=30)
    parser.add_argument("--event-seconds", type=int, default=90)
    parser.add_argument("--min-shared-terms", type=int, default=3)
    parser.add_argument("--min-shared-scene-terms", type=int, default=2)
    parser.add_argument("--min-term-jaccard", type=float, default=0.38)
    parser.add_argument("--max-moments-per-story", type=int, default=20)

    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    data = json.loads(Path(args.input).read_text())
    grouped = process(data, args)

    json_path = outdir / "story_candidates_grouped.json"
    json_path.write_text(json.dumps(grouped, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {json_path}")

    langs = ["tr", "en"] if args.lang == "both" else [args.lang]
    for lang in langs:
        html_text = render_page(grouped, lang)
        html_path = outdir / f"stories-moments.{lang}.apple.apple_icloud.html"
        html_path.write_text(html_text, encoding="utf-8")
        print(f"Wrote {html_path}")

    write_index_links()

    print()
    print("Summary:")
    for story in grouped["stories"]:
        print(
            story["id"],
            "source_items:", story["source_item_count"],
            "moments:", story["moment_count"],
            "grouped_variants:", story["hidden_variant_count"]
        )


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
