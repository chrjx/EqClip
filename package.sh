#!/usr/bin/env bash
# Build EqClip.app and package it as a distributable EqClip.dmg -- the
# double-click-and-drag-to-Applications installer real Mac apps ship as.
#
#   ./package.sh
#
# Produces dist/EqClip-<version>.dmg. For local, everyday installs use
# ./install.sh instead (builds + copies straight into /Applications, no
# disk image needed); this script is for handing the app to someone else,
# and is also what the release CI workflow runs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="EqClip.app"

echo "==> Setting up build environment"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q py2app

# google-genai installs "google" as a PEP 420 namespace package (no
# __init__.py). py2app's legacy bootstrap resolver can't handle that, so
# give it a real __init__.py to make it a normal package instead -- safe,
# since google.genai/auth/oauth2 keep their own __init__.py and still
# resolve as subpackages exactly the same way.
SITE_PACKAGES="$(python3 -c 'import site; print(site.getsitepackages()[0])')"
touch "$SITE_PACKAGES/google/__init__.py"

echo "==> Building $APP_NAME"
rm -rf build dist
python3 setup.py py2app >/dev/null

if [ ! -d "dist/$APP_NAME" ]; then
  echo "Build failed: dist/$APP_NAME not found." >&2
  exit 1
fi

VERSION="$(python3 -c 'from eqclip.__version__ import __version__; print(__version__)')"
DMG_NAME="EqClip-${VERSION}.dmg"
rm -f "dist/$DMG_NAME"

echo "==> Packaging dist/$DMG_NAME"
if command -v create-dmg >/dev/null 2>&1; then
  # create-dmg returns non-zero if Finder styling (e.g. AppleScript window
  # dressing) fails even though the DMG itself was created fine -- so
  # check for the output file rather than the exit code.
  create-dmg \
    --volname "EqClip" \
    --window-size 500 320 \
    --icon-size 100 \
    --icon "$APP_NAME" 130 160 \
    --hide-extension "$APP_NAME" \
    --app-drop-link 370 160 \
    "dist/$DMG_NAME" \
    "dist/$APP_NAME" || true
fi

if [ ! -f "dist/$DMG_NAME" ]; then
  echo "==> create-dmg unavailable or failed; falling back to a plain DMG"
  echo "    (brew install create-dmg for the drag-to-Applications layout)"
  hdiutil create -volname "EqClip" -srcfolder "dist/$APP_NAME" -ov -format UDZO "dist/$DMG_NAME"
fi

echo
echo "==> Created dist/$DMG_NAME"
echo "    Double-click to mount it, then drag EqClip.app to Applications."
