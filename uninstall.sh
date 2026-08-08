#!/usr/bin/env bash
# Remove EqClip.
#
#   ./uninstall.sh          remove the app + login item, keep your config/logs
#   ./uninstall.sh --purge  also delete config (incl. saved API key) and logs

set -euo pipefail

APP_NAME="EqClip.app"
DEST="/Applications/$APP_NAME"
PURGE=false

for arg in "$@"; do
  case "$arg" in
    --purge) PURGE=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

echo "==> Removing Login Item (if any)"
osascript <<'EOF' || true
tell application "System Events"
  if exists login item "EqClip" then
    delete login item "EqClip"
  end if
end tell
EOF

if [ -d "$DEST" ]; then
  echo "==> Removing $DEST"
  rm -rf "$DEST"
else
  echo "==> $DEST not found, skipping"
fi

if [ "$PURGE" = true ]; then
  echo "==> Purging config and logs (including saved API key)"
  rm -rf "$HOME/Library/Application Support/EqClip"
  rm -rf "$HOME/Library/Logs/EqClip"
else
  echo "==> Keeping config and logs at:"
  echo "      ~/Library/Application Support/EqClip"
  echo "      ~/Library/Logs/EqClip"
  echo "    (run with --purge to remove those too)"
fi

echo "==> Done"
