# clean_nulls.py
#!/usr/bin/env python3
"""
clean_nulls.py

Rimuove i null bytes (\x00) nei file .py.
Opzioni:
  --recursive / -r   : cerca ricorsivamente nelle sottocartelle
  --dry-run / -n     : non modifica nulla, mostra cosa verrebbe fatto
  --pattern / -p     : glob pattern (default: '*.py')
  --verbose / -v     : output più verboso
"""
from pathlib import Path
from datetime import datetime
import argparse
import sys
import os

def clean_file(path: Path, dry_run: bool = False, verbose: bool = False):
    try:
        data = path.read_bytes()
    except Exception as e:
        return {"file": str(path), "error": f"read error: {e}"}
    nulls = data.count(b"\x00")
    if nulls == 0:
        return {"file": str(path), "nulls": 0}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_{ts}")
    try:
        if dry_run:
            if verbose:
                print(f"[DRY] Would backup {path} -> {bak.name} and remove {nulls} NULs")
            return {"file": str(path), "nulls": nulls, "backup": None, "dry_run": True}
        # preserve mode & mtime
        st = path.stat()
        bak.write_bytes(data)
        cleaned = data.replace(b"\x00", b"")
        path.write_bytes(cleaned)
        try:
            os.utime(str(path), (st.st_atime, st.st_mtime))
            os.chmod(str(bak), st.st_mode)
        except Exception:
            pass
        return {"file": str(path), "nulls": nulls, "backup": bak.name}
    except Exception as e:
        return {"file": str(path), "error": f"write error: {e}"}

def find_files(base: Path, pattern: str = "*.py", recursive: bool = False):
    if recursive:
        return sorted(base.rglob(pattern))
    else:
        return sorted(base.glob(pattern))

def main():
    parser = argparse.ArgumentParser(description="Rimuovi null bytes dai file .py")
    parser.add_argument("--recursive", "-r", action="store_true", help="Cerca ricorsivamente")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Non scrive file, mostra solo cosa succederebbe")
    parser.add_argument("--pattern", "-p", default="*.py", help="Glob pattern per i file (default: *.py)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Output verboso")
    args = parser.parse_args()

    base = Path(".")
    files = find_files(base, pattern=args.pattern, recursive=args.recursive)
    if not files:
        print("Nessun file trovato con il pattern:", args.pattern)
        return

    total_nulls = 0
    cleaned_files = []
    errors = []

    for f in files:
        res = clean_file(f, dry_run=args.dry_run, verbose=args.verbose)
        if "error" in res:
            print(f"[ERR] {f.name}: {res['error']}")
            errors.append(res)
        else:
            if res.get("nulls", 0):
                total_nulls += res["nulls"]
                cleaned_files.append(f.name)
                if args.dry_run:
                    print(f"[DRY] {f.name}: {res['nulls']} null byte (no changes)")
                else:
                    print(f"[OK] Puliti {res['nulls']} null byte in: {f.name}  Backup: {res.get('backup')}")
            else:
                if args.verbose:
                    print(f"[OK] Nessun null byte in: {f.name}")

    print("----")
    if args.dry_run:
        print("Dry-run: nessuna modifica effettuata.")
    if total_nulls:
        print(f"Rimosso un totale di {total_nulls} null byte da {len(cleaned_files)} file.")
        print("Consiglio: ora lancia il launcher:")
        print("    py .\\retro_arcade_interface.py")
    else:
        print("Non sono stati trovati null byte nei file selezionati.")

    if errors:
        print()
        print("Alcuni file non sono stati elaborati correttamente (vedi sopra).")

if __name__ == "__main__":
    main()
