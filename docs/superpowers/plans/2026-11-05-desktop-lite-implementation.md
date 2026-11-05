# EcoTranscribe Desktop lite — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer `whisper-transcribe` par EcoTranscribe 0.2.0 (paquet/CLI `ecotranscribe`, GUI PySide6 lite OpenRouter), produire les artefacts macOS/Windows/Linux décrits par la spec, et conserver le CLI Whisper via l'extra `[whisper]`.

**Architecture:** Le cœur `ecotranscribe.core` ne dépend ni de Qt ni d'`argparse` : modèles, erreurs, média ffmpeg, writers SRT/TXT internes, moteurs OpenRouter/Whisper et `TranscribeService`. Le CLI `ecotranscribe` et la GUI `ecotranscribe-desktop` sont deux adaptateurs du même service. Le packaging PyInstaller `--onedir` embarque ffmpeg/ffprobe et exclut torch/Whisper.

**Tech Stack:** Python ≥ 3.10 (CI et dev sur 3.13), `rich`, PySide6-Essentials 6.7–6.x, `keyring` 25+, pytest/pytest-qt, PyInstaller 6+, `uv`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-05-desktop-lite-design.md` (commit 93cc2dd)

## Contraintes globales

- Version `0.2.0` ; paquet `ecotranscribe` ; CLI `ecotranscribe` ; app `EcoTranscribe Desktop` ; entrée `ecotranscribe-desktop` ; bundle `app.ecotranscribe.desktop`.
- Aucun alias `transcribe`, `transcribe-gui`, `whisper_transcribe`.
- L'édition lite ne contient ni torch, ni Whisper, ni modèle local ; `openai-whisper` reste uniquement dans l'extra `[whisper]`.
- Aucun réseau hors OpenRouter ; aucun secret dans logs/QSettings/détails d'erreur ; HTTPS/TLS standard.
- Sorties UTF-8, LF, écriture atomique ; mêmes octets que les sorties CLI actuelles.
- Une seule transcription à la fois ; UI Qt jamais bloquée par une opération > 100 ms.
- Aucun artefact généré (DMG, ZIP, AppImage, binaires ffmpeg, `.venv`, `dist/`, `build/`, `vendor/`) commité.
- Toutes les commandes Python passent par `uv`.
- `OPENROUTER_API_KEY` n'est jamais affichée ni passée en argument de commande journalisé.
- Divergences assumées et documentées :
  1. Les goldens sont commités dans `tests/fixtures/sample.srt|txt` car `data/` est gitignoré.
  2. Le writer TXT écrit une ligne par segment (`segment.text.strip() + "\n"`), identique au CLI actuel (FR-12/NFR-08) ; le raccourci §8.7 est interprété par segment.
  3. `PROJECT_URL` par défaut : `https://github.com/ecotranscribe/ecotranscribe` (aucun remote dans le dépôt) ; à ajuster avant publication.
  4. `--diagnose` écrit toujours dans `--diagnose-output` ; stdout n'est utilisé que s'il existe (exe Windows `--windowed` sans console).
  5. ffmpeg macOS : builds GPL OSXExperts (9.0.2 arm64, 8.0 x64), win/linux : builds LGPL BtbN 9.0.2 ; obligations dans `THIRD_PARTY_NOTICES.md`.
  6. `appimagetool` épinglé en 1.9.1 avec SHA256 (la spec n'imposait pas son épinglage).

---

## Phase 0 — Extraction du cœur, writers, service, CLI

### Task 1 : Renommage du paquet, version, extras et fixtures

**Files:**
- Move: `src/whisper_transcribe/` → `src/ecotranscribe/`
- Delete: `src/whisper_transcribe/main.py`
- Create: `src/ecotranscribe/__init__.py`
- Modify: `pyproject.toml`
- Create: `tests/fixtures/sample.srt`, `tests/fixtures/sample.txt`
- Move: `tests/test_openrouter.py` (contenu réécrit Task 6)
- Modify: `.gitignore` (ajouter `build/`, `vendor/`, `*.dmg`, `*.AppImage`, `*.zip`, `*.tar.gz`, artefacts packaging ; ne jamais ignorer `tests/fixtures/`)

**Interfaces:**
- Produces: `ecotranscribe.__version__ == "0.2.0"`, entry points `ecotranscribe`, `ecotranscribe-desktop`.

- [ ] **Step 1: Déplacer le paquet et créer l'init**

```bash
git mv src/whisper_transcribe src/ecotranscribe
git rm src/ecotranscribe/main.py
```

`src/ecotranscribe/__init__.py` :

```python
"""EcoTranscribe — transcription audio/vidéo locale ou via OpenRouter."""

__version__ = "0.2.0"
```

- [ ] **Step 2: Réécrire `pyproject.toml`**

```toml
[project]
name = "ecotranscribe"
version = "0.2.0"
description = "Transcription audio/vidéo avec OpenRouter ou Whisper local"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = ["rich>=15.0.0"]

[project.optional-dependencies]
gui = [
  "PySide6-Essentials>=6.7,<7",
  "keyring>=25",
]
whisper = ["openai-whisper>=20231117"]
dev = [
  "pytest>=8",
  "pytest-qt>=4",
  "pyinstaller>=6",
  "pillow>=10",
]

[project.scripts]
ecotranscribe = "ecotranscribe.cli:main"
ecotranscribe-desktop = "ecotranscribe.gui.app:main"

[project.urls]
Source = "https://github.com/ecotranscribe/ecotranscribe"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ecotranscribe"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Fixtures golden**

Copier les octets de `data/sample.srt` et `data/sample.txt` dans `tests/fixtures/` :

```bash
mkdir -p tests/fixtures
cp data/sample.srt tests/fixtures/sample.srt
cp data/sample.txt tests/fixtures/sample.txt
```

- [ ] **Step 4: Vérifier la résolution**

Run: `uv lock && uv sync --extra dev`
Expected: lock OK, scripts absents tant que `cli.py`/`gui/app.py` n'existent pas — c'est attendu jusqu'aux Tasks 8–9. `uv run python -c "import ecotranscribe; print(ecotranscribe.__version__)"` → `0.2.0`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/ecotranscribe/__init__.py tests/fixtures .gitignore
git commit -m "refactor: rename package to ecotranscribe 0.2.0"
```

### Task 2 : Modèles, erreurs, CancelToken

**Files:**
- Create: `src/ecotranscribe/core/__init__.py`
- Create: `src/ecotranscribe/core/models.py`
- Create: `src/ecotranscribe/core/errors.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `Provider`, `OutputFormat`, `Segment`, `TranscribeRequest`, `TranscribeResult`, `EngineResult`, `ProgressUpdate`, `EngineAvailability`, `CancelToken`, exceptions `TranscribeError`, `InvalidRequestError`, `EngineUnavailableError`, `MediaToolMissingError`, `OutputExistsError`, `CancelledError`.

- [ ] **Step 1: Tests des contrats**

```python
from pathlib import Path

import pytest

from ecotranscribe.core.errors import CancelledError
from ecotranscribe.core.models import (
    CancelToken,
    OutputFormat,
    Segment,
    TranscribeRequest,
)


def test_request_defaults_output_dir_to_parent(tmp_path: Path) -> None:
    source = tmp_path / "réunion.mp3"
    source.write_bytes(b"x")
    request = TranscribeRequest(
        input_path=source, provider="openrouter", model="m"
    )
    assert request.output_dir == tmp_path
    assert request.formats == frozenset({OutputFormat.SRT, OutputFormat.TXT})
    assert request.language == "fr"
    assert request.overwrite is False
    assert request.api_key is None


def test_cancel_token_is_idempotent() -> None:
    token = CancelToken()
    assert not token.is_cancelled()
    token.cancel()
    token.cancel()
    assert token.is_cancelled()
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()


def test_segment_is_frozen() -> None:
    segment = Segment(id=1, start=0.0, end=1.0, text="Bonjour")
    with pytest.raises(Exception):
        segment.text = "Autre"  # type: ignore[misc]
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL `ModuleNotFoundError: ecotranscribe.core`.

- [ ] **Step 3: Implémenter**

`core/models.py` — points exacts :

```python
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from .errors import CancelledError

ProgressPhase = Literal[
    "validating", "extracting", "detecting_silences",
    "transcribing", "writing", "done",
]


class Provider(str, Enum):
    OPENROUTER = "openrouter"
    WHISPER = "whisper"


class OutputFormat(str, Enum):
    SRT = "srt"
    TXT = "txt"


@dataclass(frozen=True, slots=True)
class Segment:
    id: int
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class TranscribeRequest:
    input_path: Path
    provider: Provider
    model: str
    language: str | None = "fr"
    prompt_text: str | None = None
    output_dir: Path | None = None
    formats: frozenset[OutputFormat] = frozenset(
        {OutputFormat.SRT, OutputFormat.TXT}
    )
    overwrite: bool = False
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.output_dir is None:
            object.__setattr__(self, "output_dir", self.input_path.parent)
        if isinstance(self.provider, str):
            object.__setattr__(self, "provider", Provider(self.provider))
        formats = frozenset(
            fmt if isinstance(fmt, OutputFormat) else OutputFormat(fmt)
            for fmt in self.formats
        )
        object.__setattr__(self, "formats", formats)
        if not self.prompt_text:
            object.__setattr__(self, "prompt_text", None)


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    phase: ProgressPhase
    current: float = 0.0
    total: float | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class EngineAvailability:
    available: bool
    reason: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EngineResult:
    text: str
    segments: tuple[Segment, ...]
    language: str | None
    cost_usd: float | None
    duration_s: float | None


@dataclass(frozen=True, slots=True)
class TranscribeResult:
    output_paths: tuple[Path, ...]
    text: str
    segments: tuple[Segment, ...]
    language: str | None
    cost_usd: float | None
    provider: Provider
    model: str
    duration_s: float | None


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError()
```

`core/errors.py` :

```python
class TranscribeError(Exception):
    def __init__(
        self,
        user_message: str,
        detail: str | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail
        self.hint = hint


class InvalidRequestError(TranscribeError):
    pass


class EngineUnavailableError(TranscribeError):
    pass


class MediaToolMissingError(TranscribeError):
    def __init__(self, tool: str) -> None:
        super().__init__(
            "ffmpeg est introuvable. Réinstallez l'application ou "
            "signalez le problème.",
            detail=f"Outil introuvable : {tool}",
        )
        self.tool = tool


class OutputExistsError(TranscribeError):
    def __init__(self, paths: tuple[Path, ...]) -> None:
        names = ", ".join(path.name for path in paths)
        super().__init__(
            f"Ces fichiers existent déjà : {names}",
            detail="\n".join(str(path) for path in paths),
        )
        self.paths = paths


class CancelledError(TranscribeError):
    def __init__(self) -> None:
        super().__init__("Transcription annulée.")
```

`core/__init__.py` : docstring seulement.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core tests/test_models.py
git commit -m "feat(core): add request, result, progress and cancellation models"
```

### Task 3 : Writers SRT/TXT internes

**Files:**
- Create: `src/ecotranscribe/core/writers.py`
- Create: `tests/test_writers.py`

**Interfaces:**
- Produces: `format_timestamp(seconds: float) -> str`, `render_srt(segments) -> str`, `render_txt(segments) -> str`, `write_srt(path, segments) -> None`, `write_txt(path, segments) -> None`, `write_atomic(path, content) -> None`.

- [ ] **Step 1: Tests golden et limites**

```python
from pathlib import Path

import pytest

from ecotranscribe.core.models import Segment
from ecotranscribe.core.writers import (
    format_timestamp,
    render_srt,
    render_txt,
    write_atomic,
    write_srt,
    write_txt,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_srt_matches_cli_golden_bytes(tmp_path: Path) -> None:
    segments = (
        Segment(
            id=1,
            start=1.3,
            end=5.9,
            text="Bonjour, je m'appelle Geoffrey et je fais de l'accessibilité "
            "avec du RGAA.",
        ),
    )
    target = tmp_path / "sample.srt"
    write_srt(target, segments)
    assert target.read_bytes() == (FIXTURES / "sample.srt").read_bytes()


def test_txt_matches_cli_golden_bytes(tmp_path: Path) -> None:
    segments = (
        Segment(
            id=1,
            start=1.3,
            end=5.9,
            text="Bonjour, je m'appelle Geoffrey et je fais de l'accessibilité "
            "avec du RGAA.",
        ),
    )
    target = tmp_path / "sample.txt"
    write_txt(target, segments)
    assert target.read_bytes() == (FIXTURES / "sample.txt").read_bytes()


def test_txt_writes_one_line_per_segment() -> None:
    segments = (
        Segment(id=1, start=0.0, end=1.0, text="  Premier  "),
        Segment(id=2, start=1.0, end=2.0, text="Deuxième"),
    )
    assert render_txt(segments) == "Premier\nDeuxième\n"


def test_empty_txt_is_empty() -> None:
    assert render_txt(()) == ""


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0.0, "00:00:00,000"),
        (3661.234, "01:01:01,234"),
        (59.9999, "00:01:00,000"),
    ],
)
def test_srt_timestamp(seconds: float, expected: str) -> None:
    assert format_timestamp(seconds) == expected


