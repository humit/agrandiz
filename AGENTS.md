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

## Platform strategy

The current MVP is macOS-focused because Apple Photos plus `osxphotos` provides a rich, practical local metadata source. The immediate implementation may reference Apple/iCloud-specific generated outputs, filenames, and builders.

However, the product horizon should remain cross-platform. Future versions may ingest photo metadata and assets from other systems such as exported Google Photos archives, Android photo libraries, NAS folders, external drives, cloud exports, or other local media catalogs.

When designing architecture or naming abstractions:

- Keep Apple/iCloud-specific logic isolated at the adapter/source layer where practical.
- Avoid naming generic concepts as if they only apply to Apple Photos.
- Prefer extensible source concepts: `photo_source`, `library_source`, `metadata_provider`, `asset_provider`, `story_profile`.
- Do not block the MVP by prematurely building full cross-platform support.
- Do not make UI copy imply that the product only works for families or only for Apple Photos unless the page is explicitly Apple/MVP-specific.

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

## Current UI/UX direction

The immediate UI/UX roadmap is:

1. Add the same `app-nav` used by the main stories page to `family-timeline.apple.apple_icloud.html`.
2. Add `app-nav` and i18n infrastructure to `dashboard.apple.apple_icloud.html`.
3. Bring `stories-raw.*` and `stories-moments.*` pages closer to the same nav/header structure.
4. Then extract a shared app shell/template system.

Do not jump directly to a large shared template refactor unless explicitly requested. Prefer incremental patches.

Important: although the next UI task touches the Family Timeline page, do not reframe the whole application around family timelines. In the UI, navigation, and code abstractions, treat Family Timeline as one story profile among many possible profiles.

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
