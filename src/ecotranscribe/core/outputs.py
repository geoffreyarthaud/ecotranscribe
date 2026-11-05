"""Calcul et vérification des chemins de sortie."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .models import OutputFormat

_OUTPUT_SUFFIXES = {OutputFormat.SRT: ".srt", OutputFormat.TXT: ".txt"}


def output_paths(
    input_path: Path,
    output_dir: Path,
    formats: frozenset[OutputFormat],
) -> tuple[Path, ...]:
    """Retourne les chemins SRT puis TXT demandés, dans un ordre stable."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    return tuple(
        output_dir / f"{input_path.stem}{_OUTPUT_SUFFIXES[fmt]}"
        for fmt in (OutputFormat.SRT, OutputFormat.TXT)
        if fmt in formats
    )


def existing_outputs(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Retourne les chemins déjà présents, sans en modifier aucun."""
    return tuple(Path(path) for path in paths if Path(path).exists())
