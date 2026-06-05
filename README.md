# NutriCoach — documenti di progetto

App di diario alimentare multi-utente: database alimenti, motore di calcolo
nutrizionale deterministico, e una chat (coach) basata su Claude API che parla
sui dati reali dell'utente. Stack: FastAPI + SQLite, Docker a immagine singola,
self-host.

Questa cartella contiene i documenti da dare a Claude Code per costruire l'app.
Non è ancora codice: è tutto il materiale per partire.

## I file, in ordine d'uso

1. **PROMPT-CLAUDE-CODE.md** — il punto di partenza. Contiene il prompt da
   incollare in Claude Code e le istruzioni su come guidarlo con `/goal` fase
   per fase. Leggi questo per primo.

2. **PROJECT.md** — la specifica completa del progetto: architettura, modello
   dati, motore di calcolo, layer LLM, API, Docker, ordine delle fasi, decisioni
   prese. È il riferimento che Claude Code consulta durante il lavoro.

3. **CLAUDE.md** — i vincoli duri, in forma breve. Va messo nel repo: Claude
   Code lo rilegge a ogni sessione per non perdere la rotta.

4. **DEPLOY-HETZNER.md** — come mettere l'app in produzione sul server Hetzner
   con dominio e HTTPS. Serve alla fine, quando l'app è pronta.

5. **.env.example** — modello delle variabili d'ambiente (senza valori reali).
   Da copiare in `.env` e riempire al momento del deploy.

## Come iniziare

1. Crea un repo Git e copiaci dentro `PROJECT.md`, `CLAUDE.md` e
   `.env.example`.
2. Apri Claude Code in quella cartella.
3. Incolla il prompt da `PROMPT-CLAUDE-CODE.md`.
4. Guidalo fase per fase con i comandi `/goal` (esempi pronti nel prompt).
5. A fine progetto, segui `DEPLOY-HETZNER.md` per il deploy.

## Promemoria

- La tua API key Anthropic serve solo dalla Fase 8 (chat coach) in poi.
- `tasks/todo.md` (che Claude Code crea) è la memoria del progetto: se una
  sessione si interrompe, si riprende da lì.
- Lancia tu `pytest` ogni tanto, come verifica indipendente.
