#!/usr/bin/env bash
set -euo pipefail

APP="${1:?Usage: sign_macos.sh \"EcoTranscribe Desktop.app\"}"

if [[ ! -d "$APP" ]]; then
  echo "Application introuvable : $APP" >&2
  exit 1
fi

echo "Signature ad-hoc des binaires imbriqués…"
while IFS= read -r -d '' file; do
  if file -b "$file" | grep -q "Mach-O"; then
    codesign --force --sign - --timestamp=none "$file"
  fi
done < <(find "$APP" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -111 \) -print0)

echo "Signature de l'application…"
codesign --force --sign - --timestamp=none "$APP"

echo "Vérification…"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "Évaluation Gatekeeper (rejet attendu sans notarisation)…"
spctl --assess --type execute --verbose=4 "$APP" || true

echo "Signature ad-hoc terminée : $APP"
