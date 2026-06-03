#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from datetime import datetime
from agrandiz_i18n import i18n_js, language_switcher_html
from agrandiz_shell import APP_NAV_CSS, app_nav_html
from agrandiz_curation_ui import (
    esc, esc_attr,
    normalize_excludes, item_is_excluded, moment_is_excluded,
    variant_payload, frames_for_moment,
    render_curation_card,
    CURATION_CARD_CSS,
    curation_js,
    curation_panel_html,
)


def num(n):
    return f"{n:,}".replace(",", ".")


def load_json_file(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def lang_spans(tr_text, en_text):
    return (
        f'<span data-lang="tr">{esc(tr_text)}</span>'
        f'<span data-lang="en">{esc(en_text)}</span>'
    )


def story_lang_spans(story, tr_key, en_key):
    return lang_spans(story.get(tr_key, ""), story.get(en_key, ""))


def i18n_label(key, fallback):
    return f'<span data-i18n="{esc_attr(key)}">{esc(fallback)}</span>'


def filter_data(data, excludes):
    filtered = dict(data)
    filtered["generated_at"] = datetime.now().isoformat(timespec="seconds")
    filtered["source"] = data.get("source")
    filtered["mode"] = "moment_renderer"
    filtered["exclude_counts"] = {
        "uuids": len(excludes["uuids"]),
        "phashes": len(excludes["phashes"]),
        "filenames": len(excludes["filenames"]),
        "captions": len(excludes["captions"]),
    }

    stories_out = []

    for story in data.get("stories", []):
        story_out = dict(story)

        moments = []
        excluded_moments = 0

        for moment in story.get("moments", []):
            if moment_is_excluded(moment, excludes):
                excluded_moments += 1
                continue
            moments.append(moment)

        story_out["moments"] = moments
        story_out["items"] = [m["representative"] for m in moments]
        story_out["moment_count"] = len(moments)
        story_out["item_count"] = len(moments)
        story_out["hidden_variant_count"] = sum(max(m.get("variant_count", 1) - 1, 0) for m in moments)
        story_out["excluded_moment_count"] = excluded_moments

        # Keep story only if still useful.
        if len(moments) >= 3:
            stories_out.append(story_out)

    filtered["stories"] = stories_out
    filtered["story_count"] = len(stories_out)

    return filtered


def render_story(story, lang):
    outputs = "".join(f'<span class="output-chip">{esc(o)}</span>' for o in story.get("output_types", []))
    moments = "".join(render_curation_card(m, lang) for m in story.get("moments", [])[:20])

    return f"""
    <section class="story-section" id="{esc(story['id'])}">
      <div class="story-head">
        <div>
          <div class="story-emoji">{esc(story.get('emoji', '•'))}</div>
          <h2>{story_lang_spans(story, 'title_tr', 'title_en')}</h2>
          <p>{story_lang_spans(story, 'desc_tr', 'desc_en')}</p>
        </div>
        <div class="story-score">
          <div class="score-number">{story.get('story_score')}</div>
          <div class="score-label" data-i18n="stories.preparation_score">Hazırlık skoru</div>
        </div>
      </div>

      <div class="story-stats">
        <span>{story.get('moment_count', 0)} {i18n_label('stories.moments', 'moment')}</span>
        <span>{story.get('source_item_count', 0)} {i18n_label('stories.source_items', 'kaynak kare')}</span>
        <span>{story.get('hidden_variant_count', 0)} {i18n_label('stories.grouped_variants', 'gruplanan varyant')}</span>
        <span>{story.get('excluded_moment_count', 0)} {i18n_label('stories.excluded_moments', 'exclude edilen moment')}</span>
        <span>{story.get('reel_structure', {}).get('duration', '')} · 9:16</span>
      </div>

      <div class="story-output">
        <strong data-i18n="stories.output_candidates">Çıktı adayları</strong><strong>:</strong>
        {outputs}
      </div>

      <div class="reel-idea">
        <strong data-i18n="stories.reel_idea">Reel/Shorts fikri</strong><strong>:</strong> {story_lang_spans(story, 'reel_tr', 'reel_en')}
      </div>

      <div class="story-photo-grid">
        {moments}
      </div>
    </section>
    """


def render_page(data, lang):
    if lang == "tr":
        title = "agrandiz hikâye keşfi"
        hero = "Kürasyon kontrollü moment galerisi"
        subtitle = "Tam görünen thumbnail'ler, hızlı exclude akışı ve hover/touch micro-sequence ile daha kullanılabilir hikâye adayları."
        candidates_label = "story adayı"
        moments_label = "seçili moment"
        grouped_label = "gruplanan varyant"
        excluded_label = "aktif exclude kuralı"
        copy_label = "Exclude JSON'u kopyala"
        reset_label = "Bu tarayıcıdaki geçici exclude listesini temizle"
        panel_title = "Kürasyon araçları"
        panel_desc = "Exclude butonuna bastığında kart hemen gizlenir ve aşağıdaki JSON güncellenir. Kalıcı yapmak için JSON'u config/excludes.json dosyasına yapıştırıp sayfayı yeniden üret."
    else:
        title = "agrandiz story discovery"
        hero = "Curatable moment gallery"
        subtitle = "Full-image thumbnails, fast exclude flow and hover/touch micro-sequences for more usable story candidates."
        candidates_label = "story candidates"
        moments_label = "selected moments"
        grouped_label = "grouped variants"
        excluded_label = "active exclude rules"
        copy_label = "Copy exclude JSON"
        reset_label = "Clear temporary exclude list in this browser"
        panel_title = "Curation tools"
        panel_desc = "When you click Exclude, the card is hidden immediately and the JSON below is updated. To make it persistent, paste the JSON into config/excludes.json and regenerate."

    stories = data.get("stories", [])
    total_moments = sum(s.get("moment_count", 0) for s in stories)
    total_grouped = sum(s.get("hidden_variant_count", 0) for s in stories)
    total_excludes = sum(data.get("exclude_counts", {}).values())

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
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}

    .summary-card, .story-section, .curation-panel {{
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

    @media (max-width: 900px) {{
      .story-summary {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .story-head {{
        flex-direction: column;
      }}
    }}

    @media (max-width: 620px) {{
      .story-summary {{
        grid-template-columns: 1fr;
      }}
    }}

{CURATION_CARD_CSS}

{APP_NAV_CSS}

  </style>
</head>

<body class="theme-apple profile-apple_icloud">
  <div class="shell">
    <header class="hero">
      <div class="brand">agrandiz <span data-i18n="stories.brand_section">story discovery</span></div>
      {language_switcher_html()}
      {app_nav_html(active="stories")}
      <div class="hero-copy">
        <h1 data-i18n="stories.hero_title">{esc(hero)}</h1>
        <p data-i18n="stories.hero_subtitle">{esc(subtitle)}</p>
      </div>
    </header>

    <section class="story-summary">
      <article class="summary-card">
        <div class="value">{num(len(stories))}</div>
        <div class="label" data-i18n="stories.story_candidates">{esc(candidates_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(total_moments)}</div>
        <div class="label" data-i18n="stories.selected_moments">{esc(moments_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(total_grouped)}</div>
        <div class="label" data-i18n="stories.grouped_variants">{esc(grouped_label)}</div>
      </article>
      <article class="summary-card">
        <div class="value">{num(total_excludes)}</div>
        <div class="label" data-i18n="stories.active_exclude_rules">{esc(excluded_label)}</div>
      </article>
    </section>

    {curation_panel_html(panel_title, panel_desc, copy_label, reset_label)}

    {story_cards}
  </div>

{curation_js(copy_label)}
{i18n_js()}
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="cache/story_candidates_grouped.json")
    parser.add_argument("--exclude", default="config/excludes.json")
    parser.add_argument("--outdir", default="cache")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    raw = load_json_file(args.input, {"stories": []})
    excludes = normalize_excludes(load_json_file(args.exclude, {}))
    data = filter_data(raw, excludes)

    json_path = outdir / "story_candidates.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {json_path}")

    html_text = render_page(data, "tr")
    html_path = outdir / "stories.apple.apple_icloud.html"
    html_path.write_text(html_text, encoding="utf-8")
    print(f"Wrote {html_path}")


    print()
    print("Summary:")
    print("stories:", data.get("story_count"))
    print("exclude_counts:", data.get("exclude_counts"))

    for story in data.get("stories", []):
        print(
            story["id"],
            "moments:", story.get("moment_count"),
            "grouped_variants:", story.get("hidden_variant_count"),
            "excluded:", story.get("excluded_moment_count")
        )


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
