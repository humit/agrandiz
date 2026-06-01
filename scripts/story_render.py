#!/usr/bin/env python3

"""Story dashboard rendering helpers.

This module renders neutral story timeline data into a single i18n-aware HTML
dashboard. It intentionally does not perform database access, discovery or
grouping.
"""

from __future__ import annotations

from typing import Any

from agrandiz_i18n import i18n_js, language_switcher_html
from agrandiz_shell import APP_NAV_CSS, app_nav_html
from agrandiz_curation_ui import (
    esc, esc_attr,
    normalize_excludes, moment_is_excluded,
    render_curation_card,
    CURATION_CARD_CSS,
    curation_js,
    curation_panel_html,
)


def num(value: Any, digits: int = 0) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def render_html(timeline, config, lang, profile=None, excludes=None):
    profile = profile or {}
    i18n = profile.get("i18n") or {}
    legacy_titles = profile.get("legacy_titles") or {}

    title_key = i18n.get("title", "story.timeline_title")
    subtitle_key = i18n.get("subtitle", "story.timeline_subtitle")
    eyebrow_key = i18n.get("eyebrow", "story.timeline_eyebrow")

    if lang == "tr":
        title = legacy_titles.get("title_tr") or config.get("title_tr") or "Hikâye Zaman Çizelgesi"
        subtitle = legacy_titles.get("subtitle_tr") or config.get("subtitle_tr") or ""
    else:
        title = legacy_titles.get("title_en") or config.get("title_en") or "Story Timeline"
        subtitle = legacy_titles.get("subtitle_en") or config.get("subtitle_en") or ""

    if lang == "tr":
        story_label = "hikâye zaman çizelgesi"
        source_label = "aday fotoğraf"
        moment_label = "seçili moment"
        grouped_label = "gruplanan varyant"
        years_label = "yıl"
        note = "Bu sayfa orijinalleri indirmeden, mevcut preview cache üzerinden oluşturuldu."
        copy_label = "Exclude JSON'u kopyala"
        reset_label = "Bu tarayıcıdaki geçici exclude listesini temizle"
        panel_title = "Kürasyon araçları"
        panel_desc = "Exclude butonuna bastığında kart hemen gizlenir ve aşağıdaki JSON güncellenir. Kalıcı yapmak için JSON'u config/excludes.json dosyasına yapıştırıp sayfayı yeniden üret."
    else:
        story_label = "story timeline"
        source_label = "candidate photos"
        moment_label = "selected moments"
        grouped_label = "grouped variants"
        years_label = "years"
        note = "This page was generated from the preview cache without downloading originals."
        copy_label = "Copy exclude JSON"
        reset_label = "Clear temporary exclude list in this browser"
        panel_title = "Curation tools"
        panel_desc = "When you click Exclude, the card is hidden immediately and the JSON below is updated. To make it persistent, paste the JSON into config/excludes.json and regenerate."

    excludes_norm = normalize_excludes(excludes or {})
    year_sections = []

    for year in timeline["years"]:
        filtered_moments = [
            m for m in year["moments"]
            if not moment_is_excluded(m, excludes_norm)
        ]

        cards_html = []
        for moment in filtered_moments:
            adapted = dict(moment)
            rep = dict(adapted.get("representative", {}))
            rep["matched_terms"] = moment.get("matched_terms") or moment.get("milestone_terms") or []
            adapted["representative"] = rep
            month = moment.get("month_label_tr" if lang == "tr" else "month_label_en") or ""
            extra = [month] if month else None
            cards_html.append(render_curation_card(adapted, lang, extra_badges=extra))

        year_sections.append(
            f"""
            <section class="year-section">
              <div class="year-head">
                <h2>{esc(year['year'])}</h2>
                <span>{len(filtered_moments)} {moment_label}</span>
              </div>
              <div class="story-photo-grid">
                {''.join(cards_html)}
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
    .summary-card, .year-section, .curation-panel {{
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
    .mini-badge {{
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
    .curation-panel {{
      padding: 22px;
      margin: 24px 0;
    }}
    .curation-panel h2 {{
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: -0.03em;
    }}
    .curation-panel p {{
      margin: 0 0 14px;
      color: #6e6e73;
      line-height: 1.5;
    }}
    .curation-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .curation-actions button, .exclude-button {{
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 999px;
      padding: 8px 12px;
      background: #fff;
      color: #0071e3;
      font-weight: 650;
      cursor: pointer;
    }}
    .exclude-button {{
      color: #b42318;
    }}
    #exclude-json {{
      width: 100%;
      min-height: 130px;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 18px;
      padding: 14px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      background: #fff;
      color: #1d1d1f;
    }}
    @media (max-width: 900px) {{
      .timeline-summary {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 620px) {{
      .timeline-summary {{
        grid-template-columns: 1fr;
      }}
      .year-head {{
        flex-direction: column;
      }}
    }}
{CURATION_CARD_CSS}
{APP_NAV_CSS}
  </style>
</head>
<body class="theme-apple profile-apple_icloud">
  <div class="shell">
    <header class="hero">
      <div class="brand">agrandiz <span data-i18n="{esc_attr(eyebrow_key)}">{esc(story_label)}</span></div>
      {language_switcher_html()}
      {app_nav_html(active="family_timeline")}
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

    {curation_panel_html(panel_title, panel_desc, copy_label, reset_label)}

    {''.join(year_sections)}
  </div>

{curation_js(copy_label)}
  {i18n_js(default_lang=lang)}
</body>
</html>
"""
