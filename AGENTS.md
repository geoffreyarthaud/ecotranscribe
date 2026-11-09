# AGENTS.md

Guide opérationnel pour les agents de code et les développeurs qui font évoluer
EcoTranscribe. Pour l'usage, voir `README.md` ; pour l'historique de conception,
voir `docs/superpowers/specs/` et `docs/superpowers/plans/`.

## Invariants

Ces règles ne se négocient pas. Une évolution qui les casse doit être
explicitement validée.

- **Nommage** : paquet/CLI `ecotranscribe`, application `EcoTranscribe Desktop`,
  entrée `ecotranscribe-desktop`, bundle `app.ecotranscribe.desktop`. Aucun
  alias `transcribe`, `transcribe-gui` ou `whisper_transcribe`.
- **Cœur sans interface** : `src/ecotranscribe/core/` ne dépend ni de Qt ni
  d'`argparse`, n'écrit pas sur stdout, ne demande jamais de confirmation et
  n'appelle pas `sys.exit`. Le CLI et la GUI sont deux adaptateurs du même
  `TranscribeService`.
- **Sorties identiques** : CLI et GUI produisent les mêmes octets SRT/TXT via
  `core/writers.py`. UTF-8, fins de ligne LF, écriture atomique ; une annulation
  avant l'écriture finale ne laisse aucun fichier partiel.
- **Édition lite** : pas de `torch`, pas d'`openai-whisper`, pas de modèle local.
  Whisper reste disponible uniquement via l'extra `[whisper]` et n'est jamais
  importé par l'application lite.
- **Réseau** : au runtime, seule l'API OpenRouter est contactée. Pas de
  télémétrie, pas de vérification de mise à jour.
- **Secrets** : la clé OpenRouter ne doit apparaître ni dans les logs, ni dans
  `QSettings`, ni dans les détails d'erreur. Utiliser le keyring ou
  `OPENROUTER_API_KEY`.
- **Une tâche à la fois** : une seule transcription simultanée ; le thread Qt
  n'est jamais bloqué par une opération > 100 ms.
- **Outillage** : toute commande Python passe par `uv`. Ne jamais commiter
  `dist/`, `build/`, `vendor/`, `data/`, `.venv/`, les artefacts d'installation
  ou les binaires ffmpeg.
- **Erreurs** : message utilisateur actionnable en français + détail technique
  + accès au journal. Ne jamais masquer une erreur par un succès partiel.

## Carte du code

| Chemin | Responsabilité |
|---|---|
| `core/models.py` | Contrats gelés : `TranscribeRequest`, `TranscribeResult`, `Segment`, `ProgressUpdate`, `CancelToken`. |
| `core/service.py` | Orchestration : validation → moteur → écriture atomique. |
| `core/engines/base.py` | Protocole `TranscriptionEngine` (`provider`, `availability`, `transcribe`). |
| `core/engines/openrouter.py` | Découpage, silences, requêtes OpenRouter, recollage. |
| `core/engines/whisper.py` | Moteur local optionnel. |
| `core/media.py` | ffmpeg/ffprobe, extraction, durée. |
| `core/prompts.py`, `core/outputs.py`, `core/writers.py` | Prompt auto, chemins, rendu SRT/TXT. |
| `core/config.py`, `core/errors.py`, `core/formatting.py` | Constantes, erreurs typées, formatage. |
| `cli.py` | Adaptateur `argparse` + `rich`. |
| `gui/` | Fenêtre PySide6, worker QThread, réglages, keyring, diagnostic, logs. |
| `packaging/` | PyInstaller, ffmpeg épinglé, signatures, DMG/Inno/AppImage. |
| `tests/` | Tests cœur, CLI, GUI et packaging ; goldens dans `tests/fixtures/`. |

Flux : `CLI`/`GUI` → `TranscribeService` → `TranscriptionEngine` → writers →
`TranscribeResult`. La progression et les logs remontent par callbacks ; la GUI
les convertit en signaux Qt.

## Commandes

```bash
# Environnement de développement complet
uv sync --extra gui --extra dev

# Tests (comme la CI)
uv run pytest
QT_QPA_PLATFORM=offscreen uv run pytest     # Linux sans affichage

# Test ciblé
uv run pytest tests/test_service.py -v

# CLI
uv run ecotranscribe --provider openrouter fichier.mp4
uv run ecotranscribe fichier.mp3             # Whisper, après uv sync --extra whisper

# GUI
uv run ecotranscribe-desktop
uv run ecotranscribe-desktop --diagnose --diagnose-output /tmp/diag.json

# Packaging (procédure complète dans docs/distribution.md)
uv run python packaging/build_ffmpeg_source.py --target darwin-arm64
uv run python packaging/fetch_ffmpeg.py --target win-x64   # Windows/Linux
uv run python packaging/check_ffmpeg_build.py --target darwin-arm64
uv run python packaging/make_icons.py
uv run pyinstaller --noconfirm packaging/pyinstaller.spec
```

