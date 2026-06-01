#!/usr/bin/env python3

import argparse
import html
import json
from pathlib import Path
from datetime import datetime
from agrandiz_i18n import i18n_js, language_switcher_html
from agrandiz_shell import APP_NAV_CSS, app_nav_html


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


def load_json_file(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def normalize_excludes(raw):
    return {
        "uuids": {normalize(x) for x in raw.get("uuids", []) if x},
        "phashes": {normalize(x) for x in raw.get("phashes", []) if x},
        "filenames": {normalize(x) for x in raw.get("filenames", []) if x},
        "captions": {normalize(x) for x in raw.get("captions", []) if x},
    }


def item_is_excluded(item, excludes):
    uuid = normalize(item.get("uuid"))
    phash = normalize(item.get("phash"))
    filename = normalize(item.get("filename"))
    caption = normalize(item.get("caption"))

    if uuid and uuid in excludes["uuids"]:
        return True
    if phash and phash in excludes["phashes"]:
        return True
    if filename and filename in excludes["filenames"]:
        return True
    if caption and caption in excludes["captions"]:
        return True

    return False


def moment_is_excluded(moment, excludes):
    rep = moment.get("representative", {})
    if item_is_excluded(rep, excludes):
        return True

    for variant in moment.get("variants", []):
        if item_is_excluded(variant, excludes):
            return True

    return False


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


def variant_payload(moment):
    variants = moment.get("variants", [])
    if not variants:
        variants = [moment.get("representative", {})]

    uuids = []
    phashes = []
    filenames = []
    captions = []

    for item in variants:
        if item.get("uuid"):
            uuids.append(item["uuid"])
        if item.get("phash"):
            phashes.append(item["phash"])
        if item.get("filename"):
            filenames.append(item["filename"])
        if item.get("caption"):
            captions.append(item["caption"])

    return {
        "uuids": sorted(set(uuids)),
        "phashes": sorted(set(phashes)),
        "filenames": sorted(set(filenames)),
        "captions": sorted(set(captions)),
    }


def frames_for_moment(moment):
    variants = moment.get("variants", [])
    if not variants:
        variants = [moment.get("representative", {})]

    frames = []
    seen = set()

    # Keep representative first.
    rep = moment.get("representative", {})
    if rep.get("thumb"):
        frames.append(rep["thumb"])
        seen.add(rep["thumb"])

    for item in variants:
        thumb = item.get("thumb")
        if thumb and thumb not in seen:
            frames.append(thumb)
            seen.add(thumb)

    return frames[:10]


def render_moment(moment, lang):
    item = moment.get("representative", {})
    caption = item.get("caption") or ("Açıklama yok" if lang == "tr" else "No caption")
    score = f"{float(item.get('score') or 0):.3f}"

    labels = "".join(f'<span class="chip">{esc(label)}</span>' for label in (item.get("labels") or [])[:6])
    terms = "".join(f'<span class="chip matched">{esc(term)}</span>' for term in (item.get("matched_terms") or [])[:4])

    if lang == "tr":
        original = "Orijinal iCloud'da" if item.get("original_status") == "icloud" else "Orijinal lokal"
        album_label = "Albüm"
        moment_label = "Moment"
        similar_label = "benzer kare"
        variants_label = "Varyantlar"
        exclude_label = "Exclude"
        exclude_title = "Bu momenti gizle / exclude listesine ekle"
        preview_label = "Preview hazır"
    else:
        original = "Original in iCloud" if item.get("original_status") == "icloud" else "Original local"
        album_label = "Album"
        moment_label = "Moment"
        similar_label = "similar shots"
        variants_label = "Variants"
        exclude_label = "Exclude"
        exclude_title = "Hide this moment / add to exclude list"
        preview_label = "Preview ready"

    variant_count = int(moment.get("variant_count", 1) or 1)
    frames = frames_for_moment(moment)
    payload = variant_payload(moment)

    frames_json = esc_attr(json.dumps(frames, ensure_ascii=False))
    payload_json = esc_attr(json.dumps(payload, ensure_ascii=False))

    variant_badge = ""
    if variant_count > 1:
        variant_badge = f'<span class="mini-badge moment-badge">{moment_label} · {variant_count} {similar_label}</span>'

    variant_list = ""
    if variant_count > 1:
        lines = []
        for v in moment.get("variants", [])[1:6]:
            v_caption = esc(v.get("caption") or "-")
            v_score = f"{float(v.get('score') or 0):.3f}"
            v_time = esc(v.get("date") or "")
            lines.append(f"<li>{v_caption}<small>Score {v_score} · {v_time}</small></li>")

        if lines:
            variant_list = f"""
            <details class="variants">
              <summary>{variants_label}</summary>
              <ul>{''.join(lines)}</ul>
            </details>
            """

    return f"""
    <article
      class="story-photo"
      data-frames="{frames_json}"
      data-exclude-payload="{payload_json}"
    >
      <div class="story-photo-img">
        <img src="{esc(item.get('thumb'))}" alt="{esc(caption)}" loading="lazy">
        <div class="sequence-hint">{esc('micro sequence' if lang == 'en' else 'micro sequence')}</div>
      </div>

      <div class="story-photo-meta">
        <div class="photo-badges">
          <span class="mini-badge">{esc(preview_label)}</span>
          <span class="mini-badge">{esc(original)}</span>
          <span class="mini-badge">Score {score}</span>
          {variant_badge}
        </div>

        <div class="photo-caption">{esc(caption)}</div>
        <div class="photo-sub">{album_label}: {esc(item.get('album') or '-')} · {esc(item.get('date') or '')}</div>

        <div class="chips">{terms}{labels}</div>

        <div class="moment-actions">
          <button class="exclude-button" type="button" title="{esc_attr(exclude_title)}">{esc(exclude_label)}</button>
        </div>

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
        excluded_label = "exclude edilen moment"
        output_label = "Çıktı adayları"
        reel_label = "Reel/Shorts fikri"
    else:
        score_label = "Readiness score"
        moment_label = "moments"
        source_label = "source items"
        hidden_label = "grouped variants"
        excluded_label = "excluded moments"
        output_label = "Output candidates"
        reel_label = "Reel/Shorts idea"

    outputs = "".join(f'<span class="output-chip">{esc(o)}</span>' for o in story.get("output_types", []))
    moments = "".join(render_moment(m, lang) for m in story.get("moments", [])[:20])

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
        <span>{story.get('excluded_moment_count', 0)} {excluded_label}</span>
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

    .story-photo-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
      align-items: start;
    }}

    .story-photo {{
      overflow: hidden;
      background: #fff;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 22px;
      transition: opacity .18s ease, transform .18s ease;
    }}

    .story-photo.is-excluded {{
      display: none;
    }}

    .story-photo.is-playing {{
      transform: translateY(-2px);
    }}

    .story-photo-img {{
      position: relative;
      height: clamp(210px, 22vw, 330px);
      overflow: hidden;
      background:
        linear-gradient(45deg, #f2f2f4 25%, transparent 25%),
        linear-gradient(-45deg, #f2f2f4 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #f2f2f4 75%),
        linear-gradient(-45deg, transparent 75%, #f2f2f4 75%);
      background-size: 20px 20px;
      background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
      background-color: #fafafa;
    }}

    .story-photo-img img {{
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

    .story-photo:hover .sequence-hint,
    .story-photo.is-playing .sequence-hint {{
      opacity: 1;
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

    .moment-actions {{
      margin-top: 10px;
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

    @media (max-width: 1200px) {{
      .story-photo-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 900px) {{
      .story-photo-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .story-summary {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .story-head {{
        flex-direction: column;
      }}
    }}

    @media (max-width: 620px) {{
      .story-photo-grid,
      .story-summary {{
        grid-template-columns: 1fr;
      }}
    }}
  
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
      <article class="summary-card">
        <div class="value">{num(total_excludes)}</div>
        <div class="label">{esc(excluded_label)}</div>
      </article>
    </section>

    <section class="curation-panel">
      <h2>{esc(panel_title)}</h2>
      <p data-i18n="stories.curation_desc">{esc(panel_desc)}</p>
      <div class="curation-actions">
        <button id="copy-exclude-json" type="button">{esc(copy_label)}</button>
        <button id="clear-excludes" type="button">{esc(reset_label)}</button>
      </div>
      <textarea id="exclude-json" spellcheck="false"></textarea>
    </section>

    {story_cards}
  </div>

  <script>
    const STORAGE_KEY = "agrandiz_excludes_v1";

    function emptyExcludes() {{
      return {{ uuids: [], phashes: [], filenames: [], captions: [] }};
    }}

    function unique(arr) {{
      return Array.from(new Set((arr || []).filter(Boolean)));
    }}

    function normalizePayload(p) {{
      return {{
        uuids: unique(p.uuids || []),
        phashes: unique(p.phashes || []),
        filenames: unique(p.filenames || []),
        captions: unique(p.captions || [])
      }};
    }}

    function loadExcludes() {{
      try {{
        return normalizePayload(JSON.parse(localStorage.getItem(STORAGE_KEY)) || emptyExcludes());
      }} catch (e) {{
        return emptyExcludes();
      }}
    }}

    function saveExcludes(payload) {{
      const clean = normalizePayload(payload);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(clean, null, 2));
      updateExcludeTextarea();
      return clean;
    }}

    function mergeExcludes(a, b) {{
      return normalizePayload({{
        uuids: [...(a.uuids || []), ...(b.uuids || [])],
        phashes: [...(a.phashes || []), ...(b.phashes || [])],
        filenames: [...(a.filenames || []), ...(b.filenames || [])],
        captions: [...(a.captions || []), ...(b.captions || [])]
      }});
    }}

    function updateExcludeTextarea() {{
      const el = document.getElementById("exclude-json");
      if (el) {{
        el.value = JSON.stringify(loadExcludes(), null, 2);
      }}
    }}

    function payloadIntersects(a, b) {{
      const fields = ["uuids", "phashes", "filenames", "captions"];
      for (const field of fields) {{
        const A = new Set(a[field] || []);
        for (const value of (b[field] || [])) {{
          if (A.has(value)) return true;
        }}
      }}
      return false;
    }}

    function applyHiddenCards() {{
      const excludes = loadExcludes();

      document.querySelectorAll(".story-photo").forEach(card => {{
        let payload = emptyExcludes();
        try {{
          payload = normalizePayload(JSON.parse(card.dataset.excludePayload || "{{}}"));
        }} catch (e) {{}}

        if (payloadIntersects(excludes, payload)) {{
          card.classList.add("is-excluded");
        }}
      }});
    }}

    function setupExcludeButtons() {{
      document.querySelectorAll(".exclude-button").forEach(button => {{
        button.addEventListener("click", () => {{
          const card = button.closest(".story-photo");
          if (!card) return;

          let payload = emptyExcludes();
          try {{
            payload = normalizePayload(JSON.parse(card.dataset.excludePayload || "{{}}"));
          }} catch (e) {{}}

          const merged = mergeExcludes(loadExcludes(), payload);
          saveExcludes(merged);
          card.classList.add("is-excluded");
        }});
      }});
    }}

    function setupCopyAndClear() {{
      const copyButton = document.getElementById("copy-exclude-json");
      if (copyButton) {{
        copyButton.addEventListener("click", async () => {{
          const text = JSON.stringify(loadExcludes(), null, 2);
          try {{
            await navigator.clipboard.writeText(text);
            copyButton.textContent = "Copied";
            setTimeout(() => copyButton.textContent = "{esc_attr(copy_label)}", 1200);
          }} catch (e) {{
            const textarea = document.getElementById("exclude-json");
            textarea.focus();
            textarea.select();
          }}
        }});
      }}

      const clearButton = document.getElementById("clear-excludes");
      if (clearButton) {{
        clearButton.addEventListener("click", () => {{
          localStorage.removeItem(STORAGE_KEY);
          updateExcludeTextarea();
          document.querySelectorAll(".story-photo.is-excluded").forEach(card => {{
            card.classList.remove("is-excluded");
          }});
        }});
      }}
    }}

    function setupMicroSequences() {{
      document.querySelectorAll(".story-photo").forEach(card => {{
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
          card.classList.add("is-playing");
          idx = 0;
          timer = setInterval(() => {{
            idx = (idx + 1) % frames.length;
            img.src = frames[idx];
          }}, 360);
        }}

        function stop() {{
          if (timer) {{
            clearInterval(timer);
            timer = null;
          }}
          img.src = original;
          card.classList.remove("is-playing");
        }}

        card.addEventListener("mouseenter", start);
        card.addEventListener("mouseleave", stop);

        card.querySelector(".story-photo-img").addEventListener("click", () => {{
          if (timer) stop();
          else start();
        }});
      }});
    }}

    updateExcludeTextarea();
    setupExcludeButtons();
    setupCopyAndClear();
    setupMicroSequences();
    applyHiddenCards();
  </script>
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
