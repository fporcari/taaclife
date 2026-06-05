# CLAUDE.md

Istruzioni operative per chi lavora su questo repo (incluso Claude Code).
Il progetto completo è in PROJECT.md. Questo file sono le regole che non si
violano mai, da rileggere all'inizio di ogni sessione.

## Cos'è questo progetto
Assistente conversazionale per l'alimentazione, multi-utente. L'app conosce la
persona (gusti, peso, percorso) e genera percorsi alimentari su misura dei suoi
gusti dialogando. Un motore di calcolo deterministico verifica i conti. Ogni
utente usa la propria chiave Claude. Stack: FastAPI + SQLite + SQLAlchemy/
Alembic, Docker a immagine singola, self-host.

## Regole dure (non negoziabili)

1. **L'LLM propone, il motore verifica.**
   L'LLM ha libertà creativa sui percorsi e sul dialogo. Ma i valori
   nutrizionali si ancorano al database alimenti, e i conti di un percorso li
   verifica core/nutrition.py (deterministico, testato). Numeri mostrati come
   certi vengono da database/motore, non inventati dall'LLM. Ciò che non è in
   database va dichiarato come stima. core/nutrition.py resta puro: niente DB,
   niente rete, niente LLM lì dentro.

2. **Chiave per-utente, cifrata, mai esposta.**
   Non esiste una chiave di sistema. Ogni utente salva la sua, che va cifrata a
   riposo nel database (mai in chiaro), decifrata solo in RAM per la durata
   della chiamata, mai rimandata al frontend, mai loggata. La ENCRYPTION_KEY per
   cifrarle sta nel .env del server.

3. **Tono e scopo etici.**
   Default goal = feel_good: nessun obiettivo di peso, si lavora sui gusti e sul
   benessere. Nessun deficit aggressivo, nessuna gamification del deficit.
   Niente cibi "buoni/cattivi", niente colpa. L'utente può non vedere mai un
   numero. L'app non è un dispositivo medico: disclaimer sempre accessibile,
   niente linguaggio diagnostico o prescrittivo. I percorsi sono suggerimenti di
   benessere, non prescrizioni.

4. **Convenzione alimenti: da crudo.**
   Valori del database per 100 g di alimento crudo / peso secco. Porzioni
   etichettate di conseguenza. Sbagliarlo raddoppia i conti. In dubbio,
   fermarsi e chiedere.

5. **Sicurezza generale.**
   Ogni rotta dati è scoped sull'utente del token: mai fidarsi di uno user_id
   passato dal client.

## Metodo di lavoro

- Seguire l'ordine di fasi del PROJECT.md §15, una alla volta.
- **Committare a fine di ogni fase**, con messaggio chiaro.
- **Non passare alla fase successiva se i test della fase corrente non
  passano.** I test del motore di calcolo sono obbligatori. I test che toccano
  l'LLM o la chiave non devono chiamare davvero l'API: testano cifratura,
  costruzione del contesto, comportamento a chiave assente.
- "Fase completa" = test verdi E vincoli duri rispettati. Non far passare i test
  con scorciatoie che violano i vincoli o svuotano il test.
- Se una decisione non è coperta da PROJECT.md, scegliere l'opzione più semplice
  e documentarla, oppure fermarsi e segnalarla, invece di inventare.

## File di riferimento
- PROJECT.md — specifica completa.
- GOALS.md — comandi /goal pronti, uno per fase.
- DEPLOY-HETZNER.md — messa in produzione.
- .env.example — variabili d'ambiente (senza valori reali).
