#!/usr/bin/env python3

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Shared i18n helpers live under scripts/.
APP_FILE = Path(__file__).resolve()
PROJECT_ROOT_FOR_IMPORTS = APP_FILE.parents[1]
SCRIPTS_DIR_FOR_IMPORTS = PROJECT_ROOT_FOR_IMPORTS / "scripts"
if str(SCRIPTS_DIR_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR_FOR_IMPORTS))

try:
    from agrandiz_i18n import i18n_js, language_switcher_html
except Exception as exc:
    def i18n_js(default_lang="en"):
        return ""

    def language_switcher_html():
        return ""



APP_NAME = "Agrandiz"
PORT = 8765

SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
PROJECT_DIR = SUPPORT_DIR / "project"

LOG_LINES = []
CURRENT_SERVER_PORT = None

CURRENT_STATUS = {
    "busy": False,
    "title": "Ready",
    "last_error": None,
}



def load_app_version():
    root = bundled_project_dir()
    vf = root / "VERSION.json"

    if not vf.exists():
        return {
            "name": "Agrandiz",
            "version": "0.0.0",
            "channel": "dev",
            "updated_at": None,
        }

    try:
        return json.loads(vf.read_text())
    except Exception:
        return {
            "name": "Agrandiz",
            "version": "0.0.0",
            "channel": "unknown",
            "updated_at": None,
        }


def app_version_string():
    data = load_app_version()
    name = data.get("name", "Agrandiz")
    version = data.get("version", "0.0.0")
    channel = data.get("channel", "dev")

    if channel:
        return f"{name} {version} {channel}"

    return f"{name} {version}"

def log(message):
    line = str(message)
    print(line, flush=True)
    LOG_LINES.append(line)
    if len(LOG_LINES) > 1200:
        del LOG_LINES[:300]


def set_status(busy, title, error=None):
    CURRENT_STATUS["busy"] = bool(busy)
    CURRENT_STATUS["title"] = title
    CURRENT_STATUS["last_error"] = error


def running_from_app_bundle():
    return ".app/Contents/Resources" in str(Path(__file__).resolve())


def bundled_project_dir():
    """
    In app bundle:
      Agrandiz.app/Contents/Resources/agrandiz
    In dev mode:
      repo root
    """
    here = Path(__file__).resolve()

    if running_from_app_bundle():
        for parent in [here] + list(here.parents):
            if parent.name == "agrandiz":
                return parent

    return here.parents[1]


def app_python():
    """
    In app bundle, use embedded venv.
    In dev mode, use current Python.
    """
    if running_from_app_bundle():
        root = bundled_project_dir()
        py = root.parent / "venv" / "bin" / "python"
        if py.exists():
            return str(py)

    return sys.executable


def sync_project_code(src, dst):
    """
    Keep bundled code up to date without destroying user-generated cache
    or user curation files.

    Preserved:
      - cache/
      - config/excludes.json

    Synced:
      - scripts/
      - app/
      - themes/
      - config/story_profiles/
      - requirements / static files at repo root when needed later
    """
    sync_dirs = [
        "scripts",
        "app",
        "themes",
        "locales",
        "config/story_profiles",
    ]

    for rel in sync_dirs:
        s = src / rel
        d = dst / rel

        if not s.exists():
            continue

        if d.exists():
            shutil.rmtree(d)

        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            s,
            d,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
        )

    # Keep shared version file in sync too.
    version_src = src / "VERSION.json"
    version_dst = dst / "VERSION.json"
    if version_src.exists():
        shutil.copy2(version_src, version_dst)

    # Ensure required writable dirs/files exist.
    (dst / "cache").mkdir(parents=True, exist_ok=True)
    (dst / "config").mkdir(parents=True, exist_ok=True)

    excludes = dst / "config" / "excludes.json"
    if not excludes.exists():
        excludes.write_text(
            '{\n  "uuids": [],\n  "phashes": [],\n  "filenames": [],\n  "captions": []\n}\n',
            encoding="utf-8"
        )


