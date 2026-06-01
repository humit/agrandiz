#!/usr/bin/env python3

"""Story dashboard rendering helpers.

This module renders neutral story timeline data into a single i18n-aware HTML
dashboard. It intentionally does not perform database access, discovery or
grouping.
"""

from __future__ import annotations

import html
import json
from typing import Any

from agrandiz_i18n import i18n_js, language_switcher_html


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def esc_attr(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


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


def render_html(timeline, config, lang, profile=None):
    profile = profile or {}
    i18n = profile.get("i18n") or {}
    legacy_titles = profile.get("legacy_titles") or {}

    title_key = i18n.get("title", "family.page_title")
    subtitle_key = i18n.get("subtitle", "family.subtitle")
    eyebrow_key = i18n.get("eyebrow", "family.timeline")

    if lang == "tr":
        title = legacy_titles.get("title_tr") or config.get("title_tr") or "Çocukların Büyüme Hikâyesi"
        subtitle = legacy_titles.get("subtitle_tr") or config.get("subtitle_tr") or ""
    else:
        title = legacy_titles.get("title_en") or config.get("title_en") or "Children's Growing-Up Story"
        subtitle = legacy_titles.get("subtitle_en") or config.get("subtitle_en") or ""

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
      <div class="brand">agrandiz <span data-i18n="{esc_attr(eyebrow_key)}">{esc(story_label)}</span></div>
      {language_switcher_html()}
      <div class="hero-copy">
        <h1 data-i18n="{esc_attr(title_key)}">{esc(title)}</h1>
        <p data-i18n="{esc_attr(subtitle_key)}">{esc(subtitle)}</p>
        <div class="meta-line" data-i18n="family.note">{esc(note)}</div>
      </div>
    </header>

    <section class="timeline-summary">
      <article class="summary-card">
        <div class="value">{num(len(timeline['years']))}</div>
        <div class="label" data-i18n="family.years">{esc(years_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(timeline['source_item_count'])}</div>
        <div class="label" data-i18n="family.candidate_photos">{esc(source_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(timeline['selected_moment_count'])}</div>
        <div class="label" data-i18n="family.selected_moments">{esc(moment_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(timeline['grouped_variant_count'])}</div>
        <div class="label" data-i18n="family.grouped_variants">{esc(grouped_label)}</div>
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
  {i18n_js(default_lang=lang)}
</body>
</html>
"""