def test_srt_escapes_arrow_and_strips_text() -> None:
    segments = (Segment(id=1, start=0, end=1, text="  a --> b  "),)
    assert render_srt(segments) == "1\n00:00:00,000 --> 00:00:01,000\na -> b\n\n"


def test_srt_is_lf_only(tmp_path: Path) -> None:
    target = tmp_path / "out.srt"
    write_srt(target, (Segment(1, 0, 1, "x"),))
    assert b"\r" not in target.read_bytes()


def test_atomic_write_keeps_original_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.txt"
    target.write_text("ancien", encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr("ecotranscribe.core.writers.os.replace", boom)
    with pytest.raises(OSError):
        write_atomic(target, "nouveau")
    assert target.read_text(encoding="utf-8") == "ancien"
    assert list(tmp_path.iterdir()) == [target]
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_writers.py -v`
Expected: FAIL `ModuleNotFoundError`/`ImportError`.

- [ ] **Step 3: Implémenter**

```python
def format_timestamp(seconds: float) -> str:
    milliseconds = round(max(0.0, seconds) * 1000.0)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1_000)
    return (
        f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},"
        f"{milliseconds:03d}"
    )


def render_srt(segments) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip().replace("-->", "->")
        blocks.append(
            f"{index}\n"
            f"{format_timestamp(segment.start)} --> "
            f"{format_timestamp(segment.end)}\n"
            f"{text}\n"
        )
    return "\n".join(blocks) + ("\n" if blocks else "")


def render_txt(segments) -> str:
    return "".join(f"{segment.text.strip()}\n" for segment in segments)
```

`write_atomic` : `tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")`, `os.fdopen(..., "w", encoding="utf-8", newline="\n")`, `flush`, `os.fsync`, `os.replace`, suppression du temporaire dans `except BaseException`. `write_srt`/`write_txt` appellent `write_atomic`.

Note exacte : `render_srt` produit un `\n` final après le dernier bloc, donc deux `\n` après le dernier texte — identique à `data/sample.srt`.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_writers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core/writers.py tests/test_writers.py
git commit -m "feat(core): add internal SRT and TXT writers with atomic writes"
```

### Task 4 : Prompts et chemins de sortie

**Files:**
- Create: `src/ecotranscribe/core/prompts.py`
- Create: `src/ecotranscribe/core/outputs.py`
- Create: `tests/test_prompts.py`
- Create: `tests/test_outputs.py`

**Interfaces:**
- Produces: `find_prompt_file(input_path) -> Path | None`, `read_prompt(path) -> str`, `resolve_prompt(input_path) -> tuple[Path | None, str | None]`, `output_paths(input_path, output_dir, formats) -> tuple[Path, ...]`, `existing_outputs(paths) -> tuple[Path, ...]`.

- [ ] **Step 1: Tests**

`tests/test_prompts.py` : priorité `.prompt.md` > `.prompt.txt` > `.prompt`, absence → `(None, None)`, lecture UTF-8 avec accents, `resolve_prompt` retourne le texte strippé, fichier illisible → `InvalidRequestError`.

`tests/test_outputs.py` :

```python
def test_output_paths_order_and_alt_dir(tmp_path):
    source = tmp_path / "source" / "réunion.mp3"
    source.parent.mkdir()
    source.write_bytes(b"x")
    out = tmp_path / "sortie"
    out.mkdir()
    paths = output_paths(source, out, frozenset({OutputFormat.TXT, OutputFormat.SRT}))
    assert paths == (out / "réunion.srt", out / "réunion.txt")


def test_existing_outputs_only_existing(tmp_path):
    a, b = tmp_path / "a.srt", tmp_path / "a.txt"
    a.write_text("x")
    assert existing_outputs((a, b)) == (a,)
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_prompts.py tests/test_outputs.py -v`
Expected: FAIL imports.

- [ ] **Step 3: Implémenter**

`prompts.py` : constante `PROMPT_EXTENSIONS = (".prompt.md", ".prompt.txt", ".prompt")` (ou import depuis `config`), `find_prompt_file` teste `is_file()` dans cet ordre, `read_prompt` fait `read_text(encoding="utf-8").strip()` et enveloppe `OSError` en `InvalidRequestError("Impossible de lire le fichier prompt.", detail=str(exc))`.

`outputs.py` :

```python
def output_paths(input_path, output_dir, formats):
    suffix_by_format = {OutputFormat.SRT: ".srt", OutputFormat.TXT: ".txt"}
    return tuple(
        output_dir / f"{input_path.stem}{suffix_by_format[fmt]}"
        for fmt in (OutputFormat.SRT, OutputFormat.TXT)
        if fmt in formats
    )
```

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_prompts.py tests/test_outputs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core/prompts.py src/ecotranscribe/core/outputs.py tests/test_prompts.py tests/test_outputs.py
git commit -m "feat(core): add prompt discovery and output path planning"
```

### Task 5 : Couche média ffmpeg/ffprobe

**Files:**
- Create: `src/ecotranscribe/core/config.py`
- Create: `src/ecotranscribe/core/media.py`
- Create: `tests/test_media.py`

**Interfaces:**
- Produces: `resolve_tool(name) -> str | None`, `run_media(args, *, cancel=None, timeout=None) -> MediaProcessResult`, `get_media_duration(path, *, cancel=None) -> float | None`, `is_video_file(path, *, cancel=None) -> bool`, `extract_audio(src, dst, *, cancel=None) -> None`, `detect_silences(path, *, cancel=None) -> list[tuple[float, float]]`, `extract_chunk_mp3(src, dst, start, duration, *, cancel=None) -> None`, `tool_version(tool) -> str | None`.

- [ ] **Step 1: Tests**

```python
def test_env_override_wins(tmp_path, monkeypatch):
    tool = tmp_path / "ffmpeg"
    tool.write_bytes(b"#!/bin/sh\n")
    tool.chmod(0o755)
    monkeypatch.setenv("ECOTRANSCRIBE_FFMPEG_DIR", str(tmp_path))
    monkeypatch.setattr(media.shutil, "which", lambda name: "/bin/" + name)
    assert media.resolve_tool("ffmpeg") == str(tool)


def test_bundle_wins_over_path(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle" / "bin"
    bundle.mkdir(parents=True)
    tool = bundle / "ffprobe"
    tool.write_bytes(b"x")
    tool.chmod(0o755)
    monkeypatch.delenv("ECOTRANSCRIBE_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(media.sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(media.shutil, "which", lambda name: "/bin/" + name)
    assert media.resolve_tool("ffprobe") == str(tool)


def test_run_media_decodes_utf8(tmp_path):
    result = media.run_media(
        [sys.executable, "-c", "print('accentué — ok')"], timeout=10
    )
    assert result.returncode == 0
    assert "accentué" in result.stdout


def test_cancel_terminates_process():
    token = CancelToken()
    timer = threading.Timer(0.3, token.cancel)
    timer.start()
    started = time.monotonic()
    with pytest.raises(CancelledError):
        media.run_media(
            [sys.executable, "-c", "import time; time.sleep(30)"], cancel=token
        )
    timer.join()
    assert time.monotonic() - started < 4.0


def test_windows_creation_flags(monkeypatch):
    monkeypatch.setattr(media.sys, "platform", "win32")
    assert media.creation_flags() == media.CREATE_NO_WINDOW
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_media.py -v`
Expected: FAIL import.

- [ ] **Step 3: Implémenter**

`config.py` : constantes déplacées telles quelles de l'ancien `main.py` (`WHISPER_MODEL`, `WHISPER_OPTIONS`, `OPENROUTER_*`, `VIDEO_EXTENSIONS`, `PROMPT_EXTENSIONS`), plus :

```python
APP_NAME = "EcoTranscribe Desktop"
APP_SLUG = "ecotranscribe"
FLAVOR = "lite"
PROJECT_URL = "https://github.com/ecotranscribe/ecotranscribe"
WHISPER_NOT_INSTALLED_MESSAGE = (
    "Moteur Whisper non installé. Lancez `uv sync --extra whisper`."
)
WHISPER_LITE_REASON = "Moteur Whisper local non inclus dans l'édition lite."
KEY_MISSING_MESSAGE = (
    "Clé OpenRouter manquante. Saisissez-la ou définissez OPENROUTER_API_KEY."
)
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma", ".aiff", ".aif"})
```

