#!/usr/bin/env python3
"""
Transcription d'un fichier audio ou vidéo avec OpenAI Whisper.

Usage:
    transcribe <fichier_audio_ou_video>

Sorties :
    <racine>.srt  — sous-titres avec horodatage
    <racine>.txt  — transcription en texte brut

Fichier prompt optionnel :
    Si <racine>.prompt.md / <racine>.prompt.txt / <racine>.prompt existe,
    son contenu est passé à Whisper via l'option initial_prompt.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import torch
import whisper
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from whisper.utils import get_writer

# ── Configuration Whisper ──────────────────────────────────────────────────────

WHISPER_MODEL = "medium"

WHISPER_OPTIONS: dict = {
    "language": "fr",
    "temperature": (
        0.0,
        0.2,
        0.4,
    ),  # glouton en priorité, fallback léger si segment dégradé
    "compression_ratio_threshold": 2.8,  # seuil actif (défaut Whisper : 2.4, légèrement assoupli)
    # fp16 : défini dynamiquement selon le device (voir get_device())
    # max_context n'existe pas dans l'API Python openai-whisper (spécifique à whisper.cpp)
}

# ── Constantes Whisper pour la conversion frames → secondes ───────────────────
# Whisper découpe l'audio en fenêtres mel : 1 frame = HOP_LENGTH / SAMPLE_RATE = 10 ms
_WHISPER_HOP_LENGTH: int = 160
_WHISPER_SAMPLE_RATE: int = 16_000


# ── Device ─────────────────────────────────────────────────────────────────────


def get_device() -> str:
    """
    Sélectionne le meilleur device disponible :
      MPS  (Apple Silicon — GPU intégré via Metal)
      CUDA (NVIDIA)
      CPU  (fallback)
    """
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


# ── Extensions ─────────────────────────────────────────────────────────────────

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        ".m4v",
        ".ts",
        ".mts",
        ".m2ts",
        ".3gp",
        ".ogv",
        ".mxf",
        ".f4v",
    }
)

# Ordre de priorité pour la recherche du fichier prompt
PROMPT_EXTENSIONS: list[str] = [".prompt.md", ".prompt.txt", ".prompt"]


# ── Helpers généraux ───────────────────────────────────────────────────────────


def _fmt_seconds(total_s: float) -> str:
    """Formate une durée en m:ss ou h:mm:ss."""
    total_s = max(0.0, total_s)
    h = int(total_s // 3600)
    m = int((total_s % 3600) // 60)
    s = int(total_s % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def get_media_duration(path: Path) -> Optional[float]:
    """Retourne la durée du média en secondes via ffprobe. None si indisponible."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration_str = data.get("format", {}).get("duration")
            if duration_str:
                return float(duration_str)
    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ):
        pass
    return None


def is_video_file(path: Path) -> bool:
    """
    Détermine si le fichier est une vidéo.
    Vérifie d'abord l'extension, puis interroge ffprobe pour les cas ambigus.
    """
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return True

    # Vérification via ffprobe (détecte les fichiers mal nommés)
    try:
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return any(s.get("codec_type") == "video" for s in data.get("streams", []))
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    return False


def extract_audio(video_path: Path, output_path: Path) -> None:
    """Extrait la piste audio d'un fichier vidéo via ffmpeg (WAV 16 kHz mono)."""
    cmd = [
        "ffmpeg",
        "-y",  # écraser sans demander
        "-i",
        str(video_path),
        "-vn",  # pas de flux vidéo
        "-acodec",
        "pcm_s16le",  # PCM 16 bits
        "-ar",
        "16000",  # 16 kHz — taux optimal pour Whisper
        "-ac",
        "1",  # mono
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg a échoué lors de l'extraction audio :\n{result.stderr}"
        )


def find_prompt_file(input_path: Path) -> Optional[Path]:
    """
    Cherche un fichier de prompt dont la racine est identique à input_path.
    Priorité : .prompt.md > .prompt.txt > .prompt
    """
    parent = input_path.parent
    stem = input_path.stem  # ex. "enregistrement" pour "enregistrement.mp3"

    for ext in PROMPT_EXTENSIONS:
        candidate = parent / (stem + ext)
        if candidate.is_file():
            return candidate

    return None


