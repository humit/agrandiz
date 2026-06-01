# AGENTS.md — Agrandiz project guide for AI coding agents

This file gives AI coding/design agents enough project context to make safe, small, reviewable changes without rediscovering the architecture every time.

## Project overview

Agrandiz is a local-first photo/story curation project. It generates static HTML pages from cached photo metadata and preview assets, with an emphasis on family archive exploration, story discovery, and curated visual timelines.

The current UI/UX work is happening after the `refactor/story-engine` branch was merged into `main`. New UI work should start from a clean branch such as:

```bash
git checkout uiux/app-shell-nav
```

Current generated output examples include:

```text
cache/dashboard.apple.apple_icloud.html
cache/stories.apple.apple_icloud.html
cache/family-timeline.apple.apple_icloud.html
cache/stories-raw.tr.apple.apple_icloud.html
cache/stories-raw.en.apple.apple_icloud.html
cache/stories-moments.tr.apple.apple_icloud.html
cache/stories-moments.en.apple.apple_icloud.html
cache/dashboard_data.json
cache/family_timeline.json
cache/story_candidates.json
cache/story_candidates_raw.json
cache/story_candidates_grouped.json
```

## Current UI/UX direction

The immediate UI/UX roadmap is:

1. Add the same `app-nav` used by the main stories page to `family-timeline.apple.apple_icloud.html`.
2. Add `app-nav` and i18n infrastructure to `dashboard.apple.apple_icloud.html`.
3. Bring `stories-raw.*` and `stories-moments.*` pages closer to the same nav/header structure.
4. Then extract a shared app shell/template system.

Do not jump directly to a large shared template refactor unless explicitly requested. Prefer incremental patches.

## Important architectural intent

The project recently moved toward a cleaner story engine architecture. Keep that direction:

- Prefer explicit builder/rendering modules over ad-hoc generated HTML patching.
- Avoid post-processing generated HTML when the same result can be produced by the renderer/builder.
- Keep story discovery, grouping, dashboard rendering, and family timeline rendering conceptually separate unless a shared abstraction clearly reduces duplication.
- Treat `cache/*.html` and `cache/*.json` as generated output unless the maintainer explicitly says otherwise.

## Generated output policy

Before editing generated files directly, inspect how they are produced.

Preferred workflow:

```bash
git status
grep -R "family-timeline\|stories.apple\|app-nav\|data-i18n" -n . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=node_modules \
  | head -120
```

Then patch the source renderer/builder and regenerate the cache output using the project’s normal command.

If the correct command is unclear, search first:

```bash
find . -maxdepth 3 -type f | sort | grep -E 'story|render|build|dashboard|timeline|Makefile|README'
grep -R "if __name__ == .__main__.\|argparse\|story_render\|dashboard" -n . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=node_modules \
  | head -120
```

## UI conventions discovered so far

The main stories page already has the target nav pattern:

```html
<nav class="app-nav" aria-label="Agrandiz">
  <a href="dashboard.apple.apple_icloud.html" data-i18n="nav.dashboard">Dashboard</a>
  <a href="stories.apple.apple_icloud.html" aria-current="page" data-i18n="nav.stories">Stories</a>
  <a href="family-timeline.apple.apple_icloud.html" data-i18n="nav.family_timeline">Family Timeline</a>
</nav>
```

When adding this nav to another page:

- Use `aria-current="page"` only for the active page.
- Keep link targets relative and static.
- Preserve existing visual identity unless the task explicitly asks for redesign.
- Prefer the same class names: `brand`, `app-nav`, `hero`, `toolbar`, etc., where appropriate.
- Keep i18n keys stable and semantic: `nav.dashboard`, `nav.stories`, `nav.family_timeline`.

## i18n conventions

Existing newer pages use attributes such as:

```html
data-i18n="..."
data-i18n-title="..."
data-i18n-placeholder="..."
data-i18n-prefix="..."
```

Before adding new i18n behavior:

