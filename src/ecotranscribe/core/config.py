"""Constantes partagées du cœur et de l'interface."""

from __future__ import annotations

APP_NAME = "EcoTranscribe Desktop"
APP_SLUG = "ecotranscribe"
FLAVOR = "desktop"
PROJECT_URL = "https://github.com/ecotranscribe/ecotranscribe"

WHISPER_MODEL = "medium"
WHISPER_OPTIONS: dict = {
    "language": "fr",
    "temperature": (0.0, 0.2, 0.4),
    "compression_ratio_threshold": 2.8,
}

OPENROUTER_MODEL = "mistralai/voxtral-small-transcribe-3-0"
# Liste embarquée : repli hors ligne du catalogue distant.
OPENROUTER_MODELS: tuple[str, ...] = (
    OPENROUTER_MODEL,
    "mistralai/voxtral-mini-transcribe-3-0",
)
MODELS_CATALOG_URL = (
    "https://raw.githubusercontent.com/ecotranscribe/ecotranscribe/"
    "main/catalog/models.json"
)
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHUNK_SECONDS = 20 * 60
OPENROUTER_AUDIO_BITRATE = "64k"
OPENROUTER_REQUEST_TIMEOUT = 90
OPENROUTER_MAX_RETRIES = 3
OPENROUTER_CUT_SEARCH_WINDOW = 60.0
OPENROUTER_MIN_CHUNK_SECONDS = 60.0
OPENROUTER_SILENCE_NOISE = "-35dB"
OPENROUTER_SILENCE_DURATION = 0.4

WHISPER_HOP_LENGTH = 160
WHISPER_SAMPLE_RATE = 16_000

PROMPT_EXTENSIONS: tuple[str, ...] = (".prompt.md", ".prompt.txt", ".prompt")

AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".aac",
        ".aif",
        ".aiff",
        ".flac",
        ".m4a",
        ".mp3",
        ".oga",
        ".ogg",
        ".opus",
        ".wav",
        ".wma",
    }
)

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".3gp",
        ".avi",
        ".f4v",
        ".flv",
        ".m2ts",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mts",
        ".mxf",
        ".ogv",
        ".ts",
        ".webm",
        ".wmv",
    }
)

WHISPER_NOT_INSTALLED_MESSAGE = (
    "Moteur Whisper non installé. Lancez `uv sync --extra whisper`."
)
WHISPER_DESKTOP_REASON = (
    "Moteur Whisper local non inclus dans EcoTranscribe Desktop."
)
KEY_MISSING_MESSAGE = (
    "Clé OpenRouter manquante. Saisissez-la ou définissez OPENROUTER_API_KEY."
)
