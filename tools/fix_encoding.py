# fix_encoding.py
#!/usr/bin/env python3
"""
fix_encoding.py

Ripulisce file convertendo in UTF-8:
 - tenta decode con 'utf-8-sig'
 - se fallisce prova 'latin-1' come fallback (mantenendo i bytes non validi)
 - riscrive il file in UTF-8 (senza BOM)
Opzioni:
  --file <path>    : un singolo file da processare (default: game_shared.py)
  --all / -a       : processa tutti i .py nella cartella (non ricorsivo)
  --backup / -b    : crea backup <file>.bak_TIMESTAMP
  --dry-run / -n   : non modifica nulla
"""
from pathlib import Path
import argparse
from datetime import datetime
import sys
import os

def fix_utf8(path: Path, make_backup: bool = True, dry_run: bool = False):
    try:
        raw = path.read_bytes()
    except Exception as e:
        return {"file": str(path), "error": f"read error: {e}"}
    try:
        text = raw.decode("utf-8-sig")
        used = "utf-8-sig"
    except Exception:
        try:
            text = raw.decode("latin-1")
            used = "latin-1"
        except Exception as e:
            return {"file": str(path), "error": f"decode error: {e}"}
    if dry_run:
        return {"file": str(path), "encoding": used, "dry_run": True}
    try:
        bak = None
        if make_backup:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = path.with_suffix(path.suffix + f".bak_{ts}")
            bak.write_bytes(raw)
        # write utf-8 without BOM
        path.write_text(text, encoding="utf-8")
        return {"file": str(path), "encoding": used, "backup": bak.name if bak else None}
    except Exception as e:
        return {"file": str(path), "error": f"write error: {e}"}

def main():
    parser = argparse.ArgumentParser(description="Fix file encoding -> UTF-8")
    parser.add_argument("--file", "-f", help="Singolo file da processare")
    parser.add_argument("--all", "-a", action="store_true", help="Processa tutti i .py nella cartella (non ricorsivo)")
    parser.add_argument("--backup", "-b", action="store_true", default=True, help="Crea backup dei file modificati")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Non scrive i file")
    args = parser.parse_args()

    targets = []
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print("File non trovato:", args.file)
            return
        targets = [p]
    elif args.all:
        targets = sorted(Path(".").glob("*.py"))
        if not targets:
            print("Nessun .py trovato nella cartella.")
            return
    else:
        default = Path("game_shared.py")
        if not default.exists():
            print("File game_shared.py non trovato e nessun argomento --file/--all fornito.")
            return
        targets = [default]

    for t in targets:
        res = fix_utf8(t, make_backup=args.backup, dry_run=args.dry_run)
        if "error" in res:
            print(f"[ERR] {t.name}: {res['error']}")
        else:
            if args.dry_run:
                print(f"[DRY] {t.name}: would convert from {res.get('encoding')}")
            else:
                print(f"[OK] {t.name}: converted from {res.get('encoding')}  Backup: {res.get('backup')}")

if __name__ == "__main__":
    main()
