# Distribution et build — EcoTranscribe Desktop

Ce guide décrit le build local et la release GitHub de l'application desktop.

## Cibles

| Cible | Runner CI | Artefacts |
|---|---|---|
| macOS arm64 | `macos-15` | `.dmg`, `.zip` |
| macOS x64 | `macos-15-intel` | `.dmg`, `.zip` |
| Windows x64 | `windows-2025` | `.zip`, installeur Inno optionnel |
| Linux x64 | `ubuntu-22.04` | `.AppImage`, `.tar.gz` |

Noms :

```text
ecotranscribe-desktop-macos-arm64-<version>.dmg
ecotranscribe-desktop-macos-arm64-<version>.zip
ecotranscribe-desktop-macos-x64-<version>.dmg
ecotranscribe-desktop-macos-x64-<version>.zip
ecotranscribe-desktop-windows-x64-<version>.zip
ecotranscribe-desktop-windows-x64-<version>-setup.exe
ecotranscribe-desktop-linux-x64-<version>.AppImage
ecotranscribe-desktop-linux-x64-<version>.tar.gz
SHA256SUMS.txt
```

Les binaires ne sont jamais commités. `dist/`, `build/` et `vendor/` sont
ignorés.

## Préparer l'environnement

```bash
uv sync --extra gui --extra dev
```

Sur macOS, la compilation source de ffmpeg nécessite les Xcode Command Line
Tools (`clang`, `make`). `--disable-x86asm` évite la dépendance `nasm` ; LAME
et FFmpeg sont compilés depuis leurs tarballs, sans Homebrew.

`build_ffmpeg_source.py` (macOS) et `fetch_ffmpeg.py` (Windows/Linux) sont les
seules étapes réseau du build. Le lock `packaging/ffmpeg.lock.json` fixe URL,
SHA256, version et configuration :

| Cible | Build | Licence |
|---|---|---|
| `darwin-arm64` | source FFmpeg 9.0.2 + LAME 3.100 | LGPLv2.1+ |
| `darwin-x64` | source FFmpeg 9.0.2 + LAME 3.100 | LGPLv2.1+ |
| `win-x64` | BtbN 9.0.2 static | LGPLv2.1+ |
| `linux-x64` | BtbN 9.0.2 static | LGPLv2.1+ |

```bash
# macOS : compilation LGPL depuis les sources
uv run python packaging/build_ffmpeg_source.py --target darwin-arm64
# ou --target darwin-x64 sur une machine/runner Intel

# Windows/Linux : binaire précompilé LGPL, vérifié par SHA256
uv run python packaging/fetch_ffmpeg.py --target win-x64
# ou --target linux-x64

# Vérification fonctionnelle et de licence
uv run python packaging/check_ffmpeg_build.py --target darwin-arm64
```

Le build macOS vérifie les SHA256 des tarballs FFmpeg et LAME, compile LAME en
statique, configure FFmpeg avec les composants strictement utilisés par
l'application, puis exécute le même contrôle que `check_ffmpeg_build.py`. Le
cache CI est indexé par le hash du lock ; un second appel est ignoré si le
marqueur `.source-build.json` correspond. Utiliser `--force` pour reconstruire.

`ECOTRANSCRIBE_FFMPEG_DIR` permet de pointer vers un autre dossier en
développement. Hors override, la résolution cherche `_MEIPASS/bin`,
`Contents/Resources/bin` pour une app macOS gelée, puis le `PATH`.

## Icônes

```bash
uv run python packaging/make_icons.py
```

Génère les PNG multi-tailles embarqués dans
`src/ecotranscribe/gui/assets/` (icône de l'application et logo d'en-tête),
puis `packaging/build/icon.png`, `EcoTranscribe.icns` (macOS avec
`iconutil`) et `icon.ico` (Pillow). La source est
`assets/ecotranscribe-650.png` ; relancer le script après tout changement de
logo.

## Build PyInstaller

```bash
ECOTRANSCRIBE_TARGET=darwin-arm64 \
ECOTRANSCRIBE_COMMIT="$(git rev-parse --short HEAD)" \
ECOTRANSCRIBE_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
uv run pyinstaller --noconfirm packaging/pyinstaller.spec
```

Caractéristiques :

