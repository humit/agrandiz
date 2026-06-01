# Agrandiz

**Agrandiz** is a local-first Mac application for discovering meaningful stories inside large Apple Photos / iCloud photo libraries.

It helps turn forgotten photo archives into curated story candidates, family timelines, local web galleries, and future album or short-video outputs — without uploading photos anywhere.

Agrandiz is currently an early local beta.

---

## What Agrandiz Does

Modern photo libraries are huge. They contain family memories, travel moments, children growing up, pets, meals, screenshots, memes, WhatsApp images, duplicates, and thousands of images nobody ever revisits.

Agrandiz scans an Apple Photos library locally and creates:

- A local dashboard summarizing the archive
- Story candidates such as family, children, pets, travel, outdoors, food, WhatsApp highlights, and surprisingly beautiful photos
- Moment-based story galleries with near-duplicate grouping
- A family timeline showing children’s growth across years
- Local preview galleries that work without downloading all iCloud originals
- JSON data contracts for future UI, album, reel, or print workflows

The current MVP focuses on **Apple Photos / iCloud on macOS**.

---

## Core Product Idea

Agrandiz follows a **preview-first, original-on-demand** workflow.

Most iCloud Photos libraries keep lightweight preview/derivative images locally even when the full-resolution originals are stored in iCloud. Agrandiz uses these local previews, Apple Photos metadata, AI labels, captions, and aesthetic scores to discover meaningful story candidates first.

Only later, when a user chooses a story or album candidate, full-resolution originals may need to be downloaded.

This means the user does **not** need to download their entire iCloud photo archive before discovering what is worth keeping, sharing, printing, or turning into a story.

---

## Privacy Model

Agrandiz is designed as a local-first tool.

Current beta behavior:

- No cloud upload
- No account login
- No image deletion
- No automatic modification of the Photos library
- Processing happens locally on the Mac
- Generated outputs are stored under the user’s local Application Support directory when running the app bundle

The app reads the Apple Photos library metadata and local preview/original paths through local tools.

---

## Current Features

### Local Photos Scan

Scans the Apple Photos library and creates a local SQLite cache:

    cache/agrandiz.sqlite

The scan includes metadata such as:

- Asset UUID
- Filename
- Date
- Local/iCloud availability
- Preview path
- Albums
- Labels
- Captions
- Apple Photos scores
- Media type
- Favorite status
- Screenshot / Live Photo flags

### Dashboard

Generates an Apple-style local dashboard page:

    cache/dashboard.apple.apple_icloud.html
    cache/dashboard_data.json

### Story Discovery

Finds story candidates using configurable story profiles.

Current story categories include:

- Childhood moments
- Pets
- Fishing, sea, and water stories
- Outdoor, camping, and roads
- Travel and place memory
- Tables and gatherings
- Pandemic days
- WhatsApp highlights
- Surprisingly beautiful photos

Raw discovery outputs:

    cache/story_candidates_raw.json
    cache/stories-raw.apple.apple_icloud.html

### Moment Grouping

Groups near-duplicate, burst-like, or same-moment images into moment clusters.

Instead of showing five almost-identical birthday photos, Agrandiz shows one representative moment and keeps the variants available for review or future micro-sequence use.

Grouped outputs:

    cache/story_candidates_grouped.json
    cache/stories-moments.apple.apple_icloud.html

### Curatable Story Gallery

Renders the final story gallery with:

- Full-image thumbnails using object-fit: contain
- Moment badges
- Grouped variants
- Hover/touch micro-sequences
- Exclude buttons
- Local curation JSON

Final story outputs:

    cache/story_candidates.json
    cache/stories.apple.apple_icloud.html

### Family Timeline

Builds a year-by-year family timeline focused on children, family, birthday, school, play, and daily-life memories.

Outputs:

    cache/family_timeline.json
    cache/family-timeline.apple.apple_icloud.html

### Local Web UI

The macOS app launches a local web UI instead of a native GUI.

The UI runs on localhost:

    http://127.0.0.1:<port>/

From the web UI, the user can:

1. Scan Photos Library
2. Build Outputs
3. Open Portal
4. Open Output Folder

---

## Repository Structure

    .
    ├── VERSION.json
    ├── app/
    │   └── agrandiz_gui.py
    ├── config/
    │   ├── excludes.json
    │   ├── family_timeline.json
    │   └── story_profiles/
    │       └── apple_icloud_default.json
    ├── scripts/
    │   ├── agrandiz_version.py
    │   ├── build_dmg.sh
    │   ├── story_builder.py
    │   ├── build_macos_app.sh
    │   ├── discover_stories.py
    │   ├── group_story_moments.py
    │   ├── make_dashboard.py
    │   ├── render_story_moments.py
    │   └── scan_to_sqlite.py
    ├── themes/
    │   └── apple.css
    ├── requirements-macos-app.txt
    └── README.md

