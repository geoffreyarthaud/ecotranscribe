# Distribution et build — EcoTranscribe Desktop lite

Ce guide décrit le build local et la release GitHub de l'édition lite 0.2.0.

## Cibles

| Cible | Runner CI | Artefacts |
|---|---|---|
| macOS arm64 | `macos-14` | `.dmg`, `.zip` |
| macOS x64 | `macos-13` | `.dmg`, `.zip` |
| Windows x64 | `windows-latest` | `.zip`, installeur Inno optionnel |
| Linux x64 | `ubuntu-22.04` | `.AppImage`, `.tar.gz` |

Noms :

```text
ecotranscribe-desktop-lite-macos-arm64-0.2.0.dmg
ecotranscribe-desktop-lite-macos-arm64-0.2.0.zip
ecotranscribe-desktop-lite-macos-x64-0.2.0.dmg
ecotranscribe-desktop-lite-macos-x64-0.2.0.zip
ecotranscribe-desktop-lite-windows-x64-0.2.0.zip
ecotranscribe-desktop-lite-windows-x64-0.2.0-setup.exe
ecotranscribe-desktop-lite-linux-x64-0.2.0.AppImage
ecotranscribe-desktop-lite-linux-x64-0.2.0.tar.gz
SHA256SUMS.txt
```

Les binaires ne sont jamais commités. `dist/`, `build/` et `vendor/` sont
ignorés.

## Préparer l'environnement

```bash
uv sync --extra gui --extra dev
```

`fetch_ffmpeg.py` est la seule étape réseau du build. Le lock
`packaging/ffmpeg.lock.json` fixe URL, SHA256, type d'archive et membres :

| Cible | Build | Licence |
|---|---|---|
| `darwin-arm64` | OSXExperts 9.0.2 | GPLv2+ |
| `darwin-x64` | OSXExperts 8.0 | GPLv2+ |
| `win-x64` | BtbN 9.0.2 static | LGPLv2.1+ |
| `linux-x64` | BtbN 9.0.2 static | LGPLv2.1+ |

```bash
uv run python packaging/fetch_ffmpeg.py --target darwin-arm64
# ou --target win-x64 / linux-x64 / darwin-x64
```

Le script vérifie le SHA256 avant extraction, extrait uniquement les membres
déclarés et rend les binaires exécutables. Le cache CI est indexé par le hash
du lock.

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
- exclusions lite : `whisper`, `torch`, `torchaudio`, `torchvision`, `numba`,
  `tiktoken`, `triton`, `tensorboard`, `pytest`, `tkinter` ;
- `ecotranscribe_build_info` généré dans `build/generated/` avec commit et
  date ;
- `LSMinimumSystemVersion=12.0` sur macOS.

## macOS : signature ad-hoc, DMG et ZIP

```bash
bash packaging/sign_macos.sh "dist/EcoTranscribe Desktop.app"

bash packaging/make_dmg.sh 0.2.0 arm64 \
  "$(git rev-parse --short HEAD)" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" v0.2.0
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

`.github/workflows/build-lite.yml` :

- déclencheurs : tags `v*`, `workflow_dispatch` ;
- tests `uv run pytest` sur chaque OS, avec `QT_QPA_PLATFORM=offscreen` ;
- cache uv et cache ffmpeg (clé = hash du lock) ;
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
- [ ] `packaging/fetch_ffmpeg.py` vérifie les SHA256.
- [ ] `pyinstaller.spec` produit un onedir sans torch/whisper.
- [ ] macOS : `codesign --verify --deep --strict` OK, `spctl` rejeté comme
      attendu, DMG avec notice/licences/lien Applications.
- [ ] Windows : ZIP s'extrait, l'exe se lance sans console, diagnostic OK.
- [ ] Linux : AppImage se lance avec `--appimage-extract-and-run`, tar.gz OK.
- [ ] Diagnostic `flavor=lite`, `whisper_available=false`, chemins ffmpeg
      dans le bundle.
- [ ] Tailles : app ≤ 450 Mo, artefact compressé ≤ 300 Mo.
- [ ] `SHA256SUMS.txt` couvre tous les assets.
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
  développement, ou réinstaller l'artefact.
- **Taille dépassée** : inspecter les plugins Qt, les doublons PyInstaller et
  la taille du build ffmpeg. Ne pas retirer de fonctionnalité sans validation.
