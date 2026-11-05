#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?version}"
ARCH="${2:-x64}"
COMMIT="${3:-dev}"
BUILD_DATE="${4:-}"
TAG="${5:-v$VERSION}"
PROJECT_URL="${PROJECT_URL:-https://github.com/ecotranscribe/ecotranscribe}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/EcoTranscribe Desktop"
APPDIR="$ROOT/packaging/build/AppDir"
STAGE="$ROOT/packaging/build/linux"
TOOL="$ROOT/packaging/build/appimagetool"
APPIMAGE="$DIST/ecotranscribe-desktop-lite-linux-$ARCH-$VERSION.AppImage"
TARBALL="$DIST/ecotranscribe-desktop-lite-linux-$ARCH-$VERSION.tar.gz"

APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"

if [[ ! -d "$APP" ]]; then
  echo "Application introuvable : $APP" >&2
  exit 1
fi

rm -rf "$APPDIR" "$STAGE" "$TOOL"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$STAGE"

cp -R "$APP" "$APPDIR/usr/lib/ecotranscribe"
mkdir -p "$APPDIR/usr/bin"
cp "$ROOT/packaging/build/icon.png" "$APPDIR/ecotranscribe.png"
cp "$ROOT/packaging/build/icon.png" "$APPDIR/.DirIcon"

cat > "$APPDIR/usr/bin/ecotranscribe-desktop" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/../lib/ecotranscribe/EcoTranscribe Desktop" "$@"
EOF
chmod 755 "$APPDIR/usr/bin/ecotranscribe-desktop"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/ecotranscribe-desktop" "$@"
EOF
chmod 755 "$APPDIR/AppRun"

cat > "$APPDIR/usr/share/applications/ecotranscribe.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=EcoTranscribe Desktop
Comment=Transcription audio et vidéo via OpenRouter
Exec=ecotranscribe-desktop
Icon=ecotranscribe
Categories=AudioVideo;Audio;Utility;
Terminal=false
EOF

uv run --project "$ROOT" python "$ROOT/packaging/render_notices.py" \
  --os linux \
  --output "$APPDIR/LIRE-MOI-Linux.txt" \
  --version "$VERSION" \
  --arch "$ARCH" \
  --commit "$COMMIT" \
  --build-date "$BUILD_DATE" \
  --tag "$TAG" \
  --project-url "$PROJECT_URL"
cp "$ROOT/LICENSE" "$APPDIR/LICENSE"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$APPDIR/THIRD_PARTY_NOTICES.md"
cp -R "$ROOT/packaging/notices" "$APPDIR/notices"

curl -fsSL --retry 3 --max-time 300 -o "$TOOL" "$APPIMAGETOOL_URL"
echo "$APPIMAGETOOL_SHA256  $TOOL" | sha256sum -c -
chmod 755 "$TOOL"

rm -f "$APPIMAGE"
ARCH=x86_64 VERSION="$VERSION" "$TOOL" --appimage-extract-and-run "$APPDIR" "$APPIMAGE"

cp -R "$APP" "$STAGE/EcoTranscribe Desktop"
cp "$APPDIR/LIRE-MOI-Linux.txt" "$STAGE/"
cp "$ROOT/LICENSE" "$STAGE/"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$STAGE/"
cp -R "$ROOT/packaging/notices" "$STAGE/notices"
rm -f "$TARBALL"
tar -C "$STAGE" -czf "$TARBALL" .

(
  cd "$DIST"
  sha256sum "$(basename "$APPIMAGE")" "$(basename "$TARBALL")"
) | tee "$DIST/SHA256SUMS-linux-$ARCH.txt"

echo "Artefacts :"
echo "  $APPIMAGE"
echo "  $TARBALL"
