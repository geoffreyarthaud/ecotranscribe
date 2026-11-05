import hashlib
import importlib.util
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "fetch_ffmpeg.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "fetch_ffmpeg_test", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fetch():
    return _load_module()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_lock(path: Path, target: str, source: dict) -> None:
    path.write_text(
        json.dumps({"version": 1, "targets": {target: {"sources": [source]}}}),
        encoding="utf-8",
    )


def _make_zip(path: Path, members: dict[str, bytes]) -> str:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return _sha256(path)


def _make_tar_xz(path: Path, members: dict[str, bytes]) -> str:
    import io

    with tarfile.open(path, "w:xz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(data))
    return _sha256(path)


def test_detect_target_mapping(
    fetch, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fetch.sys, "platform", "darwin")
    monkeypatch.setattr(fetch.platform, "machine", lambda: "arm64")
    assert fetch.detect_target() == "darwin-arm64"
    monkeypatch.setattr(fetch.platform, "machine", lambda: "x86_64")
    assert fetch.detect_target() == "darwin-x64"
    monkeypatch.setattr(fetch.sys, "platform", "win32")
    assert fetch.detect_target() == "win-x64"
    monkeypatch.setattr(fetch.sys, "platform", "linux")
    monkeypatch.setattr(fetch.platform, "machine", lambda: "x86_64")
    assert fetch.detect_target() == "linux-x64"


def test_real_lock_is_pinned_and_covers_all_targets(fetch) -> None:
    lock = json.loads((ROOT / "packaging" / "ffmpeg.lock.json").read_text())
    assert set(lock["targets"]) == {
        "darwin-arm64",
        "darwin-x64",
        "win-x64",
        "linux-x64",
    }
    for target in lock["targets"].values():
        assert target["sources"]
        for source in target["sources"]:
            assert "latest" not in source["url"].lower()
            assert len(source["sha256"]) == 64
            assert source["files"]


def test_extracts_zip_and_sets_executable(
    fetch, tmp_path: Path
) -> None:
    archive = tmp_path / "ffmpeg.zip"
    digest = _make_zip(
        archive,
        {
            "prefix/bin/ffmpeg": b"ffmpeg",
            "prefix/bin/ffprobe": b"ffprobe",
        },
    )
    lock = tmp_path / "lock.json"
    _write_lock(
        lock,
        "linux-x64",
        {
            "url": archive.as_uri(),
            "sha256": digest,
            "type": "zip",
            "files": {
                "ffmpeg": "prefix/bin/ffmpeg",
                "ffprobe": "prefix/bin/ffprobe",
            },
        },
    )
    dest = tmp_path / "out"
    paths = fetch.fetch_target(
        "linux-x64",
        dest=dest,
        lock_path=lock,
        download_dir=tmp_path / "cache",
    )
    assert [path.name for path in paths] == ["ffmpeg", "ffprobe"]
    assert (dest / "ffmpeg").read_bytes() == b"ffmpeg"
    if sys.platform != "win32":
        assert (dest / "ffmpeg").stat().st_mode & 0o111


def test_extracts_tar_xz(fetch, tmp_path: Path) -> None:
    archive = tmp_path / "ffmpeg.tar.xz"
    digest = _make_tar_xz(
        archive,
        {
            "prefix/bin/ffmpeg": b"ffmpeg",
            "prefix/bin/ffprobe": b"ffprobe",
        },
    )
    lock = tmp_path / "lock.json"
    _write_lock(
        lock,
        "linux-x64",
        {
            "url": archive.as_uri(),
            "sha256": digest,
            "type": "tar.xz",
            "files": {
                "ffmpeg": "prefix/bin/ffmpeg",
                "ffprobe": "prefix/bin/ffprobe",
            },
        },
    )
    fetch.fetch_target(
        "linux-x64",
        dest=tmp_path / "out",
        lock_path=lock,
        download_dir=tmp_path / "cache",
    )
    assert (tmp_path / "out" / "ffprobe").read_bytes() == b"ffprobe"


def test_bad_hash_writes_nothing(fetch, tmp_path: Path) -> None:
    archive = tmp_path / "ffmpeg.zip"
    _make_zip(archive, {"ffmpeg": b"x"})
    lock = tmp_path / "lock.json"
    _write_lock(
        lock,
        "linux-x64",
        {
            "url": archive.as_uri(),
            "sha256": "0" * 64,
            "type": "zip",
            "files": {"ffmpeg": "ffmpeg"},
        },
    )
    dest = tmp_path / "out"
    with pytest.raises(fetch.FetchError):
        fetch.fetch_target(
            "linux-x64",
            dest=dest,
            lock_path=lock,
            download_dir=tmp_path / "cache",
        )
    assert not (dest / "ffmpeg").exists()


def test_missing_member_is_reported(fetch, tmp_path: Path) -> None:
    archive = tmp_path / "ffmpeg.zip"
    digest = _make_zip(archive, {"ffmpeg": b"x"})
    lock = tmp_path / "lock.json"
    _write_lock(
        lock,
        "linux-x64",
        {
            "url": archive.as_uri(),
            "sha256": digest,
            "type": "zip",
            "files": {"ffmpeg": "missing/ffmpeg"},
        },
    )
    with pytest.raises(fetch.FetchError) as error:
        fetch.fetch_target(
            "linux-x64",
            dest=tmp_path / "out",
            lock_path=lock,
            download_dir=tmp_path / "cache",
        )
    assert "missing/ffmpeg" in str(error.value)


def test_existing_destination_skips_download(
    fetch, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "ffmpeg").write_bytes(b"ffmpeg")
    (dest / "ffprobe").write_bytes(b"ffprobe")
    lock = tmp_path / "lock.json"
    _write_lock(
        lock,
        "linux-x64",
        {
            "url": "https://invalid.example/ffmpeg.zip",
            "sha256": "0" * 64,
            "type": "zip",
            "files": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
        },
    )

    def no_download(*args, **kwargs):
        raise AssertionError("le téléchargement doit être évité")

    monkeypatch.setattr(fetch, "_download", no_download)
    fetch.fetch_target(
        "linux-x64",
        dest=dest,
        lock_path=lock,
        download_dir=tmp_path / "cache",
    )
