#!/usr/bin/python3
"""Mirror Claude Desktop session cards across every account you log into.

The Claude Desktop app keeps one session list per account/organization under
claude-code-sessions/<accountId>/<orgId>/. Only the active account's folder
changes, so mirroring every shared file (newest mtime wins) keeps the inactive
folders current, and switching accounts shows the same sessions.

Usage: session-sync.py [--dry-run]
"""
import filecmp
import os
import shutil
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path.home() / "Library/Application Support/Claude/claude-code-sessions"
HOME = Path.home() / ".claude-multi-accounts"
TRASH = HOME / "trash"
BACKUPS = HOME / "backups"
LOG = HOME / "logs/session-sync.log"
LOCK = HOME / ".session-sync.lock"
KEEP_BACKUPS = 7
BACKUP_EVERY = 24 * 3600
# Shared besides local_*.json and deleted_*; scheduled-tasks.json stays per account on purpose.
SHARED_SINGLE = ("archived-sessions.idx", "backlog/tasks.json")

DRY = "--dry-run" in sys.argv


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + ("[dry-run] " if DRY else "") + msg
    print(line)
    if not DRY:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(line + "\n")


def org_dirs():
    return sorted(p for p in ROOT.glob("*/*") if p.is_dir())


def shared_files(d):
    names = [p.name for p in d.glob("local_*.json")] + [p.name for p in d.glob("deleted_*")]
    names += [rel for rel in SHARED_SINGLE if (d / rel).is_file()]
    return names


def short(d):
    return f"{d.parent.name[:8]}/{d.name[:8]}"


def copy(src, dst):
    if DRY:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / (".sync-tmp-" + dst.name)
    shutil.copy2(src, tmp)  # keeps mtime, so the copy never looks newer than the source
    os.replace(tmp, dst)


def trash(path):
    if DRY:
        return
    dest = TRASH / time.strftime("%Y%m%d") / path.parent.parent.name / path.parent.name
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest / path.name))


def backup():
    BACKUPS.mkdir(parents=True, exist_ok=True)
    existing = sorted(BACKUPS.glob("sessions-*.tar.gz"))
    if existing and time.time() - existing[-1].stat().st_mtime < BACKUP_EVERY:
        return
    if DRY:
        log("would write daily backup")
        return
    out = BACKUPS / time.strftime("sessions-%Y%m%d-%H%M.tar.gz")
    with tarfile.open(out, "w:gz") as tar:
        tar.add(ROOT, arcname="claude-code-sessions")
    log(f"backup {out.name}")
    for old in sorted(BACKUPS.glob("sessions-*.tar.gz"))[:-KEEP_BACKUPS]:
        old.unlink()


def sync():
    dirs = org_dirs()
    if len(dirs) < 2:
        return

    newest = {}
    for d in dirs:
        for rel in shared_files(d):
            p = d / rel
            m = p.stat().st_mtime
            if rel not in newest or m > newest[rel][1]:
                newest[rel] = (p, m)

    tombstones = {rel[len("deleted_"):]: m for rel, (_, m) in newest.items() if rel.startswith("deleted_")}

    copied = trashed = 0
    for d in dirs:
        for rel, (src, m) in newest.items():
            if src.parent == d or (rel in SHARED_SINGLE and src.parent.parent == d):
                continue
            if rel.startswith("local_"):
                sid = rel[len("local_"):-len(".json")]
                if sid in tombstones and tombstones[sid] >= m:
                    continue  # deleted somewhere: never resurrect
            dst = d / rel
            if dst.exists() and (dst.stat().st_mtime >= m or filecmp.cmp(src, dst, shallow=False)):
                continue
            log(f"copy {rel} -> {short(d)}")
            copy(src, dst)
            copied += 1

        for sid, m in tombstones.items():
            card = d / f"local_{sid}.json"
            if card.exists() and card.stat().st_mtime <= m:
                log(f"trash local_{sid}.json in {short(d)}")
                trash(card)
                trashed += 1

    if copied or trashed:
        log(f"done: {copied} copied, {trashed} trashed, {len(dirs)} folders")


def main():
    if not ROOT.exists():
        return
    HOME.mkdir(exist_ok=True)
    try:
        LOCK.mkdir()
    except FileExistsError:
        if time.time() - LOCK.stat().st_mtime < 300:
            return
        LOCK.rmdir()
        LOCK.mkdir()
    try:
        backup()
        sync()
    except Exception as e:
        log(f"error: {e!r}")
        raise
    finally:
        LOCK.rmdir()


if __name__ == "__main__":
    main()
