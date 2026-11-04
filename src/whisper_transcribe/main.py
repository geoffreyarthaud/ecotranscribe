#!/usr/bin/env python3
"""
Transcription d'un fichier audio ou vidéo avec Whisper (local) ou OpenRouter.

Usage:
    transcribe <fichier_audio_ou_video>
    transcribe --provider openrouter <fichier_audio_ou_video>

Sorties :
    <racine>.srt  — sous-titres avec horodatage
    <racine>.txt  — transcription en texte brut

Fichier prompt optionnel :
    Si <racine>.prompt.md / <racine>.prompt.txt / <racine>.prompt existe,
    son contenu est passé à Whisper via initial_prompt, ou à OpenRouter
    via context_bias pour les modèles Mistral.
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

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

# ── Configuration OpenRouter ───────────────────────────────────────────────────

OPENROUTER_MODEL = "mistralai/voxtral-mini-transcribe-3-0"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENROUTER_CHUNK_SECONDS = 20 * 60
OPENROUTER_AUDIO_BITRATE = "64k"
OPENROUTER_REQUEST_TIMEOUT = 90
OPENROUTER_MAX_RETRIES = 3
OPENROUTER_CUT_SEARCH_WINDOW = 60.0
OPENROUTER_MIN_CHUNK_SECONDS = 60.0
OPENROUTER_SILENCE_NOISE = "-35dB"
OPENROUTER_SILENCE_DURATION = 0.4

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
    import torch

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
    """Extrait la piste audio d'un fichier média via ffmpeg (WAV 16 kHz mono)."""
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


# ── OpenRouter ─────────────────────────────────────────────────────────────────


class _ChunkTimeout(RuntimeError):
    """Le provider a dépassé son timeout : la tranche doit être coupée."""


def _normalize_context_bias(prompt: str) -> str:
    """Compacte le prompt en une seule chaîne pour context_bias."""
    return " ".join(prompt.split())


def _detect_silences(audio_path: Path) -> list[tuple[float, float]]:
    """Détecte les silences d'un fichier audio via ffmpeg silencedetect."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(audio_path),
        "-af",
        (
            f"silencedetect=noise={OPENROUTER_SILENCE_NOISE}"
            f":d={OPENROUTER_SILENCE_DURATION}"
        ),
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []

    starts = [
        float(value)
        for value in re.findall(r"silence_start:\s*([0-9.]+)", result.stderr)
    ]
    ends = [
        float(value)
        for value in re.findall(r"silence_end:\s*([0-9.]+)", result.stderr)
    ]
    return list(zip(starts, ends))


def _choose_cut_points(
    duration: float,
    silences: list[tuple[float, float]],
    chunk_seconds: float,
    search_window: float = OPENROUTER_CUT_SEARCH_WINDOW,
) -> list[float]:
    """
    Choisit les points de coupure.

    Chaque frontière cible (chunk_seconds, 2 × chunk_seconds, …) est déplacée
    vers le milieu du silence le plus proche, dans la limite de search_window.
    Si aucun silence ne convient, la frontière fixe est conservée.
    """
    cuts: list[float] = []
    target = chunk_seconds

    while target < duration - OPENROUTER_MIN_CHUNK_SECONDS:
        candidates = [
            (start + end) / 2.0
            for start, end in silences
            if abs((start + end) / 2.0 - target) <= search_window
        ]
        cut = (
            min(candidates, key=lambda value: abs(value - target))
            if candidates
            else target
        )
        previous = cuts[-1] if cuts else 0.0
        if cut - previous >= OPENROUTER_MIN_CHUNK_SECONDS:
            cuts.append(cut)
        target += chunk_seconds

    # Évite une dernière tranche trop courte.
    if cuts and duration - cuts[-1] < OPENROUTER_MIN_CHUNK_SECONDS:
        cuts.pop()

    return cuts


def _extract_chunk_mp3(
    audio_path: Path, chunk_path: Path, start: float, duration: float
) -> None:
    """Extrait une tranche audio en MP3 mono 16 kHz."""
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(audio_path),
        "-t",
        f"{duration:.3f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        OPENROUTER_AUDIO_BITRATE,
        str(chunk_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg a échoué lors du découpage audio :\n{result.stderr}"
        )


def _offset_segments(segments: list[dict], offset: float) -> list[dict]:
    """Décale les timestamps d'une tranche et renumérote les segments."""
    shifted: list[dict] = []
    for index, segment in enumerate(segments):
        shifted.append(
            {
                **segment,
                "id": index,
                "start": float(segment["start"]) + offset,
                "end": float(segment["end"]) + offset,
            }
        )
    return shifted


