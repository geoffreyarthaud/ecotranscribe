# Third-party notices — EcoTranscribe Desktop

EcoTranscribe est distribué sous licence MIT (voir `LICENSE`). Les composants
suivants sont embarqués dans les artefacts binaires.

## PySide6 / Qt

- Composant : PySide6-Essentials 6.9.3, Qt 6.9.
- Licence : LGPLv3 (PySide6), LGPLv3/GPLv3 (Qt selon les modules).
- Version épinglée `< 6.10` pour conserver macOS 12+ et le runner Intel
  `macos-15-intel`.
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

Les binaires sont téléchargés ou construits au build, vérifiés par SHA256 et
embarqués dans `bin/` (`Contents/Resources/bin` sur macOS). Ils ne sont pas
versionnés.

### macOS arm64 et x64 — build source EcoTranscribe 9.0.2 LGPL

- Source : <https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz>.
- SHA256 : `8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`.
- Configuration : `--disable-gpl --disable-nonfree --disable-version3`,
  composants limités aux formats audio/vidéo pris en charge par
  EcoTranscribe, `--enable-libmp3lame`.
- Licence : GNU LGPL version 2.1 ou ultérieure.
- Texte : `notices/COPYING.LGPLv2.1.txt`.
- Source correspondante : le tarball ci-dessus, le script
  `packaging/build_ffmpeg_source.py` et la configuration dans
  `packaging/ffmpeg.lock.json`.
- Aucun code source modifié par EcoTranscribe.

### Windows x64 et Linux x64 — builds BtbN 9.0.2 LGPL

- Source : <https://github.com/BtbN/FFmpeg-Builds>.
- Licence : LGPLv2.1+.
- Texte : `notices/COPYING.LGPLv2.1.txt`.
- Source correspondante : <https://ffmpeg.org/download.html> et la release
  BtbN épinglée dans `ffmpeg.lock.json`.
- Aucun code source modifié par EcoTranscribe.

## LAME (libmp3lame)

- Composant : LAME 3.100, bibliothèque `libmp3lame`.
- Licence : GNU LGPL version 2.0.
- Texte : `notices/COPYING.LGPLv2.0.txt`.
- Source : <https://downloads.sourceforge.net/project/lame/lame/3.100/lame-3.100.tar.gz>.
- Utilisé par ffmpeg pour encoder les tranches MP3 envoyées à OpenRouter.

## zlib

- Composant : zlib, bibliothèque système sur macOS.
- Licence : zlib License.
- Texte : <https://zlib.net/zlib_license.html>.

Les obligations GPL/LGPL applicables (notice, textes de licence, accès à la
source correspondante) sont satisfaites par ce document, les fichiers de
licence joints et les URL ci-dessus. Les binaires ffmpeg sont fournis tels
quels, sans garantie.
