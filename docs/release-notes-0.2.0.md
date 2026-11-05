## EcoTranscribe Desktop 0.2.0 — édition lite

Application desktop OpenRouter pour macOS, Windows et Linux.

### Téléchargements

- macOS arm64 : `ecotranscribe-desktop-lite-macos-arm64-0.2.0.dmg` / `.zip`
- macOS x64 : `ecotranscribe-desktop-lite-macos-x64-0.2.0.dmg` / `.zip`
- Windows x64 : `ecotranscribe-desktop-lite-windows-x64-0.2.0.zip` (installeur `.exe` optionnel)
- Linux x64 : `ecotranscribe-desktop-lite-linux-x64-0.2.0.AppImage` / `.tar.gz`

### Installation macOS

Ce build est open-source mais non notarié. Voir la notice incluse :
Réglages Système > Confidentialité et sécurité > « Ouvrir quand même »,
ou `xattr -dr com.apple.quarantine "/Applications/EcoTranscribe Desktop.app"`.

### Vérification

`SHA256SUMS.txt` est joint à la release. Vérifiez chaque artefact avant de
l'ouvrir :

```bash
shasum -a 256 ecotranscribe-desktop-lite-macos-arm64-0.2.0.dmg
sha256sum ecotranscribe-desktop-lite-linux-x64-0.2.0.AppImage
certutil -hashfile ecotranscribe-desktop-lite-windows-x64-0.2.0.zip SHA256
```

### Données

L'édition lite envoie l'audio à OpenRouter ; le prompt est envoyé comme
contexte lorsque le modèle le supporte. La clé API est stockée dans le
trousseau du système si vous cochez « Mémoriser ».
