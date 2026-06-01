#!/usr/bin/env python3

"""Generic story dashboard pipeline.

This is the new top-level entrypoint for story dashboards. At this stage it is
a compatibility orchestrator: it reads a generic story profile and delegates the
actual family timeline build to the existing builder. Later steps will move
discovery, grouping and rendering into generic modules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from agrandiz_version import print_version
from story_profile import load_story_profile
from story_common import source_identity
from story_builder import run_story_builder


LEGACY_BUILDER_FALLBACKS = {
    "family_timeline": "story_builder.py",
    "people_timeline": "story_builder.py",
}



def script_dir() -> Path:
    return Path(__file__).resolve().parent


def builder_for_profile(profile: dict[str, Any]) -> str:
    """Return the builder script for a story profile.

    Preferred source is profile["builder"]["script"]. The legacy fallback exists
    only so older profiles without an explicit builder can still run.
    """

    builder = profile.get("builder")
    if isinstance(builder, dict):
        script = builder.get("script")
        if script:
            return str(script)

    profile_id = str(profile.get("id") or "")
    template_id = str(profile.get("template_id") or "")

    if profile_id in LEGACY_BUILDER_FALLBACKS:
        return LEGACY_BUILDER_FALLBACKS[profile_id]

    if template_id in LEGACY_BUILDER_FALLBACKS:
        return LEGACY_BUILDER_FALLBACKS[template_id]

    raise SystemExit(
        "Unsupported story profile. Add an explicit builder.script field to the "
        f"profile. profile_id={profile_id!r} template_id={template_id!r}"
    )


def run_builder(args: argparse.Namespace, profile: dict[str, Any]) -> int:
    builder_script = builder_for_profile(profile)

    print("Story pipeline profile:", args.profile)
    print("Story pipeline id:", profile.get("id"))
    print("Story pipeline template:", profile.get("template_id"))
    print("Story pipeline layout:", profile.get("layout"))
    print("Story pipeline source:", source_identity(profile))
    print("Story pipeline builder:", builder_script)
    print("Story pipeline output dir:", args.outdir)

    if args.dry_run:
        print("Dry run direct call:")
        print(
            "run_story_builder("
            f"db={args.db!r}, "
            f"config_path={args.profile!r}, "
            f"outdir={args.outdir!r}, "
            f"lang={args.lang!r}, "
            f"fast={args.fast!r}, "
            f"max_candidates={args.max_candidates!r}, "
            f"max_total_moments={args.max_total_moments!r}, "
            f"no_phash={args.no_phash!r})"
        )
        return 0

    if builder_script != "story_builder.py":
        raise SystemExit(f"Unsupported direct builder: {builder_script}")

    run_story_builder(
        db=args.db,
        config_path=args.profile,
        outdir=args.outdir,
        lang=args.lang,
        fast=args.fast,
        max_candidates=args.max_candidates,
        max_total_moments=args.max_total_moments,
        no_phash=args.no_phash,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate story dashboards from generic story profiles.")
    parser.add_argument("--db", default="cache/agrandiz.sqlite")
    parser.add_argument("--profile", "--config", dest="profile", default="config/story_profiles/family_timeline.json")
    parser.add_argument("--outdir", default="cache")
    parser.add_argument("--lang", default="both", choices=["tr", "en", "both"])
    parser.add_argument("--fast", action="store_true", help="Use faster beta/test settings")
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--max-total-moments", type=int, default=None)
    parser.add_argument("--no-phash", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    profile = load_story_profile(args.profile)
    return run_builder(args, profile)


if __name__ == "__main__":
    print_version()
    raise SystemExit(main())
