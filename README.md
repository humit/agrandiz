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

Generates Apple-style local dashboard pages:

    cache/dashboard.tr.apple.apple_icloud.html
    cache/dashboard.en.apple.apple_icloud.html
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
    cache/stories-raw.tr.apple.apple_icloud.html
    cache/stories-raw.en.apple.apple_icloud.html

### Moment Grouping

Groups near-duplicate, burst-like, or same-moment images into moment clusters.

Instead of showing five almost-identical birthday photos, Agrandiz shows one representative moment and keeps the variants available for review or future micro-sequence use.

Grouped outputs:

    cache/story_candidates_grouped.json
    cache/stories-moments.tr.apple.apple_icloud.html
    cache/stories-moments.en.apple.apple_icloud.html

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
    cache/stories.tr.apple.apple_icloud.html
    cache/stories.en.apple.apple_icloud.html

### Family Timeline

Builds a year-by-year family timeline focused on children, family, birthday, school, play, and daily-life memories.

Outputs:

    cache/family_timeline.json
    cache/family-timeline.tr.apple.apple_icloud.html
    cache/family-timeline.en.apple.apple_icloud.html

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
    │   ├── build_family_timeline.py
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

### 1. Scan Photos Library

    python scripts/scan_to_sqlite.py

Expected output:

    cache/agrandiz.sqlite

### 2. Build Dashboard

    python scripts/make_dashboard.py \
      --db cache/agrandiz.sqlite \
      --outdir cache \
      --theme apple \
      --profile apple_icloud \
      --lang both

### 3. Discover Raw Stories

    python scripts/discover_stories.py \
      --db cache/agrandiz.sqlite \
      --outdir cache \
      --config config/story_profiles/apple_icloud_default.json \
      --lang both

### 4. Group Story Moments

    python scripts/group_story_moments.py \
      --input cache/story_candidates_raw.json \
      --outdir cache \
      --lang both

### 5. Render Final Story Gallery

    python scripts/render_story_moments.py \
      --input cache/story_candidates_grouped.json \
      --exclude config/excludes.json \
      --outdir cache \
      --lang both

### 6. Build Family Timeline

    python scripts/build_family_timeline.py \
      --db cache/agrandiz.sqlite \
      --config config/family_timeline.json \
      --outdir cache \
      --lang both

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
      --outdir cache \
      --lang both

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

Agrandiz tries to make those memories visible again — safely, locally, and in a form that can become a gallery, a printed album, a family archive, or a short story worth sharing.
