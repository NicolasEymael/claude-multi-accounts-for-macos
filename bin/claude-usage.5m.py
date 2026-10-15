#!/usr/bin/python3
# <swiftbar.title>Claude usage</swiftbar.title>
# <swiftbar.desc>Session and weekly limits of every Claude account on this Mac</swiftbar.desc>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
"""SwiftBar plugin: session (5h) and weekly usage for each Claude account.

Accounts come from ~/.claude-multi-accounts/accounts.json (see setup-accounts.py).
Each account's Claude Code OAuth token is read from the Keychain (never printed)
and used to query the usage endpoint. An expired token is renewed by the CLI
itself with a one-word Haiku call, at most once every 30 min per account.
"""
import base64
import datetime as dt
import getpass
import json
import struct
import subprocess
import time
import urllib.request
import zlib
from pathlib import Path

HOME = Path.home() / ".claude-multi-accounts"
CONFIG = HOME / "accounts.json"
STATE = HOME / "state"
RENEW_EVERY = 30 * 60
CACHE_FRESH = 180  # the endpoint rate-limits hard; reuse a reading this recent

# SwiftBar colors are "light,dark" pairs with 6-digit hex (3-digit hex renders wrong).
RED, ORANGE, MUTED = "#C62828,#FF6B6B", "#B26A00,#FFB74D", "#555555,#C8C8C8"
FILL = {RED: (230, 80, 70), ORANGE: (240, 160, 50), None: (100, 150, 240)}
TRACK = (160, 160, 160, 120)
BAR_W, BAR_H, SCALE = 240, 6, 2  # points; drawn at 2x for Retina
TITLE_H, MINI_W, MINI_H, MINI_GAP, GROUP_GAP = 18, 26, 4, 3, 9

FONT = {  # 5x7 pixel font for the account letters in the menu bar
    "A": "01110/10001/10001/11111/10001/10001/10001", "B": "11110/10001/10001/11110/10001/10001/11110",
    "C": "01110/10001/10000/10000/10000/10001/01110", "D": "11100/10010/10001/10001/10001/10010/11100",
    "E": "11111/10000/10000/11110/10000/10000/11111", "F": "11111/10000/10000/11110/10000/10000/10000",
    "G": "01110/10001/10000/10111/10001/10001/01111", "H": "10001/10001/10001/11111/10001/10001/10001",
    "I": "01110/00100/00100/00100/00100/00100/01110", "J": "00111/00010/00010/00010/00010/10010/01100",
    "K": "10001/10010/10100/11000/10100/10010/10001", "L": "10000/10000/10000/10000/10000/10000/11111",
    "M": "10001/11011/10101/10101/10001/10001/10001", "N": "10001/10001/11001/10101/10011/10001/10001",
    "O": "01110/10001/10001/10001/10001/10001/01110", "P": "11110/10001/10001/11110/10000/10000/10000",
    "Q": "01110/10001/10001/10001/10101/10010/01101", "R": "11110/10001/10001/11110/10100/10010/10001",
    "S": "01111/10000/10000/01110/00001/00001/11110", "T": "11111/00100/00100/00100/00100/00100/00100",
    "U": "10001/10001/10001/10001/10001/10001/01110", "V": "10001/10001/10001/10001/10001/01010/00100",
    "W": "10001/10001/10001/10101/10101/10101/01010", "X": "10001/10001/01010/00100/01010/10001/10001",
    "Y": "10001/10001/01010/00100/00100/00100/00100", "Z": "11111/00001/00010/00100/01000/10000/11111",
    "0": "01110/10001/10011/10101/11001/10001/01110", "1": "00100/01100/00100/00100/00100/00100/01110",
    "2": "01110/10001/00001/00010/00100/01000/11111", "3": "11111/00010/00100/00010/00001/10001/01110",
    "4": "00010/00110/01010/10010/11111/00010/00010", "5": "11111/10000/11110/00001/00001/10001/01110",
    "6": "00110/01000/10000/11110/10001/10001/01110", "7": "11111/00001/00010/00100/01000/01000/01000",
    "8": "01110/10001/10001/01110/10001/10001/01110", "9": "01110/10001/10001/01111/00001/00010/01100",
    "?": "01110/10001/00001/00110/00100/00000/00100",
}


def token(service):
    out = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                         capture_output=True, text=True)
    if out.returncode:
        return None, 0
    data = json.loads(out.stdout).get("claudeAiOauth", {})
    return data.get("accessToken"), data.get("expiresAt", 0) / 1000


