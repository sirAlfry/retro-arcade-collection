# Politica di Sicurezza

Grazie per dare un'occhiata a questo documento: significa che ti interessa la
salute del progetto. Qui trovi cosa è considerato un problema di sicurezza in
**Retro Arcade Collection**, come segnalarlo e cosa aspettarti dopo.

## Versioni supportate

| Versione | Stato |
| -------- | ----- |
| `main` (ultima release, attualmente 3.x) | ✅ supportata |
| versioni precedenti / fork non upstream | ❌ non supportate |

Se mantieni un fork modificato, la sua sicurezza è sotto la tua responsabilità;
resto comunque disponibile a discutere segnalazioni che riguardano il codice
originale.

## Modello di minaccia

Per non creare aspettative sbagliate, ecco com'è fatta la "superficie di
attacco" di Retro Arcade Collection:

- È un'**applicazione desktop offline** scritta in Python con
  [Pygame-CE](https://pyga.me/): nessun server, nessuna API, nessun account,
  **nessuna connessione di rete**.
- Non raccoglie **dati personali**: niente analytics, niente telemetria.
- Scrive solo file locali:
  - `scores.json` (record e impostazioni), con scrittura atomica;
  - `retro_arcade.log` (eventuali errori dei giochi);
  - immagini PNG nella cartella `screenshots/` quando premi F12.
- Unica dipendenza di runtime: `pygame-ce`. Strumenti di sviluppo: `pytest`,
  `ruff`, `pyinstaller`, `pillow` (vedi `requirements-dev.txt`).
- L'eseguibile per Windows viene prodotto in locale con PyInstaller
  (`packaging/RetroArcadeCollection.spec`).

### Cose che *considero* problemi di sicurezza

- **Esecuzione di codice** o scrittura di file in percorsi inattesi a partire
  da un `scores.json` costruito ad arte (il file viene letto solo con
  `json.loads`, ma segnala qualunque vettore concreto).
- **Scritture fuori dalle cartelle documentate**: il programma deve creare o
  modificare solo `scores.json`, `retro_arcade.log` e `screenshots/` (nella
  cartella del programma o nella cartella utente descritta nel README).
- **Vulnerabilità note nelle dipendenze** (`pygame-ce`, SDL incluso nelle sue
  wheel, `pyinstaller`) che impattino l'eseguibile distribuito.
- **Manomissione della catena di build**: spec di PyInstaller o script in
  `tools/` che potrebbero far finire codice estraneo nell'eseguibile.

### Cose che *non sono* problemi di sicurezza

- **Modificare `scores.json` a mano** per avere record altissimi: non c'è una
  classifica online, i salvataggi sono personali e locali.
- **Vedere o modificare il codice sorgente**: il progetto è open source.
- **Antivirus che segnalano l'eseguibile PyInstaller** come sospetto: è un
  falso positivo noto dei programmi "impacchettati"; la spec di PyInstaller
  usa `upx=False` proprio per ridurlo. Se succede, apri una normale issue.
- **Bug di gioco**, crash o glitch grafici: sono bug normali, da aprire come
  issue pubbliche.

## Come segnalare una vulnerabilità

**Per favore non aprire una Issue pubblica per problemi di sicurezza**: la
renderebbe visibile a chiunque prima che esista una correzione.

Usa le **GitHub Security Advisories** (segnalazione privata): pagina del
repository → scheda **Security** → **Report a vulnerability**, oppure
direttamente:

> https://github.com/sirAlfry/retro-arcade-collection/security/advisories/new

### Cosa includere

Anche solo in parte va benissimo:

1. **descrizione** del problema e dell'impatto previsto;
2. **passi per riprodurlo** (sistema operativo, versione di Python e di
   pygame-ce, eventuale file `scores.json` o comando usato);
3. **proof-of-concept**, se ne hai uno;
4. **idee per la correzione**, se ne hai.

Se non sei sicuro che sia un problema di sicurezza, segnalalo lo stesso:
meglio un falso allarme che un problema reale taciuto.

## Cosa aspettarti dopo la segnalazione

- **Conferma di ricezione** entro **5 giorni lavorativi**.
- **Prima valutazione** (gravità, impatto, riproducibilità) entro **14 giorni**.
- **Correzione**: i tempi dipendono dalla gravità; i problemi critici (es.
  esecuzione di codice) hanno la precedenza assoluta.
- **Divulgazione coordinata**: i dettagli diventano pubblici solo dopo la
  correzione, tramite un advisory GitHub. Ti chiederò se vuoi essere
  ringraziato pubblicamente.

È un progetto open source mantenuto nel tempo libero: farò del mio meglio per
rispettare questi tempi. Se passa più di un mese senza notizie, sentiti libero
di sollecitarmi.

## Ringraziamenti

Le persone che segnalano in modo responsabile vulnerabilità reali verranno
elencate qui, se lo desiderano.

_(ancora nessuno: il primo ringraziamento potrebbe essere il tuo!)_

## Risorse utili

- [GitHub Security Advisories — documentazione](https://docs.github.com/en/code-security/security-advisories)
- [Python Packaging Advisory Database](https://github.com/pypa/advisory-database)
- [`pip-audit`](https://pypi.org/project/pip-audit/) per controllare le
  vulnerabilità note delle dipendenze Python: `pip install pip-audit && pip-audit -r requirements.txt`
