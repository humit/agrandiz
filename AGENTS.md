# AGENTS.md — Agrandiz project guide for AI coding/design agents

This file gives AI coding/design agents enough project context to make safe, small, reviewable changes without rediscovering the product intent and architecture every time.

## Product vision

Agrandiz is a local-first photo memory and story curation project.

The macOS MVP uses metadata from Apple Photos through `osxphotos` and iCloud-derived photo metadata to help users discover meaningful stories inside large, noisy personal photo libraries. The core value is not merely browsing photos; it is extracting human-relevant narratives, patterns, milestones, relationships, places, objects, and recurring themes from otherwise overwhelming photo clutter.

The project should remain flexible enough to support many different story angles. “Family Timeline” and “children growing up” are important and potentially popular use cases, but they are examples, not the whole product. Another user may care most about:

- a partner, spouse, or close friend;
- a car, boat, house, workshop, or other personal object;
- a travel period or city;
- a civil society movement, school, club, or community;
- a pet;
- a creative project or work archive;
- a long-running personal transformation.

Agents must therefore avoid hard-coding product assumptions around family, children, or genealogy unless the task explicitly targets that profile. Prefer neutral concepts such as story, collection, subject, moment, memory, theme, candidate, timeline, and profile.


## Canonical product framing from the project dossier

The project dossier defines Agrandiz as a privacy-focused archive and curation service that turns meaningful stories, giftable memories, and period archives hidden inside personal photo libraries into digital and printable albums.

The central promise is:

```text
Do not just delete photos. Find the invisible stories between them and turn digital clutter into durable personal memory.
```

Core product pillars:

- Archive lightening: detect duplicate, low-value, WhatsApp-origin, screenshot, burst, low-resolution, or document-like candidates.
- Story discovery: detect recurring people, places, periods, themes, objects, events, activities, and emotional patterns.
- Durable output: produce web galleries, PDF albums, printable photo books, gift albums, collages, short videos, or digital legacy packages.

Important distinction:

```text
Agrandiz is not primarily a photo cleaner.
Agrandiz is a local-first memory curation and story discovery tool.
```

The product language should therefore emphasize review, curation, preservation, story discovery, and memory-making over deletion or cleanup.

## Platform strategy

The current MVP is macOS-focused because Apple Photos plus `osxphotos` provides a rich, practical local metadata source. The immediate implementation may reference Apple/iCloud-specific generated outputs, filenames, and builders.

However, the product horizon should remain cross-platform. Future versions may ingest photo metadata and assets from other systems such as exported Google Photos archives, Android photo libraries, NAS folders, external drives, cloud exports, or other local media catalogs.

When designing architecture or naming abstractions:

- Keep Apple/iCloud-specific logic isolated at the adapter/source layer where practical.
- Avoid naming generic concepts as if they only apply to Apple Photos.
- Prefer extensible source concepts: `photo_source`, `library_source`, `metadata_provider`, `asset_provider`, `story_profile`.
- Do not block the MVP by prematurely building full cross-platform support.
- Do not make UI copy imply that the product only works for families or only for Apple Photos unless the page is explicitly Apple/MVP-specific.


### MVP platform decision

For v0.1, the product is deliberately narrow:

```text
macOS + Apple Photos + iCloud metadata + osxphotos
```

This is a product-speed decision, not a permanent product boundary. Apple Photos currently provides unusually rich local signals through `osxphotos`, including labels, captions, faces/person clusters, moments, albums, preview paths, cloud/local availability, and aesthetic scores. Use those signals aggressively for the Mac MVP, but keep generic concepts source-neutral so that later adapters can target Google Photos exports, Android/local folders, NAS/external disks, or other media catalogs.

Do not build generic cross-platform support prematurely. Design seams for it.

## Current repository state

The `refactor/story-engine` branch has been merged into `main`. Current UI/UX work is expected to happen on a clean branch such as:

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

These filenames may still be Apple/iCloud-specific because the MVP data source is Apple Photos/iCloud. Treat them as current implementation details, not the final product taxonomy.


## Current validated data and technical findings

The first real `osxphotos` scan produced enough signal for a convincing MVP and video demo. Agents should treat these as useful constraints when designing UI copy, dashboard cards, and story discovery flows.

Known scan environment:

```text
Python 3.12.13
osxphotos 0.75.9
Photos Library: local macOS Photos library
Photos version: 10
DB Version: 5001
```

Observed library scale and availability:

```text
Total assets: 14,286
Photos: 11,465
Videos: 2,821
Cloud assets: 14,276
Local originals available: about 888
Stored only in iCloud / missing locally: about 13,398
Favorites: 94
Edited: 420
Live Photos: 1,587
Selfies: 520
Screenshots: 200
Detected faces: 17,618
Assets with persons: 7,363
Named persons: 0
AI labels: about 13,488 assets
Albums: 12
Moments: 4,216
```

Story discovery signals already observed:

