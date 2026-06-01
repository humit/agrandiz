# Agrandiz — Product Positioning Notes

This document records competitor-aware positioning research and the decisions made for
dashboard brand copy and shared navigation wording.

It is a living document. Update it when decisions are finalized or reversed.

---

## Current positioning hypothesis

Agrandiz is a local-first story discovery and curation layer for existing photo libraries.
It complements Apple Photos rather than replacing it.
It uses Apple Photos / osxphotos metadata in the macOS MVP.
It surfaces editable story candidates from photo clutter.
It should not be framed only as a family archive or family timeline product.

---

## Competitor matrix

| Product | Primary job | Privacy model | Language owned | Story/narrative claim |
|---|---|---|---|---|
| Apple Photos / Memories / Apple Intelligence | Sync + automatic memory creation | On-device / Private Cloud | "Memories", "moments", "narrative arc", "chapters" | Yes — opaque AI generates storylines |
| Google Photos / Ask Photos | Backup + AI natural-language search | Cloud (privacy concerns) | "Rediscover", "memories", natural-language search | Partial — search framing, not curation |
| Mylio Photos | Local-first sync/backup without cloud | Strong, device-local | "Scattered memories", "lasting legacy", "whole family" | No — organiser framing |
| Immich | Self-hosted Google Photos alternative | Very strong, self-hosted | "Control", "self-hosted", "privacy" | No |
| PhotoPrism | Self-hosted AI tagging and search | Very strong, self-hosted | "Organised", "accessible", "bring back memories" | No |
| Excire Foto | AI keywording and semantic search | Local, no subscription | "Never drown in photos", "preserve memories" | No — search framing |
| Peakto | Multi-app meta-cataloger (Apple Photos + Lightroom + others) | Local, macOS only | "High-altitude view", "AI media organiser" | No — cataloging framing |
| Adobe Lightroom | Professional DAM and editing | Subscription / Adobe cloud | "Organise", "creative workflow" | No — professional tool |
| Narrative.so | AI culling and editing for photographers | Local | "Speed and clarity", "creative work only you can do" | No — workflow tool |
| Slidebox / HashPhotos | Camera roll declutter | Device-local | "Swipe to organise" | No |
| Mimeo Arlo / Chatbooks | Photo book creation with AI layout | Cloud | "Storytelling Engine", "narrative-driven sequences" | Yes — but output framing, not discovery |

---

## Language ownership map

**"Memories"** — Owned by Apple and Google. Used constantly and specifically.
Agrandiz should not lead with "memories" as a primary term.

**"Stories"** — Used loosely by Apple Intelligence ("storyline"), StoryRoll, Storify, Chatbooks,
Mimeo Arlo. None own it as a category for a curation tool — they use it for output
(slideshow, photo book). **"Story discovery"** as a category name is unclaimed.

**"Archive"** — Used by Mylio, PhotoPrism, Excire. Generic and neutral.
Acceptable for Agrandiz if not paired with "family".

**"Organise"** — Deeply owned by Lightroom, Mylio, Excire, HashPhotos. Commodity language.
Agrandiz should not compete on this word.

**"Local-first" / "Private"** — Owned by Mylio, Immich, PhotoPrism. Necessary to assert but
not sufficient to differentiate alone.

**"Curation"** — Lightly used by Mixbook, Narrative. Not specifically claimed in the personal
photo library space. Available.

**"Companion layer"** — Peakto implicitly uses this framing. Not phrased this way by anyone.
Available and accurate for Agrandiz.

---

## Validated unmet needs

### 1. Volume paralysis — "a seven-year memory pit"

> "Every photo is a reminder of both the extent to which I have failed and the enormity of
> trying to dig myself out." — Lucie's List
> "The task in its entirety is just so MUCH."

Users with large libraries do not need better search. They need a starting point — something
that tells them what is worth looking at before they begin.

### 2. Opaque automatic memories frustrate users

Apple and Google Memories repeat the same photos, resist meaningful editing, and sometimes
surface painful or inappropriate content. Google paused the Ask Photos rollout in June 2025
amid privacy backlash. Apple Intelligence creates memory movies from text prompts but the
curation logic remains invisible to the user.

### 3. "Having the photos is less important than what I do with them"

> "What the f*ck are you supposed to DO with all the pictures?" — Lucie's List

The real job is not organising or finding. It is making memories usable and meaningful.
No existing tool addresses this except output-focused services (photo books, slideshows) —
and those skip the curation step entirely.

### 4. Privacy-first tools are too technical for mainstream users

Immich and PhotoPrism require Docker, a home server, and technical confidence. Mylio is
closer to mainstream but still complex. There is no polished, local-first story discovery
tool for non-technical Mac users who already use Apple Photos.

### 5. Family is the default framing but not the only real use case

Virtually every competitor defaults to family. Yet photo libraries contain travel memories,
pet histories, hobby projects, community events, creative work, seasonal rituals, and
personal milestones — none of which are family-timeline material. This is an unaddressed
segment.

---

## Differentiation opportunities

