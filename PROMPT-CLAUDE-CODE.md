# Prompt di avvio per Claude Code

Incolla il blocco "Prompt" come primo messaggio in Claude Code, dalla cartella
del repo dove hai messo `PROJECT.md` e `CLAUDE.md`. Pensato per auto mode + il
comando `/goal`: imposti il traguardo di una fase e lo lasci correre, con la
verifica a ogni turno, fino a fase completa e committata.

Serve Claude Code aggiornato (il comando `/goal` e i dynamic workflows sono
recenti: tieni la CLI all'ultima versione).

---

## Prompt (copia da qui)

Sei l'ingegnere di questo progetto. Prima di tutto leggi `CLAUDE.md` e
`PROJECT.md` interamente, poi conferma riassumendo in 5 righe il principio
architetturale e i vincoli duri. Non scrivere codice prima di averlo fatto.

Regole di ingaggio, valide per questa sessione e le successive:

1. **Pianifica prima di costruire.** All'inizio di ogni fase entra in plan mode:
   leggi i file rilevanti (mai affermazioni sul codice senza averlo aperto),
   poi scrivi il piano della fase in `tasks/todo.md` come voci spuntabili.

2. **Lavora a fasi sequenziali** seguendo l'ordine del §12 di `PROJECT.md`. Le
   fasi dipendono l'una dall'altra: non saltarle e non parallelizzarle.

3. **I test sono il cancello, non un di più.** A fine fase: scrivi/aggiorna i
   test, eseguili, e non considerare la fase completa finché non sono verdi. Per
   `core/nutrition.py` i test sono obbligatori e completi (Mifflin uomo/donna,
   TDEE per ogni livello, somma diario, edge case). Attenzione: "fase completa"
   non significa solo "test verdi". Significa test verdi **e** codice che
   rispetta i vincoli duri di `CLAUDE.md`. Non far passare i test con
   scorciatoie che violano quei vincoli o che svuotano di senso il test.

4. **Committa a fine di ogni fase** con messaggio chiaro che cita la fase, e
   aggiorna `tasks/todo.md` spuntando le voci fatte.

5. **Vincoli duri di `CLAUDE.md`, sempre, senza eccezioni:** i numeri li fa il
   motore mai l'LLM; la chiave Anthropic mai fuori dal backend; alimenti da
   crudo; tono non giudicante; ogni rotta scoped sull'utente del token.

6. **Procedi da solo** da una fase alla successiva quando la precedente è
   completa e committata. Fermati a chiedere solo in due casi: un test che non
   riesci a far passare dopo un tentativo serio e onesto (senza barare sul
   test), oppure una decisione che `PROJECT.md` non copre. In quei casi spiega
   il problema in poche righe e proponi un'opzione.

7. **Fase 0 (`build.sh`) e frontend per ultimi**, solo dopo che il backend è
   completo, testato e containerizzabile (§15 e §11).

Modalità di lavoro: userò `/goal` per farti procedere fase per fase. Quando ti
do un goal, lavoraci fino a raggiungerlo davvero secondo i criteri qui sopra,
senza ridarmi il controllo a metà a ogni turno.

Parti ora: leggi i due file e conferma.

---

## Come guidarlo con /goal (per te, Ghigo — non incollare)

Dopo che ha confermato la lettura, dai un goal per fase. La formulazione del
goal è tutto: `/goal` raggiunge alla lettera ciò che scrivi, quindi la
condizione di completamento deve includere i test E i vincoli, non solo "che
funzioni". Esempi pronti:

- `/goal Completa la Fase 1 (scaffold): FastAPI avviabile, Dockerfile, SQLite su
  volume con WAL, Alembic inizializzato, pytest che gira a vuoto. Fase completa
  quando pytest passa e tutto è committato.`

- `/goal Completa la Fase 5 (motore di calcolo) come da PROJECT.md §7. core/
  nutrition.py puro, senza DB/rete/LLM. Test completi e verdi: Mifflin uomo e
  donna su casi noti, TDEE per ogni livello attività, somma diario, edge case
  profilo incompleto. Fase completa quando i test passano e il commit è fatto.`

Regola pratica per ogni goal: nomina la fase, cita il paragrafo di PROJECT.md,
elenca la condizione di completamento, e chiudi sempre con "test verdi +
committata". Così il verificatore ha un metro vero.

## Note d'uso

- **Limiti orari**: con `/goal` lasciato correre puoi tamponare il rate limit
  orario e vederlo fermarsi a metà. Non è un problema: il `tasks/todo.md` è la
  memoria. Quando la finestra si ricarica, riapri e di' "riprendi dal
  tasks/todo.md, continua dalla prima voce non spuntata". Riparte da lì.

- **La tua API key**: serve solo dalla Fase 8 (chat coach) per testarla davvero,
  e poi al deploy. Fino a lì non metterla.

- **Quando torni**: guarda i commit e `tasks/todo.md` per capire dove è
  arrivato. Lancia tu `pytest` una volta, come conferma indipendente dal suo
  giudizio.

## Dynamic workflows: due fasi dove conviene davvero

I dynamic workflows (parola "workflow" nel prompt, o `/effort ultracode`)
lanciano molti subagent in parallelo con verifica e convergenza. NON usarli per
costruire il backend da zero: le fasi sono sequenziali e dipendenti, lì il
parallelo non aiuta. Servono per lavoro parallelizzabile su codice che esiste
già. Due punti del progetto sono fatti apposta:

1. **Espansione del seed alimenti** (dopo la Fase 4, quando schema e rotte
   /foods esistono):
   `workflow: espandi seed/foods.csv da ~100 a ~400 alimenti italiani comuni,
   valori per 100g da fonte CREA, convenzione da crudo come da CLAUDE.md. Ogni
   gruppo di alimenti a un agente, verifica ogni voce contro lo schema della
   tabella foods e segnala valori anomali. Non duplicare alimenti già presenti.`

2. **Audit finale** (dopo la Fase 10, codice maturo e testato):
   `workflow: audit di sicurezza e qualità del backend. Verifica che nessuna
   rotta si fidi dello user_id del client, che la API key non sia mai esposta o
   loggata, che ogni rotta dati sia scoped sull'utente del token, e che i
   vincoli di CLAUDE.md siano rispettati ovunque. Riporta i problemi con
   gravità, senza modificare il codice senza mio ok.`

Per il resto del progetto, auto mode + `/goal` è la strada giusta.
