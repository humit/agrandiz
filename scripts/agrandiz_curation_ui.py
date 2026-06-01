#!/usr/bin/env python3

"""Shared curation UI helpers: card rendering, exclude logic, and JavaScript.

This module owns the card-level HTML, CSS, JavaScript, and exclude helpers
used by all Agrandiz curation pages. Renderers import from here instead of
duplicating this logic.
"""

import html
import json


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def esc_attr(value):
    return html.escape(str(value), quote=True) if value is not None else ""


def _normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_excludes(raw):
    return {
        "uuids": {_normalize(x) for x in raw.get("uuids", []) if x},
        "phashes": {_normalize(x) for x in raw.get("phashes", []) if x},
        "filenames": {_normalize(x) for x in raw.get("filenames", []) if x},
        "captions": {_normalize(x) for x in raw.get("captions", []) if x},
    }


def item_is_excluded(item, excludes):
    uuid = _normalize(item.get("uuid"))
    phash = _normalize(item.get("phash"))
    filename = _normalize(item.get("filename"))
    caption = _normalize(item.get("caption"))

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


def render_curation_card(moment, lang, extra_badges=None):
    """Render a single moment as a curation card article element.

    extra_badges: optional list of plain strings rendered as mini-badges
    before the standard preview/original/score badges.
    """
    item = moment.get("representative", {})
    caption = item.get("caption") or ("Açıklama yok" if lang == "tr" else "No caption")
    score = f"{float(item.get('score') or 0):.3f}"

    labels = "".join(f'<span class="chip">{esc(label)}</span>' for label in (item.get("labels") or [])[:6])
    terms = "".join(f'<span class="chip matched">{esc(term)}</span>' for term in (item.get("matched_terms") or [])[:4])
    extra_badges_html = "".join(
        f'<span class="mini-badge">{esc(b)}</span>'
        for b in (extra_badges or [])
        if b
    )

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
          {extra_badges_html}<span class="mini-badge">{esc(preview_label)}</span>
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


# Card and grid CSS, suitable for embedding in any page's <style> block.
CURATION_CARD_CSS = """
    .story-photo-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
      align-items: start;
    }

    .story-photo {
      overflow: hidden;
      background: #fff;
      border: 1px solid rgba(0,0,0,0.08);
      border-radius: 22px;
      transition: opacity .18s ease, transform .18s ease;
    }

    .story-photo.is-excluded {
      display: none;
    }

    .story-photo.is-playing {
      transform: translateY(-2px);
    }

    .story-photo-img {
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
    }

    .story-photo-img img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .sequence-hint {
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
    }

    .story-photo:hover .sequence-hint,
    .story-photo.is-playing .sequence-hint {
      opacity: 1;
    }

    .story-photo-meta {
      padding: 12px;
    }

    .photo-badges, .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 8px;
    }

    .photo-caption {
      font-size: 13px;
      line-height: 1.4;
      min-height: 38px;
    }

    .photo-sub {
      font-size: 11px;
      color: #6e6e73;
      margin: 8px 0;
    }

    .chip {
      font-size: 11px;
      padding: 5px 8px;
      border-radius: 999px;
      border: 1px solid rgba(0,0,0,0.08);
      background: #fff;
      color: #3a3a3c;
    }

    .moment-actions {
      margin-top: 10px;
    }

    .variants {
      margin-top: 10px;
      font-size: 12px;
      color: #6e6e73;
    }

    .variants summary {
      cursor: pointer;
      color: #0071e3;
      font-weight: 650;
    }

    .variants ul {
      margin: 8px 0 0;
      padding-left: 18px;
    }

    .variants small {
      display: block;
      color: #8e8e93;
      margin-top: 2px;
    }

    @media (max-width: 1200px) {
      .story-photo-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    @media (max-width: 900px) {
      .story-photo-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 620px) {
      .story-photo-grid {
        grid-template-columns: 1fr;
      }
    }
"""


def curation_panel_html(panel_title, panel_desc, copy_label, reset_label):
    """Return the curation tools panel HTML."""
    return f"""
    <section class="curation-panel">
      <h2>{esc(panel_title)}</h2>
      <p data-i18n="stories.curation_desc">{esc(panel_desc)}</p>
      <div class="curation-actions">
        <button id="copy-exclude-json" type="button">{esc(copy_label)}</button>
        <button id="clear-excludes" type="button">{esc(reset_label)}</button>
      </div>
      <textarea id="exclude-json" spellcheck="false"></textarea>
    </section>"""


def curation_js(copy_label, reset_label=""):
    """Return the exclude-flow and micro-sequence <script> block."""
    return f"""  <script>
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
  </script>"""