def confirm_overwrite(path: Path) -> bool:
    """Demande confirmation avant d'écraser un fichier existant. Retourne True si accordé."""
    try:
        answer = (
            input(f"  ⚠️  '{path.name}' existe déjà. Écraser ? [o/N] ").strip().lower()
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("o", "oui", "y", "yes")


# ── Barre de progression rich ──────────────────────────────────────────────────


class _WhisperRichProgress:
    """
    Remplace tqdm dans whisper.transcribe pour afficher une barre rich.

    Whisper mesure sa progression interne en frames mel :
        1 frame mel = HOP_LENGTH / SAMPLE_RATE = 160 / 16 000 = 10 ms
    On convertit ces frames en position audio (h:mm:ss) pour un affichage lisible.
    """

    def __init__(self, total: int = 0, total_audio_s: float = 0.0, **_ignored) -> None:
        self._total = total
        # Si ffprobe n'a pas pu donner la durée, on l'estime depuis les frames
        self._audio_total_s = total_audio_s or (
            total * _WHISPER_HOP_LENGTH / _WHISPER_SAMPLE_RATE
        )
        self._n = 0

        total_label = _fmt_seconds(self._audio_total_s)
        self._bar = Progress(
            SpinnerColumn("dots", style="cyan"),
            TextColumn("[bold cyan]Transcription[/bold cyan]  "),
            BarColumn(bar_width=None, complete_style="cyan", finished_style="green"),
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
        self._task_id = self._bar.add_task(
            "transcription",
            total=self._total,
            audio_pos=f"00:00 / {total_label}",
        )

    # ── Context manager ────────────────────────────────────────────────────────

    def __enter__(self) -> "_WhisperRichProgress":
        self._bar.__enter__()
        return self

    def __exit__(self, *args) -> None:
        self._bar.__exit__(*args)

    # ── Interface tqdm ─────────────────────────────────────────────────────────

    def update(self, n: int = 1) -> None:
        self._n += n
        current_s = self._n * _WHISPER_HOP_LENGTH / _WHISPER_SAMPLE_RATE
        total_label = _fmt_seconds(self._audio_total_s)
        self._bar.update(
            self._task_id,
            advance=n,
            audio_pos=f"{_fmt_seconds(current_s)} / {total_label}",
        )

    # Stubs de compatibilité tqdm (appelés par certaines versions de Whisper)
    def set_postfix(self, **_) -> None:
        pass

    def set_postfix_str(self, *_, **__) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeTqdmModule:
    """
    Faux module tqdm injecté dans whisper.transcribe.

    Whisper appelle `tqdm.tqdm(total=…, unit=…, disable=…)`.
    On ignore le kwarg `disable` pour toujours afficher notre barre rich.
    """

    def __init__(self, total_audio_s: float) -> None:
        self._total_audio_s = total_audio_s

    def tqdm(self, *_args, total: int = 0, **_kwargs) -> _WhisperRichProgress:
        return _WhisperRichProgress(total=total, total_audio_s=self._total_audio_s)


def _transcribe_with_progress(
    model,
    audio_path: Path,
    total_audio_s: float,
    **options,
) -> dict:
    """
    Lance model.transcribe() en substituant le module tqdm de whisper.transcribe
    par _FakeTqdmModule pour afficher une barre de progression rich.

    verbose=False est requis pour que Whisper active son chemin tqdm
    (disable = verbose is not False → False quand verbose=False).
    """
    wt = sys.modules["whisper.transcribe"]
    original_tqdm_module = wt.tqdm
    wt.tqdm = _FakeTqdmModule(total_audio_s)  # type: ignore[assignment]
    try:
        return model.transcribe(str(audio_path), verbose=False, **options)
    finally:
        wt.tqdm = original_tqdm_module


# ── Point d'entrée ─────────────────────────────────────────────────────────────


def main() -> None:
    # ── Validation des arguments ───────────────────────────────────────────────
    if len(sys.argv) != 2:
        prog = Path(sys.argv[0]).name
        print(f"Usage : {prog} <fichier_audio_ou_video>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1]).resolve()

    if not input_path.exists():
        print(f"Erreur : le fichier '{input_path}' n'existe pas.", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(
            f"Erreur : '{input_path}' n'est pas un fichier régulier.", file=sys.stderr
        )
        sys.exit(1)

    # ── Fichiers de sortie ─────────────────────────────────────────────────────
    output_dir = input_path.parent
    stem = input_path.stem
    srt_path = output_dir / f"{stem}.srt"
    txt_path = output_dir / f"{stem}.txt"

    # ── Confirmation d'écrasement ──────────────────────────────────────────────
    print()
    for out_path in (srt_path, txt_path):
        if out_path.exists():
            if not confirm_overwrite(out_path):
                print("\nTranscription annulée.")
                sys.exit(0)

    # ── Fichier prompt ─────────────────────────────────────────────────────────
    initial_prompt: Optional[str] = None
    prompt_file = find_prompt_file(input_path)
    if prompt_file:
        initial_prompt = prompt_file.read_text(encoding="utf-8").strip()
        print(
            f"\n📄 Prompt initial trouvé : '{prompt_file.name}' "
            f"({len(initial_prompt)} caractères)"
        )

    # ── Durée du média (pour la barre de progression) ─────────────────────────
    total_audio_s: float = get_media_duration(input_path) or 0.0

    # ── Extraction audio si fichier vidéo ─────────────────────────────────────
    audio_path: Path = input_path
    tmp_audio: Optional[Path] = None

    if is_video_file(input_path):
        print("\n🎬 Fichier vidéo détecté. Extraction de l'audio en cours…")
        fd, tmp_name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        tmp_audio = Path(tmp_name)
        try:
            extract_audio(input_path, tmp_audio)
            audio_path = tmp_audio
            print("   Audio extrait avec succès.")
        except RuntimeError as exc:
            tmp_audio.unlink(missing_ok=True)
            print(f"\nErreur : {exc}", file=sys.stderr)
            sys.exit(1)

    # ── Transcription ──────────────────────────────────────────────────────────
    try:
        device = get_device()
        device_label = {
            "mps": "MPS — Apple Silicon ⚡",
            "cuda": "CUDA — GPU NVIDIA ⚡",
            "cpu": "CPU",
        }[device]
        print(
            f"\n🤖 Chargement du modèle Whisper '{WHISPER_MODEL}' sur {device_label}…"
        )
        model = whisper.load_model(WHISPER_MODEL, device=device)

        options = dict(WHISPER_OPTIONS)
        # fp16 accéléré sur MPS et CUDA ; CPU doit rester en fp32
        options["fp16"] = device in ("mps", "cuda")
        if initial_prompt:
            options["initial_prompt"] = initial_prompt
            # carry_initial_prompt : réinjecte le prompt à chaque chunk de 30 s
            # (sans ça, le prompt ne s'applique qu'aux 30 premières secondes)
            options["carry_initial_prompt"] = True

        print(f"🎙️  Transcription de '{input_path.name}' en cours…\n")

        result = _transcribe_with_progress(model, audio_path, total_audio_s, **options)

        # ── Écriture des sorties ───────────────────────────────────────────────
        # On passe toujours input_path (pas tmp_audio) pour nommer
        # correctement les fichiers de sortie.

        srt_writer = get_writer("srt", str(output_dir))
        srt_writer(result, str(input_path), {})

        txt_writer = get_writer("txt", str(output_dir))
        txt_writer(result, str(input_path), {})

        print(f"\n✅ Transcription terminée !")
        print(f"   📄 SRT : {srt_path}")
        print(f"   📝 TXT : {txt_path}")

    finally:
        # Nettoyage du fichier audio temporaire quoi qu'il arrive
        if tmp_audio and tmp_audio.exists():
            tmp_audio.unlink()


if __name__ == "__main__":
    main()
