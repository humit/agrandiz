#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

CACHE_DIR="${CACHE_DIR:-cache}"
DB_PATH="${DB_PATH:-$CACHE_DIR/agrandiz.sqlite}"
KEEP_DIR="${KEEP_DIR:-/tmp/agrandiz-cache-keep}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_ARCHIVE="${OUT_ARCHIVE:-/tmp/agrandiz-generated-html-${STAMP}.tar.gz}"

echo "== Agrandiz cache regeneration =="
echo "Root      : $ROOT_DIR"
echo "Cache dir : $CACHE_DIR"
echo "DB path   : $DB_PATH"
echo

if [[ ! -f "$DB_PATH" ]]; then
  echo "ERROR: DB not found: $DB_PATH" >&2
  echo "Run the photo scan/import first, or set DB_PATH=/path/to/agrandiz.sqlite" >&2
  exit 1
fi

mkdir -p "$KEEP_DIR"

echo "== Preserving sqlite DB =="
cp -a "$DB_PATH" "$KEEP_DIR/agrandiz.sqlite"

echo "== Resetting cache directory =="
rm -rf "$CACHE_DIR"
mkdir -p "$CACHE_DIR"
cp -a "$KEEP_DIR/agrandiz.sqlite" "$DB_PATH"

echo "== Generating main dashboard =="
python -u scripts/make_dashboard.py \
  --db "$DB_PATH" \
  --outdir "$CACHE_DIR"

if [[ -f config/story_profiles/apple_icloud_default.json ]]; then
  echo "== Discovering story candidates =="
  python -u scripts/discover_stories.py \
    --db "$DB_PATH" \
    --outdir "$CACHE_DIR" \
    --config config/story_profiles/apple_icloud_default.json \
    --lang both

  echo "== Grouping story moments =="
  python -u scripts/group_story_moments.py \
    --outdir "$CACHE_DIR"

  echo "== Deduplicating story candidates =="
  python -u scripts/dedupe_story_candidates.py \
    --input "$CACHE_DIR/story_candidates_grouped.json" \
    --output "$CACHE_DIR/story_candidates_grouped.json"

  echo "== Rendering story moments =="
  python -u scripts/render_story_moments.py \
    --outdir "$CACHE_DIR" \
    --lang both
else
  echo "WARN: config/story_profiles/apple_icloud_default.json not found; skipping generic story moments pipeline."
fi

if [[ -f config/story_profiles/family_timeline.json ]]; then
  echo "== Generating family timeline via generic story pipeline =="
  python -u scripts/story_pipeline.py \
    --db "$DB_PATH" \
    --profile config/story_profiles/family_timeline.json \
    --outdir "$CACHE_DIR" \
    --fast
else
  echo "WARN: config/story_profiles/family_timeline.json not found; skipping family timeline."
fi

echo "== Generated files =="
find "$CACHE_DIR" -maxdepth 2 -type f | sort

echo "== Packing generated HTML/JSON =="
find "$CACHE_DIR" -type f \( -name "*.html" -o -name "*.json" \) -print0 | \
  tar --null -czf "$OUT_ARCHIVE" --files-from -

echo
echo "Archive created:"
ls -lh "$OUT_ARCHIVE"

echo
echo "Archive contents:"
tar -tzf "$OUT_ARCHIVE" | sort