## Conventions

- Python ≥ 3.13 ; la CI et le développement utilisent 3.13.
- Annoter les types ; ajouter `from __future__ import annotations` en tête de
  module.
- Contrats de données : `@dataclass(frozen=True, slots=True)` ; énumérations
  pour les valeurs fermées (`Provider`, `OutputFormat`).
- Docstrings, messages UI et doc utilisateur en français ; identifiants en
  anglais.
- Chemins en `pathlib.Path` ; prendre en charge espaces, accents et caractères
  non ASCII.
- Les erreurs du cœur héritent de `TranscribeError` et portent
  `user_message`, `detail`, éventuellement `hint`.
- Ne pas importer `gui` depuis `core`, ni `cli` depuis `core`.
- Pas de nouvelle dépendance sans justifier le poids, la licence et l'impact
  packaging.

## Tests

- Aucun test ne fait d'appel réseau réel ni ne charge un modèle Whisper.
  Utiliser des faux moteurs, `monkeypatch` et des réponses fixture.
- Tests GUI : `QSettings` temporaire, `KeyStore` en mémoire, `DialogService`
  factice ; lancer avec `QT_QPA_PLATFORM=offscreen` si nécessaire.
- Toute correction de bug commence par un test qui échoue, puis passe.
- Toute modification des writers ou du service doit préserver les goldens
  `tests/fixtures/sample.srt|txt`.
- Lancer la suite complète avant de livrer ; un test ciblé ne suffit pas.

## Workflow d'évolution

- **Petit changement borné** : test → implémentation → suite complète → mise à
  jour de la doc si le comportement change. Pas de document de conception.
- **Évolution structurante** (nouveau moteur, nouveau format, changement
  d'interface ou de packaging) : écrire d'abord une spec dans
  `docs/superpowers/specs/YYYY-MM-DD-<sujet>-design.md`, puis un plan dans
  `docs/superpowers/plans/`, et implémenter par étapes vérifiables.
- **Contrats publics** : mettre à jour tous les appelants dans le même
  changement ; pas d'alias ni de shim de compatibilité.
- **Version** : garder `pyproject.toml` et `src/ecotranscribe/__init__.py`
  alignés ; ajouter une entrée datée dans `CHANGELOG.md`.
- **Documentation** : mettre à jour `README.md`, `docs/distribution.md`,
  `docs/install-macos-unsigned.md`, `THIRD_PARTY_NOTICES.md` et les notices
  concernées selon l'impact.
- **Ne jamais** commiter d'artefact généré ni modifier `uv.lock` à la main.

## Recettes

- **Nouveau moteur** : implémenter `TranscriptionEngine`, ajouter la valeur dans
  `Provider`, enregistrer le moteur dans `cli.py` (et dans `gui/main_window.py`
  seulement si le lite le supporte), puis tester disponibilité, erreurs et
  sélection sans réseau.
- **Nouveau format** : ajouter `OutputFormat`, le suffixe dans
  `core/outputs.py`, le rendu et l'écriture atomique dans `core/writers.py`,
  puis les contrôles CLI/GUI et les goldens.
- **Nouveau réglage GUI** : l'ajouter dans `gui/settings.py` (jamais un secret),
  le persister via `QSettings` avec une valeur par défaut, et le tester avec un
  `QSettings` temporaire.
- **Packaging** : toute modification de ffmpeg, PyInstaller, signature ou CI
  doit mettre à jour `packaging/ffmpeg.lock.json`, le workflow et les notices ;
  ne jamais commiter les binaires.

## Sécurité et confidentialité

- HTTPS et vérification TLS standard uniquement.
- En mode OpenRouter, l'audio est envoyé au service tiers ; l'UI doit le dire
  explicitement. Le prompt n'est envoyé que si le modèle le supporte.
- Journal local rotatif (1 Mo × 3), sans audio, sans clé, sans secret.
- Ne pas ajouter de télémétrie, de crash reporting distant ou de mise à jour
  automatique sans décision explicite.

## Definition of Done

- [ ] `uv run pytest` passe.
- [ ] Le chemin modifié a été exercé manuellement (CLI ou GUI) et le résultat
      observé.
- [ ] Les invariants ci-dessus sont respectés.
- [ ] Les tests couvrent le comportement, les limites et les erreurs nouvelles.
- [ ] README/CHANGELOG/docs/notices mis à jour si nécessaire.
- [ ] Aucun artefact généré ni secret dans le diff.
