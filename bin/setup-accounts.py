#!/usr/bin/python3
"""Find every Claude Code login on this Mac and write accounts.json for the menu bar.

Each login is a Claude Code config dir: the default one (~/.claude, no
CLAUDE_CONFIG_DIR) or any ~/.claude-<name> created with
`CLAUDE_CONFIG_DIR=~/.claude-<name> claude`. Its OAuth token lives in the
Keychain under "Claude Code-credentials" (default) or
"Claude Code-credentials-<first 8 hex of sha256(config dir)>".

Only metadata is read (email, organization, plan); tokens are never printed.

Usage: setup-accounts.py [--force]   (--force rewrites an existing accounts.json)
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CONFIG = HOME / ".claude-multi-accounts/accounts.json"


def keychain_service(config_dir):
    if config_dir is None:
        return "Claude Code-credentials"
    digest = hashlib.sha256(str(config_dir).encode()).hexdigest()[:8]
    return f"Claude Code-credentials-{digest}"


def plan(service):
    out = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                         capture_output=True, text=True)
    if out.returncode:
        return None
    oauth = json.loads(out.stdout).get("claudeAiOauth") or {}
    return oauth.get("subscriptionType") or "?"


def account_info(json_path):
    try:
        acc = json.loads(json_path.read_text()).get("oauthAccount") or {}
    except (OSError, ValueError):
        return None
    if not acc.get("accountUuid"):
        return None
    return acc


def label_for(acc, sub):
    org = acc.get("organizationName") or ""
    email = acc.get("emailAddress") or ""
    name = email if not org or org.endswith("'s Organization") else org
    return f"{name} ({sub})"


def find_claude():
    for candidate in (shutil.which("claude"), HOME / ".local/bin/claude",
                      "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def discover():
    candidates = [(None, HOME / ".claude.json")]
    for d in sorted(HOME.glob(".claude*")):
        if d.is_dir() and (d / ".claude.json").exists():
            candidates.append((d, d / ".claude.json"))

    accounts, seen = [], set()
    for config_dir, json_path in candidates:
        acc = account_info(json_path)
        if not acc:
            continue
        key = (acc["accountUuid"], acc.get("organizationUuid"))
        service = keychain_service(config_dir)
        sub = plan(service)
        if key in seen or sub is None:
            continue  # same login twice, or no token in the Keychain
        seen.add(key)
        accounts.append({
            "label": label_for(acc, sub),
            "letter": "",
            "config_dir": str(config_dir) if config_dir else None,
            "keychain_service": service,
        })

    used = set()
    for a in accounts:
        letters = [c for c in a["label"].upper() if c.isalnum()] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        a["letter"] = next(c for c in letters if c not in used)
        used.add(a["letter"])
    return accounts


def main():
    if CONFIG.exists() and "--force" not in sys.argv:
        print(f"{CONFIG} already exists (use --force to rediscover).")
        return
    accounts = discover()
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({
        "claude_bin": find_claude(),
        "auto_renew": True,
        "accounts": accounts,
    }, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {CONFIG} with {len(accounts)} account(s):")
    for a in accounts:
        print(f"  {a['letter']}  {a['label']}")
    if len(accounts) < 2:
        print("Tip: log a second account into Claude Code with\n"
              "  CLAUDE_CONFIG_DIR=~/.claude-<name> claude   (then /login)\n"
              "and run this again with --force.")


if __name__ == "__main__":
    main()
