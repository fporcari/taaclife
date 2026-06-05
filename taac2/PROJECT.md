# Proto-progetto: NutriCoach (nome di lavoro)

Documento di partenza per implementazione con Claude Code. Descrive cosa
costruire, con quali vincoli e in quale ordine. Non è codice: è il contratto
che il codice deve rispettare.

---

## 1. Obiettivo in una frase

Web app multi-utente che è un **assistente conversazionale per l'alimentazione**:
conosce la persona (gusti, peso, storia, percorso), e genera percorsi alimentari
su misura dei suoi gusti dialogando in linguaggio naturale. Un motore di calcolo
deterministico fa da verificatore dei conti dietro le quinte. Ogni utente usa la
propria chiave Claude.

## 2. Cambio di prospettiva rispetto a un contatore di calorie

Questa **non** è un'app di conteggio calorie con una chat sopra. È una chat che
conosce la persona e le costruisce percorsi. I dati (gusti, peso, percorso) non
sono schede da compilare come obbligo: sono il **contesto che arricchisce
l'assistente**. Il diario e il peso esistono come materiale per il dialogo, non
come adempimento quotidiano.

Lo spirito è quello di partenza: aiutare a sentirsi bene, senza ossessione del
numero. Niente cibi "buoni/cattivi", niente colpa, niente gamification del
deficit. L'utente può vivere l'app interamente come conversazione.

## 3. Principio architetturale: l'LLM propone, il motore verifica

Il ruolo dell'LLM e del motore è diverso da un'app di solo conteggio:

- **L'LLM genera e racconta**: costruisce i percorsi alimentari sui gusti
  dell'utente, dialoga, spiega, adatta. È la parte creativa e relazionale.
- **Il motore verifica**: `core/nutrition.py`, deterministico e testato,
  controlla che i conti di un percorso proposto stiano in piedi (fabbisogno
  stimato, ordini di grandezza calorici, coerenza con eventuali vincoli
  dichiarati). Non genera il percorso: lo valida.
- **Numeri mostrati come fatti certi vengono dal motore o dal database**, non
  inventati dall'LLM. Quando l'LLM propone un percorso, i valori nutrizionali
  delle porzioni si ricavano dal database alimenti; il motore somma e confronta.
  Se un alimento non è in database, l'LLM lo segnala come stima, non come dato.

In sintesi: l'LLM ha libertà creativa sui *percorsi e sul dialogo*, ma i
*numeri* restano ancorati a database + motore. Questa è la linea che tiene
l'app utile invece che un chatbot che allucina diete.

## 4. Disclaimer obbligatorio

L'app non è un dispositivo medico e non sostituisce un nutrizionista o un
medico. Disclaimer all'onboarding e sempre accessibile. Nessun linguaggio
diagnostico o prescrittivo. I percorsi sono suggerimenti di benessere, non
prescrizioni dietetiche. Tono di supporto, mai di giudizio.

## 5. Stack tecnico

| Livello   | Scelta                                              |
|-----------|-----------------------------------------------------|
| Backend   | FastAPI (Python 3.12)                               |
| DB        | SQLite (file su volume), WAL mode attivo            |
| ORM       | SQLAlchemy 2.x + Alembic per le migrazioni          |
| Auth      | JWT (access + refresh), password con bcrypt/argon2  |
| LLM       | Anthropic API (Claude), SDK ufficiale               |
| Crittografia | libreria per cifrare la chiave utente a riposo (es. cryptography/Fernet) |
| Frontend  | da decidere in fase finale. API-first.              |
| Container | Docker (immagine singola)                           |
| Hosting   | macchina personale del committente (self-host)      |
| Test      | pytest                                              |

Motivazione invariata: side project leggero, SQLite adatto al profilo d'uso
(poche scritture, molte letture conversazionali). Con SQLAlchemy si migra a
Postgres cambiando solo la DATABASE_URL se un domani serve concorrenza.

## 6. Chiave Claude: una per utente

Cambio rispetto alla prima impostazione. **Non c'è una chiave di sistema.** Ogni
utente inserisce e salva la propria chiave Anthropic dalle impostazioni.

Conseguenze e requisiti:
- La chiave dell'utente si salva **cifrata a riposo** nel database (mai in
  chiaro), e resta solo lato backend: mai rimandata al frontend, mai loggata.