def _openrouter_error_message(exc: urllib.error.HTTPError) -> str:
    """Extrait le message d'erreur lisible d'une réponse OpenRouter."""
    body = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(body)
        message = payload.get("error", {}).get("message")
        if message:
            return str(message)
    except json.JSONDecodeError:
        pass
    return body.strip() or f"HTTP {exc.code}"


def _post_openrouter(payload: dict, api_key: str) -> dict:
    """Envoie une requête STT à OpenRouter avec retries transitoires."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error: Optional[Exception] = None

    for attempt in range(OPENROUTER_MAX_RETRIES):
        request = urllib.request.Request(
            OPENROUTER_API_URL, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(
                request, timeout=OPENROUTER_REQUEST_TIMEOUT
            ) as response:
                try:
                    return json.load(response)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"Réponse OpenRouter invalide : {exc}"
                    ) from exc
        except urllib.error.HTTPError as exc:
            message = _openrouter_error_message(exc)
            if exc.code in (504, 524):
                raise _ChunkTimeout(message) from exc
            if (
                exc.code in (429, 500, 502, 503, 529)
                and attempt + 1 < OPENROUTER_MAX_RETRIES
            ):
                last_error = exc
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"OpenRouter HTTP {exc.code} : {message}") from exc
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            if attempt + 1 < OPENROUTER_MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"OpenRouter injoignable : {exc}") from exc

    raise RuntimeError(
        f"OpenRouter : échec après {OPENROUTER_MAX_RETRIES} tentatives "
        f"({last_error})"
    )


def _transcribe_openrouter_chunk(
    wav_path: Path,
    tmp_dir: Path,
    start: float,
    end: float,
    prompt: Optional[str],
    model_name: str,
    api_key: str,
) -> tuple[list[dict], str, float]:
    """Transcrit une tranche [start, end] et retourne segments, texte et coût."""
    chunk_path = tmp_dir / f"chunk_{int(start * 1000):09d}.mp3"
    _extract_chunk_mp3(wav_path, chunk_path, start, end - start)

    audio_b64 = base64.b64encode(chunk_path.read_bytes()).decode("ascii")
    payload: dict = {
        "model": model_name,
        "input_audio": {"data": audio_b64, "format": "mp3"},
        "language": WHISPER_OPTIONS["language"],
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }
    if prompt and model_name.startswith("mistralai/"):
        payload["provider"] = {
            "options": {
                "mistral": {"context_bias": _normalize_context_bias(prompt)}
            }
        }

    response = _post_openrouter(payload, api_key)
    text = str(response.get("text", "")).strip()
    raw_segments = response.get("segments") or [
        {"start": 0.0, "end": end - start, "text": text}
    ]
    segments = _offset_segments(raw_segments, start)
    cost = float(response.get("usage", {}).get("cost", 0.0) or 0.0)
    return segments, text, cost


def _transcribe_openrouter_range(
    wav_path: Path,
    tmp_dir: Path,
    start: float,
    end: float,
    prompt: Optional[str],
    model_name: str,
    api_key: str,
) -> tuple[list[dict], str, float]:
    """Transcrit une plage, en la coupant en deux si le provider timeout."""
    try:
        return _transcribe_openrouter_chunk(
            wav_path, tmp_dir, start, end, prompt, model_name, api_key
        )
    except _ChunkTimeout:
        if end - start <= OPENROUTER_MIN_CHUNK_SECONDS:
            raise
        middle = (start + end) / 2.0
        left_segments, left_text, left_cost = _transcribe_openrouter_range(
            wav_path, tmp_dir, start, middle, prompt, model_name, api_key
        )
        right_segments, right_text, right_cost = _transcribe_openrouter_range(
            wav_path, tmp_dir, middle, end, prompt, model_name, api_key
        )
        return (
            left_segments + right_segments,
            " ".join(part for part in (left_text, right_text) if part),
            left_cost + right_cost,
        )


def transcribe_openrouter(
    input_path: Path, prompt: Optional[str], model_name: str
) -> dict:
    """Transcrit via OpenRouter en découpant l'audio en tranches de 20 min."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY n'est pas définie. "
            "Exportez-la avant de lancer la transcription."
        )

    print(f"\n☁️  Transcription via OpenRouter avec '{model_name}'…")
    if prompt and not model_name.startswith("mistralai/"):
        print(
            "   ⚠️  Prompt ignoré : context_bias n'est supporté que par "
            "les modèles Mistral."
        )

    with tempfile.TemporaryDirectory(prefix="whisper-transcribe-") as tmp:
        tmp_dir = Path(tmp)
        wav_path = tmp_dir / "audio.wav"

        print("   Extraction de l'audio en cours…")
        extract_audio(input_path, wav_path)

        duration = get_media_duration(wav_path)
        if not duration:
            raise RuntimeError("Impossible de déterminer la durée de l'audio.")

        print("   Détection des silences…")
        silences = _detect_silences(wav_path)
        cuts = _choose_cut_points(duration, silences, OPENROUTER_CHUNK_SECONDS)
        boundaries = [0.0, *cuts, duration]
        ranges = list(zip(boundaries, boundaries[1:]))
        print(
            f"   {len(ranges)} tranche(s) d'environ "
            f"{OPENROUTER_CHUNK_SECONDS // 60} min."
        )

        all_segments: list[dict] = []
        texts: list[str] = []
        total_cost = 0.0

        with Progress(
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
        ) as progress:
            task_id = progress.add_task(
                "transcription",
                total=duration,
                audio_pos=f"00:00 / {_fmt_seconds(duration)}",
            )
            completed = 0.0

            for start, end in ranges:
                segments, text, cost = _transcribe_openrouter_range(
                    wav_path, tmp_dir, start, end, prompt, model_name, api_key
                )
                all_segments.extend(segments)
                if text:
                    texts.append(text)
                total_cost += cost
                completed += end - start
                progress.update(
                    task_id,
                    advance=end - start,
                    audio_pos=(
                        f"{_fmt_seconds(completed)} / {_fmt_seconds(duration)}"
                    ),
                )

        for index, segment in enumerate(all_segments):
            segment["id"] = index

        return {
            "text": " ".join(texts).strip(),
            "segments": all_segments,
            "language": WHISPER_OPTIONS["language"],
            "cost": total_cost,
        }


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