`media.py` :

```python
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

def creation_flags() -> int:
    return CREATE_NO_WINDOW if sys.platform == "win32" else 0

@dataclass(frozen=True)
class MediaProcessResult:
    returncode: int
    stdout: str
    stderr: str

def resolve_tool(name: str) -> str | None:
    filename = name + ".exe" if sys.platform == "win32" and not name.endswith(".exe") else name
    candidates: list[Path] = []
    env_dir = os.environ.get("ECOTRANSCRIBE_FFMPEG_DIR")
    if env_dir:
        candidates.append(Path(env_dir) / filename)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "bin" / filename)
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        candidates.append(
            Path(sys.executable).resolve().parents[1] / "Resources" / "bin" / filename
        )
    for candidate in candidates:
        if candidate.is_file() and (sys.platform == "win32" or os.access(candidate, os.X_OK)):
            return str(candidate)
    found = shutil.which(filename)
    return found

def _require_tool(name: str) -> str:
    path = resolve_tool(name)
    if not path:
        raise MediaToolMissingError(name)
    return path
```

`run_media` : `Popen(args, stdout=PIPE, stderr=PIPE, text=True, encoding="utf-8", errors="replace", creationflags=creation_flags(), shell=False)`. Boucle `communicate(timeout=0.1)` ; à chaque itération `cancel.raise_if_cancelled()` ; annulation → `terminate()`, `communicate(timeout=2)`, sinon `kill()`, puis lever `CancelledError`. Timeout global → même arrêt puis `TranscribeError("Le traitement du média a pris trop de temps.", detail=" ".join(args))`.

Les fonctions média utilisent `_require_tool` et `run_media` :
- durée : `ffprobe -v quiet -print_format json -show_format <path>`, parse `format.duration`, `None` si échec.
- vidéo : extension d'abord, sinon `-show_streams` et `codec_type == "video"`.
- extraction : `ffmpeg -y -i <src> -vn -acodec pcm_s16le -ar 16000 -ac 1 <dst>`.
- silences : `-af silencedetect=noise=-35dB:d=0.4 -f null -`, regex `silence_start`/`silence_end` sur stderr, zip.
- chunk : `-ss`, `-t`, `-ac 1 -ar 16000 -c:a libmp3lame -b:a 64k`.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_media.py -v`
Expected: PASS (le test d'annulation tue le process en < 4 s).

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core/config.py src/ecotranscribe/core/media.py tests/test_media.py
git commit -m "feat(core): add cancellable ffmpeg/ffprobe media layer"
```

### Task 6 : Moteur OpenRouter

**Files:**
- Create: `src/ecotranscribe/core/engines/__init__.py`
- Create: `src/ecotranscribe/core/engines/base.py`
- Create: `src/ecotranscribe/core/engines/openrouter.py`
- Move/Rewrite: `tests/test_openrouter.py`

**Interfaces:**
- Consumes: `media`, `models`, `errors`, `config`.
- Produces: `TranscriptionEngine` (Protocol), `OpenRouterEngine`, `build_payload`, `choose_cut_points`, `offset_segments`, `normalize_context_bias`.

- [ ] **Step 1: Tests (conserver les cas existants + ajouts)**

Cas obligatoires :
1. `choose_cut_points` : silence proche, fallback fixe, silence hors fenêtre, queue < 60 s supprimée, queue = 60 s conservée, silence créant une queue courte ignoré.
2. `offset_segments` : décalage + renumérotation, entrée non mutée.
3. `normalize_context_bias` : espaces compactés.
4. `build_payload` : `language="fr"` présent ; `language=None` absent ; prompt Mistral → `provider.options.mistral.context_bias` ; prompt non-Mistral → aucun `provider` ; `input_audio.format == "mp3"` ; `timestamp_granularities == ["segment"]`.
5. Coût : deux réponses `usage.cost` 0.1 et absent → `0.1` ; toutes absentes → `None` ; `usage.cost=0` → `0.0`.
6. Progression : 2500 s, chunk 1200 → 3 tranches (0–1200, 1200–2400, 2400–2500) ; `ProgressUpdate` émis après chaque tranche avec `current` croissant, `total=2500`, `detail="Tranche i/3"`.
7. Annulation entre tranches : le faux transport annule le token pendant la première requête ; `CancelledError` levée, une seule requête HTTP.
8. Payload sans clé : l'adaptateur ne lit jamais `OPENROUTER_API_KEY` ; la clé vient de `request.api_key`.

Faux média injecté par monkeypatch de `ecotranscribe.core.engines.openrouter.media` :

```python
def fake_extract(src, dst, **kwargs): dst.write_bytes(b"wav")
def fake_duration(path, **kwargs): return 2500.0
def fake_silences(path, **kwargs): return []
def fake_chunk(src, dst, start, duration, **kwargs): dst.write_bytes(b"mp3")
```

`OpenRouterEngine(http_post=fake, sleep=lambda s: None)`.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_openrouter.py -v`
Expected: FAIL imports.

- [ ] **Step 3: Implémenter**

`engines/base.py` :

```python
class TranscriptionEngine(Protocol):
    provider: Provider

    def availability(self) -> EngineAvailability: ...

    def transcribe(
        self,
        request: TranscribeRequest,
        *,
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
        cancel: CancelToken,
    ) -> EngineResult: ...
```

`openrouter.py` points exacts :
- `build_payload(model, audio_b64, language, prompt)` :

```python
payload = {
    "model": model,
    "input_audio": {"data": audio_b64, "format": "mp3"},
    "response_format": "verbose_json",
    "timestamp_granularities": ["segment"],
}
if language is not None:
    payload["language"] = language
if prompt and model.startswith("mistralai/"):
    payload["provider"] = {
        "options": {"mistral": {"context_bias": normalize_context_bias(prompt)}}
    }
```

- `_post_openrouter(payload, api_key, *, url, cancel, sleep, on_log, timeout=90, max_retries=3)` :
  - `Authorization: Bearer <key>` ; jamais loggée.
  - retries 429/500/502/503/529, backoff 1/2/4 s via `_interruptible_sleep` (tranches 0,2 s, `cancel.raise_if_cancelled()`).
  - 504/524 → `_ChunkTimeout`.
  - 401 → `EngineUnavailableError("Clé OpenRouter refusée. Vérifiez-la dans vos réglages OpenRouter.", detail=message)`.
  - 402 → `TranscribeError("Crédit OpenRouter insuffisant.", detail=message)`.
  - autre HTTP → `TranscribeError(f"OpenRouter a renvoyé une erreur (HTTP {code}).", detail=message)`.
  - `URLError/OSError` épuisé → `TranscribeError("OpenRouter est injoignable. Vérifiez votre connexion.", detail=str(exc))`.
  - JSON invalide → `TranscribeError("Réponse OpenRouter invalide.", detail=str(exc))`.
  - Vérifier `cancel.raise_if_cancelled()` avant la requête, après la réponse et avant chaque retry.
- `OpenRouterEngine` :
  - `transcribe` : valide `api_key` non vide, `TemporaryDirectory(prefix="ecotranscribe-")`, extraction, durée (erreur `"Impossible de lire la durée du média. Le fichier est peut-être corrompu."`), silences, cuts, tranches.
  - Émet `extracting` (`total=None`, `detail="Extraction audio"`), `detecting_silences` (`total=None`), `transcribing` (`total=duration`, `detail=f"Tranche {i}/{n}"`), avec `current` = fin de tranche après chaque tranche.
  - Prompt non-Mistral → `on_log("warning", "Prompt ignoré : context_bias n'est supporté que par les modèles Mistral.")`.
  - Coût cumulé `None` si aucune réponse ne fournit `usage.cost`.
  - Segments : conversion en `Segment`, offset, IDs globaux renumérotés à partir de 1 (writer ignore l'ID mais le contrat doit être cohérent). `text` = `" ".join(texts).strip()`.
  - Fallback segment unique si `segments` absent : `Segment(1, start, end, text)`.
  - Timeout de tranche : découpage récursif en deux si durée > 60 s ; sinon `TranscribeError("OpenRouter a mis trop de temps à transcrire ce passage.", detail=...)`.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_openrouter.py -v`
Expected: PASS, aucun réseau.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core/engines tests/test_openrouter.py
git commit -m "feat(core): port OpenRouter engine with progress and cancellation"
```

### Task 7 : Moteur Whisper optionnel

**Files:**
- Create: `src/ecotranscribe/core/engines/whisper.py`
- Create: `tests/test_whisper_engine.py`

**Interfaces:**
- Produces: `WhisperEngine`, `whisper_availability()`.
- Consumes: `media`, `config`, callback API.

- [ ] **Step 1: Tests**

- `whisper_availability()` retourne indisponible avec `WHISPER_NOT_INSTALLED_MESSAGE` quand `importlib.util.find_spec("whisper")` est `None` (monkeypatch).
- La conversion frames → secondes : 100 frames = 1,0 s.
- Le shim tqdm appelle `on_progress` avec `phase="transcribing"`.
- Les tests réels Whisper sont marqués `@pytest.mark.skipif(find_spec("whisper") is None, ...)` et n'exécutent pas de modèle (ils testent seulement les options construites).

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_whisper_engine.py -v`
Expected: FAIL import.

- [ ] **Step 3: Implémenter**

- `whisper_availability()` : `find_spec("whisper")` et `find_spec("torch")` ; raison exacte `WHISPER_NOT_INSTALLED_MESSAGE`, détail technique.
- `WhisperEngine.transcribe` :
  - import `whisper` localement.
  - vidéo → extraction temporaire (`extracting`).
  - `get_device()` (MPS/CUDA/CPU) déplacé ici ; import torch local.
  - `whisper.load_model(model, device=device)`, options `WHISPER_OPTIONS` + `fp16`, `language` seulement si non `None`, prompt → `initial_prompt` + `carry_initial_prompt=True`.
  - Remplace `sys.modules["whisper.transcribe"].tqdm` par un shim dont `tqdm(...).update(n)` émet `ProgressUpdate("transcribing", current_s, total_audio_s, "Transcription Whisper")`, conversion `n * 160 / 16000`.
  - Vérifie l'annulation avant chargement, après chargement, après transcription.
  - Segments → `Segment(id=i+1, start, end, text)` ; `language = result.get("language") or request.language` ; coût `None` ; durée du média.
  - Erreurs `RuntimeError`/`OSError` → `TranscribeError("La transcription Whisper a échoué.", detail=str(exc))`.
  - Nettoyage du WAV temporaire dans `finally`.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_whisper_engine.py -v`
Expected: PASS ou SKIP si l'extra n'est pas installé.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core/engines/whisper.py tests/test_whisper_engine.py
git commit -m "feat(core): add optional Whisper engine via whisper extra"
```

