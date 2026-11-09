import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "build_ffmpeg_source.py"
sys.path.insert(0, str(ROOT / "packaging"))


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_ffmpeg_source_test", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def build():
    return _load_module()


def test_source_spec_covers_both_macos_targets(build) -> None:
    for target in ("darwin-arm64", "darwin-x64"):
        spec = build.load_source_spec(target)
        assert spec["license"] == "LGPL-2.1-or-later"
        assert spec["ffmpeg"]["version"] == "9.0.2"
        assert spec["lame"]["version"] == "3.100"
    with pytest.raises(build.SourceBuildError):
        build.load_source_spec("win-x64")


def test_configure_args_append_prefix_and_lame_paths(build, tmp_path: Path) -> None:
    spec = build.load_source_spec("darwin-arm64")
    args = build.configure_args(spec, tmp_path)
    assert f"--prefix={tmp_path}" in args
    assert f"--extra-cflags=-I{tmp_path / 'include'}" in args
    assert f"--extra-ldflags=-L{tmp_path / 'lib'}" in args
    assert "--disable-gpl" in args
    assert "--enable-libmp3lame" in args


def test_fingerprint_tracks_configure_changes(build) -> None:
    spec = build.load_source_spec("darwin-arm64")
    changed = {**spec, "configure": [*spec["configure"], "--enable-foo"]}
    assert build._fingerprint(spec) != build._fingerprint(changed)
