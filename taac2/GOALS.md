# Goal pronti — uno per fase

Comandi /goal da incollare in Claude Code uno alla volta, in ordine. Dai il goal
successivo solo quando la fase precedente è completa e committata. Tra una fase e
l'altra puoi lanciare tu pytest come verifica indipendente.

Prima di tutto incolla il prompt di avvio (PROMPT-CLAUDE-CODE.md) e aspetta che
confermi di aver letto PROJECT.md e CLAUDE.md. Poi parti da qui.

---

## Fase 1 — Scaffold

```
/goal Completa la Fase 1 (scaffold) come da PROJECT.md §15. FastAPI avviabile
(endpoint di health), Dockerfile a immagine singola, SQLite su volume con WAL
abilitato all'avvio, Alembic inizializzato, struttura cartelle pulita, pytest
configurato che gira a vuoto. Fase completa quando pytest passa e tutto è
committato.
```

## Fase 2 — Auth

```
/goal Completa la Fase 2 (auth) come da PROJECT.md §11. Tabella users, register/
login/refresh con JWT (access + refresh), password con hashing sicuro (argon2 o
bcrypt). Ogni rotta protetta ricava l'utente dal token, mai da input del client
(vincolo CLAUDE.md). Test su registrazione, login, refresh, accesso negato senza
token. Fase completa quando i test passano e il commit è fatto.
```

## Fase 3 — Modello dati + migrazioni

```
/goal Completa la Fase 3 (modello dati) come da PROJECT.md §7. Crea tutte le
tabelle: profiles, preferences, weight_logs, foods, portions, paths,
diary_entries, chat_messages, più il campo anthropic_key_encrypted su users, con
le migrazioni Alembic relative. Rispetta le note: diary_entries ammette
free_text e non salva kcal/macro. Test che le migrazioni applicano e fanno
rollback puliti. Fase completa quando i test passano e il commit è fatto.
```

## Fase 4 — Chiave utente (cifrata)

```
/goal Completa la Fase 4 (chiave utente) come da PROJECT.md §6. Rotta POST
/settings/anthropic-key che salva la chiave Anthropic dell'utente CIFRATA a
riposo (usa ENCRYPTION_KEY dal .env), validandola alla prima immissione con una
chiamata di test leggera. La chiave si decifra solo in RAM al momento dell'uso,
non si rimanda mai al frontend, non si logga (vincolo CLAUDE.md). Test su
cifratura/decifratura e sul fatto che la chiave non compaia mai in risposte o
log; il test NON deve chiamare davvero l'API Anthropic (mocka la validazione).
Fase completa quando i test passano e il commit è fatto.
```

## Fase 5 — Database alimenti

```
/goal Completa la Fase 5 (database alimenti) come da PROJECT.md §8. CSV di seed
con ~100 alimenti italiani comuni, valori per 100g da fonte CREA, convenzione DA
CRUDO (vincolo CLAUDE.md), con porzioni di riferimento etichettate. Script di
seed idempotente (popola solo se vuoto). Rotte GET /foods con ricerca e filtro
categoria, POST /foods per alimenti personali. Commento nel CSV con fonte e
convenzione crudo. Test su seed e ricerca. Fase completa quando i test passano e
il commit è fatto.
```

## Fase 6 — Motore di calcolo (verificatore)

```
/goal Completa la Fase 6 (motore di calcolo) come da PROJECT.md §9. core/
nutrition.py PURO: niente DB, niente rete, niente LLM. Implementa BMR Mifflin-St
Jeor (basi M/F), TDEE coi fattori di attività, fabbisogno per goal (feel_good e
maintain ≈ TDEE di default, gentle_loss/gain moderati), e soprattutto la
funzione di VERIFICA di un percorso: data una struttura di pasti con alimenti e
grammature, somma kcal/macro dai valori del database, confronta col fabbisogno e
produce esito verified + note neutre. Rispetta il requisito etico §9 (default
benessere, nessun giudizio nei dati). Test completi e verdi: Mifflin M/F su casi
noti, TDEE per ogni livello, verifica di un percorso con totali noti, edge case
(profilo incompleto, alimento fuori database). Fase completa quando i test
passano e il commit è fatto.
```

