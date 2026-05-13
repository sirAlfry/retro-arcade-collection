# Politica di Sicurezza

Grazie per dare un'occhiata a questo documento: significa che ti interessa la
salute del progetto, e questo aiuta chiunque ci giochi. Qui sotto trovi cosa
è considerato problema di sicurezza in Neon Arcade, come segnalarlo, e cosa
aspettarti dopo.

## Versioni supportate

Neon Arcade è un progetto giovane: riceve aggiornamenti di sicurezza solo
sull'ultima versione pubblicata sul branch `main` e deployata su GitHub Pages.

| Versione | Stato                              |
| -------- | ---------------------------------- |
| `main`   | ✅ supportata                       |
| versioni precedenti / fork non upstream | ❌ non supportate    |

Se hai un fork modificato, sei responsabile della sua manutenzione di
sicurezza. Resto comunque disponibile a discutere segnalazioni che riguardano
il codice originale upstream.

## Modello di minaccia

Per non darti aspettative sbagliate, ecco com'è fatta la "superficie di
attacco" di Neon Arcade:

- È una **single-page application statica** servita da GitHub Pages.
- Non ha **backend**, non ha **API**, non ha **autenticazione**.
- Non raccoglie **dati personali**: niente analytics, niente cookie di
  tracciamento, niente account.
- Salva solo dati locali in `localStorage` (livello massimo, tempi migliori,
  conteggio duelli) sotto la chiave `neon-arcade.progress.v1`. Questi dati
  sono visibili e modificabili dall'utente stesso — non è una vulnerabilità,
  è una caratteristica architetturale.
- Carica risorse esterne solo da `fonts.googleapis.com` e `fonts.gstatic.com`
  (Google Fonts) tramite `<link>` HTTPS.

### Cose che *considero* problemi di sicurezza

- **Cross-site scripting (XSS)** tramite input dell'utente. Il punto più
  esposto è il campo "Scrivi tu un insulto" in *Sfida di Insulti*: anche se
  Phaser rende l'input come testo puro tramite `Text.setText()` e non come
  HTML, una catena di chiamate potrebbe in teoria iniettare codice se il
  testo finisse inavvertitamente in un `innerHTML`. Segnala se trovi un
  vettore concreto.
- **Vulnerabilità nelle dipendenze npm** in produzione (esbuild, rolldown,
  vite, phaser, ecc.) che impattino il bundle pubblicato. Le dipendenze di
  solo sviluppo (devDependencies) sono meno critiche ma comunque accetto
  segnalazioni.
- **Manomissione della catena di build** (npm scripts, GitHub Actions,
  workflow di deploy) che potrebbero permettere a un attaccante di iniettare
  codice nel bundle pubblicato.
- **Errori in `Content-Security-Policy`** o nelle intestazioni del deploy
  GitHub Pages che riducano le difese del browser.

### Cose che *non sono* problemi di sicurezza in questo progetto

- **Modificare il proprio `localStorage`** per sbloccare livelli o falsare i
  tempi migliori. Non c'è leaderboard online né punteggi competitivi; il save
  è personale e locale.
- **Vedere il codice sorgente JavaScript** nelle DevTools: il progetto è
  open source e il bundle è pubblico per progetto, niente lì dentro è
  considerato segreto.
- **Comportamenti di gioco "stranamente facili" o "stranamente difficili"**:
  sono bug di game design, vanno aperti come issue normali, non come
  segnalazioni di sicurezza.
- **Avvisi di "low severity"** segnalati da `npm audit` su transitive
  dependencies che non sono raggiungibili dal codice in produzione. Saranno
  comunque valutate ma con priorità più bassa.
- **Bug nel rendering** (artefatti grafici, glitch di Phaser, layout rotto su
  certe risoluzioni): di nuovo, issue normale.

## Come segnalare una vulnerabilità

**Per favore non aprire una Issue pubblica per problemi di sicurezza.** Una
issue pubblica rende il problema visibile a chiunque prima che ci sia una
patch, esponendo gli utenti al rischio.

I canali corretti, in ordine di preferenza:

### 1. GitHub Security Advisories (raccomandato)

Vai sulla pagina del repository su GitHub → scheda **Security** → **Report a
vulnerability**, oppure direttamente:

> `https://github.com/<owner>/neon-arcade/security/advisories/new`

GitHub gestirà la segnalazione in privato, mi avviserà, e ci permetterà di
discutere il problema senza che sia pubblicamente visibile finché non c'è
una soluzione.

### 2. Email diretta

Se per qualsiasi motivo non riesci a usare GitHub Security Advisories, puoi
scrivermi a:

> _<scrivi qui la tua email, oppure rimuovi questa sezione se preferisci usare solo GitHub Security Advisories>_

Includi il prefisso `[neon-arcade security]` nell'oggetto per aiutarmi a
filtrare.

### Cosa includere nella segnalazione

Per accelerare il triage, prova a fornire (anche solo in parte va bene):

1. **Una descrizione** del problema e dell'impatto previsto
2. **Passi per riprodurre** (URL, input, sequenza di azioni, browser e
   versione, sistema operativo)
3. **Proof-of-concept** se ne hai uno (anche una GIF o uno screenshot
   aiutano)
4. **Suggerimenti per la mitigazione**, se hai un'idea

Se non sei sicuro che sia un problema di sicurezza, segnalalo lo stesso:
preferisco un falso positivo a un vero positivo non segnalato.

## Cosa aspettarti dopo la segnalazione

- **Conferma di ricezione** entro **5 giorni lavorativi**.
- **Prima valutazione** (severità, impatto, riproducibilità) entro
  **14 giorni**. Se non riesco a confermare il problema, ti chiederò
  informazioni aggiuntive.
- **Fix e deploy**: il tempo dipende dalla severità.
  - Critica (esecuzione di codice arbitrario, compromissione della catena
    di build): obiettivo entro 7 giorni.
  - Alta (XSS sfruttabile, leak di dati locali sensibili): obiettivo entro
    30 giorni.
  - Media / bassa: nella prossima release pianificata.
- **Disclosure coordinata**: aspetto che il fix sia rilasciato prima di
  rendere pubblici i dettagli. Ti chiederò se vuoi essere accreditato
  nell'advisory pubblico (vedi sotto).
- **Trasparenza**: una volta risolto, pubblico l'advisory tramite GitHub
  con i dettagli necessari a capire l'impatto e a verificare il fix.

Tieni presente che Neon Arcade è un progetto open source mantenuto nel tempo
libero: farò del mio meglio per rispettare questi tempi, ma in periodi
particolarmente impegnativi potrebbero allungarsi. Se passa più di un mese
senza aggiornamenti, sentiti libero di sollecitarmi.

## Crediti

Le persone che segnalano in modo responsabile vulnerabilità reali sono
elencate qui sotto come ringraziamento, se sono d'accordo. Nessun obbligo
e nessun "hall of fame" da ostentare — è solo un modo di dire grazie.

<!-- Esempio:
- **Nome / nickname** — [breve descrizione della segnalazione, data]
-->

_(ancora nessuno: il primo ringraziamento potresti essere tu!)_

## Risorse utili

- [GitHub Security Advisories — documentazione](https://docs.github.com/en/code-security/security-advisories)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/) per familiarizzare
  con le categorie di vulnerabilità più comuni
- [npm audit](https://docs.npmjs.com/cli/v10/commands/npm-audit) per
  controllare lo stato delle dipendenze del progetto

Grazie per contribuire alla sicurezza di Neon Arcade. 🛡️
