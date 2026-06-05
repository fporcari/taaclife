# CLAUDE.md

Istruzioni operative per chi lavora su questo repo (incluso Claude Code).
Il progetto completo è in `PROJECT.md`. Questo file sono le regole che non si
violano mai, da rileggere all'inizio di ogni sessione.

## Cos'è questo progetto
Web app multi-utente di diario alimentare: database alimenti, motore di calcolo
nutrizionale deterministico, e una chat (coach) basata su Claude API che parla
sui dati reali dell'utente. Stack: FastAPI + SQLite + SQLAlchemy/Alembic, Docker
a immagine singola, self-host.

## Regole dure (non negoziabili)

1. **I numeri li fa il motore, l'LLM parla.**
   Calorie, macro, fabbisogno, bilanci: solo da `core/nutrition.py`,
   deterministico e testato. L'LLM riceve i numeri già calcolati e li spiega.
   Non somma, non stima, non deduce calorie. Se manca un dato, dice che manca.

2. **Tono e scopo etici.**
   Default obiettivo = mantenimento, non dimagrimento. Nessun deficit
   aggressivo, nessuna gamification del deficit. Niente cibi "buoni/cattivi",
   niente colpa. Possibilità di nascondere del tutto le calorie. L'app non è un
   dispositivo medico e non sostituisce un professionista: disclaimer sempre
   accessibile, niente linguaggio diagnostico.

3. **Sicurezza.**
   La API key Anthropic sta solo nel backend (`.env`), mai nel frontend, mai
   nell'immagine Docker, mai in un log. Ogni rotta dati è scoped sull'utente del
   token: mai fidarsi di uno user_id passato dal client.

4. **Convenzione alimenti: da crudo.**
   I valori nel database sono per 100 g di alimento crudo / peso secco. Le
   porzioni sono etichettate di conseguenza. Sbagliare questo raddoppia i
   totali. In dubbio, fermarsi e chiedere, non indovinare.

## Metodo di lavoro

- Seguire l'ordine di fasi del `PROJECT.md` §12, una alla volta.
- **Committare a fine di ogni fase**, con messaggio chiaro.
- **Non passare alla fase successiva se i test della fase corrente non
  passano.** I test non sono opzionali, soprattutto per il motore di calcolo.
- Tenere `core/nutrition.py` puro: niente DB, niente rete, niente LLM lì dentro.
- Se una decisione non è coperta dal `PROJECT.md`, scegliere l'opzione più
  semplice e documentarla, oppure fermarsi e segnalarla, invece di inventare.

## File di riferimento
- `PROJECT.md` — specifica completa.
- `DEPLOY-HETZNER.md` — come mettere l'app in produzione.
- `.env.example` — variabili d'ambiente (senza valori reali).