### Task 8 : TranscribeService

**Files:**
- Create: `src/ecotranscribe/core/service.py`
- Create: `tests/test_service.py`

**Interfaces:**
- Produces: `TranscribeService(engines: Mapping[Provider, TranscriptionEngine])`, `transcribe(request, *, on_progress=None, on_log=None, cancel=None) -> TranscribeResult`.
- Consumes: `writers`, `outputs`, `errors`.

- [ ] **Step 1: Tests**

Faux moteur :

```python
class FakeEngine:
    provider = Provider.OPENROUTER

    def __init__(self, result=None, *, cancel=False, error=None, updates=()):
        self.result = result or EngineResult(
            text="Bonjour",
            segments=(Segment(1, 0.5, 1.5, "Bonjour"),),
            language="fr",
            cost_usd=0.000123,
            duration_s=1.5,
        )
        self.cancel = cancel
        self.error = error
        self.updates = updates
        self.calls = 0

    def availability(self):
        return EngineAvailability(True)

    def transcribe(self, request, *, on_progress=None, on_log=None, cancel):
        self.calls += 1
        for update in self.updates:
            on_progress(update)
        if self.cancel:
            cancel.cancel()
        if self.error:
            raise self.error
        return self.result
```

Cas :
1. succès : fichiers SRT/TXT exacts, `output_paths`, `cost_usd`, `provider`, `model` ; progression `validating` → updates moteur → `writing` → `done`.
2. `input_path` absent → `InvalidRequestError("Le fichier sélectionné n'existe plus.")`.
3. `output_dir` absent → `InvalidRequestError("Le dossier de sortie n'existe pas.")`.
4. formats vides → `InvalidRequestError("Choisissez au moins un format de sortie.")`.
5. provider absent du mapping → `EngineUnavailableError`.
6. `availability().available=False` → `EngineUnavailableError(reason)`.
7. OpenRouter sans clé → `EngineUnavailableError(KEY_MISSING_MESSAGE)` et moteur non appelé.
8. existant + `overwrite=False` → `OutputExistsError`, moteur non appelé, contenu existant intact.
9. existant + `overwrite=True` → remplacé.
10. moteur annule puis retourne → `CancelledError`, aucun fichier.
11. moteur lève `TranscribeError` → propagation, aucun fichier.
12. sortie identique à l'entrée (`.srt` en entrée) → `InvalidRequestError`.
13. échec d'écriture du TXT après SRT → `TranscribeError` dont `detail` contient le SRT déjà écrit.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_service.py -v`
Expected: FAIL import.

- [ ] **Step 3: Implémenter**

Ordre strict :

```python
def transcribe(self, request, *, on_progress=None, on_log=None, cancel=None):
    cancel = cancel or CancelToken()
    self._emit(on_progress, ProgressUpdate("validating", detail="Validation"))
    self._validate(request)
    engine = self._engines.get(request.provider)
    if engine is None:
        raise EngineUnavailableError("Ce moteur n'est pas disponible dans cette édition.")
    availability = engine.availability()
    if not availability.available:
        raise EngineUnavailableError(
            availability.reason or "Moteur indisponible.", availability.detail
        )
    if request.provider is Provider.OPENROUTER and not (request.api_key or "").strip():
        raise EngineUnavailableError(KEY_MISSING_MESSAGE)
    paths = output_paths(request.input_path, request.output_dir, request.formats)
    existing = existing_outputs(paths)
    if existing and not request.overwrite:
        raise OutputExistsError(existing)
    cancel.raise_if_cancelled()
    result = engine.transcribe(
        request, on_progress=on_progress, on_log=on_log, cancel=cancel
    )
    cancel.raise_if_cancelled()
    self._emit(on_progress, ProgressUpdate("writing", detail="Écriture des fichiers"))
    written: list[Path] = []
    try:
        for fmt, path in zip((OutputFormat.SRT, OutputFormat.TXT), paths):
            (write_srt if fmt is OutputFormat.SRT else write_txt)(path, result.segments)
            written.append(path)
    except OSError as exc:
        detail = f"{exc}"
        if written:
            detail += "\nFichiers déjà écrits : " + ", ".join(map(str, written))
        raise TranscribeError("Impossible d'écrire les fichiers de sortie.", detail) from exc
    self._emit(on_progress, ProgressUpdate("done", detail="Terminé"))
    return TranscribeResult(
        output_paths=tuple(written), text=result.text, segments=result.segments,
        language=result.language, cost_usd=result.cost_usd,
        provider=request.provider, model=request.model,
        duration_s=result.duration_s,
    )
```

Validation :
- `input_path.exists()`, `is_file()`, `os.access(R_OK)`.
- `output_dir.exists()`, `is_dir()`, `os.access(W_OK | X_OK)`.
- `request.formats` non vide.
- modèle `.strip()` non vide.
- `request.prompt_text` est déjà du texte ; pas de lecture.
- Vérifier que chaque chemin de sortie diffère de `input_path`.
- `output_paths` avant l'existence.
- `zip` doit suivre l'ordre de `paths` : construire `(fmt, path)` avec `[(OutputFormat.SRT, srt), ...]` filtré ; ne pas supposer que `paths` contient toujours 2 éléments.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/core/service.py tests/test_service.py
git commit -m "feat(core): add TranscribeService orchestration"
```

### Task 9 : CLI `ecotranscribe`

**Files:**
- Create: `src/ecotranscribe/cli.py`
- Create: `tests/test_cli.py`
- Delete: any remaining old imports.

**Interfaces:**
- Produces: `main(argv: Sequence[str] | None = None) -> None`.
- Consumes: `TranscribeService`, `OpenRouterEngine`, `WhisperEngine`, `outputs`, `prompts`, `rich`.

- [ ] **Step 1: Tests**

- `main(["--help"])` lève `SystemExit(0)` et contient `ecotranscribe`/`--provider`.
- `main([str(missing)])` code 1, message « n'existe pas ».
- `--provider whisper` avec `WhisperEngine.availability` monkeypatchée indisponible → stderr contient `uv sync --extra whisper`, code 1.
- Confirmation d'écrasement refusée → code 0, aucun fichier modifié, message « conservés ».
- Un faux service monkeypatché reçoit `provider=openrouter`, `model` par défaut, `api_key` depuis `OPENROUTER_API_KEY`, `prompt_text` détecté.
- Le coût `None` affiche « Coût indisponible » ; `0.000123` affiche `0.000123`.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL import/entry point.

- [ ] **Step 3: Implémenter**

- `argparse` : `prog="ecotranscribe"`, `input`, `--provider` (`whisper` défaut, `openrouter`), `--model`.
- Résolution `input.resolve()` ; prompt via `resolve_prompt`.
- Clé : `os.environ.get("OPENROUTER_API_KEY")` pour openrouter ; jamais loggée.
- Modèle par défaut : `WHISPER_MODEL` ou `OPENROUTER_MODEL`.
- Existence des sorties : `output_paths` + boucle `confirm_overwrite(path)` (comportement actuel : une question par fichier) ; refus → message et `return` (code 0).
- `overwrite=True` si toutes confirmées.
- Engines : `{Provider.OPENROUTER: OpenRouterEngine(), Provider.WHISPER: WhisperEngine()}`.
- `RichReporter` :
  - `Progress(SpinnerColumn, TextColumn("{task.fields[phase]}"), BarColumn, TaskProgressColumn, TextColumn("[dim]audio[/dim] {task.fields[audio_pos]}"), TimeElapsedColumn, TimeRemainingColumn)`.
  - `on_progress` : si `total is None` → `update(total=None, completed=0, phase=detail or label)` ; sinon `completed=current, total=total, phase=f"{label} — {detail}"`, `audio_pos=f"{_fmt_seconds(current)} / {_fmt_seconds(total)}"`.
  - `on_log` : `warning`/`error` → `console.print(f"[yellow]{message}[/yellow]")`.
- `KeyboardInterrupt` : `cancel.cancel()`, message, code 130.
- `TranscribeError` : `print(f"Erreur : {exc.user_message}", file=sys.stderr)`, détail optionnel sur stderr, code 1.
- Succès : afficher SRT/TXT, puis coût pour openrouter (`$%.6f` ou « Coût indisponible »).
- Ne jamais appeler `sys.exit` ailleurs que `main`/`argparse`.

- [ ] **Step 4: Tests au vert**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke réel Phase 0**

```bash
uv sync --extra dev
uv run ecotranscribe --provider whisper data/sample.mp4
# attendu : message extra manquant, code 1

uv sync --extra whisper --extra dev
uv run ecotranscribe --provider whisper --model tiny data/sample.mp4
# attendu : SRT/TXT Whisper générés (ou vérifier le code de sortie et les fichiers)

mkdir -p /tmp/eco-smoke && cp data/sample.mp4 /tmp/eco-smoke/
cd /tmp/eco-smoke
uv run --project /Users/geoffrey/forge/ecotranscribe ecotranscribe --provider openrouter sample.mp4
# attendu : sample.srt/sample.txt, progression rich, coût affiché
cmp sample.srt /Users/geoffrey/forge/ecotranscribe/data/sample.srt
cmp sample.txt /Users/geoffrey/forge/ecotranscribe/data/sample.txt
```

Note : `OPENROUTER_API_KEY` est déjà dans l'environnement ; ne jamais l'afficher. Le smoke Whisper `tiny` peut télécharger le modèle ; si le téléchargement est indisponible, exécuter au minimum `--provider whisper` avec un modèle déjà en cache et consigner le blocage.

- [ ] **Step 6: Commit Phase 0**

```bash
git add src/ecotranscribe/cli.py tests/test_cli.py
git commit -m "feat(cli): add ecotranscribe command on core service"
```

---

## Phase 1 — GUI lite PySide6

### Task 10 : Settings, keyring, logging

**Files:**
- Create: `src/ecotranscribe/gui/__init__.py`
- Create: `src/ecotranscribe/gui/settings.py`
- Create: `src/ecotranscribe/gui/logging_setup.py`
- Create: `tests/gui/test_settings.py`

**Interfaces:**
- Produces: `AppSettings`, `KeyStore` (Protocol), `KeyringStore`, `MemoryStore`, `EnvStore`, `configure_logging() -> Path`, `log_file_path() -> Path`, `config_dir() -> Path`.

- [ ] **Step 1: Tests**

- `AppSettings` sur `QSettings(ini temporaire, IniFormat)` : défauts (`model`, `language="fr"`, formats `["srt","txt"]`, remember True, log False, recent `[]`) ; écriture/relecture ; `add_recent_model` déduplique, place en tête, garde 5.
- `MemoryStore` : get/set/delete ; `EnvStore` lit `OPENROUTER_API_KEY` sans le logger.
- `KeyringStore` avec `keyring` monkeypatché en échec : `get()` retourne le fallback env et ne lève pas ; `set()` propage pour que la GUI affiche un avertissement.
- `configure_logging(tmp_path)` : fichier UTF-8, rotation configurée `maxBytes=1_000_000`, `backupCount=3` ; aucune clé journalisée par les helpers.
- `log_file_path()` sous `QStandardPaths.AppDataLocation`, dossier créé.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_settings.py -v`
Expected: FAIL import.

