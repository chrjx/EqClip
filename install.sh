#!/usr/bin/env bash
# Build EqClip and install it to /Applications.
#
#   ./install.sh                 build + install
#   ./install.sh --login-item    also start EqClip automatically at login
#
# Safe to re-run: rebuilds from source and replaces the previous install.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="EqClip.app"
DEST="/Applications/$APP_NAME"
LOGIN_ITEM=false

for arg in "$@"; do
  case "$arg" in
    --login-item) LOGIN_ITEM=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

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

echo "==> Installing to $DEST"
if [ -d "$DEST" ]; then
  rm -rf "$DEST"
fi
cp -R "dist/$APP_NAME" "$DEST"

if [ "$LOGIN_ITEM" = true ]; then
  echo "==> Adding EqClip to Login Items"
  osascript <<EOF
tell application "System Events"
  if not (exists login item "EqClip") then
    make login item at end with properties {path:"$DEST", hidden:false}
  end if
end tell
EOF
fi

cat <<EOF

==> Installed: $DEST

Next steps:
  1. Open EqClip: open "$DEST"
  2. Grant Accessibility permission for the global hotkey:
     System Settings -> Privacy & Security -> Accessibility -> add EqClip.
     (First launch may warn "unidentified developer" since this build
     isn't code-signed -- right-click the app -> Open to bypass once.)
  3. Set a free Gemini API key or switch to Ollama from the tray menu.

Run ./uninstall.sh to remove EqClip.
EOF