- Il costo delle chiamate è dell'utente, non di chi ospita l'istanza. Sparisce
  il rate limiting come difesa di spesa (resta sensato un limite tecnico per
  evitare abusi).
- Onboarding: finché l'utente non ha messo una chiave valida, la chat è
  disattivata con un messaggio chiaro che spiega come ottenerne una. Il resto
  dell'app (profilo, gusti, eventuale diario) funziona comunque.
- Validazione della chiave: alla prima immissione, una chiamata di test leggera
  per verificare che funzioni, poi salvataggio cifrato.

## 7. Modello dati (prima bozza)

```
users
  id (uuid, pk)
  email (unique)
  password_hash
  anthropic_key_encrypted (nullable)   # chiave dell'utente, cifrata a riposo
  created_at

profiles                      # contesto della persona per l'assistente
  user_id (fk users, unique)
  calc_basis     # 'F' | 'M' -> solo per la formula del fabbisogno (vedi §9)
  birth_date
  height_cm
  activity_level # enum: sedentary, light, moderate, active, very_active
  goal           # enum: feel_good (default), maintain, gentle_loss, gentle_gain
  updated_at

preferences                   # i gusti: il cuore del contesto
  user_id (fk)
  liked   (tabella o array)   # cibi graditi
  avoided (tabella o array)   # cibi da evitare (allergie, antipatie)
  constraints (text)          # note libere: "vegetariana", "poco tempo la sera"

weight_logs
  id (pk)
  user_id (fk)
  measured_at (date)
  weight_kg

foods                         # database alimenti (vedi §8)
  id (pk)
  name
  category
  kcal_100g
  protein_100g / carbs_100g / fat_100g / fiber_100g (nullable)
  source         # 'CREA' | 'user'
  is_public (bool)
  created_by (fk users, nullable)

portions
  id (pk)
  food_id (fk)
  label          # es. "80 g di pasta cruda"
  grams

paths                         # i percorsi alimentari generati
  id (pk)
  user_id (fk)
  created_at
  title
  summary        # descrizione in linguaggio naturale
  content (json) # struttura del percorso (pasti/giorni proposti)
  verified (bool) # esito della verifica del motore
  verify_notes   # eventuali segnalazioni del motore

diary_entries                 # opzionale, materiale per il dialogo
  id (pk)
  user_id (fk)
  consumed_at (timestamp)
  meal           # breakfast/lunch/dinner/snack
  food_id (fk, nullable)
  free_text (nullable)        # "una pizza con gli amici" senza per forza il db
  grams (nullable)

chat_messages
  id (pk)
  user_id (fk)
  role           # 'user' | 'assistant'
  content
  created_at
```

Nota: diary_entries ammette testo libero, perché in un'app conversazionale
l'utente racconta ("ieri sera pizza") senza voler per forza agganciare un
alimento del database. L'assistente usa anche questo come contesto.

## 8. Database alimenti

### Fonte
Tabelle di composizione degli alimenti **CREA** (ex-INRAN), valori per 100 g.
Standard italiano di riferimento. Open Food Facts rimandato a una v2.

### Strategia
- Seed curato di ~100 alimenti italiani comuni in seed/foods.csv versionato.
- Migrazione + seed idempotente (popola solo se vuoto).
- Serve all'LLM come vocabolario per costruire percorsi con valori reali, e al
  motore per verificarli.

### Convenzione crudo/cotto (decisa)
Alimenti registrati **da crudo / peso secco** (es. pasta 100g ~350 kcal). Le
porzioni etichettate di conseguenza ("80 g di pasta cruda"). Documentare nel CSV
e nel CLAUDE.md: sbagliarla raddoppia i conti.

## 9. Motore di calcolo (verificatore deterministico)

Modulo core/nutrition.py, puro (niente DB/rete/LLM), interamente testato.
Il suo ruolo qui è **verificare**, non generare.

### Funzioni di calcolo
- **BMR** Mifflin-St Jeor:
  - base M: 10*kg + 6.25*cm - 5*età + 5
  - base F: 10*kg + 6.25*cm - 5*età - 161
- **TDEE** = BMR × fattore attività (sedentary 1.2 … very_active 1.9).
- **Fabbisogno** secondo il goal: feel_good e maintain ≈ TDEE; gentle_loss
  TDEE −10/15%; gentle_gain +10%. (Vedi nota etica sotto.)

