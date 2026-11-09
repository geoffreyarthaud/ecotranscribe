# EcoTranscribe

Transcription audio et vidéo avec **OpenRouter** (cloud) ou **Whisper** (local),
en application desktop ou en ligne de commande.

EcoTranscribe existe en deux éditions :

- **lite** : application desktop OpenRouter, sans Python, sans `ffmpeg` système
  et sans Whisper local ;
- **CLI** : `ecotranscribe`, pour les développeurs, avec OpenRouter ou Whisper
  local via l'extra `[whisper]`.

## Nommage

| Élément | Nom |
|---|---|
| Produit | EcoTranscribe |
| Paquet Python | `ecotranscribe` |
| CLI | `ecotranscribe` |
| Application desktop | EcoTranscribe Desktop |
| Entrée desktop | `ecotranscribe-desktop` |
| Bundle macOS | `app.ecotranscribe.desktop` |

Aucun alias `transcribe`, `transcribe-gui` ou `whisper_transcribe` n'est
conservé.

## Fonctionnalités

- Fichiers audio et vidéo (mp3, wav, m4a, flac, ogg, mp4, mkv, mov, avi…).
- Sorties `<racine>.srt` et `<racine>.txt`, UTF-8 avec fins de ligne LF.
- Mêmes writers internes pour le CLI et l'application : les octets produits
  sont identiques pour une même réponse moteur.
- Prompt automatique `.prompt.md` > `.prompt.txt` > `.prompt`.
- Découpage OpenRouter des longs médias, avec recherche de silence et
  recollage des timestamps.
- Progression par phase, pourcentage, position audio, temps écoulé et ETA.
- Annulation avant l'écriture finale ; aucun fichier partiel.
- Coût OpenRouter affiché à 6 décimales, ou « Coût indisponible ».
- Clé API dans le trousseau système, ou `OPENROUTER_API_KEY`.
- Journal local rotatif (1 Mo × 3), sans clé ni audio.

## Prérequis

