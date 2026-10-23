# 🛠️ Development Tools

Script di supporto allo sviluppo. **Non fanno parte del gioco**.

## Script disponibili

### `make_icon.py`

Rigenera l'icona dell'applicazione dagli stessi pixel usati a runtime (la
piccola navicella aliena di `game_shared.make_icon()`).

```bash
python tools/make_icon.py
```

Crea `assets/icon.png` (256×256) e, se è installato [Pillow](https://pillow.readthedocs.io/)
(`pip install pillow`), anche `assets/icon.ico` usato da PyInstaller per l'eseguibile Windows.

### `clean_nulls.py`

Rimuove i null byte (`\x00`) dai file Python. Utile dopo trasferimenti di file corrotti o editor che inseriscono byte non validi.

```bash
python tools/clean_nulls.py --dry-run     # anteprima, non modifica nulla
python tools/clean_nulls.py               # file .py della cartella corrente
python tools/clean_nulls.py --recursive   # anche nelle sottocartelle
python tools/clean_nulls.py --verbose
```

I file modificati vengono salvati con backup `<file>.bak_TIMESTAMP`.

### `fix_encoding.py`

Converte i file Python in UTF-8 (senza BOM). Prova prima `utf-8-sig`, poi ripiega su `latin-1`.

```bash
python tools/fix_encoding.py --file game_shared.py   # singolo file
python tools/fix_encoding.py --all                   # tutti i .py della cartella
python tools/fix_encoding.py --all --dry-run         # anteprima
python tools/fix_encoding.py --all --no-backup       # senza file di backup
```

### `clean_game_ai.py`

Versione "veloce" e monouso di `clean_nulls.py`, specifica per `game_ai.py`. Mantenuta solo per riferimento storico: per nuovi usi preferisci `clean_nulls.py`.

## ⚠️ Attenzione

`clean_nulls.py` e `fix_encoding.py` **modificano i file sul posto** (con backup). Assicurati di avere un commit pulito prima di usarli, oppure lancia prima `--dry-run`.

Per evitare che i problemi di encoding si ripresentino, in VS Code imposta `"files.encoding": "utf8"` e controlla che in basso a destra compaia **UTF-8**.
