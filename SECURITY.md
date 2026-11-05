# Sécurité — EcoTranscribe

## Versions prises en charge

La version 0.2.x de l'édition lite reçoit les correctifs de sécurité.

## Binaires non notariés

- macOS : signature ad-hoc, sans Developer ID ni notarisation. Gatekeeper
  demande une confirmation au premier lancement. La notice
  [`docs/install-macos-unsigned.md`](docs/install-macos-unsigned.md) décrit la
  procédure et la vérification `codesign`.
- Windows : pas de signature Authenticode. SmartScreen peut demander une
  confirmation. Vérifiez le SHA256 avant exécution.
- Linux : AppImage non signé. Vérifiez le SHA256 avant exécution.

Chaque release publie `SHA256SUMS.txt`. Ne désactivez pas Gatekeeper ou
SmartScreen globalement ; contournez uniquement l'avertissement pour l'artefact
vérifié.

## Vérifier un artefact

```bash
# macOS
shasum -a 256 ecotranscribe-desktop-lite-macos-arm64-0.2.0.dmg
codesign --verify --deep --strict --verbose=2 "/Applications/EcoTranscribe Desktop.app"

# Windows
certutil -hashfile ecotranscribe-desktop-lite-windows-x64-0.2.0.zip SHA256

# Linux
sha256sum ecotranscribe-desktop-lite-linux-x64-0.2.0.AppImage
```

Comparez avec `SHA256SUMS.txt` de la même release. `spctl --assess` est rejeté
comme attendu pour un binaire non notarié.

## Données et secrets

- L'édition lite envoie l'audio à OpenRouter pour transcription. Le prompt est
  envoyé comme contexte lorsque le modèle le supporte (Mistral).
- La clé OpenRouter est lue depuis le trousseau système ou
  `OPENROUTER_API_KEY`. Elle n'est jamais écrite dans `QSettings`, les logs ou
  les détails d'erreur.
- Le journal applicatif est local et rotatif (1 Mo × 3). Il peut contenir des
  chemins et des messages d'erreur, jamais l'audio ni la clé.
- Aucune télémétrie, vérification de mise à jour ou requête hors OpenRouter.

## Signaler une vulnérabilité

N'ouvrez pas d'issue publique contenant une clé, un audio, un transcript ou un
chemin personnel. Utilisez l'avis de sécurité privé du dépôt GitHub
(*Security > Advisories > Report a vulnerability*) ou contactez le mainteneur
par un canal privé indiqué sur la page du dépôt. Incluez version, OS,
artefact, étapes de reproduction et impact ; ne joignez pas de secret.

## Chaîne d'approvisionnement

- `uv.lock` fige les dépendances Python ; `PyInstaller` est épinglé par le lock.
- `packaging/ffmpeg.lock.json` fige URL et SHA256 de ffmpeg/ffprobe.
- `appimagetool` 1.9.1 est épinglé et vérifié par SHA256.
- Les artefacts sont construits par GitHub Actions à partir du tag ; aucun
  binaire n'est commité.
- Les licences et obligations ffmpeg (GPL/LGPL) sont documentées dans
  `THIRD_PARTY_NOTICES.md` et `packaging/notices/`.
