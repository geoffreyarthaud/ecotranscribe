# Third-party notices — EcoTranscribe Desktop lite 0.2.0

EcoTranscribe est distribué sous licence MIT (voir `LICENSE`). Les composants
suivants sont embarqués dans les artefacts binaires.

## PySide6 / Qt

- Composant : PySide6-Essentials 6.9.3, Qt 6.9.
- Licence : LGPLv3 (PySide6), LGPLv3/GPLv3 (Qt selon les modules).
- Version épinglée `< 6.10` pour conserver macOS 12+ et `macos-13`.
- Texte : <https://www.gnu.org/licenses/lgpl-3.0.html>.
- Le build PyInstaller `--onedir` conserve les bibliothèques Qt sous forme de
  fichiers remplaçables dans `_internal/PySide6/Qt/lib` (ou l'équivalent
  `Contents/Frameworks` sur macOS), ce qui permet de relier une version
  modifiée de Qt.

## Python

- Composant : CPython.
- Licence : Python Software Foundation License 2.0.
- Texte : <https://docs.python.org/3/license.html>.

## keyring

- Composant : keyring et ses backends plateforme.
- Licence : MIT.
- Source : <https://github.com/jaraco/keyring>.

## rich

- Composant : rich.
- Licence : MIT.
- Source : <https://github.com/Textualize/rich>.

## Pillow (outil de build uniquement)

- Composant : Pillow.
- Licence : HPND.
- Source : <https://python-pillow.org>.

## PyInstaller

- Composant : PyInstaller.
- Licence : GPLv2 avec exception autorisant la distribution de binaires
  produits ; le bootloader est distribué sous cette exception.
- Source : <https://pyinstaller.org>.

## ffmpeg / ffprobe

Les binaires sont téléchargés au build, vérifiés par SHA256 et embarqués dans
`bin/` (`Contents/Resources/bin` sur macOS). Ils ne sont pas versionnés.

### macOS arm64 — build OSXExperts 9.0.2

- Source : <https://www.osxexperts.net/>.
- Configuration : `--enable-gpl` (GPLv2+), avec notamment libmp3lame, libx264,
  libx265, libvpx.
- Licence : GNU GPL version 2 ou ultérieure.
- Texte : `notices/COPYING.GPLv2.txt`.
- Source correspondante : <https://ffmpeg.org/download.html> et
  <https://www.osxexperts.net/> (build GPL 9.0.2 arm64).
- Aucun code source modifié par EcoTranscribe.

### macOS x64 — build OSXExperts 8.0

- Source : <https://www.osxexperts.net/>.
- Configuration : GPLv2+.
- Texte : `notices/COPYING.GPLv2.txt`.
- Source correspondante : <https://ffmpeg.org/download.html> et
  <https://www.osxexperts.net/> (build GPL 8.0 Intel).
- Aucun code source modifié par EcoTranscribe.

### Windows x64 et Linux x64 — builds BtbN 9.0.2 LGPL

- Source : <https://github.com/BtbN/FFmpeg-Builds>.
- Licence : LGPLv2.1+.
- Texte : `notices/COPYING.LGPLv2.1.txt`.
- Source correspondante : <https://ffmpeg.org/download.html> et la release
  BtbN épinglée dans `ffmpeg.lock.json`.
- Aucun code source modifié par EcoTranscribe.

Les obligations GPL/LGPL applicables (notice, textes de licence, accès à la
source correspondante) sont satisfaites par ce document, les fichiers de
licence joints et les URL ci-dessus. Les binaires ffmpeg sont fournis tels
quels, sans garantie.
