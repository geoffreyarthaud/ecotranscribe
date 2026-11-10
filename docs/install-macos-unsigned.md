# Installer EcoTranscribe Desktop sur macOS (binaire non notarié)

EcoTranscribe Desktop 0.4.1.

Version 0.4.1 — build CI
Commit : voir la release `v0.4.1` (`SHA256SUMS.txt` et notes de release).
Source : <https://github.com/geoffreyarthaud/ecotranscribe>

Cette application est open-source (MIT). Le binaire macOS est **signé
ad-hoc**, mais **non notarié** : le projet ne dispose pas d'un compte Apple
Developer payant. Gatekeeper demande donc une confirmation au premier
lancement.

## Téléchargement

Selon votre Mac :

```text
ecotranscribe-desktop-macos-arm64-0.4.1.dmg   # Apple Silicon
ecotranscribe-desktop-macos-x64-0.4.1.dmg     # Intel
```

Les archives ZIP sont fournies en fallback.

## Installation

1. Ouvrir le `.dmg` et glisser « EcoTranscribe Desktop.app » dans
   `/Applications`.
2. Premier lancement :
   - Si macOS affiche « ... ne peut pas être ouverte », ouvrir
     **Réglages Système > Confidentialité et sécurité**, puis cliquer sur
     **« Ouvrir quand même »** et s'authentifier.
   - Ou, dans Terminal :

     ```bash
     xattr -dr com.apple.quarantine "/Applications/EcoTranscribe Desktop.app"
     ```

   - Sur macOS 12 à 14, un clic droit sur l'application puis **« Ouvrir »**
     fonctionne généralement.
3. Lancer l'application.

## Vérifier l'intégrité

Télécharger `SHA256SUMS.txt` depuis la release, puis :

```bash
shasum -a 256 "ecotranscribe-desktop-macos-arm64-0.4.1.dmg"
# comparer avec la ligne correspondante de SHA256SUMS.txt
```

Pour vérifier la signature ad-hoc du bundle installé :

```bash
codesign --verify --deep --strict --verbose=2 "/Applications/EcoTranscribe Desktop.app"
```

`spctl --assess --type execute` échoue volontairement : c'est le comportement
attendu d'un binaire non notarié. Ne désactivez pas Gatekeeper globalement et
n'utilisez pas `spctl --master-disable`.

## Pourquoi cet avertissement ?

macOS Gatekeeper vérifie la signature Developer ID et la notarisation. Sans
compte Apple Developer, le binaire est signé ad-hoc : il peut s'exécuter, mais
Gatekeeper demande une confirmation manuelle au premier lancement. Chaque
nouvelle version téléchargée peut nécessiter à nouveau cette étape.

## Sécurité

- Code source et workflow de build publics :
  <https://github.com/geoffreyarthaud/ecotranscribe>
- Le binaire est produit par GitHub Actions à partir du tag `v0.4.1`.
- La release publie `SHA256SUMS.txt`.
- Le bundle embarque `ffmpeg`/`ffprobe` ; aucun `ffmpeg` système ni Python
  n'est requis.

## Données

L'application desktop envoie l'audio à OpenRouter pour transcription. Le prompt est
envoyé comme contexte lorsque le modèle le supporte (modèles Mistral).
Au démarrage, elle récupère aussi le catalogue public des modèles depuis
GitHub raw ; cette requête ne contient ni audio ni clé.
N'utilisez pas cette édition pour des enregistrements que vous ne pouvez pas
transmettre à un service tiers. La clé API est stockée dans le trousseau macOS
si vous cochez « Mémoriser » ; sinon elle peut venir de
`OPENROUTER_API_KEY`.
