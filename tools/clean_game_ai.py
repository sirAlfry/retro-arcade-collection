from pathlib import Path
p = Path("game_ai.py")
if not p.exists():
    print("File non trovato:", p)
    raise SystemExit(1)
data = p.read_bytes()
nulls = data.count(b"\x00")
if nulls:
    bak = p.with_suffix(p.suffix + ".bak")
    bak.write_bytes(data)
    cleaned = data.replace(b"\x00", b"")
    p.write_bytes(cleaned)
    print(f"Pulito: {p} (rimosso {nulls} null bytes). Backup: {bak.name}")
else:
    print(f"OK: Nessun null byte in {p}")