### Verifica di un percorso
Data la struttura di un percorso proposto dall'LLM (pasti con alimenti e
grammature), il motore:
- somma kcal e macro usando i valori del database,
- confronta col fabbisogno stimato dell'utente,
- produce un esito verified + note ("il pranzo proposto è molto leggero",
  "totale giornaliero coerente col mantenimento"). Nessun giudizio morale, solo
  coerenza numerica.

### Nota etica sul goal (requisito di prodotto, non cosmetico)
- Default feel_good: nessun obiettivo di peso, l'assistente lavora sui gusti e
  sul benessere, non sul calo.
- Nessun deficit aggressivo selezionabile; nessuna gamification del deficit.
- L'utente può non vedere mai un numero se non vuole: i conti restano lato
  motore come garanzia di sensatezza, non come metrica da esibire.

### Sesso biologico vs identità
calc_basis ('F'|'M') è solo il parametro della formula, distinto da come
l'utente si identifica. Per chi non vuole specificarlo, media delle due formule
dichiarando l'assunzione.

### Test minimi
Mifflin M/F su casi noti; TDEE per ogni livello; verifica di un percorso con
totali noti; edge case (profilo incompleto, alimento fuori database).

## 10. Layer LLM (l'assistente)

Modulo core/coach.py. È il cuore dell'app: l'utente dialoga, l'assistente
conosce la persona e costruisce percorsi.

### Chiave
Quella dell'utente (vedi §6), decifrata a runtime solo per la durata della
chiamata, mai persistita in chiaro né inviata al client.

### Contesto a ogni messaggio
Il backend assembla dai dati reali: profilo, gusti (liked/avoided/constraints),
peso recente, percorsi attivi/passati, ultime voci diario, storico chat
(troncato). Passato come dati strutturati + system prompt.

### System prompt (contratto)
- Ruolo: assistente di supporto all'alimentazione, **non medico**, non
  sostituisce un professionista.
- **Libertà** di proporre percorsi e dialogare, ma i valori nutrizionali si
  ancorano al database; ciò che non è in database va dichiarato come stima.
- I percorsi generati vanno passati al motore per la verifica prima di
  presentarli come "a posto"; riportare le note del motore all'utente in modo
  naturale.
- Tono non giudicante, lavora sui gusti, default sul benessere non sul calo.
- Se manca un dato, lo dice.

### Generazione + verifica di un percorso (flusso chiave)
```
utente: "creami un percorso per la settimana coi miei gusti"
backend:
  1. assembla contesto (gusti, profilo, fabbisogno dal motore)
  2. LLM genera una proposta di percorso strutturato (json) coi gusti dell'utente
  3. il motore verifica i conti del percorso -> verified + note
  4. se non verificato/incoerente: l'LLM rivede la proposta (1 o 2 giri)
  5. salva in paths, risponde all'utente in linguaggio naturale con le note
```

### Function calling (consigliato già in versione base qui)
Dato che l'LLM genera percorsi, conviene esporgli i tool:
search_food, verify_path(path), get_user_context(), save_path(path).
Così l'LLM pesca alimenti reali e fa verificare i conti dal motore invece di
inventarli. save_* e azioni che scrivono dati dietro conferma dell'utente.

### Sicurezza
Chiave utente cifrata a riposo, decifrata solo in RAM per la chiamata, mai
loggata né esposta. Storico e percorsi scoped sull'utente del token.

## 11. API (FastAPI) — superficie minima

```
POST /auth/register
POST /auth/login
POST /auth/refresh

GET/PUT /profile
GET/PUT /preferences            # i gusti
POST    /settings/anthropic-key # salva la chiave (cifrata); valida alla prima

GET  /foods?q=&category=
POST /foods                     # alimento personale

POST /coach/chat                # dialogo; può generare percorsi
GET  /coach/history

POST /paths/generate            # genera un percorso (LLM) + verifica (motore)
GET  /paths                     # percorsi dell'utente
GET  /paths/{id}

POST/GET /weights
POST/GET/DELETE /diary          # opzionale, testo libero ammesso

GET  /summary/needs             # fabbisogno dal motore (se l'utente lo vuole vedere)
```