- [ ] **Step 3: Implémenter**

- `AppSettings` clés exactes de §9.5. `geometry` en `QByteArray`/bytes, `last_input_dir` défaut `QStandardPaths.HomeLocation`, `output_dir` défaut `""`, `formats` normalisés en set de `"srt"`/`"txt"`, `recent_models` liste de str.
- `KeyringStore` : service `ecotranscribe`, utilisateur `openrouter`, import `keyring` local, `get()` keyring → `OPENROUTER_API_KEY`, erreurs attrapées et `logger.warning("Trousseau indisponible...")` sans secret.
- `MemoryStore` et `EnvStore` (fallback tests/dev).
- `logging_setup.py` :
  ```python
  QCoreApplication.setOrganizationName("ecotranscribe")
  QCoreApplication.setApplicationName("EcoTranscribe Desktop")
  ```
  `RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")`, format `%(asctime)s %(levelname)s %(name)s: %(message)s`, idempotent (ne pas ajouter deux handlers).
- Ne jamais journaliser le contenu de `api_key_edit`.

- [ ] **Step 4: Tests au vert**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_settings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/gui tests/gui/test_settings.py
git commit -m "feat(gui): add settings, keyring and rotating logs"
```

### Task 11 : Disponibilité, diagnostic, dialogues, worker

**Files:**
- Create: `src/ecotranscribe/gui/availability.py`
- Create: `src/ecotranscribe/gui/dialogs.py`
- Create: `src/ecotranscribe/gui/worker.py`
- Create: `tests/gui/test_diagnostic.py`
- Create: `tests/gui/test_worker.py`

**Interfaces:**
- Produces: `whisper_availability() -> EngineAvailability`, `openrouter_availability() -> EngineAvailability`, `collect_diagnostic() -> dict`, `QtDialogService`, `DialogService` Protocol, `TranscribeWorker`.
- Worker signals : `progress(object)`, `log(str)`, `finished(object)`, `failed(str, str)`, `cancelled()` ; slot `run()`.

- [ ] **Step 1: Tests**

- `collect_diagnostic()` contient toutes les clés §9.7, `flavor == "lite"`, `whisper_available is False`, `openrouter_model` par défaut, `config_dir`/`log_file` absolus.
- `whisper_availability()` indisponible avec raison « non inclus dans l'édition lite ».
- `TranscribeWorker` avec faux service : `progress`/`log` transmis ; succès → `finished(result)` ; `TranscribeError` → `failed(user_message, detail)` ; `CancelledError` → `cancelled()` ; exception inattendue → `failed("La transcription a échoué.", str(exc))`.
- Aucun `QMessageBox` dans le worker ; `QtDialogService` est le seul à créer des dialogues.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_diagnostic.py tests/gui/test_worker.py -v`
Expected: FAIL imports.

- [ ] **Step 3: Implémenter**

- `collect_diagnostic()` : champs exacts §9.7 ; `ffmpeg_path`/`ffprobe_path` via `resolve_tool` ; versions via `tool_version` ; `qt` via `PySide6.QtCore.qVersion()` ; `commit`/`build_date` via env ou `ecotranscribe_build_info` optionnel ; `frozen=bool(getattr(sys,"frozen",False))` ; `whisper_reason=WHISPER_LITE_REASON`.
- `QtDialogService` :
  - `confirm_overwrite(paths)` : `QMessageBox.warning` avec liste, boutons `Écraser`/`Annuler`, défaut Annuler, retourne `True` seulement pour Écraser.
  - `show_error` : `QMessageBox.critical`, `setDetailedText(detail)`.
  - `show_info`, `confirm_close_while_running`.
- `TranscribeWorker` : `QObject`, `@Slot()` `run`, garde `CancelToken`, mappe les exceptions, émet uniquement des signaux.

- [ ] **Step 4: Tests au vert**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_diagnostic.py tests/gui/test_worker.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/gui/availability.py src/ecotranscribe/gui/dialogs.py src/ecotranscribe/gui/worker.py tests/gui
git commit -m "feat(gui): add availability, diagnostics, dialogs and worker"
```

### Task 12 : Fenêtre principale — construction et état

**Files:**
- Create: `src/ecotranscribe/gui/main_window.py`
- Create: `tests/gui/test_main_window.py`
- Create: `tests/gui/conftest.py`

**Interfaces:**
- Produces: `MainWindow(settings: AppSettings, key_store: KeyStore, dialogs: DialogService, service_factory=None)`.
- Méthodes stables pour les tests : `set_input_path(path)`, `on_worker_progress(update)`, `on_worker_log(text)`, `on_worker_finished(result)`, `on_worker_failed(message, detail)`, `on_worker_cancelled()`, `start_transcription()`, `cancel_transcription()`, `save_settings()`.
- Widgets nommés : `input_edit`, `browse_button`, `provider_openrouter`, `provider_whisper`, `whisper_reason`, `model_combo`, `language_combo`, `prompt_path_label`, `prompt_preview`, `output_edit`, `srt_checkbox`, `txt_checkbox`, `api_key_edit`, `remember_checkbox`, `delete_key_button`, `launch_button`, `cancel_button`, `progress_bar`, `phase_label`, `elapsed_label`, `log_view`, `log_toggle`, `status_label`, `cost_label`, `open_folder_button`, `source_error`, `output_error`, `formats_error`, `api_error`.

- [ ] **Step 1: Tests construction**

- La fenêtre se construit sans réseau (aucun service créé) ; taille minimale ≥ 760×640.
- OpenRouter coché, Whisper décoché + désactivé ; raison contient « édition lite » ; lien « Édition full ».
- `launch_button` désactivé sans fichier.
- Modèle par défaut `mistralai/voxtral-mini-transcribe-3-0` ; langue `fr` ; SRT/TXT cochés.
- Clé chargée depuis `MemoryStore` dans un champ `EchoMode.Password` ; placeholder `OPENROUTER_API_KEY`.
- Avertissement cloud visible et contient « envoyé à OpenRouter ».
- Raccourcis : `Ctrl+O`, `Ctrl+Entrée`, `Échap` (vérifier les `QShortcut`/`QAction`).
- Drag & drop activé.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_main_window.py -v`
Expected: FAIL import.

- [ ] **Step 3: Implémenter la construction**

- `QMainWindow`, `setMinimumSize(760, 640)`, geometry restaurée.
- En-tête : titre + badge « Édition lite — OpenRouter » + bouton « À propos ».
- Groupes avec labels associés (`setBuddy`) : Source, Fournisseur, Modèle, Langue, Prompt, Sortie, Clé API, Actions/Progression/Résultat.
- `QFormLayout` pour modèle/langue ; `QHBoxLayout` pour fichiers/dossiers.
- Combos : modèles récents + défaut ; langues `fr, Auto (None), en, es, de, it, pt, nl` via `addItem(label, code)`.
- Prompt : chemin, aperçu 2 lignes (`QLabel`, `setWordWrap`), « Éditer… », « Effacer ».
- Clé : `QLineEdit.Password`, bouton œil optionnel non requis, « Mémoriser » coché, « Supprimer ».
- Progression : `QProgressBar` (texte visible), labels phase/audio/élapsed, `QToolButton` checkable « Journal », `QPlainTextEdit` read-only.
- Résultat : statut, coût, « Ouvrir le dossier » désactivé.
- Drag & drop : `setAcceptDrops(True)`, `dragEnterEvent` accepte une URL locale, `dropEvent` appelle `set_input_path`.
- `Ctrl+O` → parcourir, `Ctrl+Entrée` → `start_transcription`, `Échap` → annuler sinon fermer.
- `set_input_path` : valide le fichier, met à jour le dossier de sortie si `_output_dir_user_set` est faux, résout le prompt, met à jour l'aperçu, active Lancer. Une nouvelle sélection réinitialise le prompt édité.
- « Effacer » vide le prompt courant sans toucher au fichier.
- Édition du prompt : `QDialog` + `QPlainTextEdit`, accepte → met à jour `_prompt_text` et l'aperçu.
- `save_settings()` : géométrie, dernier dossier, dossier de sortie, modèle, langue, formats, remember, log, modèles récents. Jamais la clé.
- « À propos » : version, flavour, commit, date, licence MIT, URL source, mention notices tierces.

- [ ] **Step 4: Tests au vert**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_main_window.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/gui/main_window.py tests/gui
git commit -m "feat(gui): build main window layout and settings state"
```

### Task 13 : Cycle de tâche, progression, annulation, résultat

**Files:**
- Modify: `src/ecotranscribe/gui/main_window.py`
- Extend: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: `TranscribeWorker`, `TranscribeService`, `CancelToken`, `output_paths`, `existing_outputs`.

- [ ] **Step 1: Tests**

- `start_transcription` sans fichier → `source_error` visible, aucun service.
- Dossier de sortie non inscriptible → `output_error`, aucun service.
- Aucun format → `formats_error`.
- Clé absente → `api_error` avec le message exact §9.8.
- Modèle vide → erreur inline.
- Existant + `confirm_overwrite=False` → dialogue appelé avec les chemins, statut « conservés », aucun service, fichiers intacts.
- Existant + `True` → request `overwrite=True`.
- Progression déterminée `ProgressUpdate("transcribing", 30, 120, "Tranche 1/4")` : barre `maximum()==1000`, `value()==250`, label contient `25 %`, `00:30`, `02:00`, `Tranche 1/4` ; avec `_task_started` reculé de 10 s, `elapsed_label` contient `ETA`.
- `total=None` ou `total=0` → barre indéterminée (`maximum()==0`).
- Phase `writing` → annuler désactivé, barre indéterminée.
- `on_worker_log` ajoute au journal ; un log contenant la clé ne doit jamais être produit par la fenêtre.
- Annuler pendant la tâche → `token.is_cancelled()`, libellé « Annulation en cours… », bouton désactivé.
- `on_worker_finished` → statut terminé, chemins, coût 6 décimales ou « Coût indisponible », bouton dossier actif, contrôles réactivés.
- `on_worker_failed` → `dialogs.show_error` appelé avec message, détail, journal ; contrôles réactivés.
- `on_worker_cancelled` → statut annulé, pas de fichiers, contrôles réactivés.
- Fermeture pendant tâche : `confirm_close_while_running` demandé ; refus → fenêtre reste ; acceptation → annulation puis fermeture après signal terminal.
- Réglages persistés/rechargés entre deux fenêtres ; clé absente du fichier INI.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_main_window.py -v`
Expected: FAIL sur les nouveaux cas.

