# Catalogue de modèles dynamique — plan d'implémentation 0.4.0

## 1. Contrat et parseur

- Ajouter `catalog/models.json` (schéma 1, modèles actuels).
- Ajouter `src/ecotranscribe/core/catalog.py` : `parse_catalog`.
- Tests `tests/test_catalog.py` : valide, invalide, doublons, journal,
  identifiants rejetés, fichier commité.

## 2. Client GUI et cache

- Ajouter `src/ecotranscribe/gui/catalog.py` : `CatalogClient`,
  `GitHubCatalogClient`, lecture/écriture atomique du cache.
- Tests `tests/gui/test_catalog.py` : payload valide, cache, payload
  invalide, erreur réseau simulée.

## 3. Intégration GUI

- `SettingsPage.set_catalog` remplace la liste en conservant le modèle
  sélectionné.
- `MainWindow` reçoit un `catalog_client`, applique le catalogue à l'ouverture
  des réglages, rafraîchit les tarifs des nouveaux modèles.
- `app.py` injecte `GitHubCatalogClient`.
- Tests d'intégration avec `FakeCatalogClient`.

## 4. Livraison 0.4.0

- Version `0.4.0`, entrée `CHANGELOG.md`, notes `docs/release-notes-0.4.0.md`.
- Mettre à jour `README.md`, `AGENTS.md`, exemples de version.
- `uv run pytest` complet et smoke du client sur un catalogue local.