Generated files are written under cache/ during development and under the user’s Application Support directory when running the app bundle.

---

## Requirements

Current beta target:

- macOS
- Apple Photos library
- Python 3.12 recommended
- osxphotos
- Pillow
- imagehash

Install dependencies in a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -r requirements-macos-app.txt

---

## Development Workflow

The pipeline reads Apple Photos metadata through `osxphotos` and a local SQLite cache,
then produces static HTML galleries and JSON data contracts.
All steps run locally; no cloud upload or Apple Photos modification occurs.

The five canonical HTML outputs are:

    cache/dashboard.apple.apple_icloud.html
    cache/stories.apple.apple_icloud.html
    cache/stories-raw.apple.apple_icloud.html
    cache/stories-moments.apple.apple_icloud.html
    cache/family-timeline.apple.apple_icloud.html

All pages share a navigation shell (`scripts/agrandiz_shell.py`) and in-page
language switching (`scripts/agrandiz_i18n.py`). Language is selected at runtime
in the browser; a separate per-language HTML file is not generated.

---

### 1. Prepare or refresh the local metadata cache

**What it does:** Reads the Apple Photos library through `osxphotos` and writes
every asset's metadata to a local SQLite database. This is the only step that
touches Apple Photos directly.

**Inputs:** The default Apple Photos library on the current Mac user account.

**Output:**

    cache/agrandiz.sqlite

**When to run:** Once before the first build, and again whenever the Photos
library has changed significantly (new imports, face tags, albums, etc.).

    python scripts/scan_to_sqlite.py

**Verify:** The file `cache/agrandiz.sqlite` exists and has a non-zero size.

---

### 2. Discover story candidates

**What it does:** Queries the SQLite cache against configurable story profiles
(e.g. childhood moments, pets, travel, WhatsApp highlights). Scores candidates,
removes near-duplicates, and applies cross-story diversity. Produces raw
story candidate data and a developer-facing gallery for inspection.

**Inputs:**
- `cache/agrandiz.sqlite`
- `config/story_profiles/apple_icloud_default.json`

**Outputs:**

    cache/story_candidates_raw.json
    cache/stories-raw.apple.apple_icloud.html

    python scripts/discover_stories.py \
      --db cache/agrandiz.sqlite \
      --outdir cache \
      --config config/story_profiles/apple_icloud_default.json

**Verify:** `stories-raw.apple.apple_icloud.html` opens in a browser and shows
story sections with photo thumbnails.

---

### 3. Group story moments and render the moments gallery

**What it does:** Takes the raw story candidates and clusters near-duplicate,
burst-like, and same-moment photos. Each cluster is reduced to one representative
image, with variants kept for hover micro-sequences. Produces a moments-grouped
gallery for review before final curation.

**Inputs:** `cache/story_candidates_raw.json`

**Outputs:**

    cache/story_candidates_grouped.json
    cache/stories-moments.apple.apple_icloud.html

    python scripts/group_story_moments.py \
      --input cache/story_candidates_raw.json \
      --outdir cache

**Verify:** `stories-moments.apple.apple_icloud.html` shows moment cards with
variant counts where applicable.

---

### 4. Render the final story gallery

**What it does:** Applies the active exclusion list to the grouped candidates and
renders the final curatable story gallery. This is the primary output users
interact with — it includes exclude buttons, hover micro-sequences, and full-image
thumbnails. It also writes the clean story candidates JSON used by downstream
workflows.

**Inputs:**
- `cache/story_candidates_grouped.json`
- `config/excludes.json` (persistent user exclusions; safe if empty)

**Outputs:**

    cache/story_candidates.json
    cache/stories.apple.apple_icloud.html

    python scripts/render_story_moments.py \
      --input cache/story_candidates_grouped.json \
      --exclude config/excludes.json \
      --outdir cache

**Verify:** `stories.apple.apple_icloud.html` shows the curated gallery with
exclude controls. If a moment was previously excluded via the browser and the JSON
was saved to `config/excludes.json`, it should be absent here.

---

### 5. Build the dashboard

**What it does:** Queries the SQLite cache for archive-level metrics (total
assets, local vs. iCloud availability, top labels, suggested story types) and
renders the main dashboard. The dashboard links to all other generated outputs.

**Inputs:** `cache/agrandiz.sqlite`

**Outputs:**

    cache/dashboard.apple.apple_icloud.html
    cache/dashboard_data.json

    python scripts/make_dashboard.py \
      --db cache/agrandiz.sqlite \
      --outdir cache \
      --theme apple \
      --profile apple_icloud

**Verify:** `dashboard.apple.apple_icloud.html` shows archive metrics and portal
cards linking to the story gallery and family timeline.

---

### 6. Build the family timeline

**What it does:** Runs a dedicated story profile (`family_timeline.json`) that
filters for child, family, birthday, school, play, and daily-life moments. Groups
them by year and renders a year-by-year memory timeline. This is one story profile
among many; the same `story_builder.py` engine can run other profiles.