```text
WhatsApp assets: 7,215
Child-labelled assets: 3,015
People-labelled assets: 7,814
Food-labelled assets: 925
Tree-labelled assets: 417
```

Important implications:

- The first real archive is heavily cloud-backed. Many strong story candidates can be discovered from metadata and preview paths before full-resolution originals are available.
- UI must distinguish `Ready now` from `Needs download` instead of failing silently when an original is iCloud-only.
- Named persons may be unavailable. Do not assume person names exist; support unnamed people, face clusters, labels, albums, moments, and user-guided enrichment.
- WhatsApp is a major source. It is both noise and story material: possible low-value media, but also a strong source for gift albums and friend/community memories.
- Location metadata may be sparse. Do not make location-based discovery a hard dependency for the first MVP.
- Preview-first UI is a key MVP strategy. Use previews for discovery/review; require full-resolution originals only for print/export.

### Apple Photos hidden signals

`osxphotos` exposes Apple Photos analysis signals that can power MVP discovery without building a heavy custom AI pipeline first:

```text
photo.score.overall
score.curation
score.behavioral
score.well_framed_subject
score.pleasant_composition
score.harmonious_color
score.interesting_subject
labels / labels_normalized
ai_caption
persons / person_info
albums / album_info
moment_info
path_derivatives / preview paths
ismissing / incloud / iscloudasset
screenshot / selfie / live_photo / burst / panorama / slow_mo / time_lapse
height / width / original_filesize / uti
```

Useful product features enabled by these signals:

- Smart Best Photos: high-score images not marked as favorites.
- Theme + Quality Albums: labels combined with aesthetic scores.
- Surprisingly Beautiful: unexpected high-score images that users forgot.
- Album Cover Candidates: high-quality, well-framed, theme-appropriate images.
- Print-worthy Selection: good score, good resolution, not screenshot, not duplicate, local/available or downloadable.
- Low-risk Review Queue: screenshot/source/score/favorite/album/missing signals combined into review candidates.
- Cloud-aware Album Flow: preview-based review first, original download only at export/print stage.

## Current UI/UX direction

The immediate UI/UX roadmap is:

1. ✅ Add the same `app-nav` used by the main stories page to `family-timeline.apple.apple_icloud.html`.
2. ✅ Add `app-nav` and i18n infrastructure to `dashboard.apple.apple_icloud.html`.
3. ✅ Bring `stories-raw.*` and `stories-moments.*` pages closer to the same nav/header structure.
4. ✅ Extract a shared app shell/template system (`agrandiz_shell.py`: `APP_NAV_CSS`, `app_nav_html`).
5. Remove `--lang` CLI argument from all renderers once every page uses in-page i18n switching (currently `stories-raw.*` and `stories-moments.*` still generate separate per-lang files).

Do not jump directly to a large shared template refactor unless explicitly requested. Prefer incremental patches.

Important: although the next UI task touches the Family Timeline page, do not reframe the whole application around family timelines. In the UI, navigation, and code abstractions, treat Family Timeline as one story profile among many possible profiles.


### Current product/output roadmap

The first product validation path is not full SaaS. The intended sequence is:

```text
1. Local read-only scan
2. SQLite metadata cache
3. Static local dashboard / gallery HTML
4. Suggested story cards and preview-first galleries
5. Web gallery output
6. Video demo + landing/waitlist validation
7. Later: local web wizard, PDF/print mockups, pilot workflows
```

Initial web pages mentioned in the dossier:

```text
Dashboard
Timeline
People / Subjects
Suggested Stories
Duplicate Review
Album Builder
Print Preview
Export
```

For the current repo, static HTML in `cache/` is acceptable for MVP/video-demo speed. Later, this may evolve into FastAPI/Flask with a local wizard.

## Product language guidelines

Prefer broad, extensible language:

```text
Stories
Moments
Memory map
Timeline
Subjects
Themes
Collections
Story candidates
Curated memories
Photo library
Source library
```

Use narrower language only when the page or profile is explicitly narrow:

```text
Family Timeline
Children growing up
Partner memories
Travel stories
Car timeline
Community archive
```

Avoid making generic UI labels too specific:

- Avoid: “Family archive dashboard” for the whole app.
- Prefer: “Story dashboard” or “Memory dashboard”.
- Avoid: “Children timeline engine” as a generic module name.
- Prefer: “story profile”, “timeline profile”, or “subject timeline”.


### Safer archive-lightening language

Because photos are emotionally sensitive, avoid destructive wording in generic UI:

```text
Avoid: Delete, Trash, Junk, Bulk delete, Remove forever
Prefer: Review, Not for Album, Low-value candidates, Archive out, Archive-light, Optimize storage, Needs review
```

Never make the product appear to automatically delete, move, upload, or rewrite the user’s photos. The default posture is recommendation plus human approval.

## Story profiles and flexibility

A useful mental model is: the engine discovers candidate moments from a photo library, then different story profiles interpret those moments through different lenses.

