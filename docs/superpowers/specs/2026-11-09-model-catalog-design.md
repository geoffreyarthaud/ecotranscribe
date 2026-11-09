# Catalogue de modèles dynamique — conception 0.4.0

## Objectif

Mettre à jour, sans release applicative, la liste des modèles proposés dans
l'écran Réglages de l'application desktop, à partir d'un fichier JSON public
versionné dans le dépôt.

## Décisions

- Source canonique : `catalog/models.json`, commité sur la branche `main`.
- URL primaire : `https://raw.githubusercontent.com/ecotranscribe/ecotranscribe/main/catalog/models.json`.
- Aucun domaine personnalisé pour 0.4.0.
- Schéma versionné (`schema: 1`) ; seuls des identifiants de modèles sont
  publiés. Les tarifs restent récupérés en direct depuis OpenRouter.
- L'application tente le téléchargement au démarrage, sans bloquer l'interface.
- Le dernier catalogue valide est mis en cache localement ; la liste embarquée
  `OPENROUTER_MODELS` reste le repli hors ligne.
- Le modèle sélectionné, les modèles récents et un modèle absent du catalogue
  ne sont jamais supprimés de la liste.
- Le CLI ne fait aucun appel catalogue : son défaut embarqué et `--model`
  restent inchangés.
- Les nouveaux modèles reçoivent leur tarif via le client existant.

## Contrat JSON

```json
{
  "schema": 1,
  "updated_at": "2026-11-09",
  "models": [
    "mistralai/voxtral-small-transcribe-3-0",
    "mistralai/voxtral-mini-transcribe-3-0"
  ]
}
```

Règles de validation : objet racine, `schema` entier égal à 1, `models` liste
non vide ; identifiants non vides, uniques, limités à 128 caractères et au
alphabet `A-Za-z0-9._:/-` ; 50 modèles au maximum. Une entrée invalide est
ignorée ; un catalogue structurellement invalide est rejeté en bloc.

## Réseau et confidentialité

L'invariant « seule l'API OpenRouter est contactée » est remplacé par :
OpenRouter et le catalogue statique GitHub raw sont les seuls appels réseau au
runtime. Le catalogue ne contient ni audio, ni clé, ni identifiant utilisateur.
La requête révèle l'adresse IP à GitHub, comme toute requête HTTPS publique.

## Échecs

- Réseau indisponible, HTTP en erreur, JSON invalide : conservation du cache,
  puis de la liste embarquée ; journal en niveau debug uniquement.
- Catalogue valide mais modèle courant absent : le modèle courant reste
  sélectionnable.
- Cache illisible ou non inscriptible : ignoré ; l'application continue.

## Non-objectifs

Signature du catalogue, domaines personnalisés, libellés ou tarifs dans le
JSON, téléchargement depuis le CLI, mise à jour du catalogue pendant une
transcription.

## Critères d'acceptation

- Une modification de `catalog/models.json` sur `main` apparaît dans la liste
  après redémarrage de l'application, sans nouvelle version applicative.
- Hors ligne, la liste embarquée ou le dernier cache restent utilisables.
- Les tests n'effectuent aucun appel réseau réel.
- Les invariants de sortie, de sécurité et de non-blocage restent respectés.
