# Support des proxies PAC dans l'interface graphique

## Intention

Sur un poste Windows sans droits administrateur, le proxy est configuré
par un fichier PAC (`AutoConfigURL`). `urllib.request` ne lit pas le PAC :
il lit les variables d'environnement puis, sur Windows, le registre
(`ProxyEnable`/`ProxyServer`), mais pas `AutoConfigURL`. L'application
graphique doit donc résoudre le PAC via Qt et transmettre le proxy résolu
au moteur OpenRouter, sans modifier le comportement par défaut du CLI ni
des configurations classiques.

## Objectifs

- Le GUI résout le PAC de la configuration système quand aucun proxy
  classique n'est disponible.
- Le moteur OpenRouter utilise le proxy résolu pour ses requêtes HTTP.
- Les variables d'environnement et la configuration système classique
  (macOS, registre Windows) conservent leur comportement actuel.
- Aucune nouvelle dépendance.

## Non-objectifs

- Ne pas ajouter de dépendance (pas de `pypac`, `requests`, `httpx`).
- Ne pas modifier le comportement du CLI.
- Ne pas gérer l'authentification NTLM/Negotiate.
- Ne pas ajouter de réglage proxy manuel dans l'interface.

## Approches

1. **Résolution Qt côté GUI, proxy injecté dans le moteur (retenu).**
   `QNetworkProxyFactory.systemProxyForQuery` résout le PAC. Le proxy
   résolu est passé à `OpenRouterEngine`, qui construit un `ProxyHandler`
   `urllib`. Le comportement par défaut reste intact quand aucun proxy
   n'est résolu.
2. **Résolution PAC dans le cœur avec une bibliothèque dédiée.**
   Ajoute une dépendance (`pypac`) et un moteur JavaScript. Rejeté :
   poids et impact packaging.
3. **Réglage proxy manuel dans l'interface.**
   L'utilisatrice saisit le proxy. Rejeté : moins automatique, et le PAC
   peut changer selon l'URL.

## Conception retenue

### Moteur

`OpenRouterEngine` accepte un paramètre optionnel `proxy: str | None`.
Si `proxy` est fourni, le moteur construit un opener avec
`urllib.request.ProxyHandler({"http": proxy, "https": proxy})`. Sinon, il
conserve l'opener par défaut (`urllib.request.urlopen`), qui lit déjà
`getproxies()`.

`_post_openrouter` accepte un `opener` optionnel ; s'il est fourni, il
utilise `opener.open` au lieu de `urllib.request.urlopen`.

### GUI

Une fonction `resolve_proxy_for(url: str) -> str | None` :

1. Si `urllib.request.getproxies()` contient une entrée pour le schéma
   de l'URL (`https` pour OpenRouter), retourne `None` (le moteur
   utilisera le comportement par défaut). Les entrées `no` et les
   schémas non concernés sont ignorés.
2. Sinon, interroge `QNetworkProxyFactory.systemProxyForQuery` avec
   `QNetworkProxyQuery(QUrl(url))`.
3. Si un proxy de type `HttpProxy` est retourné, retourne
   `http://host:port`. Les proxys SOCKS sont ignorés : `urllib` ne les
   supporte pas sans dépendance supplémentaire.
4. Sinon, retourne `None`.

`MainWindow._default_service` appelle `resolve_proxy_for(OPENROUTER_API_URL)`
et passe le résultat à `OpenRouterEngine(proxy=...)`.

### Cas non couverts

- Proxy PAC nécessitant une authentification NTLM : `urllib` ne la gère
  pas. Le proxy résolu sera utilisé, mais la requête peut échouer.
- Proxy PAC retournant un proxy SOCKS : `urllib` ne supporte pas SOCKS
  sans dépendance supplémentaire. On se limite à HTTP/HTTPS.
- PAC inaccessible : `QNetworkProxyFactory` retourne `NoProxy` ou lève
  une erreur ; on retombe sur le comportement par défaut.

## Tests

- `tests/test_openrouter.py` : le moteur transmet l'opener au transport ;
  l'opener par défaut est utilisé sans proxy.
- `tests/gui/test_network.py` : `resolve_proxy_for` retourne `None` quand
  `getproxies()` est non vide ; retourne le proxy Qt quand `getproxies()`
  est vide ; retourne `None` quand Qt retourne `NoProxy`.
- `tests/gui/test_main_window.py` : `_default_service` injecte le proxy
  résolu dans `OpenRouterEngine`.
