"""CLI `ecotranscribe`, adaptateur rich du service commun."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .core.config import (
    OPENROUTER_MODEL,
    WHISPER_MODEL,
)
from .core.engines.openrouter import OpenRouterEngine
from .core.engines.whisper import WhisperEngine
from .core.errors import TranscribeError
from .core.formatting import format_seconds
from .core.models import (
    CancelToken,
    OutputFormat,
    ProgressUpdate,
    Provider,
    TranscribeRequest,
)
from .core.outputs import existing_outputs, output_paths
from .core.prompts import resolve_prompt
from .core.service import TranscribeService

_PHASE_LABELS = {
    "validating": "Validation",
    "extracting": "Extraction audio",
    "detecting_silences": "Détection des silences",
    "transcribing": "Transcription",
    "writing": "Écriture des fichiers",
    "done": "Terminé",
}


def confirm_overwrite(path: Path) -> bool:
    """Demande confirmation avant d'écraser un fichier existant."""
    try:
        answer = (
            input(
                f"  ⚠️  '{path.name}' existe déjà. Écraser ? [o/N] "
            )
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("o", "oui", "y", "yes")


class RichReporter:
    """Rend les ProgressUpdate du cœur dans une barre rich déterminée/indéterminée."""

    def __init__(self) -> None:
        self.progress = Progress(
            SpinnerColumn("dots", style="cyan"),
            TextColumn("[bold cyan]{task.fields[phase]}[/bold cyan]"),
            BarColumn(
                bar_width=None,
                complete_style="cyan",
                finished_style="green",
            ),
            TaskProgressColumn(),
            TextColumn(
                "  [dim]audio[/dim] [bold cyan]{task.fields[audio_pos]}[/bold cyan]"
            ),
            TextColumn("  [dim]écoulé[/dim] "),
            TimeElapsedColumn(),
            TextColumn("  [dim]ETA[/dim] "),
            TimeRemainingColumn(),
            expand=True,
        )
        self.task_id = None

    def __enter__(self) -> "RichReporter":
        self.progress.__enter__()
        self.task_id = self.progress.add_task(
            "transcription",
            total=None,
            phase="Validation",
            audio_pos="",
        )
        return self

    def __exit__(self, *args: object) -> None:
        self.progress.__exit__(*args)

    def on_progress(self, update: ProgressUpdate) -> None:
        if self.task_id is None:
            return
        label = _PHASE_LABELS.get(update.phase, update.phase)
        detail = update.detail.strip()
        phase = f"{label} — {detail}" if detail and detail != label else label
        if update.total is None or update.total <= 0:
            self.progress.update(
                self.task_id,
                total=None,
                completed=0,
                phase=phase,
                audio_pos="",
            )
            return
        self.progress.update(
            self.task_id,
            total=update.total,
            completed=min(update.current, update.total),
            phase=phase,
            audio_pos=(
                f"{format_seconds(update.current)} / "
                f"{format_seconds(update.total)}"
            ),
        )

    def on_log(self, level: str, message: str) -> None:
        if level in ("warning", "error"):
            style = "red" if level == "error" else "yellow"
            self.progress.console.print(f"[{style}]{message}[/{style}]")
        elif message:
            self.progress.console.print(f"[dim]{message}[/dim]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecotranscribe",
        description="Transcription audio/vidéo avec Whisper ou OpenRouter.",
    )
    parser.add_argument(
        "input", type=Path, help="Fichier audio ou vidéo à transcrire"
    )
    parser.add_argument(
        "--provider",
        choices=("whisper", "openrouter"),
        default="whisper",
        help="Moteur de transcription (défaut : whisper)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Modèle à utiliser (défaut : medium pour Whisper, "
            f"{OPENROUTER_MODEL} pour OpenRouter)"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    input_path = args.input.expanduser().resolve()

    if not input_path.exists():
        print(
            f"Erreur : le fichier '{input_path}' n'existe pas.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not input_path.is_file():
        print(
            f"Erreur : '{input_path}' n'est pas un fichier régulier.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    provider = Provider(args.provider)
    model = args.model or (
        WHISPER_MODEL if provider is Provider.WHISPER else OPENROUTER_MODEL
    )
    prompt_path, prompt_text = resolve_prompt(input_path)
    if prompt_path is not None:
        print(
            f"\n📄 Prompt initial trouvé : '{prompt_path.name}' "
            f"({len(prompt_text or '')} caractères)"
        )

    output_dir = input_path.parent
    formats = frozenset({OutputFormat.SRT, OutputFormat.TXT})
    paths = output_paths(input_path, output_dir, formats)
    existing = existing_outputs(paths)
    overwrite = False
    for path in existing:
        if not confirm_overwrite(path):
            print(
                "\nTranscription annulée : les fichiers existants sont "
                "conservés."
            )
            return
    if existing:
        overwrite = True

    request = TranscribeRequest(
        input_path=input_path,
        provider=provider,
        model=model,
        language="fr",
        prompt_text=prompt_text,
        output_dir=output_dir,
        formats=formats,
        overwrite=overwrite,
        api_key=(
            os.environ.get("OPENROUTER_API_KEY")
            if provider is Provider.OPENROUTER
            else None
        ),
    )
    engines = {
        Provider.OPENROUTER: OpenRouterEngine(),
        Provider.WHISPER: WhisperEngine(),
    }
    service = TranscribeService(engines)
    cancel = CancelToken()
    reporter = RichReporter()

    try:
        with reporter:
            result = service.transcribe(
                request,
                on_progress=reporter.on_progress,
                on_log=reporter.on_log,
                cancel=cancel,
            )
    except KeyboardInterrupt:
        cancel.cancel()
        print("\nTranscription annulée.", file=sys.stderr)
        raise SystemExit(130)
    except TranscribeError as exc:
        print(f"\nErreur : {exc.user_message}", file=sys.stderr)
        if exc.detail:
            print(f"Détail : {exc.detail}", file=sys.stderr)
        raise SystemExit(1)

    print("\n✅ Transcription terminée !")
    for output_path in result.output_paths:
        print(f"   📄 {output_path}")
    if provider is Provider.OPENROUTER:
        if result.cost_usd is None:
            print("   💵 Coût OpenRouter : Coût indisponible")
        else:
            print(f"   💵 Coût OpenRouter : ${result.cost_usd:.6f}")


if __name__ == "__main__":
    main()