| Usage | Prérequis |
|---|---|
| Application desktop lite | macOS 12+, Windows 10 21H2+/11 x64, Ubuntu 22.04+ x64 |
| CLI | Python ≥ 3.13, [uv](https://docs.astral.sh/uv/) |
| Moteur Whisper local | `uv sync --extra whisper` |
| Développement | `ffmpeg` et `ffprobe` dans le `PATH` (ou l'override ci-dessous) |

Les artefacts desktop embarquent `ffmpeg` et `ffprobe` ; les utilisateurs du
CLI en développement doivent les installer :

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

## Installation

```bash
# Application desktop lite (OpenRouter uniquement)
uv sync --extra gui
uv run ecotranscribe-desktop

# CLI OpenRouter (dépendances de base)
uv sync
uv run ecotranscribe --provider openrouter fichier.mp4

# CLI Whisper local
uv sync --extra whisper
uv run ecotranscribe fichier.mp3

# Installation complète pour le futur build full
uv sync --extra gui --extra whisper
```

L'application lite n'installe ni `torch`, ni `openai-whisper`, ni modèle local.
Le moteur Whisper du CLI est désormais optionnel : sans l'extra `[whisper]`,
`ecotranscribe --provider whisper` affiche :

```text
Moteur Whisper non installé. Lancez `uv sync --extra whisper`.
```

## Utilisation du CLI

```bash
uv run ecotranscribe <fichier>
uv run ecotranscribe --provider openrouter <fichier>
uv run ecotranscribe --provider openrouter --model <modèle> <fichier>
uv run ecotranscribe --model tiny <fichier>   # Whisper, avec l'extra
```

| Option | Défaut | Description |
|---|---|---|
| `input` | — | Fichier audio ou vidéo |
| `--provider` | `whisper` | `whisper` ou `openrouter` |
| `--model` | `medium` / `mistralai/voxtral-small-transcribe-3-0` | Modèle du moteur |

Le CLI demande confirmation avant d'écraser un fichier existant. Les sorties
sont écrites à côté de la source.

### Clé OpenRouter

```bash
export OPENROUTER_API_KEY="sk-or-..."
uv run ecotranscribe --provider openrouter fichier.mp4
```

L'application desktop permet de saisir la clé, de la mémoriser dans le
trousseau système et de la supprimer. Priorité : champ de l'application >
trousseau > `OPENROUTER_API_KEY`. La clé n'est jamais écrite dans
`QSettings`, les logs ou les détails d'erreur.

## Interface graphique

`uv run ecotranscribe-desktop` ouvre un assistant en six écrans :

1. **Accueil** : transcrire un fichier, transcrire une URL (bientôt
   disponible), options.
2. **Clé OpenRouter** : affiché uniquement si aucune clé active (trousseau,
   session ou `OPENROUTER_API_KEY`).
3. **Fichier et prompt** : chemin, durée, prompt optionnel détecté et
   éditable.
4. **Réglages** : modèle (liste stricte) avec coût estimé de la vidéo,
   langue, SRT/TXT, dossier de sortie.
5. **Progression** : phases, journal, annulation, erreurs inline.
6. **Fin** : fichiers produits, coût, ouverture du dossier.

La clé peut être mémorisée dans le trousseau ou fournie par
`OPENROUTER_API_KEY` ; elle n'est jamais écrite dans les réglages ni dans le
journal. Les réglages non secrets sont conservés entre les lancements.

Le thème est **inspiré des principes du DSFR**, sans utiliser son code, ses
composants, son logo ni ses assets. La police Marianne est utilisée si elle
est installée sur le système, sans être embarquée ; Arial sert de repli.
L'application ne revendique pas une conformité DSFR et ne se présente pas
comme un service de l'État.

Diagnostic sans fenêtre :

```bash
uv run ecotranscribe-desktop --diagnose --diagnose-output /tmp/diag.json
```

Le code de sortie est 0 si `ffmpeg` et `ffprobe` sont résolus, 1 sinon. Le JSON
contient version, flavour, commit, date de build, Python, Qt, plateforme,
architecture, chemins/versions ffmpeg, disponibilité Whisper, modèle par défaut,
dossier de configuration et journal.

## Prompt

Si un fichier de même racine que la source existe, par ordre de priorité :

| Extension | Exemple |
|---|---|
| `.prompt.md` | `réunion.prompt.md` |
| `.prompt.txt` | `réunion.prompt.txt` |
| `.prompt` | `réunion.prompt` |

Le prompt est envoyé comme `context_bias` pour les modèles Mistral. Pour un
autre modèle OpenRouter, il est ignoré avec un avertissement. Whisper l'utilise
comme `initial_prompt`, réinjecté à chaque fenêtre.

Dans l'application, l'édition du prompt modifie uniquement le texte envoyé pour
la requête, pas le fichier `.prompt.*`. Une nouvelle sélection de fichier
recharge le prompt auto-détecté.

## Confidentialité et coût

En mode OpenRouter, **l'audio est envoyé à OpenRouter** ; le prompt l'est
lorsque le modèle le supporte. N'utilisez pas cette édition pour des
enregistrements que vous ne pouvez pas transmettre à un service tiers.

L'application n'émet aucune requête réseau hors OpenRouter : pas de télémétrie,
pas de vérification de mise à jour. Le coût cumulé `usage.cost` est affiché
après la transcription. `0.0` est un coût valide ; le champ absent donne
« Coût indisponible ».

## Distribution

Les releases GitHub publient :

| OS | Artefact principal | Fallback |
|---|---|---|
| macOS arm64 / x64 | DMG signé ad-hoc + ZIP | notice `LIRE-MOI-macOS.txt` |
| Windows x64 | ZIP portable | installeur Inno Setup optionnel |
| Linux x64 | AppImage | `tar.gz` |

Chaque release publie `SHA256SUMS.txt` avec une ligne par artefact. Les DMG,
ZIP et AppImage sont construits par GitHub Actions à partir du tag.

Le build macOS est signé ad-hoc, **non notarié**. Au premier lancement,
Gatekeeper peut demander une confirmation : suivez
[`docs/install-macos-unsigned.md`](docs/install-macos-unsigned.md), ou exécutez :

```bash
xattr -dr com.apple.quarantine "/Applications/EcoTranscribe Desktop.app"
```

Ne désactivez pas Gatekeeper globalement. La notice complète et les commandes
de vérification SHA256 sont incluses dans les artefacts.

## Build local

```bash
# Préparer l'environnement de build
uv sync --extra gui --extra dev

# macOS : compiler ffmpeg/ffprobe LGPL depuis les sources épinglées
uv run python packaging/build_ffmpeg_source.py --target darwin-arm64
# Windows/Linux : récupérer le binaire LGPL précompilé, vérifié par SHA256
uv run python packaging/fetch_ffmpeg.py --target win-x64

# Icônes
uv run python packaging/make_icons.py

# Application PyInstaller onedir
uv run pyinstaller --noconfirm packaging/pyinstaller.spec
```

Sur macOS :

```bash
bash packaging/sign_macos.sh "dist/EcoTranscribe Desktop.app"
bash packaging/make_dmg.sh 0.3.0 arm64 "$(git rev-parse --short HEAD)" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" v0.3.0
```

Windows : `packaging/make_windows.ps1` produit le ZIP portable et, si Inno
Setup est installé, l'installeur optionnel. Linux :
`packaging/make_appimage.sh` produit l'AppImage et le `tar.gz`.

La procédure complète, les variables et les vérifications sont dans
[`docs/distribution.md`](docs/distribution.md).

## Tests

```bash
uv run pytest
```

Sous Linux sans affichage :

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
```

Les tests unitaires ne font aucun appel réseau et ne nécessitent pas de clé
OpenRouter. Les tests GUI utilisent un `QSettings` temporaire, un `KeyStore`
en mémoire et un `DialogService` factice.

## Structure

```text
src/ecotranscribe/
├── core/          # modèles, erreurs, média, writers, service, moteurs
├── cli.py         # CLI rich
└── gui/           # fenêtre PySide6, worker, settings, keyring, diagnostic
packaging/         # PyInstaller, ffmpeg épinglé, signature, DMG, Inno, AppImage
tests/             # tests cœur, CLI, GUI et packaging
docs/              # notice macOS, distribution, release notes
```

## Compatibilité macOS

`PySide6-Essentials` est borné à `< 6.10` (6.9.3) : les versions 6.10+ exigent
macOS 13 ou 14 selon les wheels, alors que l'édition lite cible macOS 12+.
Cette borne est nécessaire pour `macos-15-intel` et macOS 12.

## Licence

MIT — voir [`LICENSE`](LICENSE). Les composants tiers et les licences
embarquées (PySide6/Qt, ffmpeg LGPLv2.1+, keyring, etc.)
sont documentés dans [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
