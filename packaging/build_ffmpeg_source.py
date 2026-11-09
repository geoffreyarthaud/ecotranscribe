#!/usr/bin/env python3
"""Construit ffmpeg/ffprobe LGPL depuis les sources pour macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.parse import urlparse

from check_ffmpeg_build import CheckError, check_tools
from fetch_ffmpeg import FetchError, download_verified

ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = Path(__file__).with_name("ffmpeg.lock.json")
VENDOR = ROOT / "vendor"


class SourceBuildError(RuntimeError):
    """Build source impossible ou incohérent."""


def _load_lock(lock_path: Path) -> dict:
    try:
        return json.loads(Path(lock_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceBuildError(f"Lock illisible : {lock_path} : {exc}") from exc


def load_source_spec(
    target: str, *, lock_path: Path = LOCK_PATH
) -> dict:
    lock = _load_lock(lock_path)
    spec = lock.get("source_build")
    if not spec:
        raise SourceBuildError("Section source_build absente du lock")
    if target not in spec.get("targets", []):
        raise SourceBuildError(f"Cible source inconnue : {target}")
    return spec


def configure_args(spec: dict, prefix: Path) -> list[str]:
    return [
        *spec["configure"],
        f"--prefix={prefix}",
        f"--extra-cflags=-I{prefix / 'include'}",
        f"--extra-ldflags=-L{prefix / 'lib'}",
    ]


def _fingerprint(spec: dict) -> str:
    payload = json.dumps(spec, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _archive_suffix(url: str) -> str:
    path = urlparse(url).path
    for suffix in (".tar.xz", ".tar.gz", ".tar.bz2", ".tgz"):
        if path.endswith(suffix):
            return suffix
    return Path(path).suffix or ".archive"


def _extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:*") as bundle:
            bundle.extractall(destination, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise SourceBuildError(f"Extraction impossible de {archive.name} : {exc}") from exc


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    print("+", " ".join(command), flush=True)
    try:
        subprocess.run(command, cwd=cwd, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        raise SourceBuildError(
            f"Commande en échec ({exc.returncode}) : {' '.join(command)}"
        ) from exc


def _check_arch(target: str) -> None:
    if sys.platform != "darwin":
        raise SourceBuildError("Le build source macOS doit tourner sur macOS")
    machine = platform.machine().lower()
    arm = machine in ("arm64", "aarch64")
    if target == "darwin-arm64" and not arm:
        raise SourceBuildError(f"Cible arm64 sur machine {machine}")
    if target == "darwin-x64" and arm:
        raise SourceBuildError(f"Cible x64 sur machine {machine}")


def build_lame(
    spec: dict,
    *,
    source_dir: Path,
    prefix: Path,
    jobs: int,
) -> None:
    roots = sorted(source_dir.glob("lame-*"))
    if not roots:
        raise SourceBuildError("Source LAME introuvable après extraction")
    lame_dir = roots[0]
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["CFLAGS"] = f"{env.get('CFLAGS', '')} -O2 -Wno-error".strip()
    _run(
        [
            "./configure",
            f"--prefix={prefix}",
            "--disable-shared",
            "--enable-static",
            "--disable-frontend",
        ],
        cwd=lame_dir,
        env=env,
    )
    _run(["make", f"-j{jobs}"], cwd=lame_dir, env=env)
    _run(["make", "install"], cwd=lame_dir, env=env)


def build_ffmpeg(
    spec: dict,
    *,
    source_dir: Path,
    prefix: Path,
    jobs: int,
) -> None:
    roots = sorted(source_dir.glob("ffmpeg-*"))
    if not roots:
        raise SourceBuildError("Source FFmpeg introuvable après extraction")
    ffmpeg_dir = roots[0]
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    _run(["./configure", *configure_args(spec, prefix)], cwd=ffmpeg_dir, env=env)
    _run(["make", f"-j{jobs}"], cwd=ffmpeg_dir, env=env)
    _run(["make", "install"], cwd=ffmpeg_dir, env=env)


def _already_built(destination: Path, fingerprint: str) -> bool:
    marker = destination / ".source-build.json"
    if not marker.is_file():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("fingerprint") != fingerprint:
        return False
    return all((destination / name).is_file() for name in ("ffmpeg", "ffprobe"))


def build_target(
    target: str,
    *,
    destination: Path,
    work_dir: Path,
    lock_path: Path = LOCK_PATH,
    force: bool = False,
    jobs: int | None = None,
    skip_smoke: bool = False,
) -> list[Path]:
    spec = load_source_spec(target, lock_path=lock_path)
    _check_arch(target)
    fingerprint = _fingerprint(spec)
    destination = Path(destination)
    if not force and _already_built(destination, fingerprint):
        print(f"Build source déjà présent : {destination}")
        return [destination / "ffmpeg", destination / "ffprobe"]

    jobs = jobs or min(os.cpu_count() or 4, 8)
    work_dir = Path(work_dir)
    source_dir = work_dir / "src"
    prefix = work_dir / "prefix"
    downloads = work_dir / "downloads"
    for stale in (source_dir, prefix):
        shutil.rmtree(stale, ignore_errors=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    prefix.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)

    ffmpeg_archive = download_verified(
        spec["ffmpeg"]["url"],
        spec["ffmpeg"]["sha256"],
        downloads / (spec["ffmpeg"]["sha256"] + _archive_suffix(spec["ffmpeg"]["url"])),
    )
    lame_archive = download_verified(
        spec["lame"]["url"],
        spec["lame"]["sha256"],
        downloads / (spec["lame"]["sha256"] + _archive_suffix(spec["lame"]["url"])),
    )
    _extract(ffmpeg_archive, source_dir)
    _extract(lame_archive, source_dir)

    print(f"== LAME {spec['lame']['version']} ==", flush=True)
    build_lame(spec, source_dir=source_dir, prefix=prefix, jobs=jobs)

    print(f"== FFmpeg {spec['ffmpeg']['version']} ==", flush=True)
    build_ffmpeg(spec, source_dir=source_dir, prefix=prefix, jobs=jobs)

    destination.mkdir(parents=True, exist_ok=True)
    for name in ("ffmpeg", "ffprobe"):
        source = prefix / "bin" / name
        if not source.is_file():
            raise SourceBuildError(f"Binaire absent après build : {source}")
        target_path = destination / name
        shutil.copy2(source, target_path)
        target_path.chmod(0o755)

    try:
        summary = check_tools(
            destination / "ffmpeg",
            destination / "ffprobe",
            require_lgpl=True,
            smoke=not skip_smoke,
        )
    except CheckError as exc:
        raise SourceBuildError(f"Vérification du build échouée : {exc}") from exc

    marker = {
        "fingerprint": fingerprint,
        "ffmpeg_version": spec["ffmpeg"]["version"],
        "lame_version": spec["lame"]["version"],
        "license": spec["license"],
        "checked": summary["license"],
    }
    (destination / ".source-build.json").write_text(
        json.dumps(marker, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return [destination / "ffmpeg", destination / "ffprobe"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Construit ffmpeg/ffprobe LGPL depuis les sources (macOS)."
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--skip-smoke", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    destination = args.dest or VENDOR / "ffmpeg" / args.target
    work_dir = args.work_dir or ROOT / "build" / "ffmpeg-source" / args.target
    try:
        paths = build_target(
            args.target,
            destination=destination,
            work_dir=work_dir,
            lock_path=args.lock,
            force=args.force,
            jobs=args.jobs,
            skip_smoke=args.skip_smoke,
        )
    except (SourceBuildError, FetchError, OSError, subprocess.SubprocessError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(f"Cible {args.target} :")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
