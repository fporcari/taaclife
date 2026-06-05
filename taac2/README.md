# NutriCoach — documenti di progetto

Assistente conversazionale per l'alimentazione, multi-utente. L'app conosce la
persona (gusti, peso, percorso) e genera percorsi alimentari su misura dei suoi
gusti dialogando in linguaggio naturale; un motore di calcolo deterministico
verifica i conti dietro le quinte. Ogni utente usa la propria chiave Claude.
Stack: FastAPI + SQLite, Docker a immagine singola, self-host.

Questa cartella contiene i documenti da dare a Claude Code per costruire l'app.
Non è ancora codice: è tutto il materiale per partire.

## I file, in ordine d'uso

1. **PROMPT-CLAUDE-CODE.md** — il punto di partenza. Il prompt da incollare in
   Claude Code e come guidarlo con /goal. Leggi questo per primo.

2. **PROJECT.md** — la specifica completa: architettura (l'LLM propone, il
   motore verifica), modello dati, chiave per-utente, API, Docker, ordine delle
   fasi, decisioni prese. È il riferimento che Claude Code consulta.

3. **CLAUDE.md** — i vincoli duri, in forma breve. Va nel repo: Claude Code lo
   rilegge a ogni sessione per non perdere la rotta.

4. **GOALS.md** — tutti i comandi /goal pronti, uno per fase, da incollare in
   sequenza. Il tuo copione operativo.

5. **DEPLOY-HETZNER.md** — messa in produzione sul server Hetzner con dominio e
   HTTPS. Serve alla fine.

6. **.env.example** — variabili d'ambiente di sistema (JWT, ENCRYPTION_KEY).
   NON contiene chiavi Claude: quelle le mettono gli utenti dall'app.

## Come iniziare

1. Crea un repo Git e copiaci dentro PROJECT.md, CLAUDE.md e .env.example.
2. Apri Claude Code in quella cartella.
3. Incolla il prompt da PROMPT-CLAUDE-CODE.md.
4. Guidalo fase per fase coi comandi /goal pronti in GOALS.md.
5. A fine progetto, segui DEPLOY-HETZNER.md per il deploy.

## Promemoria

- La chiave Claude la mettono gli utenti dall'app (cifrata nel db), non sta nel
  .env. A te serve una chiave vera solo dalla Fase 8 per il test end-to-end.
- tasks/todo.md (che Claude Code crea) è la memoria del progetto: se una
  sessione si interrompe, si riprende da lì.
- Lancia tu pytest ogni tanto, come verifica indipendente.
- Il file .db conterrà le chiavi cifrate degli utenti: trattalo come dato
  sensibile nei backup.