- [ ] **Step 3: Implémenter**

- `_validate_form()` : erreurs inline, retourne `(input_path, output_dir, formats, api_key)` ou `None`. Ne fait aucun appel réseau ni ffprobe.
- `_resolve_api_key()` : champ non vide > `key_store.get()` (keyring/env).
- « Mémoriser » : si coché et clé saisie, `key_store.set()` dans try/except, log warning non bloquant + message inline ; ne jamais logger la clé.
- « Supprimer » : `key_store.delete()`, champ vidé, erreurs non bloquantes.
- `start_transcription` :
  1. validation ;
  2. prompt = `_prompt_text.strip() or None` ;
  3. `output_paths`/`existing_outputs` ;
  4. écrasement via `dialogs.confirm_overwrite` ;
  5. construction `TranscribeRequest(provider=OPENROUTER, overwrite=True, api_key=...)` ;
  6. `save_settings()`, `add_recent_model` ;
  7. `_start_worker(request)`.
- `_start_worker` : `CancelToken`, `service_factory(request)` (défaut : `TranscribeService({OPENROUTER: OpenRouterEngine()})`), `QThread`, moveToThread, connexions, `thread.started.connect(worker.run)`, signaux terminaux → `thread.quit`, `thread.finished` → cleanup et `_thread=None`.
- `_set_running(True/False)` : désactive tous les champs, Lancer désactivé, Annuler actif ; en écriture Annuler désactivé ; en fin réactive.
- `on_worker_progress` :
  - mapping phases : `validation`, `extraction audio`, `détection des silences`, `transcription`, `écriture des fichiers`, `terminé`.
  - déterminé si `total` non nul et > 0 : `setRange(0,1000)`, `setValue(round(1000*current/total))`, `setFormat(f"{pct} %")`, label `f"{phase} — {fmt(current)} / {fmt(total)} — {detail}"`.
  - indéterminé sinon : `setRange(0,0)`, `setFormat("")`.
  - `_last_progress = update`, `_task_started` initialisé au lancement.
  - `QTimer` 1 s : `elapsed_label` `Temps écoulé : mm:ss` + `ETA : mm:ss` si fraction > 0 et total connu.
  - `writing` → Annuler désactivé + barre indéterminée.
- `on_worker_log(text)` : append au `QPlainTextEdit`, scroll en bas ; `logger.info("%s", text)`.
- `on_worker_finished(result)` : statut, `output_paths` joints, coût, bouton dossier (dossier du premier chemin), `_set_running(False)`.
- `on_worker_failed(message, detail)` : statut « Échec », détail + extrait journal (max 4000 derniers caractères), `dialogs.show_error("Transcription impossible", message, detail)`, réactivation.
- `on_worker_cancelled()` : statut « Transcription annulée. », réactivation, aucun fichier.
- `closeEvent` : si tâche active, demander ; refus → `ignore()` ; acceptation → `cancel_transcription()`, `_close_when_done=True`, `ignore()` puis fermer sur signal terminal.

- [ ] **Step 4: Tests au vert**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ecotranscribe/gui/main_window.py tests/gui
git commit -m "feat(gui): wire worker, progress, cancellation and results"
```

### Task 14 : Entrée desktop, diagnostic CLI, smoke GUI

**Files:**
- Create: `src/ecotranscribe/gui/app.py`
- Create: `tests/gui/test_app.py`

**Interfaces:**
- Produces: `main(argv: Sequence[str] | None = None) -> int`; `--diagnose`, `--diagnose-output PATH`.

- [ ] **Step 1: Tests**

- `main(["--diagnose", "--diagnose-output", str(out)])` sans afficher de fenêtre, code 0 si ffmpeg/ffprobe trouvés, JSON relu avec `flavor=lite`, `whisper_available=False`.
- Si `resolve_tool` monkeypatché à `None`, code 1 mais JSON écrit.
- `--diagnose` n'instancie pas `MainWindow` (monkeypatch `MainWindow` pour lever si appelé).
- `QApplication` : `setApplicationName("EcoTranscribe Desktop")`, `setOrganizationName("ecotranscribe")`.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_app.py -v`
Expected: FAIL import.

- [ ] **Step 3: Implémenter**

- `parse_args` avec `argparse` : `--diagnose`, `--diagnose-output`.
- Diagnostic : `configure_logging()` d'abord, `collect_diagnostic`, JSON UTF-8 `ensure_ascii=False, indent=2`, `print` seulement si `sys.stdout is not None`, écriture du fichier (parents créés), `return 0/1`.
- Mode normal : `QApplication(sys.argv)`, nom/org, `configure_logging()`, `AppSettings(QSettings())`, `KeyringStore()`, `QtDialogService()`, `MainWindow(...)`, `show()`, `exec()`.
- `if __name__ == "__main__": raise SystemExit(main())`.
- Aucune requête réseau au démarrage.

- [ ] **Step 4: Tests au vert**

Run: `QT_QPA_PLATFORM=offscreen uv run pytest tests/gui -v`
Expected: PASS.

- [ ] **Step 5: Smoke GUI**

```bash
uv sync --extra gui --extra dev
QT_QPA_PLATFORM=offscreen uv run ecotranscribe-desktop --diagnose --diagnose-output /tmp/eco-diag.json
uv run python -c "import json; d=json.load(open('/tmp/eco-diag.json')); assert d['flavor']=='lite' and d['whisper_available'] is False; print(d['ffmpeg_version'])"
```

Puis script jetable (non commité) qui construit `MainWindow`, `set_input_path` sur une copie de `data/sample.mp4`, remplit la clé depuis l'environnement, lance, attend `on_worker_finished`, vérifie les SRT/TXT et enregistre une capture `window.grab().save("/tmp/eco-gui.png")` sous `QT_QPA_PLATFORM=offscreen`. Vérifier que la capture n'est pas vide. Consigner la limite : pas de test Gatekeeper visuel.

- [ ] **Step 6: Commit Phase 1**

```bash
git add src/ecotranscribe/gui tests/gui
git commit -m "feat(gui): add desktop entry point and diagnostics"
```

---

## Phase 2 — Packaging macOS ad-hoc et CI macOS

### Task 15 : Lock et fetch ffmpeg

**Files:**
- Create: `packaging/ffmpeg.lock.json`
- Create: `packaging/fetch_ffmpeg.py`
- Create: `tests/test_fetch_ffmpeg.py`
- Modify: `.gitignore` (`vendor/`, `packaging/build/`)

**Interfaces:**
- Produces: `fetch_ffmpeg.py --target <target>` → `vendor/ffmpeg/<target>/{ffmpeg,ffprobe}` exécutables ; vérification SHA256 ; `detect_target()`.

- [ ] **Step 1: Lock exact**

```json
{
  "version": 1,
  "targets": {
    "darwin-arm64": {
      "sources": [
        {
          "url": "https://www.osxexperts.net/ffmpeg902arm.zip",
          "sha256": "07e00300593799005b060c03a99fe648b1edda0f30c36b0c1adafe8e3247e586",
          "type": "zip",
          "files": {"ffmpeg": "ffmpeg"}
        },
        {
          "url": "https://www.osxexperts.net/ffprobe902arm.zip",
          "sha256": "ec72b6a81dac926bd568681d766b74943701f291ac3cdbb387829dc2a275a00b",
          "type": "zip",
          "files": {"ffprobe": "ffprobe"}
        }
      ]
    },
    "darwin-x64": {
      "sources": [
        {
          "url": "https://www.osxexperts.net/ffmpeg80intel.zip",
          "sha256": "2d24d22db78c87f394a5822867acd5c5dc5e762cd261a44bd26923f3a5af3e07",
          "type": "zip",
          "files": {"ffmpeg": "ffmpeg"}
        },
        {
          "url": "https://www.osxexperts.net/ffprobe80intel.zip",
          "sha256": "0b6576104a95c1b39d4939e2df86f8f7cf1d55287ff57da48777d94605d12feb",
          "type": "zip",
          "files": {"ffprobe": "ffprobe"}
        }
      ]
    },
    "win-x64": {
      "sources": [
        {
          "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-05-12-48/ffmpeg-n9.0.2-47-gb204e94e90-win64-lgpl-9.0.zip",
          "sha256": "9d557b1a39b9db87ff9b5cf7a4c2c3fd42e5f3d21c68714b2dd6e104bd48f715",
          "type": "zip",
          "files": {
            "ffmpeg": "ffmpeg-n9.0.2-47-gb204e94e90-win64-lgpl-9.0/bin/ffmpeg.exe",
            "ffprobe": "ffmpeg-n9.0.2-47-gb204e94e90-win64-lgpl-9.0/bin/ffprobe.exe"
          }
        }
      ]
    },
    "linux-x64": {
      "sources": [
        {
          "url": "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-05-12-48/ffmpeg-n9.0.2-47-gb204e94e90-linux64-lgpl-9.0.tar.xz",
          "sha256": "06ef07fd9252e42ae0d5cd5d47c7b39db3e4264a792a2e4dbf56b36d3cbce5f5",
          "type": "tar.xz",
          "files": {
            "ffmpeg": "ffmpeg-n9.0.2-47-gb204e94e90-linux64-lgpl-9.0/bin/ffmpeg",
            "ffprobe": "ffmpeg-n9.0.2-47-gb204e94e90-linux64-lgpl-9.0/bin/ffprobe"
          }
        }
      ]
    }
  }
}
```

- [ ] **Step 2: Tests**

- `detect_target()` mappe `darwin/arm64`, `darwin/x86_64`, `win32`, `linux`.
- Archive ZIP et TAR.XZ synthétiques dans `tmp_path` avec un lock de test : extraction correcte, `chmod 755` sous POSIX.
- SHA256 erroné → `SystemExit`/`ValueError` avec message, aucun binaire écrit.
- Membre absent → erreur claire.
- Le script ne télécharge pas si le binaire cible existe déjà (idempotence).

- [ ] **Step 3: Lancer (échec attendu)**

Run: `uv run pytest tests/test_fetch_ffmpeg.py -v`
Expected: FAIL import.

- [ ] **Step 4: Implémenter**

