#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?version}"
ARCH="${2:?arch}"
COMMIT="${3:-dev}"
BUILD_DATE="${4:-}"
TAG="${5:-v$VERSION}"
PROJECT_URL="${PROJECT_URL:-https://github.com/geoffreyarthaud/ecotranscribe}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/EcoTranscribe Desktop.app"
STAGE="$ROOT/packaging/build/dmg"
ZIP_STAGE="$ROOT/packaging/build/zip"

if [[ ! -d "$APP" ]]; then
  echo "Application introuvable : $APP" >&2
  exit 1
fi

rm -rf "$STAGE" "$ZIP_STAGE"
mkdir -p "$STAGE" "$ZIP_STAGE"

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cp "$ROOT/LICENSE" "$STAGE/LICENSE"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$STAGE/THIRD_PARTY_NOTICES.md"
cp -R "$ROOT/packaging/notices" "$STAGE/notices"
uv run --project "$ROOT" python "$ROOT/packaging/render_notices.py" \
  --os macos \
  --output "$STAGE/LIRE-MOI-macOS.txt" \
  --version "$VERSION" \
  --arch "$ARCH" \
  --commit "$COMMIT" \
  --build-date "$BUILD_DATE" \
  --tag "$TAG" \
  --project-url "$PROJECT_URL"

DMG="$DIST/ecotranscribe-desktop-macos-$ARCH-$VERSION.dmg"
ZIP="$DIST/ecotranscribe-desktop-macos-$ARCH-$VERSION.zip"
rm -f "$DMG" "$ZIP"

hdiutil create \
  -volname "EcoTranscribe Desktop" \
  -srcfolder "$STAGE" \
  -ov -format UDZO "$DMG" >/dev/null

cp -R "$APP" "$ZIP_STAGE/"
cp "$STAGE/LIRE-MOI-macOS.txt" "$STAGE/LICENSE" \
  "$STAGE/THIRD_PARTY_NOTICES.md" "$ZIP_STAGE/"
ditto -c -k "$ZIP_STAGE" "$ZIP"

echo "Artefacts :"
echo "  $DMG"
echo "  $ZIP"
(
  cd "$DIST"
  shasum -a 256 "$(basename "$DMG")" "$(basename "$ZIP")"
) | tee "$DIST/SHA256SUMS-macos-$ARCH.txt"
