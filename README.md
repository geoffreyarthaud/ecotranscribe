# whisper-transcribe

Outil de transcription audio/vidéo en ligne de commande.

Deux moteurs sont disponibles :

- **Whisper** en local (par défaut), via [OpenAI Whisper](https://github.com/openai/whisper) ;
- **OpenRouter**, via le modèle [`mistralai/voxtral-mini-transcribe-3-0`](https://openrouter.ai/mistralai/voxtral-mini-transcribe-3-0).

## Fonctionnalités

- Transcription d'un fichier **audio** (mp3, wav, m4a, flac, ogg…) ou **vidéo** (mp4, mkv, mov, avi…)
- Extraction automatique de l'audio si un fichier vidéo est fourni
- Génération de deux fichiers de sortie dans le même dossier que la source :
  - `<racine>.srt` — sous-titres avec horodatage
  - `<racine>.txt` — transcription en texte brut
- Demande de confirmation avant d'écraser un fichier de sortie existant
- Support d'un **fichier prompt** pour guider la transcription (vocabulaire spécifique, noms propres…)
- Découpage automatique des longs médias pour OpenRouter, avec recollage des timestamps

## Prérequis

| Outil | Rôle |
|-------|------|
| [Python](https://python.org) ≥ 3.10 | Runtime |
| [uv](https://docs.astral.sh/uv/) | Gestionnaire de paquets et d'environnement |
| [ffmpeg](https://ffmpeg.org/) | Extraction audio, découpage et décodage des formats média |

`ffmpeg` doit être accessible dans le `PATH` système.

```bash
# macOS (Homebrew)
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

Pour le moteur OpenRouter, une clé API est nécessaire :

```bash
export OPENROUTER_API_KEY="sk-or-..."
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

### Choisir le moteur

```bash
# Whisper local (comportement par défaut)
uv run transcribe réunion.mp3

# OpenRouter avec le modèle par défaut
uv run transcribe --provider openrouter réunion.mp3

# OpenRouter avec un autre modèle Mistral
uv run transcribe --provider openrouter \
  --model mistralai/voxtral-small-transcribe-3-0 réunion.mp3

# Whisper avec un autre modèle
uv run transcribe --model tiny réunion.mp3
```

| Option | Valeur par défaut | Description |
|--------|-------------------|-------------|
| `--provider` | `whisper` | Moteur : `whisper` ou `openrouter` |
| `--model` | `medium` (Whisper) / `mistralai/voxtral-mini-transcribe-3-0` (OpenRouter) | Modèle utilisé |

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

Si un fichier dont la racine est identique au fichier source existe avec l'une des extensions suivantes (par ordre de priorité), son contenu est utilisé comme contexte :

| Extension | Exemple |
|-----------|---------|
| `.prompt.md` | `réunion.prompt.md` |
| `.prompt.txt` | `réunion.prompt.txt` |
| `.prompt`    | `réunion.prompt`    |

Le prompt permet d'améliorer la qualité de la transcription en fournissant du contexte : noms propres, acronymes, vocabulaire technique, style de ponctuation souhaité, etc.

### Comportement selon le moteur

- **Whisper** : le contenu est passé via `initial_prompt`, puis réinjecté à chaque fenêtre de 30 secondes (`carry_initial_prompt`).
- **OpenRouter / Mistral** : le contenu est passé via `context_bias`, dans `provider.options.mistral`. C'est le mécanisme de biais contextuel de Mistral : il accepte des termes ou une description du contenu, mais pas des instructions libres. Le prompt est ignoré si le modèle OpenRouter choisi n'est pas un modèle Mistral.

### Exemple de fichier prompt

```markdown
Transcription d'une réunion médicale. Vocabulaire spécifique :
Dr. Lefebvre, CHU de Bordeaux, immunothérapie, anticorps monoclonaux, protocole FOLFOX.
Utiliser la ponctuation française standard.
```

## OpenRouter : découpage et limites

L'API Speech-to-Text d'OpenRouter impose deux contraintes :

- un timeout upstream d'environ **60 secondes de traitement** par requête ;
- une limite de **25 Mo** pour les uploads multipart.

Pour les longs médias, l'outil :

1. extrait l'audio en WAV 16 kHz mono ;
2. détecte les silences avec `ffmpeg silencedetect` ;
3. découpe en tranches d'**environ 20 minutes**, en privilégiant une coupure au silence ;
4. encode chaque tranche en **MP3 64 kbps mono 16 kHz** ;
5. transcrit chaque tranche avec `response_format: "verbose_json"` ;
6. décale les timestamps de chaque segment et recolle le tout dans le `.srt` et le `.txt`.

Si une tranche dépasse le timeout du provider, elle est automatiquement coupée en deux et rejouée. Le coût réel de chaque requête est affiché à la fin (`usage.cost`).

Référence : [OpenRouter — Speech-to-Text](https://openrouter.ai/docs/guides/overview/multimodal/stt).

## Configuration

Les paramètres sont définis dans `src/whisper_transcribe/main.py` :

| Constante | Valeur | Description |
|-----------|--------|-------------|
| `WHISPER_MODEL` | `"medium"` | Modèle Whisper par défaut |
| `WHISPER_OPTIONS` | langue `fr`, température `(0.0, 0.2, 0.4)`, etc. | Options Whisper |
| `OPENROUTER_MODEL` | `"mistralai/voxtral-mini-transcribe-3-0"` | Modèle OpenRouter par défaut |
| `OPENROUTER_CHUNK_SECONDS` | `1200` | Taille maximale d'une tranche (20 min) |
| `OPENROUTER_AUDIO_BITRATE` | `"64k"` | Débit MP3 des tranches |

## Structure du projet

```
whisper-transcribe/
├── src/
│   └── whisper_transcribe/
│       ├── __init__.py
│       └── main.py          ← logique principale
├── tests/
│   └── test_openrouter.py   ← tests du découpage et des offsets
├── pyproject.toml
├── README.md
└── .gitignore
```

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

## Licence

MIT
