#!/bin/bash
# Install claude-multi-accounts-for-macos: session sync between Claude Desktop
# accounts + a menu bar meter with the usage limits of every account.
#
#   curl -fsSL https://raw.githubusercontent.com/NicolasEymael/claude-multi-accounts-for-macos/main/install.sh | bash
#
# Options: --no-sync       skip the session sync agent
#          --no-menubar    skip SwiftBar and the usage meter
#          --reconfigure   rediscover the Claude Code accounts (rewrites accounts.json)
set -euo pipefail

REPO="NicolasEymael/claude-multi-accounts-for-macos"
DEST="$HOME/.claude-multi-accounts"
LABEL="com.github.claude-multi-accounts.session-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SESSIONS="$HOME/Library/Application Support/Claude/claude-code-sessions"
PLUGIN="claude-usage.5m.py"

SYNC=1 MENUBAR=1 RECONFIGURE=0
for arg in "$@"; do
  case "$arg" in
    --no-sync) SYNC=0 ;;
    --no-menubar) MENUBAR=0 ;;
    --reconfigure) RECONFIGURE=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Opção desconhecida: $arg" >&2; exit 1 ;;
  esac
done

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf 'Erro: %s\n' "$*" >&2; exit 1; }

[ "$(uname)" = Darwin ] || die "só funciona no macOS."
xcode-select -p >/dev/null 2>&1 || die "faltam as Command Line Tools (python3). Rode: xcode-select --install"

# Source: this checkout, or a fresh download when piped from curl.
SRC="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ ! -f "$SRC/bin/session-sync.py" ]; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  say "Baixando $REPO"
  curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/main" | tar xz -C "$TMP" --strip-components 1
  SRC="$TMP"
fi

say "Copiando arquivos para $DEST"
mkdir -p "$DEST/bin" "$DEST/logs" "$DEST/menubar"
cp "$SRC"/bin/*.py "$DEST/bin/"
cp "$SRC/install.sh" "$SRC/uninstall.sh" "$DEST/"
chmod +x "$DEST"/bin/*.py "$DEST"/*.sh

if [ "$SYNC" = 1 ]; then
  say "Instalando o sync de sessões do Claude Desktop"
  # Watch the root plus every account/org folder that exists now; the 30 s
  # interval covers folders created later (a new account).
  watch="        <string>$SESSIONS</string>"$'\n'
  for d in "$SESSIONS"/*/*/; do
    [ -d "$d" ] && watch+="        <string>${d%/}</string>"$'\n'
  done
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$DEST/bin/session-sync.py</string>
    </array>
    <key>WatchPaths</key>
    <array>
$watch    </array>
    <key>StartInterval</key>
    <integer>30</integer>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$DEST/logs/session-sync.err</string>
</dict>
</plist>
EOF
  plutil -lint "$PLIST" >/dev/null
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
fi

say "Procurando as contas logadas no Claude Code"
if [ "$RECONFIGURE" = 1 ]; then
  /usr/bin/python3 "$DEST/bin/setup-accounts.py" --force
else
  /usr/bin/python3 "$DEST/bin/setup-accounts.py"
fi

if [ "$MENUBAR" = 1 ]; then
  if [ ! -d /Applications/SwiftBar.app ] && [ ! -d "$HOME/Applications/SwiftBar.app" ]; then
    if command -v brew >/dev/null; then
      say "Instalando o SwiftBar (Homebrew)"
      brew install --cask swiftbar
    else
      die "instale o SwiftBar (https://swiftbar.app) ou o Homebrew e rode de novo, ou use --no-menubar."
    fi
  fi
  say "Configurando o medidor de uso no menu bar"
  plugins="$(defaults read com.ameba.SwiftBar PluginDirectory 2>/dev/null || true)"
  if [ -z "$plugins" ]; then
    plugins="$DEST/menubar"
    defaults write com.ameba.SwiftBar PluginDirectory "$plugins"
  fi
  mkdir -p "$plugins"
  ln -sf "$DEST/bin/$PLUGIN" "$plugins/$PLUGIN"
  open -a SwiftBar
  sleep 2
  open -g "swiftbar://refreshallplugins" || true
fi

if ! grep -q '"cleanupPeriodDays"' "$HOME/.claude/settings.json" 2>/dev/null; then
  echo
  echo "Dica: o Claude Code apaga históricos com mais de 30 dias. Para manter as sessões"
  echo "antigas, adicione \"cleanupPeriodDays\": 3650 em ~/.claude/settings.json."
fi

echo
say "Pronto."
echo "  Log do sync:   $DEST/logs/session-sync.log"
echo "  Contas:        $DEST/accounts.json (edite letra e nome à vontade)"
echo "  Desinstalar:   $DEST/uninstall.sh"
