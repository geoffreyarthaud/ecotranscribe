"""Erreurs du cœur, porteuses d'un message utilisateur et d'un détail."""

from __future__ import annotations

from pathlib import Path


class TranscribeError(Exception):
    """Erreur applicative avec message utilisateur, détail et piste."""

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
    """Entrée, chemin ou format invalide."""


class EngineUnavailableError(TranscribeError):
    """Moteur absent ou non configuré."""


class MediaToolMissingError(TranscribeError):
    """ffmpeg ou ffprobe introuvable."""

    def __init__(self, tool: str) -> None:
        super().__init__(
            "ffmpeg est introuvable. Réinstallez l'application ou "
            "signalez le problème.",
            detail=f"Outil introuvable : {tool}",
        )
        self.tool = tool


class OutputExistsError(TranscribeError):
    """Des fichiers de sortie existent et l'écrasement n'est pas autorisé."""

    def __init__(self, paths: tuple[Path, ...]) -> None:
        names = ", ".join(path.name for path in paths)
        super().__init__(
            f"Ces fichiers existent déjà : {names}",
            detail="\n".join(str(path) for path in paths),
        )
        self.paths = paths


class CancelledError(TranscribeError):
    """Transcription annulée par l'utilisateur."""

    def __init__(self) -> None:
        super().__init__("Transcription annulée.")