Tutto scoped sull'utente del token. Mai fidarsi di uno user_id dal client.

## 12. Docker

Immagine singola, niente Postgres. SQLite su volume persistente
(/data/nutricoach.db). Entrypoint: migrazioni Alembic + seed idempotente +
uvicorn. WAL all'avvio.

.env (non committato): DATABASE_URL, JWT_SECRET, JWT_REFRESH_SECRET,
ENCRYPTION_KEY (per cifrare le chiavi utente a riposo). **Nessuna
ANTHROPIC_API_KEY**: la mettono gli utenti. Fornire .env.example.

Obiettivo: una sola immagine che si avvia, db già popolato dal seed, e offre
l'assistente; ogni utente poi mette la propria chiave.

### Hosting
Self-host su macchina personale. Backup = copia del file .db (che ora contiene
anche le chiavi cifrate degli utenti: trattarlo come dato sensibile).

## 13. Frontend (fase finale)

API-first: backend completo e testabile prima della UI. Sezioni: chat con
l'assistente (centrale), gusti, percorsi salvati, profilo, impostazioni (chiave),
e opzionali peso/diario. La chat è la schermata principale, non una tab fra le
altre.

## 14. CLAUDE.md (nel repo)

Fornito già pronto. Ribadisce a ogni sessione: l'LLM propone/il motore verifica
(§3); chiave per-utente cifrata, mai esposta (§6); convenzione alimenti da crudo
(§8); tono e default benessere (§9); ogni rotta scoped sull'utente; committare a
fasi, non proseguire coi test rossi.

## 15. Ordine di lavoro per Claude Code

Fasi committabili e verificabili una alla volta.

1. **Scaffold**: FastAPI, Dockerfile, SQLite+WAL su volume, Alembic, pytest a
   vuoto.
2. **Auth**: users, register/login/refresh, JWT, test.
3. **Modello dati + migrazioni**: tutte le tabelle di §7.
4. **Chiave utente**: rotta /settings/anthropic-key, cifratura a riposo,
   validazione alla prima immissione, decifratura solo a runtime. Test (con
   cifratura, senza chiamare davvero l'API).
5. **Database alimenti**: seed CSV ~100 CREA da crudo, seed idempotente, rotte
   /foods.
6. **Motore di calcolo (verificatore)**: core/nutrition.py puro + test
   completi (Mifflin, TDEE, verifica percorso, edge case).
7. **Profilo + gusti + peso**: rotte /profile, /preferences, /weights,
   /summary/needs.
8. **Assistente (chat)**: core/coach.py, contesto da dati reali, system prompt
   del contratto §10, /coach/chat + /coach/history. Chiave utente; se
   assente, chat disattivata con messaggio. Versione base: contesto iniettato.
9. **Percorsi**: /paths/generate con il flusso genera-poi-verifica (§10), tool
   per l'LLM (search_food, verify_path, save_path), salvataggio in paths.
10. **Diario opzionale + hardening**: diario a testo libero, validazioni,
    disclaimer, gestione errori LLM (chiave invalida, timeout, quota), limiti
    tecnici anti-abuso.
11. **Frontend**.

## 16. Decisioni di progetto (chiuse)

- **Nome**: default NutriCoach, cambiabile.
- **Chiave**: una per utente, cifrata a riposo (§6). Nessuna chiave di sistema.
- **Ruolo LLM/motore**: LLM genera percorsi e dialoga, motore verifica i conti
  (§3, §9).
- **Convenzione alimenti**: da crudo (§8).
- **Modello Claude**: l'utente usa la sua chiave; come default suggerito per le
  chiamate claude-haiku-4-5-20251001 (economico, l'utente paga), con possibilità
  di scegliere un modello più potente. Configurabile.
- **Open Food Facts**: no in v1, solo seed CREA.
- **goal default**: feel_good (nessun obiettivo di peso).

## 17. Deploy su server (Hetzner)

Dettaglio in DEPLOY-HETZNER.md. In breve: immagine sul server, .env coi
segreti di sistema (JWT, ENCRYPTION_KEY — **non** la chiave Claude), volume per
SQLite, Caddy davanti per HTTPS sul dominio. Le chiavi Claude le mettono gli
utenti dall'app, e nel db stanno cifrate.