Examples:

```text
family_timeline       -> family growth, children, relatives, birthdays, home life
partner_story         -> spouse/partner memories, trips, anniversaries, shared places
car_story             -> vehicle ownership, repairs, trips, modifications
travel_story          -> cities, routes, landmarks, date clusters
community_archive     -> demonstrations, meetings, events, civil society activity
pet_story             -> pet growth, places, routines, companionship
creative_project      -> making-of archive, workshops, outputs, exhibitions
```

Agents should keep this profile-based flexibility in mind when proposing data models, UI labels, filters, or renderers.

## Important architectural intent

The project recently moved toward a cleaner story engine architecture. Keep that direction:

- Prefer explicit builder/rendering modules over ad-hoc generated HTML patching.
- Avoid post-processing generated HTML when the same result can be produced by the renderer/builder.
- Keep story discovery, grouping, dashboard rendering, and profile-specific timeline rendering conceptually separate unless a shared abstraction clearly reduces duplication.
- Treat `cache/*.html` and `cache/*.json` as generated output unless the maintainer explicitly says otherwise.
- Separate generic story concepts from Apple/iCloud ingestion details where practical.
- Avoid adding family-specific assumptions to generic modules.

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
- Do not infer from this nav that Family Timeline is the app’s central object; it is currently one visible page/profile.

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
5. Prefer generic keys for generic UI. Use family-specific keys only for family-specific surfaces.

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
- Rename an internal generic concept away from family-specific terminology, if the change is small and justified.

Avoid mixed patches such as:

- Nav + dashboard redesign + JSON schema change.
- i18n runtime rewrite + CSS refactor + renderer migration.
- Generated HTML manual edits without source changes.
- Product-language rewrite + ingestion refactor + UI redesign in one commit.

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

This project may involve family photos, partner photos, children’s photos, personal archive metadata, iCloud-derived filenames, local paths, location metadata, and sensitive social/community context.

Agents must not:

- Upload project files, images, metadata, or generated cache to external services unless explicitly instructed.
- Add telemetry, analytics, trackers, CDN dependencies, or remote fonts without explicit approval.
- Print sensitive local paths or personal photo metadata unnecessarily.
- Commit secrets, tokens, credentials, cookies, or raw private image files.
- Assume that detected people, places, organizations, or events are safe to expose in generic UI.

Prefer local-only tooling and static output.


Privacy-specific UX requirements:

- State that the MVP does not connect to the user’s iCloud account.
- State that photos are not uploaded to an external service.
- State that the local Photos library is analyzed read-only.
- Do not show sharing links by default for sensitive/community archives.
- For sensitive story profiles, consider face blurring, EXIF/location stripping, private archive mode, and export-time privacy warnings.

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
- Support generic story exploration, not only family archive browsing.


### Apple-feel UI direction

For the Mac MVP, the desired interface feeling is clean, calm, and Apple-adjacent:

- soft white/light gray backgrounds unless a page already has a dark visual system;
- large photo cards and generous spacing;
- rounded cards and simple hierarchy;
- few but meaningful metrics;
- calm animations, no noisy gamification;
- review-oriented language instead of alarmist cleanup warnings;
- privacy reassurance without overwhelming the user.

Recommended dashboard cards from the first real scan include:

```text
14,286 memories found
888 available on this Mac
13,398 stored only in iCloud
7,215 WhatsApp memories
3,015 child-related moments
7,814 people photos
925 food/table memories
417 tree/nature candidates
94 favorites
200 screenshots
1,587 live photos
```

Recommended initial story cards include:

```text
WhatsApp Memories
Childhood Moments
People & Family Archive
Food, Tables & Gatherings
Trees & Outdoor Days
Surprisingly Beautiful
Cloud-only Highlights
```

Keep these cards configurable and source-driven; do not bake these exact numbers into source code except in demo/sample fixtures.

## Commit message style

Use concise, imperative commit messages:

```text
Add app nav to family timeline
Extract shared app nav renderer
Add dashboard i18n scaffolding
Normalize story moments header
Clarify story profile terminology
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


## Landing/demo positioning notes

`agrandiz.org` should initially be understood as a landing page plus demo portal, not a mature hosted SaaS product.

Landing page responsibilities:

- explain the photo-overload and memory-preservation problem;
- show the video MVP/demo;
- collect waitlist interest;
- communicate local-first and privacy-first trust messages;
- make the Mac Photos/iCloud MVP scope clear.

Demo portal responsibilities:

- show a realistic local dashboard example;
- show sample story cards and preview-first gallery flows;
- eventually evolve into a local wizard/review interface.

Validation goals before paid pilots:

- waitlist signups;
- users asking “can you do this for my archive?”;
- comments/questions about privacy and trust;
- visible interest in family albums, gift albums, WhatsApp memories, web galleries, or digital legacy packages.

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
- The implementation does not make the overall product more family-specific; Family Timeline remains one profile/page among broader story curation possibilities.