- Téléchargement `urllib.request.urlopen` avec timeout 300, lecture par blocs, écriture dans `vendor/downloads/<sha256>.<ext>`.
- Vérification SHA256 avant extraction ; suppression du cache corrompu.
- Extraction ZIP via `zipfile.ZipFile.read(member)` ; TAR.XZ via `tarfile.open(..., "r:xz")` et `extractfile(member)`. Écriture directe vers `dest/name`, pas d'extraction arbitraire.
- `chmod(0o755)` sous POSIX.
- `--target` par défaut `detect_target()`, `--dest` par défaut `vendor/ffmpeg/<target>`, `--lock` par défaut `packaging/ffmpeg.lock.json`.
- Aucune URL « latest ».

- [ ] **Step 5: Vérifier le fetch réel macOS arm64**

Run: `uv run python packaging/fetch_ffmpeg.py --target darwin-arm64`
Expected: `vendor/ffmpeg/darwin-arm64/ffmpeg` et `ffprobe` exécutables, `file` → `Mach-O 64-bit executable arm64`, `-version` OK. `vendor/` ignoré par git.

- [ ] **Step 6: Commit**

```bash
git add packaging/ffmpeg.lock.json packaging/fetch_ffmpeg.py tests/test_fetch_ffmpeg.py .gitignore
git commit -m "build: add pinned ffmpeg download and verification"
```

### Task 16 : Icônes, spec PyInstaller, signature, DMG, notice

**Files:**
- Create: `packaging/icon.svg`
- Create: `packaging/make_icons.py`
- Create: `packaging/pyinstaller.spec`
- Create: `packaging/sign_macos.sh`
- Create: `packaging/make_dmg.sh`
- Create: `packaging/render_notices.py`
- Create: `packaging/notices/LIRE-MOI-macOS.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `dist/EcoTranscribe Desktop.app`, DMG/ZIP nommés `ecotranscribe-desktop-lite-macos-<arch>-0.2.0.*`, `LIRE-MOI-macOS.txt`, SHA256.

- [ ] **Step 1: Icône**

`packaging/icon.svg` : carré 1024, fond `#0F766E`, glyphe micro/onde blanche, pas de texte. `make_icons.py` utilise `PySide6.QtSvg.QSvgRenderer` + `QImage` (offscreen) pour générer :
- `packaging/build/icon.png` 1024 ;
- `packaging/build/EcoTranscribe.iconset/` (`icon_16x16.png` … `icon_512x512@2x.png`) puis `iconutil -c icns` sous macOS ;
- `packaging/build/icon.ico` via Pillow (sizes 16–256) ;
- ne rien générer dans `dist/`.

- [ ] **Step 2: Spec PyInstaller**

- `Analysis([src/ecotranscribe/gui/app.py], pathex=[src], datas=[...], hiddenimports=collect_submodules("keyring.backends"), excludes=[...], noarchive=False)`.
- `datas` : `LICENSE`, `THIRD_PARTY_NOTICES.md`, `README.md`, `vendor/ffmpeg/<target>/ffmpeg` et `ffprobe` → `bin` ; notices.
- `EXE(..., name="EcoTranscribe Desktop", console=False, icon=...)`, `COLLECT(..., name="EcoTranscribe Desktop")`.
- macOS : `BUNDLE(..., name="EcoTranscribe Desktop.app", bundle_identifier="app.ecotranscribe.desktop", info_plist={"LSMinimumSystemVersion": "12.0", "NSHighResolutionCapable": True, "CFBundleShortVersionString": "0.2.0", "CFBundleVersion": "0.2.0", "LSApplicationCategoryType": "public.app-category.productivity"})`.
- Exclusions : `whisper`, `torch`, `torchaudio`, `torchvision`, `numba`, `tiktoken`, `triton`, `tensorboard`, `pytest`, `tkinter`.
- `TARGET` via env `ECOTRANSCRIBE_TARGET` sinon `detect_target()` ; vérifier que les binaires ffmpeg existent avant `Analysis`.

- [ ] **Step 3: Signature et DMG**

`sign_macos.sh "dist/EcoTranscribe Desktop.app"` :
```bash
find "$APP" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -111 \) -print0 |
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q 'Mach-O'; then
    codesign --force --sign - --timestamp=none "$f"
  fi
done
codesign --force --sign - --timestamp=none "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
spctl --assess --type execute --verbose=4 "$APP" || true
```
- Signer aussi `Contents/Resources/bin/ffmpeg` et `ffprobe` (couvert par `-perm -111`).
- Ne pas appliquer `xattr` au build.

`make_dmg.sh` :
- staging `packaging/build/dmg/` avec app, `ln -s /Applications`, `LIRE-MOI-macOS.txt`, `LICENSE`, `THIRD_PARTY_NOTICES.md`.
- Notice rendue par `render_notices.py --os macos --version 0.2.0 --arch <arch> --commit <sha> --build-date <UTC> --tag <tag> --output ...` depuis le template §11.3.
- `hdiutil create -volname "EcoTranscribe Desktop" -srcfolder staging -ov -format UDZO <dmg>`.
- `ditto -c -k --keepParent "dist/EcoTranscribe Desktop.app" <zip>` puis ajouter la notice/licences au ZIP via `ditto` d'un staging ou `zip -r`.
- `shasum -a 256` sur DMG/ZIP.

- [ ] **Step 4: Build et vérifications locales**

```bash
uv sync --extra gui --extra dev
uv run python packaging/make_icons.py
uv run python packaging/fetch_ffmpeg.py --target darwin-arm64
uv run pyinstaller --noconfirm packaging/pyinstaller.spec
bash packaging/sign_macos.sh "dist/EcoTranscribe Desktop.app"
"dist/EcoTranscribe Desktop.app/Contents/MacOS/EcoTranscribe Desktop" --diagnose --diagnose-output /tmp/eco-mac-diag.json
bash packaging/make_dmg.sh 0.2.0 arm64 "$(git rev-parse --short HEAD)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" v0.2.0
```

Vérifier :
- `codesign --verify --deep --strict --verbose=2` code 0.
- `spctl --assess` rejeté (attendu) et script ne casse pas.
- JSON : `flavor=lite`, `whisper_available=false`, chemins ffmpeg dans `Contents/Resources/bin` ou `_internal/bin`, versions non nulles.
- `hdiutil attach` du DMG : app, lien Applications, notice, LICENSE, notices tierces présents.
- `find "dist/EcoTranscribe Desktop" -iname '*torch*' -o -iname '*whisper*'` → aucun hit hors nom d'app.
- `du -sh` ≤ 450 Mo ; DMG/ZIP ≤ 300 Mo. Consigner les tailles réelles.
- `unzip -l` du ZIP contient la notice.

- [ ] **Step 5: Commit Phase 2**

```bash
git add packaging .gitignore
git commit -m "build: add PyInstaller onedir, ad-hoc signing and macOS DMG"
```

### Task 17 : Workflow CI macOS

**Files:**
- Create: `.github/workflows/build-lite.yml`

**Interfaces:**
- Produces: jobs macOS arm64/x64 avec tests, fetch ffmpeg, build, signature, DMG/ZIP, diagnostic, vérification torch/whisper, artefacts et fragments SHA256.

- [ ] **Step 1: Workflow initial**

Déclencheurs `tags: v*`, `workflow_dispatch`. Matrice macOS seulement dans cette phase :

```yaml
permissions:
  contents: read
strategy:
  fail-fast: false
  matrix:
    include:
      - os: macos-14
        target: darwin-arm64
        arch: arm64
      - os: macos-13
        target: darwin-x64
        arch: x64
```

Étapes : checkout, `astral-sh/setup-uv@v5`, `uv python install 3.13`, `uv sync --extra gui --extra dev`, `uv run pytest`, cache `vendor/ffmpeg` clé `hashFiles('packaging/ffmpeg.lock.json')`, fetch, icons, pyinstaller, sign, DMG, diagnose, checks, SHA256, upload-artifact. `ECOTRANSCRIBE_TARGET` exporté.

- [ ] **Step 2: Validation syntaxique**

