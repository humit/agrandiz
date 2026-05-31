#!/usr/bin/env python3

import json
from pathlib import Path


def project_root():
    return Path(__file__).resolve().parents[1]


def version_file():
    return project_root() / "VERSION.json"


def load_version():
    p = version_file()

    if not p.exists():
        return {
            "name": "Agrandiz",
            "version": "0.0.0",
            "channel": "dev",
            "updated_at": None,
        }

    try:
        return json.loads(p.read_text())
    except Exception:
        return {
            "name": "Agrandiz",
            "version": "0.0.0",
            "channel": "unknown",
            "updated_at": None,
        }


def version_string():
    data = load_version()
    name = data.get("name", "Agrandiz")
    version = data.get("version", "0.0.0")
    channel = data.get("channel", "dev")

    if channel:
        return f"{name} {version} {channel}"

    return f"{name} {version}"


def print_version():
    print(version_string(), flush=True)


if __name__ == "__main__":
    print_version()