def renew(cfg, acc):
    """Let the CLI refresh its own token through a minimal request."""
    if not cfg.get("auto_renew") or not cfg.get("claude_bin"):
        return
    stamp = STATE / f"renew-{acc['letter']}"
    if stamp.exists() and time.time() - stamp.stat().st_mtime < RENEW_EVERY:
        return
    STATE.mkdir(parents=True, exist_ok=True)
    stamp.touch()
    # The CLI looks its credentials up in the Keychain by $USER; without it, it reports "Not logged in".
    user = getpass.getuser()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "USER": user, "LOGNAME": user}
    if acc.get("config_dir"):
        env["CLAUDE_CONFIG_DIR"] = acc["config_dir"]
    try:
        subprocess.run([cfg["claude_bin"], "-p", "ok", "--model", "haiku", "--setting-sources", "project",
                        "--strict-mcp-config"], cwd=STATE, env=env, capture_output=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        pass


def usage(tok):
    req = urllib.request.Request("https://api.anthropic.com/api/oauth/usage", headers={
        "Authorization": "Bearer " + tok, "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "claude-multi-accounts-menubar"})
    return json.load(urllib.request.urlopen(req, timeout=10))


def fetch(cfg, acc):
    cache = STATE / f"usage-{acc['letter']}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_FRESH:
        return json.loads(cache.read_text()), None
    tok, exp = token(acc["keychain_service"])
    if not tok:
        return None, "sem login no Claude Code (rode o setup de novo)"
    if exp < time.time() + 60:
        renew(cfg, acc)
        tok, exp = token(acc["keychain_service"])
        if exp < time.time():
            return None, "token expirado: abra o claude dessa conta no terminal"
    try:
        data = usage(tok)
        STATE.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        return data, None
    except Exception as e:
        if cache.exists():  # e.g. HTTP 429: show the last good reading instead of nothing
            age = time.strftime("%H:%M", time.localtime(cache.stat().st_mtime))
            return json.loads(cache.read_text()), f"leitura de {age}"
        return None, f"erro: {e}"


def when(iso):
    if not iso:
        return "—"
    t = dt.datetime.fromisoformat(iso).astimezone()
    left = t - dt.datetime.now().astimezone()
    h, m = divmod(max(int(left.total_seconds()), 0) // 60, 60)
    rel = f"{h // 24} d {h % 24} h" if h >= 24 else f"{h} h {m:02d} min"
    day = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")[t.weekday()]
    return f"Reinicia em {rel} ({day} {t:%H:%M})"


def color(pct):
    return RED if pct >= 90 else ORANGE if pct >= 70 else None


def png(width, height, pixel):
    """Encode a tiny RGBA PNG; pixel(x, y) -> (r, g, b, a)."""
    rows = b"".join(b"\0" + bytes(c for x in range(width) for c in pixel(x, y)) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def pill(x, y, w, h, pct):
    """Pixel of a rounded progress bar at local coords (x, y), or None if outside."""
    r = h / 2
    cx = min(max(x, r), w - r)
    if (x - cx) ** 2 + (y - r) ** 2 > r * r:
        return None
    if pct is None:
        return TRACK
    return (*FILL[color(pct)], 255) if x < w * min(max(pct, 0), 100) / 100 else TRACK


def bar(pct):
    w, h = BAR_W * SCALE, BAR_H * SCALE
    img = png(w, h, lambda x, y: pill(x + 0.5, y + 0.5, w, h, pct) or (0, 0, 0, 0))
    return base64.b64encode(img).decode()


def dark_mode():
    out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True)
    return out.stdout.strip() == "Dark"


def title_image(groups):
    """groups: [(letter, session_pct, weekly_pct)]; pct None = unknown."""
    ink = (235, 235, 235, 255) if dark_mode() else (40, 40, 40, 255)
    group_w = 5 + 3 + MINI_W
    width = len(groups) * group_w + (len(groups) - 1) * GROUP_GAP
    letter_top = (TITLE_H - 7) / 2
    bars_top = (TITLE_H - 2 * MINI_H - MINI_GAP) / 2
    clear = (0, 0, 0, 0)

    def pixel(x, y):
        px, py = (x + 0.5) / SCALE, (y + 0.5) / SCALE
        g, gx = divmod(px, group_w + GROUP_GAP)
        if g >= len(groups) or gx >= group_w:
            return clear
        letter, sp, wp = groups[int(g)]
        if gx < 5:
            row = int(py - letter_top)
            glyph = FONT.get(letter, FONT["?"]).split("/")
            return ink if 0 <= row < 7 and glyph[row][int(gx)] == "1" else clear
        bx = gx - 8
        for i, pct in enumerate((sp, wp)):
            top = bars_top + i * (MINI_H + MINI_GAP)
            if bx >= 0 and top <= py < top + MINI_H:
                return pill(bx, py - top, MINI_W, MINI_H, pct) or clear
        return clear

    img = png(width * SCALE, TITLE_H * SCALE, pixel)
    return base64.b64encode(img).decode(), width


def main():
    if not CONFIG.exists():
        print("Claude ? | color=" + MUTED)
        print("---")
        print("Rode ~/.claude-multi-accounts/bin/setup-accounts.py | refresh=true")
        return
    cfg = json.loads(CONFIG.read_text())
    body, groups = [], []
    for acc in cfg.get("accounts", []):
        letter = acc["letter"].upper()[:1] or "?"
        data, err = fetch(cfg, acc)
        body.append(f"{acc['label']} | size=14 refresh=true")
        if not data:
            groups.append((letter, None, None))
            body.append(f"{err} | color={MUTED} refresh=true")
            body.append("---")
            continue
        s = data.get("five_hour") or {}
        w = data.get("seven_day") or {}
        sp, wp = round(s.get("utilization") or 0), round(w.get("utilization") or 0)
        groups.append((letter, sp, wp))
        for name, pct, reset in (("Limite de sessão", sp, s.get("resets_at")), ("Semanal", wp, w.get("resets_at"))):
            c = color(pct)
            body.append(f"{name}  ·  {pct}% usado | refresh=true" + (f" color={c}" if c else ""))
            body.append(f" | image={bar(pct)} width={BAR_W} height={BAR_H} refresh=true")
            body.append(f"{when(reset)} | size=12 color={MUTED} refresh=true")
        if err:
            body.append(f"{err} | size=12 color={MUTED} refresh=true")
        body.append("---")
    if not groups:
        print("Claude ? | color=" + MUTED)
    else:
        img, width = title_image(groups)
        print(f" | image={img} width={width} height={TITLE_H}")
    print("---")
    print("\n".join(body))
    print(f"Barra: letra da conta, sessão em cima, semanal embaixo | size=11 color={MUTED} refresh=true")
    print("Atualizar | refresh=true")


if __name__ == "__main__":
    main()