def copy_project_if_needed():
    src = bundled_project_dir()
    dst = PROJECT_DIR

    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)

    marker = dst / ".agrandiz_project_ready"

    if marker.exists():
        log(f"Using existing project data: {dst}")
        log("Syncing bundled app code while preserving cache and excludes...")
        sync_project_code(src, dst)
        return dst

    if dst.exists():
        shutil.rmtree(dst)

    log(f"Preparing user project directory: {dst}")
    log(f"Bundled project source: {src}")

    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        "*.pyc",
        ".DS_Store",
        "cache",
        "dist",
        "build"
    )

    shutil.copytree(src, dst, ignore=ignore)
    sync_project_code(src, dst)

    marker.write_text("ok\n", encoding="utf-8")
    log(f"Project prepared: {dst}")

    return dst

def ensure_project():
    return copy_project_if_needed()


def make_unbuffered(args):
    """
    Ensure child Python output is visible as early as possible.
    """
    if len(args) >= 2 and args[0].endswith("/python") and args[1] != "-u":
        return [args[0], "-u"] + args[1:]
    return args


def run_command(args, title, keep_busy=False):
    project_dir = ensure_project()
    args = make_unbuffered(args)

    set_status(True, title)
    log("")
    log(f"== {title} ==")
    log("Starting now. If Photos Library is large, the first visible output may take a little while.")
    log("No upload. No deletion. Local processing only.")
    log(" ".join(args))

    try:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            args,
            cwd=str(project_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )

        assert process.stdout is not None

        for line in process.stdout:
            log(line.rstrip())

        rc = process.wait()

        if rc != 0:
            msg = f"{title} failed with exit code {rc}"
            log(msg)
            set_status(False, "Error", msg)
            return False

        log(f"{title} completed.")
        if keep_busy:
            set_status(True, f"{title} completed.")
        else:
            set_status(False, "Ready")
        return True

    except Exception as exc:
        msg = f"{title} failed: {exc}"
        log(msg)
        set_status(False, "Error", msg)
        return False


def run_pipeline():
    if CURRENT_STATUS["busy"]:
        log("Already busy; ignoring new pipeline request.")
        return

    log("Build requested. This step creates dashboard, story candidates, moment grouping and story gallery.")
    set_status(True, "Generating Stories")

    py = app_python()

    commands = [
        (
            [py, "scripts/make_dashboard.py", "--db", "cache/agrandiz.sqlite", "--outdir", "cache", "--theme", "apple", "--profile", "apple_icloud"],
            "Building dashboard",
        ),
        (
            [py, "scripts/discover_stories.py", "--db", "cache/agrandiz.sqlite", "--outdir", "cache", "--config", "config/story_profiles/apple_icloud_default.json", "--lang", "both"],
            "Discovering stories",
        ),
        (
            [py, "scripts/group_story_moments.py", "--input", "cache/story_candidates_raw.json", "--outdir", "cache"],
            "Grouping story moments",
        ),
        (
            [py, "scripts/dedupe_story_candidates.py", "--input", "cache/story_candidates_grouped.json", "--output", "cache/story_candidates_deduped.json"],
            "Removing duplicate moments",
        ),
        (
            [py, "scripts/render_story_moments.py", "--input", "cache/story_candidates_deduped.json", "--exclude", "config/excludes.json", "--outdir", "cache"],
            "Rendering story gallery",
        ),
        (
            [py, "scripts/story_pipeline.py", "--db", "cache/agrandiz.sqlite", "--profile", "config/story_profiles/family_timeline.json", "--outdir", "cache", "--fast"],
            "Building family timeline",
        ),
    ]

    for args, title in commands:
        ok = run_command(args, title, keep_busy=True)
        if not ok:
            return

    log("Story discovery pipeline completed.")
    log("You can now click Open Dashboard.")
    set_status(False, "Ready")


def run_scan():
    if CURRENT_STATUS["busy"]:
        log("Already busy; ignoring scan request.")
        return

    log("Scan requested. This step builds the local Photos metadata cache.")
    log("It will not build dashboard or story pages automatically.")
    py = app_python()
    run_command([py, "scripts/scan_to_sqlite.py"], "Scanning Photos Library")


def open_output_folder():
    project_dir = ensure_project()
    output = project_dir / "cache"
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(["open", str(output)])