def transcribe_whisper(
    input_path: Path, prompt: Optional[str], model_name: str
) -> dict:
    """Transcrit avec Whisper en local."""
    import whisper

    total_audio_s = get_media_duration(input_path) or 0.0
    audio_path: Path = input_path
    tmp_audio: Optional[Path] = None

    if is_video_file(input_path):
        print("\n🎬 Fichier vidéo détecté. Extraction de l'audio en cours…")
        fd, tmp_name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        tmp_audio = Path(tmp_name)
        extract_audio(input_path, tmp_audio)
        audio_path = tmp_audio
        print("   Audio extrait avec succès.")

    try:
        device = get_device()
        device_label = {
            "mps": "MPS — Apple Silicon ⚡",
            "cuda": "CUDA — GPU NVIDIA ⚡",
            "cpu": "CPU",
        }[device]
        print(
            f"\n🤖 Chargement du modèle Whisper '{model_name}' "
            f"sur {device_label}…"
        )
        model = whisper.load_model(model_name, device=device)

        options = dict(WHISPER_OPTIONS)
        # fp16 accéléré sur MPS et CUDA ; CPU doit rester en fp32
        options["fp16"] = device in ("mps", "cuda")
        if prompt:
            options["initial_prompt"] = prompt
            # carry_initial_prompt : réinjecte le prompt à chaque chunk de 30 s
            # (sans ça, le prompt ne s'applique qu'aux 30 premières secondes)
            options["carry_initial_prompt"] = True

        print(f"🎙️  Transcription de '{input_path.name}' en cours…\n")
        return _transcribe_with_progress(
            model, audio_path, total_audio_s, **options
        )
    finally:
        # Nettoyage du fichier audio temporaire quoi qu'il arrive
        if tmp_audio and tmp_audio.exists():
            tmp_audio.unlink()


# ── Point d'entrée ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
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
    args = parser.parse_args()

    input_path = args.input.resolve()

    if not input_path.exists():
        print(f"Erreur : le fichier '{input_path}' n'existe pas.", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(
            f"Erreur : '{input_path}' n'est pas un fichier régulier.",
            file=sys.stderr,
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

    model_name = args.model or (
        WHISPER_MODEL if args.provider == "whisper" else OPENROUTER_MODEL
    )

    # ── Transcription ──────────────────────────────────────────────────────────
    try:
        if args.provider == "whisper":
            result = transcribe_whisper(input_path, initial_prompt, model_name)
        else:
            result = transcribe_openrouter(input_path, initial_prompt, model_name)
    except RuntimeError as exc:
        print(f"\nErreur : {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Écriture des sorties ───────────────────────────────────────────────────
    srt_writer = get_writer("srt", str(output_dir))
    srt_writer(result, str(input_path), {})

    txt_writer = get_writer("txt", str(output_dir))
    txt_writer(result, str(input_path), {})

    print("\n✅ Transcription terminée !")
    print(f"   📄 SRT : {srt_path}")
    print(f"   📝 TXT : {txt_path}")
    if args.provider == "openrouter":
        print(f"   💵 Coût OpenRouter : ${result.get('cost', 0.0):.6f}")


if __name__ == "__main__":
    main()
