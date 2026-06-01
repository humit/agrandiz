#!/usr/bin/env python3

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from story_render import render_html as render_story_dashboard
from story_group import (
    cluster_items as group_story_items,
    select_year_moments as select_story_year_moments,
)
from story_discover import (
    discover_items,
    fetch_rows as fetch_story_rows,
    phash_available,
)
from story_profile import (
    legacy_selection_config,
    load_story_profile,
    profile_output_html,
    profile_output_json,
)


def build_timeline(rows, config, thumbs_dir):
    use_phash = phash_available() and not config.get("disable_phash", False)
    items = discover_items(rows, config, thumbs_dir, use_phash=use_phash)

    moments = group_story_items(items, config)
    by_year = select_story_year_moments(moments, config)

    total_selected = sum(len(v) for v in by_year.values())
    grouped_variants = sum(
        max(moment.get("variant_count", 1) - 1, 0)
        for year_items in by_year.values()
        for moment in year_items
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "phash_enabled": use_phash,
        "source_item_count": len(items),
        "moment_count": len(moments),
        "selected_moment_count": total_selected,
        "grouped_variant_count": grouped_variants,
        "years": [
            {
                "year": year,
                "moment_count": len(moments_for_year),
                "moments": moments_for_year
            }
            for year, moments_for_year in by_year.items()
        ]
    }


def patch_portal_index(outdir):
    index = outdir / "index.html"
    if not index.exists():
        return

    text = index.read_text()

    if "family-timeline.apple.apple_icloud.html" in text:
        return

    insert = """
      <a class="portal-card" href="family-timeline.apple.apple_icloud.html">
        <div class="eyebrow">Türkçe · Family Timeline</div>
        <h2>Çocukların Büyüme Hikâyesi</h2>
        <p>Çocuk, aile, doğum günü, okul ve gündelik hayat anılarından yıllara yayılan zaman çizelgesi.</p>
      </a>

      <a class="portal-card" href="family-timeline.apple.apple_icloud.html">
        <div class="eyebrow">English · Family Timeline</div>
        <h2>Children's Growing-Up Story</h2>
        <p>A year-by-year timeline from child, family, birthday, school and everyday-life memories.</p>
      </a>
"""

    needle = '    </section>'
    pos = text.find(needle)
    if pos != -1:
        text = text[:pos] + insert + "\n" + text[pos:]
        index.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--config", default="config/family_timeline.json")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    parser.add_argument("--fast", action="store_true", help="Use faster beta/test settings")
    parser.add_argument("--max-candidates", type=int, default=None, help="Limit matched candidate photos")
    parser.add_argument("--max-total-moments", type=int, default=None, help="Limit selected timeline moments")
    parser.add_argument("--no-phash", action="store_true", help="Disable perceptual hash computation")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    thumbs_dir = outdir / "thumbs"
    outdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    profile = load_story_profile(args.config)
    config = legacy_selection_config(profile)

    if args.fast:
        config["disable_phash"] = True
        config["max_candidates"] = min(int(config.get("max_candidates", 700)), 700)
        config["max_total_moments"] = min(int(config.get("max_total_moments", 60)), 60)
        config["max_moments_per_year"] = min(int(config.get("max_moments_per_year", 8)), 8)

    if args.no_phash:
        config["disable_phash"] = True

    if args.max_candidates is not None:
        config["max_candidates"] = args.max_candidates

    if args.max_total_moments is not None:
        config["max_total_moments"] = args.max_total_moments

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = fetch_story_rows(conn)
    conn.close()

    timeline = build_timeline(rows, config, thumbs_dir)

    json_path = outdir / profile_output_json(profile)
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "config": args.config,
                "profile": profile,
                "timeline": timeline
            },
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"Wrote {json_path}")
    print("source_item_count:", timeline["source_item_count"])
    print("moment_count:", timeline["moment_count"])
    print("selected_moment_count:", timeline["selected_moment_count"])
    print("grouped_variant_count:", timeline["grouped_variant_count"])

    # Single canonical HTML file. Language switching is handled in-page via i18n.
    default_lang = "tr" if args.lang == "both" else args.lang
    html_text = render_story_dashboard(timeline, config, default_lang, profile=profile)
    html_path = outdir / profile_output_html(profile)
    html_path.write_text(html_text, encoding="utf-8")
    print(f"Wrote {html_path}")

    patch_portal_index(outdir)


if __name__ == "__main__":
    from agrandiz_version import print_version
    print_version()
    main()
