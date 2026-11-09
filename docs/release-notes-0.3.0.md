## EcoTranscribe Desktop 0.3.0

Application desktop OpenRouter pour macOS, Windows et Linux.

### Téléchargements

- macOS arm64 : `ecotranscribe-desktop-macos-arm64-0.3.0.dmg` / `.zip`
- macOS x64 : `ecotranscribe-desktop-macos-x64-0.3.0.dmg` / `.zip`
- Windows x64 : `ecotranscribe-desktop-windows-x64-0.3.0.zip`
  (installeur `.exe` optionnel)
- Linux x64 : `ecotranscribe-desktop-linux-x64-0.3.0.AppImage` / `.tar.gz`

### Installation macOS

Ce build est open-source mais non notarié. Voir la notice incluse :
Réglages Système > Confidentialité et sécurité > « Ouvrir quand même »,
ou :

```bash
xattr -dr com.apple.quarantine "/Applications/EcoTranscribe Desktop.app"
```

Depuis macOS 15, le clic droit puis « Ouvrir » ne contourne plus Gatekeeper.
Ne désactivez pas Gatekeeper globalement.

### Vérification

`SHA256SUMS.txt` est joint à la release. Vérifiez chaque artefact avant de
l'ouvrir :

```bash
shasum -a 256 ecotranscribe-desktop-macos-arm64-0.3.0.dmg
sha256sum ecotranscribe-desktop-linux-x64-0.3.0.AppImage
certutil -hashfile ecotranscribe-desktop-windows-x64-0.3.0.zip SHA256
```

### Nouveautés 0.3.0

- Assistant en six écrans : accueil, clé conditionnelle, fichier/prompt,
  réglages, progression, fin.
- Page Options accessible depuis l'accueil et l'engrenage.
- Progression avec journal permanent, annulation coopérative et erreurs
  inline avec hint, détail technique et accès au journal.
- Thème Qt inspiré des principes du DSFR, clair/sombre.
- Liste des modèles OpenRouter avec tarif horaire approximatif.
- Réglages non secrets conservés à la fermeture ; clé jamais préremplie.
- ffmpeg/ffprobe macOS compilés depuis FFmpeg 9.0.2 et LAME 3.100 en
  LGPLv2.1+ ; licence uniforme macOS/Windows/Linux, sans composant GPL.

### Données

L'application desktop envoie l'audio à OpenRouter ; le prompt est envoyé comme
contexte lorsque le modèle le supporte. La clé API est stockée dans le
trousseau du système si vous cochez « Mémoriser ».