def ensure_portal_index(project_dir):
    cache_dir = project_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    index = cache_dir / "index.html"

    files = {
        "stories_tr": cache_dir / "stories.tr.apple.apple_icloud.html",
        "stories_en": cache_dir / "stories.en.apple.apple_icloud.html",
        "dashboard_tr": cache_dir / "dashboard.tr.apple.apple_icloud.html",
        "dashboard_en": cache_dir / "dashboard.en.apple.apple_icloud.html",
        "story_json": cache_dir / "story_candidates.json",
    }

    def ready(name):
        return files[name].exists()

    def card(href, eyebrow, title, desc, enabled):
        cls = "portal-card" if enabled else "portal-card disabled"
        if enabled:
            tag_start = f'<a class="{cls}" href="{href}">'
            tag_end = '</a>'
        else:
            tag_start = f'<div class="{cls}">'
            tag_end = '</div>'

        return "\n".join([
            tag_start,
            f'  <div class="eyebrow">{eyebrow}</div>',
            f'  <h2>{title}</h2>',
            f'  <p>{desc}</p>',
            tag_end,
        ])

    cards = [
        card(
            "stories.tr.apple.apple_icloud.html",
            "Türkçe · Story Discovery",
            "Kürasyon Kontrollü Moment Galerisi",
            "Tam görünen fotoğraflar, exclude butonları ve hover micro-sequence ile gelişmiş hikâye adayları.",
            ready("stories_tr"),
        ),
        card(
            "stories.en.apple.apple_icloud.html",
            "English · Story Discovery",
            "Curatable Moment Gallery",
            "Full-image thumbnails, exclude buttons and hover micro-sequences for story candidates.",
            ready("stories_en"),
        ),
        card(
            "dashboard.tr.apple.apple_icloud.html",
            "Türkçe · Dashboard",
            "agrandiz Dashboard",
            "Mac + Photos/iCloud arşivinizden keşfedilen özet, hikâye adayları ve güçlü kareler.",
            ready("dashboard_tr"),
        ),
        card(
            "dashboard.en.apple.apple_icloud.html",
            "English · Dashboard",
            "agrandiz Dashboard",
            "Summary, story candidates and strong image candidates from a Mac + Photos/iCloud archive.",
            ready("dashboard_en"),
        ),
    ]

    html = "\n".join([
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width,initial-scale=1">',
        "  <title>agrandiz demo portal</title>",
        '  <link rel="stylesheet" href="../themes/apple.css">',
        "  <style>",
        "    .portal-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 28px; }",
        "    .portal-card { display: block; text-decoration: none; color: inherit; background: rgba(255,255,255,0.78); border: 1px solid rgba(0,0,0,0.08); border-radius: 28px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }",
        "    .portal-card.disabled { opacity: .45; pointer-events: none; }",
        "    .portal-card .eyebrow { color: #0071e3; font-size: 13px; font-weight: 700; margin-bottom: 10px; }",
        "    .portal-card h2 { margin: 0 0 8px; font-size: 26px; letter-spacing: -0.03em; }",
        "    .portal-card p { margin: 0; color: #6e6e73; line-height: 1.45; }",
        "    .status-grid { margin-top: 28px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }",
        "    .status-card { background: rgba(255,255,255,0.78); border: 1px solid rgba(0,0,0,0.08); border-radius: 24px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }",
        "    .status-card .label { color: #6e6e73; font-size: 13px; margin-bottom: 8px; }",
        "    .status-card .value { font-size: 24px; font-weight: 750; letter-spacing: -0.03em; }",
        "    .dev-panel { margin-top: 32px; background: rgba(255,255,255,0.78); border: 1px solid rgba(0,0,0,0.08); border-radius: 24px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }",
        "    code { background: #f3f4f6; border-radius: 8px; padding: 2px 6px; font-size: 13px; }",
        "    @media (max-width: 900px) { .portal-actions, .status-grid { grid-template-columns: 1fr; } }",
        "  </style>",
        "</head>",
        '<body class="theme-apple profile-apple_icloud">',
        '  <div class="shell">',
        '    <header class="hero">',
        '      <div class="brand">agrandiz <span>demo portal</span></div>',
        '      <div class="hero-copy">',
        "        <h1>From Photos Library to visible stories.</h1>",
        "        <p>This local demo reads the agrandiz SQLite cache generated from Apple Photos, then renders dashboards and story discovery galleries. No iCloud account connection, no upload, no deletion.</p>",
        '        <div class="meta-line">Theme: <strong>apple</strong> · Source profile: <strong>apple_icloud</strong> · Mode: <strong>local demo</strong></div>',
        "      </div>",
        "    </header>",
        '    <section class="portal-actions">',
        *cards,
        "    </section>",
        '    <section class="status-grid">',
        '      <article class="status-card"><div class="label">Story gallery</div><div class="value">' + ("Ready" if ready("stories_tr") else "Missing") + "</div></article>",
        '      <article class="status-card"><div class="label">Dashboard</div><div class="value">' + ("Ready" if ready("dashboard_tr") else "Missing") + "</div></article>",
        '      <article class="status-card"><div class="label">Story JSON</div><div class="value">' + ("Ready" if ready("story_json") else "Missing") + "</div></article>",
        "    </section>",
        '    <section class="dev-panel">',
        "      <h2>Developer artifacts</h2>",
        "      <p>Output folder: <code>" + str(cache_dir) + "</code></p>",
        "      <p>Main story data: <code>cache/story_candidates.json</code></p>",
        "      <p>Exclude config: <code>config/excludes.json</code></p>",
        "    </section>",
        "  </div>",
        "</body>",
        "</html>",
    ])

    index.write_text(html, encoding="utf-8")
    log(f"Portal index ready: {index}")
    return index


