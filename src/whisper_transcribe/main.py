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


# ── Helpers ────────────────────────────────────────────────────────────────────


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

        print(f"🎙️  Transcription de '{input_path.name}' en cours…")
        if initial_prompt:
            print(f"   (prompt initial : {len(initial_prompt)} caractères)")

        result = model.transcribe(str(audio_path), **options)

        # ── Écriture des sorties ───────────────────────────────────────────────
        # On passe toujours input_path (pas tmp_audio) pour nommer
        # correctement les fichiers de sortie.

        srt_writer = get_writer("srt", str(output_dir))
        srt_writer(result, str(input_path), {})

        txt_writer = get_writer("txt", str(output_dir))
        txt_writer(result, str(input_path), {})

        print("\n✅ Transcription terminée !")
        print(f"   📄 SRT : {srt_path}")
        print(f"   📝 TXT : {txt_path}")

    finally:
        # Nettoyage du fichier audio temporaire quoi qu'il arrive
        if tmp_audio and tmp_audio.exists():
            tmp_audio.unlink()


if __name__ == "__main__":
    main()