- `--onedir`, jamais `--onefile`, `console=False`.
- nom `EcoTranscribe Desktop`, bundle `app.ecotranscribe.desktop` ;
- `bin/ffmpeg` et `bin/ffprobe` embarqués ;
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, `README.md` et `notices/` inclus ;
- exclusions : : `whisper`, `torch`, `torchaudio`, `torchvision`, `numba`,
  `tiktoken`, `triton`, `tensorboard`, `pytest`, `tkinter` ;
- `ecotranscribe_build_info` généré dans `build/generated/` avec commit et
  date ;
- `LSMinimumSystemVersion=12.0` sur macOS.

## macOS : signature ad-hoc, DMG et ZIP

```bash
bash packaging/sign_macos.sh "dist/EcoTranscribe Desktop.app"

bash packaging/make_dmg.sh 0.4.0 arm64 \
  "$(git rev-parse --short HEAD)" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" v0.4.0
```

La signature est faite de l'intérieur vers l'extérieur :

1. tous les Mach-O imbriqués (`*.dylib`, `*.so`, exécutables, ffmpeg/ffprobe)
   avec `codesign --force --sign -` ;
2. le `.app` en dernier ;
3. `codesign --verify --deep --strict --verbose=2` doit réussir ;
4. `spctl --assess` est exécuté mais **ne fait pas échouer** le build : le
   rejet est attendu sans notarisation.

Le DMG contient :

- `EcoTranscribe Desktop.app` ;
- un lien `Applications` → `/Applications` ;
- `LIRE-MOI-macOS.txt` ;
- `LICENSE` ;
- `THIRD_PARTY_NOTICES.md`.

`SHA256SUMS.txt` n'est pas dans le DMG : il contient le hash du DMG et est
publié comme asset de release.

Vérifications :

```bash
codesign --verify --deep --strict --verbose=2 "dist/EcoTranscribe Desktop.app"
spctl --assess --type execute --verbose=4 "dist/EcoTranscribe Desktop.app" || true
"dist/EcoTranscribe Desktop.app/Contents/MacOS/EcoTranscribe Desktop" \
  --diagnose --diagnose-output /tmp/diag.json
uv run python packaging/check_diagnostic.py /tmp/diag.json
```

## Windows : ZIP portable et installeur optionnel

Sur Windows, après PyInstaller :

```powershell
$Version = uv run python -c "import ecotranscribe; print(ecotranscribe.__version__)"
./packaging/make_windows.ps1 -Version $Version -Arch x64 `
  -Commit $env:ECOTRANSCRIBE_COMMIT -BuildDate $env:ECOTRANSCRIBE_BUILD_DATE
```

Le script :

- rend `LIRE-MOI-Windows.txt` et copie licences/notices dans le dossier de
  l'application ;
- crée le ZIP portable avec le dossier complet `EcoTranscribe Desktop/` ;
- vérifie la présence de l'exe, `_internal/bin/ffmpeg.exe`,
  `_internal/bin/ffprobe.exe`, de la notice et des licences ;
- lance Inno Setup s'il est installé, sinon avertit sans échouer ;
- écrit `SHA256SUMS-windows-x64.txt`.

Mode simple principal : extraire le ZIP et lancer
`EcoTranscribe Desktop.exe`, sans droits administrateur. L'installeur
`windows.iss` est optionnel (`PrivilegesRequired=lowest`, raccourci menu
Démarrer et désinstallation).

## Linux : AppImage principal et tar.gz

Sur Ubuntu 22.04 :

```bash
VERSION="$(uv run python -c 'import ecotranscribe; print(ecotranscribe.__version__)')"
bash packaging/make_appimage.sh "$VERSION" x64 \
  "$ECOTRANSCRIBE_COMMIT" "$ECOTRANSCRIBE_BUILD_DATE" "v$VERSION"
```

Le script :

- construit un AppDir avec l'application dans
  `usr/lib/ecotranscribe/`, un lanceur sans espace `usr/bin/ecotranscribe-desktop`,
  un `AppRun`, le desktop file et l'icône ;
- télécharge `appimagetool` 1.9.1 épinglé et vérifie son SHA256 ;
- l'exécute avec `--appimage-extract-and-run` pour ne pas dépendre de FUSE ;
- crée aussi le `tar.gz` de fallback ;
- écrit `SHA256SUMS-linux-x64.txt`.

Vérifications :

```bash
APPIMAGE="$(ls dist/*.AppImage | head -1)"
QT_QPA_PLATFORM=offscreen "$APPIMAGE" --appimage-extract-and-run \
  --diagnose --diagnose-output /tmp/diag-appimage.json