def open_portal():
    project_dir = ensure_project()
    cache_dir = project_dir / "cache"

    dashboard = cache_dir / "dashboard.apple.apple_icloud.html"
    legacy_dashboard = cache_dir / "dashboard.en.apple.apple_icloud.html"

    port = CURRENT_SERVER_PORT or PORT

    if dashboard.exists():
        url = f"http://127.0.0.1:{port}/cache/dashboard.apple.apple_icloud.html"
        webbrowser.open(url)
        log(f"Opened dashboard: {url}")
        return True

    if legacy_dashboard.exists():
        url = f"http://127.0.0.1:{port}/cache/dashboard.en.apple.apple_icloud.html"
        webbrowser.open(url)
        log(f"Opened legacy dashboard: {url}")
        return True

    log("Dashboard not found. Run Generate Stories first.")
    return False


def file_response(handler, path, content_type="text/html; charset=utf-8"):
    if not path.exists() or not path.is_file():
        json_response(handler, {"error": "not found"}, status=404)
        return

    payload = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def content_type_for(path):
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"



def read_request_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def update_excludes(payload):
    project_dir = ensure_project()
    exclude_path = project_dir / "config" / "excludes.json"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)

    if exclude_path.exists():
        try:
            data = json.loads(exclude_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}

    for key in ["uuids", "phashes", "filenames", "captions"]:
        if not isinstance(data.get(key), list):
            data[key] = []

    for key in ["uuid", "phash", "filename", "caption"]:
        value = payload.get(key)
        if not value:
            continue

        target_key = {
            "uuid": "uuids",
            "phash": "phashes",
            "filename": "filenames",
            "caption": "captions",
        }[key]

        if value not in data[target_key]:
            data[target_key].append(value)

    exclude_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\\n",
        encoding="utf-8"
    )

    return data



def sqlite_has_photos_table(db_path):
    if not db_path.exists() or db_path.stat().st_size == 0:
        return False

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='photos'"
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def runtime_state():
    project_dir = PROJECT_DIR
    cache_dir = project_dir / "cache"

    db_path = cache_dir / "agrandiz.sqlite"

    dashboard_path = cache_dir / "dashboard.apple.apple_icloud.html"
    stories_path = cache_dir / "stories.apple.apple_icloud.html"
    family_path = cache_dir / "family-timeline.apple.apple_icloud.html"
    story_json_path = cache_dir / "story_candidates.json"

    photos_cache_ready = sqlite_has_photos_table(db_path)

    outputs_ready = (
        dashboard_path.exists()
        or stories_path.exists()
        or family_path.exists()
        or story_json_path.exists()
    )

    return {
        "busy": CURRENT_STATUS["busy"],
        "title": CURRENT_STATUS["title"],
        "last_error": CURRENT_STATUS["last_error"],
        "version": app_version_string(),
        "photos_cache_ready": photos_cache_ready,
        "portal_ready": outputs_ready,
        "outputs_ready": outputs_ready,
        "paths": {
            "project_dir": str(project_dir),
            "cache_dir": str(cache_dir),
            "db": str(db_path),
            "dashboard": str(dashboard_path),
            "stories": str(stories_path),
            "family": str(family_path),
            "story_json": str(story_json_path),
        },
    }


def json_response(handler, obj, status=200):
    payload = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def html_response(handler, html_text, status=200):
    payload = html_text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def run_async(fn):
    thread = threading.Thread(target=fn, daemon=True)
    thread.start()


