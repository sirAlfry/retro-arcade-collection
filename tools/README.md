# 🛠️ Development Tools

Utility scripts usati durante lo sviluppo del progetto. **Non fanno parte del gioco**: servono solo a sistemare problemi di encoding o caratteri non validi nei sorgenti Python.

## Script disponibili

### `clean_nulls.py`

Rimuove i null bytes (`\x00`) dai file Python. Utile dopo trasferimenti di file corrotti o problemi con editor che inseriscono byte non validi.

```bash
# Modalità dry-run (non modifica niente, mostra solo cosa farebbe)
python tools/clean_nulls.py --dry-run

# Esegui sui file .py della cartella corrente
python tools/clean_nulls.py

# Ricorsivo nelle sottocartelle
python tools/clean_nulls.py --recursive

# Verbose
python tools/clean_nulls.py --verbose
```

I file modificati vengono salvati con backup `<file>.bak_TIMESTAMP`.

### `fix_encoding.py`

Converte i file Python in UTF-8 (senza BOM). Tenta prima `utf-8-sig`, poi fallback su `latin-1` per preservare caratteri non validi.

```bash
# Singolo file
python tools/fix_encoding.py --file game_shared.py

# Tutti i .py della cartella
python tools/fix_encoding.py --all

# Dry-run
python tools/fix_encoding.py --all --dry-run
```

### `clean_game_ai.py`

Script monouso (versione "quick" di `clean_nulls.py`) specifico per il file `game_ai.py`. Mantenuto per riferimento storico.

## ⚠️ Attenzione

Questi script **modificano file in-place** (con backup). Verifica sempre di avere un commit pulito prima di eseguirli, o usa `--dry-run` per anteprima.
