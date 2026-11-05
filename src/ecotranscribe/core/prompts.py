"""Découverte et lecture des fichiers prompt associés à une source."""

from __future__ import annotations

from pathlib import Path

from .config import PROMPT_EXTENSIONS
from .errors import InvalidRequestError


def find_prompt_file(input_path: Path) -> Path | None:
    """Cherche `.prompt.md`, puis `.prompt.txt`, puis `.prompt`."""
    input_path = Path(input_path)
    parent = input_path.parent
    stem = input_path.stem
    for extension in PROMPT_EXTENSIONS:
        candidate = parent / f"{stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def read_prompt(path: Path) -> str:
    """Lit un prompt UTF-8 et le strippe."""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise InvalidRequestError(
            "Impossible de lire le fichier prompt.", detail=str(exc)
        ) from exc


def resolve_prompt(input_path: Path) -> tuple[Path | None, str | None]:
    """Retourne le prompt auto-détecté et son texte, ou `(None, None)`."""
    path = find_prompt_file(input_path)
    if path is None:
        return None, None
    text = read_prompt(path)
    return path, text or None