Run: `uv run python - <<'PY'\nimport yaml; yaml.safe_load(open('.github/workflows/build-lite.yml'))\nprint('ok')\nPY` (si PyYAML absent, `uv run --with pyyaml ...`).
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build-lite.yml
git commit -m "ci: build and sign macOS lite artifacts"
```

---

## Phase 3 — Packaging Windows et Linux

### Task 18 : Windows ZIP portable + Inno Setup optionnel

**Files:**
- Create: `packaging/windows.iss`
- Create: `packaging/notices/LIRE-MOI-Windows.txt`
- Create: `packaging/make_windows.ps1`
- Modify: `.github/workflows/build-lite.yml`

**Interfaces:**
- Produces: `ecotranscribe-desktop-lite-windows-x64-0.2.0.zip`, `...-setup.exe` optionnel, notice.

- [ ] **Step 1: Script PowerShell**

- Staging `packaging/build/windows/EcoTranscribe Desktop/` : copier `dist/EcoTranscribe Desktop/*`, notice rendue, LICENSE, notices tierces.
- `Compress-Archive -Path "<staging>/EcoTranscribe Desktop" -DestinationPath "<zip>"`.
- Vérifier que le ZIP contient `EcoTranscribe Desktop/EcoTranscribe Desktop.exe`, `_internal/`, `bin/ffmpeg.exe`, `bin/ffprobe.exe`, notice.
- Inno : `packaging/windows.iss` avec `AppId={{...}}`, `AppName=EcoTranscribe Desktop`, `AppVersion={#MyAppVersion}`, `DefaultDirName={autopf}\\EcoTranscribe Desktop`, `OutputBaseFilename=ecotranscribe-desktop-lite-windows-x64-{#MyAppVersion}-setup`, `Compression=lzma2`, `ArchitecturesAllowed=x64compatible`, `PrivilegesRequired=lowest` (install per-user, pas admin), `SetupIconFile=packaging\\build\\icon.ico`, `[Files] Source: "dist\\EcoTranscribe Desktop\\*"; DestDir: "{app}"; Flags: recursesubdirs`.
- L'installeur est optionnel : CI `continue-on-error: true` sur l'étape Inno ; le ZIP reste l'artefact principal.

- [ ] **Step 2: Notice Windows**

Reprendre §11.4 avec `{version}`, `{build_date}`, `{project_url}`.

- [ ] **Step 3: CI**

- Ajouter `windows-latest` (`target=win-x64`).
- `choco install innosetup --no-progress -y` puis `iscc` (chemin `C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe`).
- Diagnostic : `Start-Process -FilePath "dist\\EcoTranscribe Desktop\\EcoTranscribe Desktop.exe" -ArgumentList "--diagnose","--diagnose-output","diag.json" -Wait -PassThru`, vérifier `ExitCode == 0` et JSON.
- Vérifier absence console : lancer l'exe avec `--diagnose` via `Start-Process` et s'assurer qu'il n'y a pas de fenêtre console (le mode `--windowed` est vérifié par la spec PyInstaller ; consigner).
- Vérification torch/whisper dans `_internal`.
- SHA256 via `Get-FileHash -Algorithm SHA256`, format `hash  filename`.

- [ ] **Step 4: Validation locale**

Sur macOS : `pwsh` peut être absent. Vérifier au minimum la syntaxe du `.iss` (revue) et que le script PowerShell n'a pas d'erreur évidente ; exécution réelle en CI. Consigner le blocage local.

- [ ] **Step 5: Commit**

```bash
git add packaging/windows.iss packaging/notices/LIRE-MOI-Windows.txt packaging/make_windows.ps1 .github/workflows/build-lite.yml
git commit -m "build: add Windows portable ZIP and optional Inno Setup installer"
```

### Task 19 : Linux AppImage + tar.gz

**Files:**
- Create: `packaging/make_appimage.sh`
- Create: `packaging/notices/LIRE-MOI-Linux.txt`
- Modify: `.github/workflows/build-lite.yml`

**Interfaces:**
- Produces: `ecotranscribe-desktop-lite-linux-x64-0.2.0.AppImage`, `...tar.gz`, notice.

- [ ] **Step 1: Script AppImage**

- Constantes : `APPIMAGETOOL_URL=https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage`, `APPIMAGETOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`.
- Télécharger, vérifier, `chmod +x`, exécuter avec `--appimage-extract-and-run` (pas de FUSE requis).
- `AppDir/usr/bin/EcoTranscribe Desktop` (copie du onedir complet dans `usr/bin`), `AppDir/usr/share/applications/ecotranscribe.desktop`, `AppDir/ecotranscribe.png` (icône 256), `AppDir/.DirIcon`, `AppRun` :
  ```sh
  #!/bin/sh
  HERE="$(dirname "$(readlink -f "$0")")"
  exec "$HERE/usr/bin/EcoTranscribe Desktop" "$@"
  ```
- `ARCH=x86_64 VERSION=0.2.0 appimagetool AppDir <output>`.
- tar.gz : staging `EcoTranscribe Desktop/` + notice + licences, `tar -czf`.
- `sha256sum`.

- [ ] **Step 2: CI**

- Ajouter `ubuntu-22.04` (`target=linux-x64`).
- `sudo apt-get update && sudo apt-get install -y libfuse2` (si nécessaire ; `--appimage-extract-and-run` reste le fallback).
- `QT_QPA_PLATFORM=offscreen` pour pytest et diagnostic.
- Diagnostic via AppImage : `./<AppImage> --appimage-extract-and-run --diagnose --diagnose-output diag.json` ; vérifier `flavor=lite`, chemins ffmpeg dans le bundle, code 0.
- Vérifier absence torch/whisper.
- `sha256sum`.

- [ ] **Step 3: Validation locale**

Sous macOS, vérifier les scripts avec `bash -n packaging/make_appimage.sh` et revue ; pas d'exécution Linux. CI réelle en Phase 4. Consigner.

- [ ] **Step 4: Commit Phase 3**

```bash
git add packaging/make_appimage.sh packaging/notices/LIRE-MOI-Linux.txt .github/workflows/build-lite.yml
git commit -m "build: add Linux AppImage and tar.gz artifacts"
```

---

## Phase 4 — Release, documentation, acceptation

### Task 20 : Release GitHub et SHA256

**Files:**
- Modify: `.github/workflows/build-lite.yml`
- Create: `docs/release-notes-0.2.0.md`

**Interfaces:**
- Produces: `SHA256SUMS.txt` global, release `v0.2.0` avec tous les assets.

- [ ] **Step 1: Job release**

- `needs: build`, `if: startsWith(github.ref, 'refs/tags/v')`, `permissions: contents: write`.
- Télécharger tous les artefacts dans `release/`.
- Concaténer les fragments `SHA256SUMS-*.txt` en `SHA256SUMS.txt`, trier, vérifier qu'il y a une ligne par fichier publié (hors SHA256SUMS).
- `softprops/action-gh-release@v2` avec `files: release/*` et `body_path: docs/release-notes-0.2.0.md`, `tag_name`.
- Le job build ne doit pas exiger de secret.

- [ ] **Step 2: Release notes**

Reprendre §11.7 avec les noms d'artefacts exacts et les instructions de vérification par OS.

- [ ] **Step 3: Validation**

- `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/build-lite.yml'))"`.
- Vérifier que le workflow n'a pas de `pull_request_target`, pas de secret, `contents: write` uniquement sur le job release.
- Consigner : release réelle impossible sans push/tag (interdiction de push).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/build-lite.yml docs/release-notes-0.2.0.md
git commit -m "ci: publish lite artifacts and SHA256SUMS on tag"
```

### Task 21 : Documentation et licences

**Files:**
- Create: `LICENSE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Create: `docs/install-macos-unsigned.md`
- Create: `docs/distribution.md`
- Rewrite: `README.md`

- [ ] **Step 1: README**

Sections : présentation lite/full, nommage, fonctionnalités, prérequis (`uv`, ffmpeg pour dev), installation :
```bash
uv sync --extra gui
uv sync --extra whisper
uv sync --extra gui --extra whisper   # build full futur
```
CLI (`uv run ecotranscribe`, providers, modèle), GUI (`uv run ecotranscribe-desktop`), clé `OPENROUTER_API_KEY`, keyring, confidentialité (audio envoyé à OpenRouter), prompts, découpage, build local, tests, distribution, macOS non notarié, licence MIT. Ne pas mentionner de version web.

- [ ] **Step 2: Notice macOS**

Copier le contenu rendu §11.3 avec `{version}`, `{build_date}`, `{commit}`, `{tag}`, `{arch}`, `{project_url}` (valeurs 0.2.0 / commit final / v0.2.0). Expliquer Gatekeeper, `xattr`, SHA256, différence ad-hoc/notarisé, données.

- [ ] **Step 3: Distribution**

`docs/distribution.md` : build local, `fetch_ffmpeg.py`, icônes, PyInstaller, signature inside-out, vérification `codesign`, `spctl` attendu, DMG, ZIP, Windows, Linux, AppImage, SHA256, checklist release, tailles cibles, variables `ECOTRANSCRIBE_TARGET`, `ECOTRANSCRIBE_COMMIT`, `ECOTRANSCRIBE_BUILD_DATE`.

- [ ] **Step 4: Notices tierces**

- Projet MIT (texte LICENSE).
- PySide6/Qt LGPLv3 : lien licence, obligation de fournir le texte et la possibilité de relinker (PyInstaller onedir permet le remplacement des bibliothèques Qt ; documenter).
- Python PSF.
- keyring MIT.
- ffmpeg : macOS builds OSXExperts GPLv2+ (source `https://www.osxexperts.net/`, configuration `--enable-gpl`, version 9.0.2 arm64 / 8.0 x64) ; Windows/Linux BtbN LGPLv2.1+ version 9.0.2, URL de release et source. Inclure les textes `packaging/notices/COPYING.GPLv2.txt` et `COPYING.LGPLv2.1.txt` (téléchargés depuis ffmpeg.org au moment du build ou commités comme textes de licence — les textes de licence sont des sources, pas des binaires).
- Notices PyInstaller (GPL avec exception de bootloader) et autres dépendances si nécessaire.

- [ ] **Step 5: SECURITY / CHANGELOG / LICENSE**

- `SECURITY.md` : binaire non notarié, vérification SHA256, signalement privé, pas de secret dans les issues, audio tiers.
- `CHANGELOG.md` : 0.2.0 — renommage, GUI lite, writers internes, extra whisper, packaging macOS ad-hoc, Windows/Linux, docs.
- `LICENSE` MIT, copyright « EcoTranscribe contributors ».

- [ ] **Step 6: Vérification docs**

Run: `grep -R "whisper-transcribe\|uv run transcribe" README.md docs` → aucun hit hors spec historique/CHANGELOG.
Run: `grep -R "OPENROUTER_API_KEY" README.md docs` → uniquement documentation, aucune valeur.

- [ ] **Step 7: Commit**

```bash
git add README.md LICENSE THIRD_PARTY_NOTICES.md SECURITY.md CHANGELOG.md docs packaging/notices
git commit -m "docs: document EcoTranscribe lite usage, packaging and licences"
```

### Task 22 : Acceptation finale

**Files:** aucun nouveau fichier sauf corrections.

- [ ] **Step 1: Suite complète**

```bash
uv sync --extra gui --extra whisper --extra dev
QT_QPA_PLATFORM=offscreen uv run pytest -v
```
Expected: PASS. Les tests GUI tournent offscreen. Les tests réseau sont absents ou mockés.

- [ ] **Step 2: Vérifications de nommage**

```bash
uv run python -c "import ecotranscribe, importlib.metadata as m; print(ecotranscribe.__version__, m.version('ecotranscribe'))"
uv run ecotranscribe --help
uv run ecotranscribe-desktop --diagnose --diagnose-output /tmp/eco-final-diag.json
grep -R "whisper_transcribe\|transcribe-gui" src tests pyproject.toml || true
```

- [ ] **Step 3: Packaging macOS final**

Refaire build/sign/DMG, vérifier codesign, diagnostic, absence torch/whisper, tailles, SHA256. Consigner les valeurs.

- [ ] **Step 4: Checklist spec**

Reprendre §12.5 point par point. Pour chaque point non exécutable localement (Windows/Linux/Gatekeeper visuel/release réelle), indiquer « préparé, vérifié en CI uniquement » ou « non testé localement » avec la raison. Ne pas cocher un point non observé.

- [ ] **Step 5: Commit final**

```bash
git status --short
git add -A
git commit -m "chore: finalize EcoTranscribe desktop lite 0.2.0"
```

Ne pas push. Ne pas commiter `dist/`, `build/`, `vendor/`, `.venv/`, `data/`.

---

## Self-review du plan

- Couverture spec : nommage/extras (T1), contrat cœur (T2), writers (T3), prompts/outputs (T4), média (T5), OpenRouter (T6), Whisper (T7), service (T8), CLI (T9), GUI (T10–T14), ffmpeg/PyInstaller/signature/DMG (T15–T16), CI macOS (T17), Windows (T18), Linux (T19), release/SHA (T20), docs (T21), acceptation (T22).
- Pas de placeholder : chaque tâche a fichiers, interfaces, tests et commandes. Les valeurs de hash ffmpeg et appimagetool sont réelles.
- Cohérence des types : `TranscribeRequest.provider` accepte `str` puis normalise en `Provider` ; `output_paths` ordre SRT/TXT ; `EngineResult` → `TranscribeResult` ; worker reçoit `TranscribeResult`.
- Points spec non implémentés volontairement : build full, notarisation, mises à jour, multi-fichiers, traduction, etc. (hors périmètre §16).
