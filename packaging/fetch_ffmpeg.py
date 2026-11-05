#!/usr/bin/env python3
"""Télécharge, vérifie et extrait ffmpeg/ffprobe pour une cible."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = Path(__file__).with_name("ffmpeg.lock.json")
VENDOR = ROOT / "vendor"
USER_AGENT = "ecotranscribe-fetch-ffmpeg/0.2.0"


class FetchError(RuntimeError):
    pass


def detect_target() -> str:
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
        return f"darwin-{arch}"
    if sys.platform == "win32":
        if machine not in ("amd64", "x86_64", "x64"):
            raise FetchError(f"Architecture Windows non supportée : {machine}")
        return "win-x64"
    if sys.platform.startswith("linux"):
        if machine not in ("x86_64", "amd64"):
            raise FetchError(f"Architecture Linux non supportée : {machine}")
        return "linux-x64"
    raise FetchError(f"Plateforme non supportée : {sys.platform}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cache_suffix(source: dict) -> str:
    kind = source.get("type", "")
    if kind == "tar.xz":
        return ".tar.xz"
    if kind == "zip":
        return ".zip"
    suffix = Path(urlparse(source["url"]).path).suffix
    return suffix or ".archive"


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            with partial.open("wb") as handle:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    handle.write(block)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _cached_archive(
    source: dict, download_dir: Path
) -> Path:
    expected = source["sha256"]
    archive = download_dir / (expected + _cache_suffix(source))
    if archive.exists() and _sha256(archive) == expected:
        return archive
    archive.unlink(missing_ok=True)
    try:
        _download(source["url"], archive)
    except Exception as exc:
        raise FetchError(
            f"Téléchargement impossible pour {source['url']} : {exc}"
        ) from exc
    actual = _sha256(archive)
    if actual != expected:
        archive.unlink(missing_ok=True)
        raise FetchError(
            f"SHA256 invalide pour {source['url']} : "
            f"attendu {expected}, obtenu {actual}"
        )
    return archive


def _extract_zip(archive: Path, member: str) -> bytes:
    try:
        with zipfile.ZipFile(archive) as bundle:
            return bundle.read(member)
    except KeyError as exc:
        raise FetchError(
            f"Membre '{member}' absent de {archive.name}"
        ) from exc


def _extract_tar_xz(archive: Path, member: str) -> bytes:
    try:
        with tarfile.open(archive, "r:xz") as bundle:
            handle = bundle.extractfile(member)
            if handle is None:
                raise FetchError(
                    f"Membre '{member}' absent de {archive.name}"
                )
            return handle.read()
    except KeyError as exc:
        raise FetchError(
            f"Membre '{member}' absent de {archive.name}"
        ) from exc
    except tarfile.TarError as exc:
        raise FetchError(
            f"Archive invalide {archive.name} : {exc}"
        ) from exc


def fetch_target(
    target: str,
    *,
    dest: Path | None = None,
    lock_path: Path = LOCK_PATH,
    download_dir: Path | None = None,
) -> list[Path]:
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    try:
        entry = lock["targets"][target]
    except KeyError as exc:
        raise FetchError(f"Cible inconnue : {target}") from exc

    destination = Path(dest) if dest is not None else VENDOR / "ffmpeg" / target
    destination.mkdir(parents=True, exist_ok=True)

    expected_names: list[str] = []
    for source in entry["sources"]:
        expected_names.extend(source["files"])
    if all((destination / name).is_file() for name in expected_names):
        return [destination / name for name in expected_names]

    cache_dir = (
        Path(download_dir)
        if download_dir is not None
        else VENDOR / "downloads"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for source in entry["sources"]:
        archive = _cached_archive(source, cache_dir)
        kind = source.get("type")
        for output_name, member in source["files"].items():
            if kind == "zip":
                data = _extract_zip(archive, member)
            elif kind == "tar.xz":
                data = _extract_tar_xz(archive, member)
            else:
                raise FetchError(f"Type d'archive inconnu : {kind}")
            output = destination / output_name
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.write_bytes(data)
            if os.name != "nt":
                temporary.chmod(0o755)
            temporary.replace(output)
            written.append(output)

    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Télécharge ffmpeg/ffprobe épinglés pour une cible."
    )
    parser.add_argument("--target", default=None)
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = args.target or detect_target()
        paths = fetch_target(
            target, dest=args.dest, lock_path=args.lock
        )
    except (FetchError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(f"Cible {target} :")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
