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


APP_NAME = "Agrandiz"
PORT = 8765

SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
PROJECT_DIR = SUPPORT_DIR / "project"

LOG_LINES = []
CURRENT_STATUS = {
    "busy": False,
    "title": "Ready",
    "last_error": None,
}


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


def run_command(args, title):
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

    py = app_python()

    commands = [
        (
            [py, "scripts/make_dashboard.py", "--db", "cache/agrandiz.sqlite", "--outdir", "cache", "--theme", "apple", "--profile", "apple_icloud", "--lang", "both"],
            "Building dashboard",
        ),
        (
            [py, "scripts/discover_stories.py", "--db", "cache/agrandiz.sqlite", "--outdir", "cache", "--config", "config/story_profiles/apple_icloud_default.json", "--lang", "both"],
            "Discovering stories",
        ),
        (
            [py, "scripts/group_story_moments.py", "--input", "cache/story_candidates_raw.json", "--outdir", "cache", "--lang", "both"],
            "Grouping story moments",
        ),
        (
            [py, "scripts/render_story_moments.py", "--input", "cache/story_candidates_grouped.json", "--exclude", "config/excludes.json", "--outdir", "cache", "--lang", "both"],
            "Rendering story gallery",
        ),
        (
            [py, "scripts/build_family_timeline.py", "--db", "cache/agrandiz.sqlite", "--config", "config/family_timeline.json", "--outdir", "cache", "--lang", "both"],
            "Building family timeline",
        ),
    ]

    for args, title in commands:
        ok = run_command(args, title)
        if not ok:
            return

    ensure_portal_index(ensure_project())
    log("Story discovery pipeline completed.")
    log("You can now click Open Portal.")
    set_status(False, "Ready")


def run_scan():
    if CURRENT_STATUS["busy"]:
        log("Already busy; ignoring scan request.")
        return

    log("Scan requested. This step only builds cache/agrandiz.sqlite.")
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
    index = ensure_portal_index(project_dir)

    if not index.exists():
        log("Portal could not be created.")
        return False

    webbrowser.open(index.as_uri())
    log(f"Opened portal: {index}")
    return True

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
    project_dir = PROJECT_DIR
    cache_dir = project_dir / "cache"

    dashboard_tr = cache_dir / "dashboard.tr.apple.apple_icloud.html"
    stories_tr = cache_dir / "stories.tr.apple.apple_icloud.html"

    portal_ready = (cache_dir / "index.html").exists()
    scan_ready = (cache_dir / "agrandiz.sqlite").exists()

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

    .status-card {{
      grid-column: span 3;
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

    .actions {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 20px 0;
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
      h1 {{
        font-size: 34px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div class="brand">Agrandiz <span>local beta</span></div>
      <h1>Preview-first story discovery for Apple Photos.</h1>
      <p>
        All processing runs locally on this Mac. No upload, no deletion.
        First scan your Photos Library. Then build dashboard and story outputs. Finally open the generated local portal.
      </p>
    </header>

    <section class="grid">
      <article class="card">
        <div class="label">Photos cache</div>
        <div class="value {'ok' if scan_ready else 'warn'}">{'Ready' if scan_ready else 'Not scanned yet'}</div>
      </article>

      <article class="card">
        <div class="label">Demo portal</div>
        <div class="value {'ok' if portal_ready else 'warn'}">{'Ready' if portal_ready else 'Not built yet'}</div>
      </article>

      <article class="card">
        <div class="label">Project folder</div>
        <div class="value" style="font-size: 13px; word-break: break-all;">{project_dir}</div>
      </article>

      <article class="card status-card">
        <div class="label">Current status</div>
        <div id="status" class="value">Loading...</div>
      </article>
    </section>

    <section class="actions">
      <button class="primary" id="scan">1. Scan Only</button>
      <button class="primary" id="build">2. Build Outputs</button>
      <button id="openPortal">3. Open Portal</button>
      <button id="openFolder">Open Output Folder</button>
    </section>

    <textarea id="log" class="log" readonly></textarea>

    <p class="note">
      If Photos Library access fails, grant Full Disk Access:
      <code>System Settings → Privacy & Security → Full Disk Access → Agrandiz</code>
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

  document.getElementById("status").textContent =
    status.busy ? "Running: " + status.title : status.title;

  const buttons = document.querySelectorAll("button");
  buttons.forEach(b => {{
    if (["openPortal", "openFolder"].includes(b.id)) return;
    b.disabled = status.busy;
  }});

  const logEl = document.getElementById("log");
  const oldBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 20;
  logEl.value = log.lines.join("\\n");
  if (oldBottom) {{
    logEl.scrollTop = logEl.scrollHeight;
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
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            html_response(self, app_html())
            return

        if parsed.path == "/api/status":
            json_response(self, CURRENT_STATUS)
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
    log("Agrandiz local beta starting.")
    log("No Tkinter. Web UI mode.")
    log(f"Python: {sys.executable}")
    log(f"Bundled project: {bundled_project_dir()}")

    try:
        project_dir = ensure_project()
        ensure_portal_index(project_dir)
    except Exception as exc:
        log(f"Project preparation error: {exc}")
        set_status(False, "Project preparation error", str(exc))

    port = find_free_port(PORT)
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
