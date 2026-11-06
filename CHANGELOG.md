# Changelog

## Non publié — 2026-11-06

### Ajouté

- Liste des modèles OpenRouter : `mistralai/voxtral-small-transcribe-3-0`
  (nouveau défaut) et `mistralai/voxtral-mini-transcribe-3-0`.
- Tarif horaire approximatif par modèle, récupéré de façon asynchrone depuis
  OpenRouter et affiché entre parenthèses ; aucune indication si le réseau ou
  l'API échoue.

### Corrigé

- Les réglages (dont le modèle sélectionné) sont enregistrés à la fermeture de
  la fenêtre et à l'arrêt de l'application, même sans lancer de transcription.

## 0.2.0 — 2026-11-05

### Ajouté

- Application desktop **EcoTranscribe Desktop** (PySide6, édition lite
  OpenRouter) avec drag & drop, prompt auto-détecté, réglages persistants,
  keyring, progression détaillée, annulation, coût et journal rotatif.
- Entrée `ecotranscribe-desktop` et mode `--diagnose`.
- Writers SRT/TXT internes, atomiques, UTF-8/LF, identiques aux sorties du CLI.
- `TranscribeService` sans Qt, callbacks de progression/journal et
  `CancelToken`.
- Packaging PyInstaller onedir avec ffmpeg/ffprobe épinglés et vérifiés par
  SHA256.
- Distribution macOS signée ad-hoc : DMG, ZIP, notice, SHA256, sans
  notarisation.
- Distribution Windows ZIP portable et installeur Inno Setup optionnel.
- Distribution Linux AppImage et archive `tar.gz` de fallback.
- Workflow GitHub Actions multi-OS, diagnostic des artefacts et release sur tag.

### Modifié

- Renommage complet : paquet `ecotranscribe`, CLI `ecotranscribe`, application
  `EcoTranscribe Desktop`. Aucun alias `transcribe`, `transcribe-gui` ou
  `whisper_transcribe`.
- `openai-whisper` déplacé dans l'extra `[whisper]` ; le CLI Whisper nécessite
  `uv sync --extra whisper`.
- `PySide6-Essentials` borné à `< 6.10` pour conserver macOS 12+ et le runner
  `macos-13`.
- Le coût OpenRouter distingue désormais absence (`None`, « Coût
  indisponible ») et coût nul valide (`0.0`).
- La langue OpenRouter est paramétrable ; `Auto` omet le champ `language`.

### Documentation

- README, notice macOS, guide de distribution, politique de sécurité,
  changelog, licence MIT et notices tierces.

## 0.1.0 — version initiale

- CLI `transcribe` avec Whisper local et OpenRouter.
- Découpage OpenRouter, détection de silences, prompt `.prompt.*`.
- Sorties SRT/TXT via `whisper.utils.get_writer`.