1. Search existing translation dictionaries and JS helper functions.
2. Reuse existing key naming style.
3. Do not introduce a second incompatible i18n runtime.
4. For UI-only patches, avoid changing translation behavior unless required.

Useful checks:

```bash
grep -R "const translations\|data-i18n\|applyI18n\|language" -n . \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=node_modules \
  | head -160
```

## Patch discipline

Make one conceptual change per patch.

Good patch examples:

- Add `app-nav` to family timeline.
- Extract `render_app_nav(active_page)` helper.
- Add dashboard i18n dictionary.
- Normalize stories-moments header structure.

Avoid mixed patches such as:

- Nav + dashboard redesign + JSON schema change.
- i18n runtime rewrite + CSS refactor + renderer migration.
- Generated HTML manual edits without source changes.

Before finishing, always show:

```bash
git diff --stat
git diff --check
git status --short
```

If possible, run the generator and relevant smoke checks.

## Suggested smoke checks

After UI generator changes:

```bash
python story_render.py
```

If this command is not valid in the current branch, identify the correct builder command before guessing.

Then inspect generated output:

```bash
grep -n "app-nav\|aria-current=\"page\"\|data-i18n=\"nav" cache/*.html
```

For the first UI/UX patch, expected result:

- `cache/stories.apple.apple_icloud.html` keeps its existing nav.
- `cache/family-timeline.apple.apple_icloud.html` gains the same nav.
- Family timeline marks itself as current.
- Dashboard may remain unchanged until the next patch.

## Privacy and data safety

This project may involve family photos, personal archive metadata, iCloud-derived filenames, and private local paths.

Agents must not:

- Upload project files, images, metadata, or generated cache to external services unless explicitly instructed.
- Add telemetry, analytics, trackers, CDN dependencies, or remote fonts without explicit approval.
- Print sensitive local paths or personal photo metadata unnecessarily.
- Commit secrets, tokens, credentials, cookies, or raw private image files.

Prefer local-only tooling and static output.

## Dependency policy

Before adding a dependency, justify why existing Python/HTML/CSS/JS cannot reasonably do the job.

Avoid dependencies for:

- Simple nav rendering.
- Basic i18n attribute replacement.
- Static HTML layout tweaks.
- Small CSS refactors.

If a dependency is necessary, update the appropriate dependency file and document the command needed to install it.

## HTML/CSS design principles

For current UI/UX work:

- Keep pages static and fast.
- Use progressive enhancement; the page should remain readable even if JS fails.
- Preserve accessibility basics: semantic headings, `aria-current`, meaningful button text, keyboard-friendly controls.
- Prefer responsive, fluid layouts over fixed pixel assumptions.
- Avoid over-styling thumbnails in a way that hides the actual photo content.
- Keep dark/light visual contrast readable.

## Commit message style

Use concise, imperative commit messages:

```text
Add app nav to family timeline
Extract shared app nav renderer
Add dashboard i18n scaffolding
Normalize story moments header
```

## Handoff format for agents

When an agent finishes a change, it should report:

1. What changed.
2. Which files changed.
3. Which commands were run.
4. Whether generated output was regenerated.
5. Any known limitations or follow-up work.

Example:

```text
Changed:
- Added render_app_nav(active_page) helper.
- Inserted app-nav into family timeline header.
- Regenerated cache/family-timeline.apple.apple_icloud.html.

Validated:
- python story_render.py
- git diff --check
- grep -n "app-nav" cache/family-timeline.apple.apple_icloud.html

Follow-up:
- Dashboard still needs app-nav + i18n scaffolding.
```

## Current next recommended task

Start with a small patch:

```text
Add the existing stories page app-nav to the family timeline page via the source renderer, not by manually editing generated HTML.
```

Acceptance criteria:

- Family timeline page has the same nav links as stories page.
- Active page is marked with `aria-current="page"`.
- Existing family timeline title, stats, language selector, and content remain intact.
- No dashboard or stories-raw/stories-moments behavior changes in this patch unless required by shared helper extraction.