| Opportunity | Agrandiz positioning | Nearest competitor | Gap |
|---|---|---|---|
| Explainable story candidates | Profile-driven, metadata-based, human-reviewable | Apple / Google AI Memories | Those are opaque; Agrandiz shows why a candidate was found |
| Companion layer over Apple Photos | Reads osxphotos metadata, no replacement | Peakto | Peakto catalogs and searches; Agrandiz discovers and curates narrative |
| Profile-based story types beyond family | Pets, travel, gatherings, pandemic days, etc. | None | No competitor addresses non-family profiles explicitly |
| Preview-first, no download required | Uses local preview cache before downloading originals | None | Works on large iCloud libraries without full sync — unique |
| Output-oriented curation | Web galleries, print albums, reel candidates | Mimeo Arlo, Chatbooks | Those start from output; Agrandiz starts from discovery |
| Editable, non-opaque | User reviews, excludes, and curates candidates | Apple / Google Memories | Memories are not editable; Agrandiz gives user the controls |

---

## Positioning risks

| Risk | Detail |
|---|---|
| "Local-first" is commoditised | Mylio, Immich, PhotoPrism all lead with this. Necessary but not differentiating alone. |
| "Privacy" is table stakes | Every self-hosted tool leads with privacy. Assert it; do not lead with it. |
| "AI-powered" is overused and increasingly mistrusted | Ask Photos backlash; Apple AI randomness complaints. Frame as "explainable suggestions" or "metadata-driven" rather than "AI". |
| "Family archive" in brand_tag | Directly contradicts flexible product framing. Appears on every user's first dashboard view. |
| Risk of being perceived as too technical | If marketed like Immich or PhotoPrism, mainstream users will assume self-hosting is required. "Local-first" must be paired with "simple". |
| "Story / Narrative" overlap with Apple | Apple now says "crafts a storyline with chapters and a narrative arc." Agrandiz's "story discovery" framing must make the human-curation difference visible. |

---

## Tagline candidates

Ranked by differentiation strength and fit with the actual product.

### Tier 1 — Recommended

| English | Turkish |
|---|---|
| "Find the stories buried in your photo library." | "Fotoğraf kitaplığındaki hikâyeleri bul." |
| "Your photo archive, made into stories." | "Fotoğraf arşivinin hikâyeleri." |
| "Story discovery for your photo library." | "Fotoğraf kitaplığın için hikâye keşfi." |

### Tier 2 — Strong alternates

| English | Turkish |
|---|---|
| "Make your photo archive visible." | "Fotoğraf arşivini görünür kıl." |
| "Turn photo clutter into curated stories." | "Fotoğraf kalabalığını özenle seçilmiş hikâyelere dönüştür." |
| "The story layer your photo library is missing." | "Fotoğraf kitaplığının eksik hikâye katmanı." |

### Tier 3 — Sub-copy candidates (not primary tagline)

| English | Turkish |
|---|---|
| "Curate, don't just store." | "Sadece depolama, kürasyona geç." |
| "Your memories deserve more than a scroll." | "Anıların yalnızca kaydırılmayı hak etmiyor." |

---

## Pending decisions

### Decision A — Dashboard brand_tag

Used in `scripts/make_dashboard.py` TRANSLATIONS dict.
Displayed on the main dashboard header, visible on every user's first view.

**Current:**
- EN: `"Make your family archive visible"`
- TR: `"Aile arşivinizi görünür hale getirin"`

**Candidate (minimum change — one word swap):**
- EN: `"Make your photo archive visible"`
- TR: `"Fotoğraf arşivini görünür hale getirin"`

**Candidate (stronger positioning signal):**
- EN: `"Find the stories in your photo archive"`
- TR: `"Fotoğraf arşivinizdeki hikâyeleri bul"`

**Status: PENDING — awaiting product decision**

---

### Decision B — Shared navigation label

Used in `scripts/agrandiz_shell.py` `app_nav_html()`.
The `nav.family_timeline` locale key is used for the nav link across all five pages.
The family timeline page and profile remain unchanged — only the nav label changes.

**Constraint:** Do not rename routes, filenames, active keys (`active="family_timeline"`),
profile IDs, or the page-level heading. This is a nav label change only.

**Current:**
- `locales/en.json` `nav.family_timeline`: `"Family Timeline"`
- `locales/tr.json` `nav.family_timeline`: `"Aile Zaman Çizelgesi"`

**Candidate:**
- EN: `"Timeline"` (generic, future-proof, still links to the family timeline page today)
- TR: `"Zaman Çizelgesi"`

**Rationale:** Having "Family Timeline" as one of three primary nav items across every page
positions family timeline as a core app feature equivalent to Dashboard and Stories, rather
than as one profile among many. "Timeline" is accurate, generic, and will not need to change
when additional profile pages are added.

**Status: PENDING — awaiting product decision**

---

## Research sources

- Apple Intelligence in Photos — Apple Support (2024–2025)
- Google Photos Ask Button — WebProNews (2025)
- Google Paused Ask Photos rollout — Droid Life (June 2025)
- Mylio Photos homepage — mylio.com
- Peakto — Fstoppers review (2025)
- Excire Foto 2025 homepage — excire.com
- PhotoPrism Features — photoprism.app
- Immich GitHub — github.com/immich-app/immich
- Narrative.so positioning — narrative.so
- Mimeo Arlo announcement — PR Newswire (2025)
- Managing Our Digital Photo Overload — Lucie's List
- Apple's New Photos App Sucks (2024) — US Mobile
