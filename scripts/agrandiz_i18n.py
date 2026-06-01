#!/usr/bin/env python3

import json
from pathlib import Path


DEFAULT_LANG = "en"


def project_root():
    return Path(__file__).resolve().parents[1]


def locales_dir():
    return project_root() / "locales"


def load_locale(lang):
    path = locales_dir() / f"{lang}.json"

    if not path.exists():
        raise FileNotFoundError(f"Locale file not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def load_locales():
    result = {}

    if not locales_dir().exists():
        return {
            "en": {
                "app.name": "Agrandiz",
                "language.label": "Language"
            }
        }

    for path in sorted(locales_dir().glob("*.json")):
        result[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    if DEFAULT_LANG not in result:
        result[DEFAULT_LANG] = {}

    return result


def i18n_js(default_lang=DEFAULT_LANG):
    locales = load_locales()

    return f"""
<script>
window.AGRANDIZ_I18N = {json.dumps(locales, ensure_ascii=False, indent=2)};
window.AGRANDIZ_DEFAULT_LANG = {json.dumps(default_lang)};

function agrandizGetLang() {{
  return localStorage.getItem("agrandiz_lang") || window.AGRANDIZ_DEFAULT_LANG || "en";
}}

function agrandizSetLang(lang) {{
  localStorage.setItem("agrandiz_lang", lang);
  agrandizApplyI18n();
}}

function agrandizT(key) {{
  const lang = agrandizGetLang();
  const fallback = window.AGRANDIZ_DEFAULT_LANG || "en";
  const table = window.AGRANDIZ_I18N[lang] || {{}};
  const fallbackTable = window.AGRANDIZ_I18N[fallback] || {{}};
  return table[key] || fallbackTable[key] || key;
}}

function agrandizApplyI18n() {{
  const lang = agrandizGetLang();
  document.documentElement.lang = lang;

  document.querySelectorAll("[data-i18n]").forEach(el => {{
    el.textContent = agrandizT(el.dataset.i18n);
  }});

  document.querySelectorAll("[data-i18n-title]").forEach(el => {{
    el.setAttribute("title", agrandizT(el.dataset.i18nTitle));
  }});

  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {{
    el.setAttribute("placeholder", agrandizT(el.dataset.i18nPlaceholder));
  }});

  document.querySelectorAll("[data-i18n-prefix]").forEach(el => {{
    const key = el.dataset.i18nPrefix;
    const value = el.dataset.i18nValue || "";
    el.textContent = agrandizT(key) + value;
  }});

  document.querySelectorAll("[data-lang-select]").forEach(el => {{
    el.value = lang;
  }});

  document.querySelectorAll("[data-lang]").forEach(el => {{
    el.style.display = el.dataset.lang === lang ? "" : "none";
  }});
}}

function agrandizLanguageSelector() {{
  const langs = Object.keys(window.AGRANDIZ_I18N || {{}}).sort();
  return `
    <label class="language-switcher">
      <span data-i18n="language.label">Language</span>
      <select data-lang-select onchange="agrandizSetLang(this.value)">
        ${{langs.map(lang => `<option value="${{lang}}">${{lang.toUpperCase()}}</option>`).join("")}}
      </select>
    </label>
  `;
}}

document.addEventListener("DOMContentLoaded", () => {{
  document.querySelectorAll("[data-language-switcher]").forEach(el => {{
    el.innerHTML = agrandizLanguageSelector();
  }});
  agrandizApplyI18n();
}});
</script>
"""


def language_switcher_html():
    return '<div data-language-switcher></div>'