## Fase 7 — Profilo + gusti + peso

```
/goal Completa la Fase 7 (profilo, gusti, peso) come da PROJECT.md §11. Rotte
GET/PUT /profile, GET/PUT /preferences (liked, avoided, constraints), POST/GET
/weights, GET /summary/needs (fabbisogno dal motore della Fase 6). Il profilo
separa l'identità dal parametro di calcolo (calc_basis, §9). Tutto scoped
sull'utente del token. Test su salvataggio profilo e gusti, log peso, calcolo
fabbisogno. Fase completa quando i test passano e il commit è fatto.
```

## Fase 8 — Assistente (chat)

```
/goal Completa la Fase 8 (assistente chat) come da PROJECT.md §10. core/coach.py
che a ogni messaggio assembla il contesto reale dell'utente (profilo, gusti,
peso recente, percorsi, ultime voci diario, storico chat) e lo passa a Claude
con il system prompt del contratto §10: l'LLM può proporre e dialogare, ma
ancora i valori nutrizionali al database e dichiara come stima ciò che non c'è;
tono non giudicante, default benessere; non sostituisce un medico. Usa la chiave
dell'utente (decifrata a runtime); se assente o invalida, la chat si disattiva
con messaggio chiaro e il resto dell'app funziona. Rotte POST /coach/chat e GET
/coach/history. La chiave mai esposta né loggata (vincolo CLAUDE.md). Test su
costruzione del contesto e comportamento a chiave assente, SENZA chiamare
davvero l'API. Fase completa quando i test passano e il commit è fatto.
```

Nota: prima fase in cui serve una chiave Claude vera per il test manuale end-to-
end. Registrati un utente e metti la tua chiave dall'app per provarla.

## Fase 9 — Percorsi (genera + verifica)

```
/goal Completa la Fase 9 (percorsi) come da PROJECT.md §10. Rotta POST
/paths/generate col flusso genera-poi-verifica: l'LLM genera un percorso
strutturato sui gusti dell'utente, il motore (Fase 6) ne verifica i conti, e se
incoerente l'LLM rivede (1-2 giri), poi si salva in paths. Esponi all'LLM i tool
search_food, verify_path, get_user_context, save_path; save_path e ogni scrittura
dietro conferma dell'utente. Rotte GET /paths e GET /paths/{id}. Test sul flusso
con LLM mockato (verifica che un percorso incoerente venga rigettato dal motore).
Fase completa quando i test passano e il commit è fatto.
```

## Fase 10 — Diario opzionale + hardening

```
/goal Completa la Fase 10 (diario + hardening) come da PROJECT.md §11 e §12.
Rotte diario POST/GET/DELETE /diary con free_text ammesso. Validazione input
(Pydantic), disclaimer medico-legale accessibile, gestione pulita degli errori
LLM (chiave invalida, timeout, quota) senza far cadere l'app, limite tecnico
anti-abuso sulle chiamate. Rivedi che tutti i vincoli duri di CLAUDE.md siano
rispettati ovunque (chiave mai esposta, rotte scoped, default benessere). Test
sui casi di errore. Fase completa quando i test passano e il commit è fatto.
```

## Fase 11 — Frontend

```
/goal Completa la Fase 11 (frontend) come da PROJECT.md §13. UI che consuma le
API, con la CHAT come schermata principale, più: gusti, percorsi salvati,
profilo, impostazioni (inserimento chiave Claude), e opzionali peso/diario. Tono
coerente col requisito etico §9 (niente colpa, l'utente può non vedere numeri).
Qui i pezzi sono indipendenti: puoi parallelizzare. Fase completa quando la UI è
navigabile, collegata al backend, e committata.
```

---

## Promemoria d'uso

- Un goal alla volta, in ordine. Aspetta che la fase sia committata.
- Se /goal si ferma per il limite orario, riapri e di': "riprendi dal
  tasks/todo.md, continua dalla prima voce non spuntata".
- La chiave Claude serve da te (utente) solo dalla Fase 8 in poi, e la metti
  dall'app, non nel .env.
- I due dynamic workflow (espansione seed dopo la Fase 5, audit dopo la Fase 10)
  sono nel PROMPT-CLAUDE-CODE.md.
