# Prompt di avvio per Claude Code

Incolla il blocco "Prompt" come primo messaggio in Claude Code, dalla cartella
del repo dove hai messo PROJECT.md e CLAUDE.md. Pensato per auto mode + il
comando /goal: imposti il traguardo di una fase e lo lasci correre, con la
verifica a ogni turno, fino a fase completa e committata.

Serve Claude Code aggiornato (il comando /goal e i dynamic workflows sono
recenti: tieni la CLI all'ultima versione).

---

## Prompt (copia da qui)

Sei l'ingegnere di questo progetto. Prima di tutto leggi CLAUDE.md e PROJECT.md
interamente, poi conferma riassumendo in 5 righe il principio architetturale e i
vincoli duri. Non scrivere codice prima di averlo fatto.

Regole di ingaggio, valide per questa sessione e le successive:

1. **Pianifica prima di costruire.** All'inizio di ogni fase entra in plan mode:
   leggi i file rilevanti (mai affermazioni sul codice senza averlo aperto),
   poi scrivi il piano della fase in tasks/todo.md come voci spuntabili.

2. **Lavora a fasi sequenziali** seguendo l'ordine del §15 di PROJECT.md. Le
   fasi dipendono l'una dall'altra: non saltarle e non parallelizzarle.

3. **I test sono il cancello, non un di più.** A fine fase: scrivi/aggiorna i
   test, eseguili, e non considerare la fase completa finché non sono verdi. Per
   core/nutrition.py i test sono obbligatori e completi. I test che toccano LLM
   o chiave NON devono chiamare davvero l'API: testano cifratura, costruzione
   del contesto, comportamento a chiave assente. Attenzione: "fase completa" =
   test verdi E vincoli duri di CLAUDE.md rispettati. Non far passare i test con
   scorciatoie che violano i vincoli o svuotano il test.

4. **Committa a fine di ogni fase** con messaggio chiaro che cita la fase, e
   aggiorna tasks/todo.md spuntando le voci fatte.

5. **Vincoli duri di CLAUDE.md, sempre, senza eccezioni:** l'LLM propone e
   dialoga ma i numeri si ancorano a database/motore; chiave per-utente cifrata
   a riposo, mai esposta né loggata; alimenti da crudo; tono non giudicante e
   default benessere; ogni rotta scoped sull'utente del token.

6. **Procedi da solo** da una fase alla successiva quando la precedente è
   completa e committata. Fermati a chiedere solo in due casi: un test che non
   riesci a far passare dopo un tentativo serio (senza barare sul test), oppure
   una decisione che PROJECT.md non copre. In quei casi spiega il problema in
   poche righe e proponi un'opzione.

7. **Frontend per ultimo** (Fase 11), solo dopo che il backend è completo,
   testato e containerizzabile.

Modalità di lavoro: userò /goal per farti procedere fase per fase. Quando ti do
un goal, lavoraci fino a raggiungerlo davvero secondo i criteri qui sopra, senza
ridarmi il controllo a metà a ogni turno.

Parti ora: leggi i due file e conferma.

---

## Come guidarlo con /goal (per te, Ghigo — non incollare)

I goal pronti, uno per fase, sono nel file GOALS.md: incollali in ordine. La
formulazione conta: /goal raggiunge alla lettera ciò che scrivi, quindi ogni
goal include la condizione di completamento E chiude con "test verdi +
committata". Esempio (Fase 6, il motore):

`/goal Completa la Fase 6 (motore di calcolo) come da PROJECT.md §9. core/
nutrition.py puro, niente DB/rete/LLM. Mifflin M/F, TDEE, fabbisogno per goal, e
la funzione di verifica di un percorso. Test completi e verdi (Mifflin, TDEE,
verifica percorso con totali noti, edge case). Fase completa quando i test
passano e il commit è fatto.`

## Note d'uso

- **Limiti orari**: con /goal lasciato correre puoi tamponare il rate limit
  orario e vederlo fermarsi a metà. Non è un problema: tasks/todo.md è la
  memoria. Quando la finestra si ricarica, riapri e di' "riprendi dal
  tasks/todo.md, continua dalla prima voce non spuntata".

- **La tua chiave Claude**: in questo progetto la chiave la mettono gli utenti
  dall'app, non sta nel .env. A te serve una chiave vera solo dalla Fase 8 in
  poi per il test manuale end-to-end: registri un utente e la inserisci dall'app.

- **Quando torni**: guarda i commit e tasks/todo.md per capire dove è arrivato.
  Lancia tu pytest una volta, come conferma indipendente.

## Dynamic workflows: due fasi dove conviene davvero

I dynamic workflows (parola "workflow" nel prompt, o /effort ultracode) lanciano
molti subagent in parallelo con verifica e convergenza. NON usarli per costruire
il backend da zero: le fasi sono sequenziali e dipendenti. Servono per lavoro
parallelizzabile su codice che esiste già. Due punti calzano:

1. **Espansione del seed alimenti** (dopo la Fase 5, quando schema e rotte
   /foods esistono):
   `workflow: espandi seed/foods.csv da ~100 a ~400 alimenti italiani comuni,
   valori per 100g da fonte CREA, convenzione da crudo come da CLAUDE.md. Ogni
   gruppo di alimenti a un agente, verifica ogni voce contro lo schema della
   tabella foods e segnala valori anomali. Non duplicare alimenti già presenti.`

2. **Audit finale** (dopo la Fase 10, codice maturo e testato):
   `workflow: audit di sicurezza e qualità del backend. Verifica che nessuna
   rotta si fidi dello user_id del client, che le chiavi Claude degli utenti
   siano sempre cifrate a riposo e mai esposte o loggate, che ogni rotta dati
   sia scoped sull'utente del token, e che i vincoli di CLAUDE.md siano
   rispettati ovunque. Riporta i problemi con gravità, senza modificare il
   codice senza mio ok.`

Per il resto del progetto, auto mode + /goal è la strada giusta.
