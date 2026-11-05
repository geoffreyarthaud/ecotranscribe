"""Formatage des durées pour la progression."""

from __future__ import annotations


def format_seconds(total_s: float) -> str:
    """Formate une durée en `m:ss`, ou `h:mm:ss` au-delà d'une heure."""
    total_s = max(0.0, total_s)
    hours = int(total_s // 3600)
    minutes = int((total_s % 3600) // 60)
    seconds = int(total_s % 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