def app_html():
    version_label = app_version_string()
    project_dir = PROJECT_DIR

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Agrandiz Beta</title>
  <style>
    :root {{
      --bg: #f5f5f7;
      --panel: rgba(255,255,255,0.82);
      --text: #1d1d1f;
      --muted: #6e6e73;
      --border: rgba(0,0,0,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,0.08);
      --accent: #0071e3;
      --danger: #b42318;
      --good: #168a4a;
      --radius: 24px;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
      color: var(--text);
      background: linear-gradient(180deg, #fbfbfd 0%, var(--bg) 60%, #eef1f5 100%);
    }}

    .shell {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 36px 22px 72px;
    }}

    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 18px;
    }}

    .version-pill {{
      font-size: 13px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(0,113,227,0.10);
      color: var(--accent);
      font-weight: 700;
    }}

    .language-switcher {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
    }}

    .language-switcher select {{
      border: 1px solid rgba(0,0,0,0.10);
      border-radius: 999px;
      padding: 6px 10px;
      background: #fff;
    }}

    .hero {{
      border: 1px solid var(--border);
      border-radius: 32px;
      padding: 34px;
      background: linear-gradient(180deg, rgba(255,255,255,.96), rgba(255,255,255,.72));
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }}

    .brand {{
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 12px;
    }}

    .brand span {{
      color: var(--muted);
      font-weight: 500;
      font-size: 14px;
      margin-left: 8px;
    }}

    h1 {{
      margin: 0 0 12px;
      font-size: 46px;
      line-height: 1.04;
      letter-spacing: -0.045em;
    }}

    .hero p {{
      color: var(--muted);
      font-size: 17px;
      line-height: 1.5;
      margin: 0;
      max-width: 840px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin: 20px 0;
    }}

    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 22px;
      box-shadow: var(--shadow);
    }}

    .action-card {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 205px;
    }}

    .status-card {{
      grid-column: span 3;
    }}

    .status-row {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .status-spinner {{
      display: none;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      border: 3px solid rgba(0,113,227,0.18);
      border-top-color: var(--accent);
      animation: agrandiz-spin .85s linear infinite;
      flex: 0 0 auto;
    }}

    .status-spinner.is-active {{
      display: inline-block;
    }}

    @keyframes agrandiz-spin {{
      to {{
        transform: rotate(360deg);
      }}
    }}


    .label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}

    .value {{
      font-size: 24px;
      font-weight: 750;
      letter-spacing: -0.03em;
    }}

    .ok {{
      color: var(--good);
    }}

    .warn {{
      color: var(--danger);
    }}

    .card-note {{
      color: var(--muted);
      line-height: 1.4;
      margin: 0;
      font-size: 14px;
      flex: 1;
    }}

    button, a.button {{
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-height: 46px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: #fff;
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
      cursor: pointer;
      padding: 10px 14px;
      font-size: 14px;
    }}

    button.primary {{
      background: linear-gradient(135deg, #0a84ff, #5ac8fa);
      color: #fff;
      border: none;
    }}

    button:disabled {{
      opacity: .55;
      cursor: not-allowed;
    }}

    .card-button {{
      width: 100%;
      margin-top: 6px;
    }}

    .actions {{
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
      margin: 20px 0;
      max-width: 360px;
    }}

    .log {{
      width: 100%;
      min-height: 300px;
      background: #111;
      color: #e6e6e6;
      border-radius: 22px;
      border: none;
      padding: 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow: auto;
    }}

    .bottom-status {{
      margin-top: 14px;
      background: rgba(255,255,255,0.72);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 14px;
      color: var(--muted);
      font-size: 13px;
    }}

    .bottom-status code {{
      display: block;
      margin-top: 6px;
      word-break: break-all;
      background: #fff;
    }}

    .note {{
      color: var(--muted);
      line-height: 1.5;
      margin-top: 12px;
    }}

    code {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 2px 6px;
      font-size: 12px;
    }}

    @media (max-width: 900px) {{
      .grid, .actions {{
        grid-template-columns: 1fr;
      }}

      .status-card {{
        grid-column: span 1;
      }}

      .topbar {{
        flex-direction: column;
        align-items: flex-start;
      }}

      h1 {{
        font-size: 34px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <div class="version-pill">{version_label}</div>
      {language_switcher_html()}
    </div>

    <header class="hero">
      <div class="brand">Agrandiz <span data-i18n="app.channel">local beta</span></div>
      <h1 data-i18n="web.hero_title">Story Discovery for Apple Photos</h1>
      <p data-i18n="web.hero_subtitle">
        First scan your Photos Library. Then build dashboard and story outputs. Finally open the generated local portal.
      </p>
    </header>

    <section class="grid">
      <article class="card action-card" id="photosCacheCard">
        <div class="label" data-i18n="web.photos_cache">Photos cache</div>
        <div id="photosCacheValue" class="value warn">Checking...</div>
        <p class="card-note" data-i18n="web.cache_card_desc">
          Build or refresh the local SQLite metadata cache from Apple Photos.
        </p>
        <button class="primary card-button" id="scan" type="button">
          <span data-i18n="web.scan_photos">Scan Photos</span>
        </button>
      </article>

      <article class="card action-card" id="demoPortalCard">
        <div class="label" data-i18n="web.demo_portal">Story Dashboard</div>
        <div id="demoPortalValue" class="value warn">Checking...</div>
        <p class="card-note" data-i18n="web.portal_card_desc">
          Generate story candidates, build the dashboard, create moment galleries, and prepare the family timeline.
        </p>
        <button class="primary card-button" id="build" type="button">
          <span data-i18n="web.generate_stories">Generate Stories</span>
        </button>
      </article>

      <article class="card action-card" id="openDashboardCard">
        <div class="label" data-i18n="web.open_dashboard">Open Dashboard</div>
        <div id="openDashboardValue" class="value warn">Unavailable</div>
        <p class="card-note">
          Open the generated local dashboard and story discovery portal.
        </p>
        <button class="primary card-button" id="openPortal" type="button">
          <span data-i18n="web.open_dashboard">Open Dashboard</span>
        </button>
      </article>

      <article class="card status-card">
        <div class="label" data-i18n="web.current_status">Current status</div>
        <div class="status-row">
          <div id="statusSpinner" class="status-spinner"></div>
          <div id="status" class="value">Loading...</div>
        </div>
      </article>
    </section>

    <section class="actions">
      <button id="openFolder" type="button">
        <span data-i18n="web.open_output_folder">Open Output Folder</span>
      </button>
    </section>

    <textarea id="log" class="log" readonly></textarea>

    <section class="bottom-status">
      <div class="label" data-i18n="web.project_folder">Project folder</div>
      <code>{project_dir}</code>
    </section>

    <p class="note" data-i18n="web.permission_note">
      If Photos Library access fails, grant Full Disk Access:
      System Settings → Privacy & Security → Full Disk Access → Agrandiz
    </p>
  </div>

<script>
async function post(path) {{
  const res = await fetch(path, {{ method: "POST" }});
  return await res.json();
}}

async function getJSON(path) {{
  const res = await fetch(path);
  return await res.json();
}}

async function refresh() {{
  const status = await getJSON("/api/status");
  const log = await getJSON("/api/log");

  const busy = !!status.busy;
  const title = status.title || "";
  const normalizedTitle = title.toLowerCase();

  const isScanning =
    busy && (
      normalizedTitle.includes("scanning") ||
      normalizedTitle.includes("photos library")
    );

  const isBuilding = busy && !isScanning;

  const statusText = document.getElementById("status");
  const statusSpinner = document.getElementById("statusSpinner");

  if (statusText) {{
    if (isScanning) {{
      statusText.textContent = "Scanning Photos...";
    }} else if (isBuilding) {{
      statusText.textContent = "Working...";
    }} else {{
      statusText.textContent = title || "Ready";
    }}
  }}

  if (statusSpinner) {{
    statusSpinner.classList.toggle("is-active", busy);
  }}

  const photosValue = document.getElementById("photosCacheValue");
  const portalValue = document.getElementById("demoPortalValue");
  const openDashboardValue = document.getElementById("openDashboardValue");

  if (photosValue) {{
    if (isScanning) {{
      photosValue.textContent = "Scanning...";
      photosValue.classList.remove("ok");
      photosValue.classList.add("warn");
    }} else {{
      photosValue.textContent = status.photos_cache_ready ? "Ready" : "Not scanned yet";
      photosValue.classList.toggle("ok", !!status.photos_cache_ready);
      photosValue.classList.toggle("warn", !status.photos_cache_ready);
    }}
  }}

  if (portalValue) {{
    if (isBuilding) {{
      portalValue.textContent = "Working...";
      portalValue.classList.remove("ok");
      portalValue.classList.add("warn");
    }} else {{
      portalValue.textContent = status.portal_ready ? "Ready" : "Empty";
      portalValue.classList.toggle("ok", !!status.portal_ready);
      portalValue.classList.toggle("warn", !status.portal_ready);
    }}
  }}

  if (openDashboardValue) {{
    if (isBuilding) {{
      openDashboardValue.textContent = "Working...";
      openDashboardValue.classList.remove("ok");
      openDashboardValue.classList.add("warn");
    }} else {{
      openDashboardValue.textContent = status.portal_ready ? "Ready" : "Unavailable";
      openDashboardValue.classList.toggle("ok", !!status.portal_ready);
      openDashboardValue.classList.toggle("warn", !status.portal_ready);
    }}
  }}

  const scanButton = document.getElementById("scan");
  const buildButton = document.getElementById("build");
  const openPortalButton = document.getElementById("openPortal");
  const openFolderButton = document.getElementById("openFolder");

  if (scanButton) {{
    scanButton.disabled = busy;
  }}

  if (buildButton) {{
    buildButton.disabled = busy || !status.photos_cache_ready;
    buildButton.title = status.photos_cache_ready
      ? ""
      : "Run Scan Photos first to create the Photos cache.";
  }}

  if (openPortalButton) {{
    openPortalButton.disabled = busy || !status.portal_ready;
    openPortalButton.title = status.portal_ready
      ? ""
      : "Discover stories first to create the dashboard.";
  }}

  if (openFolderButton) {{
    openFolderButton.disabled = false;
  }}

  const logEl = document.getElementById("log");
  const oldBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 20;
  logEl.value = log.lines.join("\\n");
  if (oldBottom) {{
    logEl.scrollTop = logEl.scrollHeight;
  }}

  if (window.agrandizApplyI18n) {{
    agrandizApplyI18n();
  }}
}}

document.getElementById("scan").addEventListener("click", async () => {{
  await post("/api/scan");
  refresh();
}});

document.getElementById("build").addEventListener("click", async () => {{
  await post("/api/build");
  refresh();
}});

document.getElementById("openPortal").addEventListener("click", async () => {{
  await post("/api/open-portal");
}});

document.getElementById("openFolder").addEventListener("click", async () => {{
  await post("/api/open-folder");
}});

setInterval(refresh, 1200);
refresh();
</script>
{i18n_js()}
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            html_response(self, app_html())
            return

        if parsed.path.startswith("/cache/"):
            rel = parsed.path.lstrip("/")
            path = PROJECT_DIR / rel
            file_response(self, path, content_type_for(path))
            return

        if parsed.path.startswith("/themes/"):
            rel = parsed.path.lstrip("/")
            path = PROJECT_DIR / rel
            file_response(self, path, content_type_for(path))
            return

        if parsed.path == "/api/status":
            json_response(self, runtime_state())
            return

        if parsed.path == "/api/log":
            json_response(self, {"lines": LOG_LINES})
            return

        json_response(self, {"error": "not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/scan":
            run_async(run_scan)
            json_response(self, {"ok": True})
            return

        if parsed.path == "/api/build":
            run_async(run_pipeline)
            json_response(self, {"ok": True})
            return

        if parsed.path == "/api/open-folder":
            run_async(open_output_folder)
            json_response(self, {"ok": True})
            return

        if parsed.path == "/api/exclude":
            payload = read_request_json(self)
            data = update_excludes(payload)
            json_response(self, {"ok": True, "excludes": data})
            return


        if parsed.path == "/api/open-portal":
            run_async(open_portal)
            json_response(self, {"ok": True})
            return

        json_response(self, {"error": "not found"}, status=404)

    def log_message(self, fmt, *args):
        # Keep console clean.
        return


def find_free_port(start):
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def main():
    log(f"{app_version_string()} starting.")
    log("No Tkinter. Web UI mode.")
    log(f"Python: {sys.executable}")
    log(f"Bundled project: {bundled_project_dir()}")

    try:
        project_dir = ensure_project()
    except Exception as exc:
        log(f"Project preparation error: {exc}")
        set_status(False, "Project preparation error", str(exc))

    global CURRENT_SERVER_PORT
    port = find_free_port(PORT)
    CURRENT_SERVER_PORT = port
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"

    log(f"Opening local UI: {url}")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
