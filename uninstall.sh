#!/bin/bash
# Remove claude-multi-accounts-for-macos. Session copies already made stay in
# Claude Desktop (harmless). --purge also deletes ~/.claude-multi-accounts
# (logs, backups and trash). SwiftBar itself is left installed.
set -euo pipefail

DEST="$HOME/.claude-multi-accounts"
LABEL="com.github.claude-multi-accounts.session-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PLUGIN="claude-usage.5m.py"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"

plugins="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
if [ -n "$plugins" ] && [ -L "$plugins/$PLUGIN" ]; then
  rm -f "$plugins/$PLUGIN"
  open -g "swiftbar://refreshallplugins" 2>/dev/null || true
fi

if [ "${1:-}" = "--purge" ]; then
  rm -rf "$DEST"
  echo "Removido, incluindo $DEST."
else
  echo "Removido. Logs, backups e lixeira continuam em $DEST (use --purge para apagar)."
fi
