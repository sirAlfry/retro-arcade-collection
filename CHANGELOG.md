# Changelog

Tutte le modifiche rilevanti al progetto sono documentate qui.
Il formato segue [Keep a Changelog](https://keepachangelog.com/it-IT/1.1.0/)
e il progetto adotta il [Semantic Versioning](https://semver.org/lang/it/).

## [3.0.0] - 2026-10-23

Revisione completa: correzione dei bug, nuova grafica, audio, salvataggi
persistenti, test automatici e packaging funzionante.

### Corretto

- **Puzzle 15 generava solo partite irrisolvibili**: il test di parità era
  invertito (veniva accettato `inversioni + riga del buco` *pari* invece che
  *dispari*). Ora ogni mescolamento è risolvibile, con test di regressione.
- **I record non venivano mai salvati su disco** nonostante il README parlasse
  di `scores.json`: il launcher li teneva solo in memoria. Ora c'è `scores.py`
  con salvataggio JSON atomico e recupero dei file danneggiati.
- **Il menu di pausa diventava nero**: l'overlay semi-trasparente veniva
  ridisegnato sopra sé stesso a ogni frame. Ora il frame di gioco viene
  catturato una volta e l'effetto resta trasparente.
- **"Q: Chiudi app" dentro un gioco** chiamava `pygame.quit()` e poi il
  launcher provava a ricreare la finestra. Ora i giochi restituiscono
  `"quit"` e solo il launcher chiude pygame.
- **Pong**: la schermata di vittoria bloccava il gioco per sempre; le modalità
  "1P" e "VS AI" erano la stessa cosa; la palla poteva incastrarsi nei bordi.
- **Tic Tac Toe**: la modalità "1P" era identica alla "2P"; la CPU
  "difficile" (profondità 6) non era perfetta; l'iterative deepening poteva
  sostituire il risultato completo con uno parziale allo scadere del tempo;
  `__slots__` non aveva effetto perché la classe base non lo definiva.
- **Snake**: le particelle usavano la radice quadrata dell'angolo invece di
  seno/coseno; l'HUD si sovrapponeva al campo; le curve rapide andavano perse.
- **Tetris**: le linee potevano essere conteggiate due volte se un pezzo si
  bloccava durante l'animazione; `↓` non faceva nulla; il flash colpiva il
  pezzo in caduta invece delle righe completate; la velocità dipendeva dal
  punteggio invece che dal livello.
- **Breakout**: collisione solo sul centro della palla (attraversava i
  mattoni e rimbalzava sempre in verticale); colori dei mattoni calcolati
  male (quasi tutti uguali); la tastiera era ignorata con il mouse nella
  finestra; scegliendo "menu" dalla pausa compariva un secondo menu
  "Hai perso!".
- **Space Invaders**: fuoco senza limiti; il riavvio usava la ricorsione
  (`return main()`); gli alieni non acceleravano.
- **Maze Runner**: la scelta della difficoltà non era raggiungibile dal
  launcher; il timer contava anche le pause.
- **Memory**: si potevano girare più di due carte nello stesso frame.
- **Cicli di attesa al 100% di CPU** nelle schermate di fine partita
  (Tris, Tetris, Puzzle 15) e `pygame.time.delay` che bloccavano la finestra.
- **Launcher**: `ESC` apriva i crediti invece di uscire (contrario a README e
  GDD); `Invio` non avviava i giochi; il pannello informativo copriva le
  istruzioni; griglia non centrata; icona `icon_32.png` inesistente.
- **`safe_font`**: la catena di font di riserva non scattava mai
  (`SysFont` non fallisce: restituisce il font predefinito).
- **PyInstaller**: la spec non era nel repository (il `.gitignore` escludeva
  tutta `build/`, quindi `!build/*.spec` non poteva funzionare) e i giochi,
  importati dinamicamente, non venivano inclusi nell'eseguibile.
- **SECURITY.md** descriveva un altro progetto (una web app con npm e Phaser).
- **`tools/fix_encoding.py`**: l'opzione `--backup` non si poteva disattivare
  (ora c'è `--no-backup`).

### Aggiunto

- Launcher in stile synthwave: griglia prospettica animata, stelle, glow,
  anteprime animate, record nel pannello informativo, ultimo gioco ricordato,
  avvio diretto con `1`-`9`, crediti scorrevoli, opzioni `--game` e `--save`.
- `pixel_font.py`: font bitmap 5×7 disegnato a mano, con cache.
- `sfx.py`: effetti sonori chiptune sintetizzati in codice (nessun file audio).
- `scores.py`: record e impostazioni persistenti, scrittura atomica.
- Menu di pausa navigabile (tastiera e mouse) con audio e filtro CRT,
  schermate di fine partita con "Nuovo record!", selettore di modalità.
- Finestra ridimensionabile, schermo intero (`F11`), screenshot (`F12`),
  notifiche a comparsa, filtro CRT attivabile.
- Particelle, testi a comparsa e screen shake condivisi tra i giochi.
- Tetris: SRS con wall kick, 7-bag, lock delay, hold, 3 pezzi in anteprima,
  DAS/ARR, punteggio guideline.
- Pong: CPU predittiva a 3 livelli, accelerazione della palla, servizio.
- Breakout: 5 livelli, mattoni 1-3 colpi, power-up (paddle largo,
  multi-palla, rallentatore, vita), lancio dalla racchetta.
- Space Invaders: sprite animati, scudi distruttibili, UFO, marcia a 4 note.
- Maze Runner: modalità al buio, suggerimento BFS, movimento fluido.
- Memory: 3 griglie, 12 icone pixel-art, flip animato, combo, tastiera.
- Puzzle 15: scorrimento di più tessere, evidenziazione delle tessere giuste.
- Tic Tac Toe: CPU imbattibile, alternanza di chi inizia, segni animati.
- Motore AI: tabella di trasposizione, tie-break casuale, `blunder_rate`,
  preset `GameAI.for_level()`.
- 144 test pytest (logica, AI esaustiva, salvataggi, smoke test di ogni gioco
  e del launcher), `pyproject.toml` con configurazione di pytest e ruff.
- `packaging/RetroArcadeCollection.spec`, `tools/make_icon.py`,
  `assets/icon.png` e `assets/icon.ico`, screenshot in `docs/screenshots/`.

### Modificato

- Tutti i giochi espongono `main(load_scores=None, save_scores=None)`;
  i vecchi nomi (`snake_game`, `tris_game`, `tetris_game`, `main_loop`,
  `PuzzleGame`) restano come alias compatibili.
- Testi dell'interfaccia uniformati in italiano.
- Fisica basata sul tempo reale (`dt` in secondi) invece che sui frame.
- `requirements.txt` solo runtime; nuovo `requirements-dev.txt`.

## [2.0.0] - 2026-03

- Prima versione pubblica: 9 giochi, launcher con dispatch pattern, cache LRU
  dei font, motore AI per il Tris.
