# Changelog

## Non publié — 2026-11-08

### Modifié

- Interface condensée : titres de page retirés des étapes, accueil centré
  verticalement, nom de fichier redondant retiré du prompt, paddings
  verticaux des champs et boutons réduits.
- Zone de prompt réduite d'environ 10 % pour afficher « Effacer le prompt »
  sans barre de défilement à la taille de fenêtre par défaut.
- Modèle présenté comme une liste stricte non éditable ; coût estimé de la
  vidéo affiché à deux chiffres significatifs, avec virgule décimale
  française et unité en fin de montant.

## 0.3.0 — 2026-11-06

### Modifié

- Interface refondue en assistant à six écrans : accueil, clé conditionnelle,
  fichier/prompt, réglages, progression, fin.
- Page Options (clé OpenRouter et à propos) accessible depuis l'accueil et
  l'engrenage, hors parcours.
- Progression avec journal permanent, annulation coopérative et erreurs
  inline avec hint, détail technique et accès au journal.
- Thème Qt inspiré des principes du DSFR (non officiel), clair/sombre, sans
  police, code, logo ni asset DSFR.
- Suppression du sélecteur de fournisseur, de la mention Whisper et du badge
  d'édition lite dans l'interface.
- La clé mémorisée n'est plus préremplie ; les réglages non secrets sont
  conservés à la fermeture ; `ui/log_visible` est supprimé.
- Bouton Options remplacé par une icône de roue dentée dans l'en-tête ;
  doublon « Options » retiré de l'accueil.
- Liste des modèles à nouveau visible avec sa flèche de sélection.
- Police Marianne utilisée lorsqu'elle est installée, sans embarquement ;
  repli Arial sinon.

## Non publié — 2026-11-06

### Ajouté

- Liste des modèles OpenRouter : `mistralai/voxtral-small-transcribe-3-0`
  (nouveau défaut) et `mistralai/voxtral-mini-transcribe-3-0`.
- Tarif horaire approximatif par modèle, récupéré de façon asynchrone depuis
  OpenRouter et affiché entre parenthèses ; aucune indication si le réseau ou
  l'API échoue.

### Modifié

- Prérequis Python relevé à 3.13 ; Python 3.10 à 3.12 ne sont plus pris en
  charge pour le CLI et le développement.

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
