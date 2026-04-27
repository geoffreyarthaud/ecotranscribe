# whisper-transcribe

Outil de transcription audio/vidéo en ligne de commande, basé sur [OpenAI Whisper](https://github.com/openai/whisper).

## Fonctionnalités

- Transcription d'un fichier **audio** (mp3, wav, m4a, flac, ogg…) ou **vidéo** (mp4, mkv, mov, avi…)
- Extraction automatique de l'audio si un fichier vidéo est fourni
- Génération de deux fichiers de sortie dans le même dossier que la source :
  - `<racine>.srt` — sous-titres avec horodatage
  - `<racine>.txt` — transcription en texte brut
- Demande de confirmation avant d'écraser un fichier de sortie existant
- Support d'un **fichier prompt** pour guider la transcription (vocabulaire spécifique, noms propres…)

## Prérequis

| Outil | Rôle |
|-------|------|
| [Python](https://python.org) ≥ 3.10 | Runtime |
| [uv](https://docs.astral.sh/uv/) | Gestionnaire de paquets et d'environnement |
| [ffmpeg](https://ffmpeg.org/) | Extraction audio et décodage des formats média |

`ffmpeg` doit être accessible dans le `PATH` système.

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

## Installation

```bash
# Cloner le dépôt (ou se placer dans le dossier du projet)
cd whisper-transcribe

# Créer l'environnement virtuel et installer les dépendances
uv sync
```

Le modèle Whisper `medium` sera téléchargé automatiquement lors de la première exécution (~1,5 Go, stocké dans `~/.cache/whisper/`).

## Utilisation

```bash
uv run transcribe <fichier_audio_ou_video>
```

### Exemples

```bash
# Transcription d'un fichier audio
uv run transcribe réunion.mp3

# Transcription d'un fichier vidéo (l'audio est extrait automatiquement)
uv run transcribe conférence.mp4

# Avec un fichier prompt (voir section dédiée)
uv run transcribe interview.wav   # si interview.prompt.md existe, il est utilisé automatiquement
```

Les fichiers de sortie sont créés à côté du fichier source :

```
réunion.mp3
réunion.srt   ← généré
réunion.txt   ← généré
```

## Fichier prompt (optionnel)

Si un fichier dont la racine est identique au fichier source existe avec l'une des extensions suivantes (par ordre de priorité), son contenu est utilisé comme `initial_prompt` pour Whisper :

| Extension | Exemple |
|-----------|---------|
| `.prompt.md` | `réunion.prompt.md` |
| `.prompt.txt` | `réunion.prompt.txt` |
| `.prompt`    | `réunion.prompt`    |

Le prompt initial permet d'améliorer la qualité de la transcription en fournissant du contexte : noms propres, acronymes, vocabulaire technique, style de ponctuation souhaité, etc.

### Exemple de fichier prompt

```markdown
Transcription d'une réunion médicale. Vocabulaire spécifique :
Dr. Lefebvre, CHU de Bordeaux, immunothérapie, anticorps monoclonaux, protocole FOLFOX.
Utiliser la ponctuation française standard.
```

## Configuration

Les paramètres Whisper sont définis directement dans `src/whisper_transcribe/main.py` :

| Constante | Valeur | Correspondance CLI | Description |
|-----------|--------|--------------------|-------------|
| `WHISPER_MODEL` | `"medium"` | `--model` | Modèle Whisper utilisé |
| `language` | `"fr"` | `--language` | Langue de transcription |
| `temperature` | `0.0` | `-tp` | Température d'échantillonnage (0 = glouton) |
| `compression_ratio_threshold` | `3.0` | `-et` | Seuil entropie/compression pour fallback |
| `max_context` | `64` | `-mc` | Nombre de tokens de contexte précédent |

## Structure du projet

```
whisper-transcribe/
├── src/
│   └── whisper_transcribe/
│       ├── __init__.py
│       └── main.py          ← logique principale
├── pyproject.toml
├── README.md
└── .gitignore
```

## Licence

MIT