uv run python packaging/check_diagnostic.py /tmp/diag-appimage.json

mkdir -p /tmp/eco-tar
tar -xzf dist/*.tar.gz -C /tmp/eco-tar
QT_QPA_PLATFORM=offscreen "/tmp/eco-tar/EcoTranscribe Desktop/EcoTranscribe Desktop" \
  --diagnose --diagnose-output /tmp/diag-tar.json
```

## CI et release

`.github/workflows/build.yml` :

- déclencheurs : tags `v*`, `workflow_dispatch` ;
- tests `uv run pytest` sur chaque OS, avec `QT_QPA_PLATFORM=offscreen` ;
- garde-fou tag == version paquet == `pyproject.toml`, et présence de
  `docs/release-notes-<version>.md` ;
- cache uv et cache ffmpeg (clé = hash du lock) ;
- build source LGPL de ffmpeg sur macOS, récupération des binaires LGPL
  épinglés sur Windows/Linux, puis contrôle `check_ffmpeg_build.py` ;
- build, signature macOS, DMG/ZIP, ZIP Windows/Inno, AppImage/tar.gz ;
- diagnostic gelé, vérification ffmpeg, absence torch/whisper, tailles ;
- upload d'artefacts et fragments SHA256 ;
- job `release` sur tag avec `permissions: contents: write`, qui concatène les
  fragments en `SHA256SUMS.txt` et publie la release via
  `softprops/action-gh-release`.

Aucun secret n'est requis pour construire les artefacts.

## Checklist avant release

- [ ] `uv run pytest` passe sur les trois OS.
- [ ] `uv run ecotranscribe-desktop` ouvre la fenêtre en développement.
- [ ] `build_ffmpeg_source.py` (macOS) et `fetch_ffmpeg.py` (Windows/Linux)
      vérifient les SHA256.
- [ ] `check_ffmpeg_build.py` confirme LGPLv2.1+, `silencedetect`,
      `libmp3lame` et les formats supportés.
- [ ] `pyinstaller.spec` produit un onedir sans torch/whisper.
- [ ] macOS : `codesign --verify --deep --strict` OK, `spctl` rejeté comme
      attendu, DMG avec notice/licences/lien Applications.
- [ ] Windows : ZIP s'extrait, l'exe se lance sans console, diagnostic OK.
- [ ] Linux : AppImage se lance avec `--appimage-extract-and-run`, tar.gz OK.
- [ ] Diagnostic `flavor=desktop`, `whisper_available=false`, chemins ffmpeg
      dans le bundle.
- [ ] Tailles : app ≤ 600 Mo (macOS reste sous 450 Mo), artefact
      compressé ≤ 300 Mo. Les builds BtbN Windows/Linux embarquent
      ffmpeg+ffprobe complets (~270 Mo).
- [ ] `SHA256SUMS.txt` couvre tous les assets.
- [ ] Tag `v<version>` == version paquet == `pyproject.toml`, et
      `docs/release-notes-<version>.md` présent.
- [ ] README, notices et release notes à jour.

## Dépannage

- **Gatekeeper** : suivre `docs/install-macos-unsigned.md` ; ne pas désactiver
  Gatekeeper globalement.
- **FUSE absent sous Linux** : utiliser
  `--appimage-extract-and-run` ou le `tar.gz`.
- **Clé non mémorisée** : le backend keyring peut être indisponible ; la clé
  reste valable pour la session et `OPENROUTER_API_KEY` sert de fallback.
- **Trousseau Linux** : installer un service Secret Service (GNOME Keyring,
  KWallet) ; sinon utiliser la variable d'environnement.
- **ffmpeg introuvable** : vérifier `ECOTRANSCRIBE_FFMPEG_DIR` en
  développement, relancer `build_ffmpeg_source.py --force` sur macOS ou
  réinstaller l'artefact.
- **Taille dépassée** : inspecter les plugins Qt, les doublons PyInstaller et
  la taille du build ffmpeg. Ne pas retirer de fonctionnalité sans validation.