**Inputs:**
- `cache/agrandiz.sqlite`
- `config/family_timeline.json`

**Outputs:**

    cache/family_timeline.json
    cache/family-timeline.apple.apple_icloud.html

    python scripts/story_builder.py \
      --db cache/agrandiz.sqlite \
      --config config/family_timeline.json \
      --outdir cache

**Fast iteration mode:** Pass `--fast` to cap candidates and moments at a lower
limit. Use this for layout and UI work when you do not need to scan the full
library. A full run on a large library can take several minutes.

    python scripts/story_builder.py \
      --db cache/agrandiz.sqlite \
      --config config/family_timeline.json \
      --outdir cache \
      --fast

**Verify:** `family-timeline.apple.apple_icloud.html` shows year sections with
moment cards. The page title and subtitle are family-specific (driven by the
`family.page_title` and `family.subtitle` locale keys).

---

### 7. Full regeneration and packaging

**What it does:** Performs a clean end-to-end regeneration: preserves the SQLite
cache, wipes and rebuilds `cache/`, runs the full pipeline in order, runs a
sanity check asserting the five canonical HTML files exist and no stale
per-language files are present, then packs all HTML and JSON into a timestamped
tarball.

    bash dev-regenerate-cache-and-pack.sh

**Sanity check — canonical files that must be present:**

    cache/dashboard.apple.apple_icloud.html
    cache/stories.apple.apple_icloud.html
    cache/stories-raw.apple.apple_icloud.html
    cache/stories-moments.apple.apple_icloud.html
    cache/family-timeline.apple.apple_icloud.html

**Stale files that must be absent after a clean run:**

    cache/stories-raw.tr.apple.apple_icloud.html
    cache/stories-raw.en.apple.apple_icloud.html
    cache/stories-moments.tr.apple.apple_icloud.html
    cache/stories-moments.en.apple.apple_icloud.html

The script exits non-zero if any canonical file is missing or any stale file is
present. The tarball is written to `/tmp/agrandiz-generated-html-<timestamp>.tar.gz`.

---

### 8. Excluding false positives

When a story moment should be permanently excluded, use the exclude button in
`stories.apple.apple_icloud.html`. Copy the generated JSON from the browser panel
into `config/excludes.json`, then re-run step 4:

    python scripts/render_story_moments.py \
      --input cache/story_candidates_grouped.json \
      --exclude config/excludes.json \
      --outdir cache

---

## Building the macOS App

Build the local beta app bundle:

    scripts/build_macos_app.sh

Run it:

    open dist/Agrandiz.app

Build the DMG:

    scripts/build_dmg.sh

Expected output:

    dist/Agrandiz-beta.dmg

---

## macOS Permissions

If Agrandiz cannot access the Photos library, grant Full Disk Access:

    System Settings
    → Privacy & Security
    → Full Disk Access
    → Add Agrandiz.app

The local web UI may trigger a macOS Local Network permission prompt because the app starts a local HTTP server. Agrandiz only uses localhost for the current beta.

---

## Versioning

Agrandiz uses a shared version file:

    VERSION.json

All CLI scripts and the local web UI display the current version.

Example:

    Agrandiz 0.1.7 beta

A Git pre-commit hook can automatically bump the patch version on each commit.

Enable hooks:

    git config core.hooksPath .githooks

---

## Excluding False Positives

The final story gallery includes Exclude buttons.

When a user excludes a moment, the browser generates an exclude JSON block. To make exclusions persistent, save that JSON into:

    config/excludes.json

Then re-render:

    python scripts/render_story_moments.py \
      --input cache/story_candidates_grouped.json \
      --exclude config/excludes.json \
      --outdir cache

---

## Current Limitations

Agrandiz is still an early beta.

Known limitations:

- Only Apple Photos / iCloud on macOS is supported
- Person recognition is not yet based on named Apple Photos people
- iCloud full-resolution original download is not yet automated as a polished workflow
- Some false positives may still appear in story candidates
- Story profiles are heuristic and config-driven, not fully personalized yet
- The macOS app is not yet signed and notarized for public distribution
- Generated outputs are local static HTML, not a full production SaaS UI

---

## Planned Improvements

Possible next steps:

- Better person-aware family timelines
- Birthdate-aware child age labels
- Story-specific export packages
- Print album mockups
- Reel / Shorts generation plans
- Original-on-demand download workflow
- Google Photos support
- Windows / local folder support
- Signed and notarized macOS beta distribution
- More polished onboarding and permissions handling

---

## Project Philosophy

Agrandiz is built around a simple observation:

Most people have thousands of meaningful photos, but very few of those memories are ever revisited.

Agrandiz tries to make those memories visible again — safely, locally, and in a form that can become a gallery, a printed album, a personal memory archive, or a short story worth sharing.
