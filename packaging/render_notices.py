#!/usr/bin/env python3
"""Rend une notice plateforme depuis packaging/notices/."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTICES = Path(__file__).with_name("notices")
PLATFORMS = {
    "macos": "LIRE-MOI-macOS.txt",
    "windows": "LIRE-MOI-Windows.txt",
    "linux": "LIRE-MOI-Linux.txt",
}


def render(
    platform: str,
    output: Path,
    *,
    version: str,
    arch: str,
    commit: str,
    build_date: str,
    tag: str,
    project_url: str,
) -> Path:
    template = (NOTICES / PLATFORMS[platform]).read_text(encoding="utf-8")
    text = template.format(
        version=version,
        arch=arch,
        commit=commit,
        build_date=build_date,
        tag=tag,
        project_url=project_url,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--os", dest="platform", required=True, choices=PLATFORMS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="0.4.0")
    parser.add_argument("--arch", default="")
    parser.add_argument("--commit", default="dev")
    parser.add_argument("--build-date", default="")
    parser.add_argument("--tag", default="v0.4.0")
    parser.add_argument(
        "--project-url",
        default="https://github.com/ecotranscribe/ecotranscribe",
    )
    args = parser.parse_args(argv)
    render(
        args.platform,
        args.output,
        version=args.version,
        arch=args.arch,
        commit=args.commit,
        build_date=args.build_date,
        tag=args.tag,
        project_url=args.project_url,
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
