## EcoTranscribe Desktop 0.4.1

Application desktop OpenRouter pour macOS, Windows et Linux.

### Téléchargements

- macOS arm64 : `ecotranscribe-desktop-macos-arm64-0.4.1.dmg` / `.zip`
- macOS x64 : `ecotranscribe-desktop-macos-x64-0.4.1.dmg` / `.zip`
- Windows x64 : `ecotranscribe-desktop-windows-x64-0.4.1.zip`
  (installeur `.exe` optionnel)
- Linux x64 : `ecotranscribe-desktop-linux-x64-0.4.1.AppImage` / `.tar.gz`

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
shasum -a 256 ecotranscribe-desktop-macos-arm64-0.4.1.dmg
sha256sum ecotranscribe-desktop-linux-x64-0.4.1.AppImage
certutil -hashfile ecotranscribe-desktop-windows-x64-0.4.1.zip SHA256
```

### Nouveautés 0.4.1

- Prise en charge des proxies PAC dans l'interface graphique : le proxy
  système est résolu via Qt quand aucun proxy classique n'est configuré,
  puis transmis au moteur OpenRouter. Le CLI et les configurations proxy
  classiques (variables d'environnement, registre Windows, système macOS)
  conservent leur comportement.

### Données

L'application desktop envoie l'audio à OpenRouter ; le prompt est envoyé comme
contexte lorsque le modèle le supporte. Au démarrage, elle récupère le
catalogue public depuis GitHub raw ; cette requête ne contient ni audio ni
clé. La clé API est stockée dans le trousseau du système si vous cochez
« Mémoriser ».
