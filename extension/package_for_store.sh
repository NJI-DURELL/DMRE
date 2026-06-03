#!/usr/bin/env bash
# Package the DMRE Chrome extension into a zip ready for the Chrome Web Store.
# POSIX equivalent of package_for_store.ps1 — same validations, same output.
#
# By default this ships `config.prod.js` renamed to `config.js` inside the
# zip, so the runtime keeps loading `config.js` unchanged. Pass
# ALLOW_LOCALHOST=1 to build a dev zip from the dev `config.js` instead.
set -euo pipefail

cd "$(dirname "$0")"

# 1. Manifest validation
if [[ ! -f manifest.json ]]; then
  echo "manifest.json missing" >&2
  exit 1
fi
VERSION=$(python -c "import json; print(json.load(open('manifest.json'))['version'])")
MV=$(python -c "import json; print(json.load(open('manifest.json'))['manifest_version'])")
if [[ "$MV" != "3" ]]; then
  echo "manifest_version must be 3 for new submissions" >&2
  exit 1
fi
echo "Manifest OK: v$VERSION"

# 2. Required files
for f in manifest.json config.js config.prod.js background.js content.js popup.html popup.js \
         icons/icon16.png icons/icon48.png icons/icon128.png; do
  if [[ ! -f "$f" ]]; then
    echo "Missing required file: $f" >&2
    exit 1
  fi
done

# 3. Pick which config to ship
if [[ "${ALLOW_LOCALHOST:-0}" == "1" ]]; then
  CONFIG_SRC="config.js"
else
  CONFIG_SRC="config.prod.js"
  if grep -qE 'localhost|127\.0\.0\.1' "$CONFIG_SRC"; then
    echo "$CONFIG_SRC still points at localhost. Edit BACKEND_URL / DASHBOARD_URL first," >&2
    echo "or run with ALLOW_LOCALHOST=1 for a dev zip." >&2
    exit 1
  fi
  if grep -qE 'CHANGE-ME|example\.com|TODO|REPLACE_ME' "$CONFIG_SRC"; then
    echo "$CONFIG_SRC still contains a placeholder URL. Set real production URLs first." >&2
    exit 1
  fi
fi

# 4. Stage and build the zip
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

cp manifest.json background.js content.js popup.html popup.js "$STAGING/"
cp -r icons "$STAGING/"
# Ship the chosen config under the runtime filename so loaders don't change.
cp "$CONFIG_SRC" "$STAGING/config.js"

mkdir -p dist
ZIP="dist/dmre-extension-v${VERSION}.zip"
rm -f "$ZIP"
(cd "$STAGING" && zip -r "$OLDPWD/$ZIP" . -x "*.DS_Store" "*.log")

echo
echo "Package built: $ZIP"
echo "  $(du -h "$ZIP" | cut -f1)"
echo "  shipped config: $CONFIG_SRC"
echo
echo "Next steps:"
echo "  1. Open https://chrome.google.com/webstore/devconsole and click 'New Item'."
echo "  2. Upload $(basename "$ZIP")."
echo "  3. Fill in the listing using PRIVACY.md and DEPLOY.md as a guide."
