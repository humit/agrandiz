#!/usr/bin/env python3

"""Generic story dashboard pipeline.

This is the new top-level entrypoint for story dashboards. At this stage it is
a compatibility orchestrator: it reads a generic story profile and delegates the
actual family timeline build to the existing builder. Later steps will move
discovery, grouping and rendering into generic modules.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from agrandiz_version import print_version
from story_profile import load_story_profile


SUPPORTED_BUILDER_IDS = {
    "family_timeline": "build_family_timeline.py",
    "people_timeline": "build_family_timeline.py",
}


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def builder_for_profile(profile: dict[str, Any]) -> str:
    """Return the builder script for a story profile.

    The current compatibility mapping intentionally routes timeline-like
    profiles to build_family_timeline.py. Future refactor steps will replace this
    with generic story_discover/story_group/story_render modules.
    """

    builder = profile.get("builder")
    if isinstance(builder, dict):
        script = builder.get("script")
        if script:
            return str(script)

    profile_id = str(profile.get("id") or "")
    template_id = str(profile.get("template_id") or "")

    if profile_id in SUPPORTED_BUILDER_IDS:
        return SUPPORTED_BUILDER_IDS[profile_id]

    if template_id in SUPPORTED_BUILDER_IDS:
        return SUPPORTED_BUILDER_IDS[template_id]

    layout = str(profile.get("layout") or "")
    if layout == "timeline":
        return "build_family_timeline.py"

    raise SystemExit(
        "Unsupported story profile. Add a builder mapping or migrate this "
        f"profile to a supported layout. profile_id={profile_id!r} "
        f"template_id={template_id!r} layout={layout!r}"
    )


def run_builder(args: argparse.Namespace, profile: dict[str, Any]) -> int:
    builder_script = builder_for_profile(profile)
    builder_path = script_dir() / builder_script

    if not builder_path.exists():
        raise SystemExit(f"Builder script not found: {builder_path}")

    cmd = [
        sys.executable,
        str(builder_path),
        "--db",
        args.db,
        "--config",
        args.profile,
        "--outdir",
        args.outdir,
        "--lang",
        args.lang,
    ]

    if args.fast:
        cmd.append("--fast")
    if args.no_phash:
        cmd.append("--no-phash")
    if args.max_candidates is not None:
        cmd += ["--max-candidates", str(args.max_candidates)]
    if args.max_total_moments is not None:
        cmd += ["--max-total-moments", str(args.max_total_moments)]

    print("Story pipeline profile:", args.profile)
    print("Story pipeline builder:", builder_script)
    print("Story pipeline output dir:", args.outdir)

    if args.dry_run:
        print("Dry run command:")
        print(" ".join(cmd))
        return 0

    return subprocess.call(cmd)


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
