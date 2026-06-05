"""Layer LLM puro: contesto + system prompt del contratto §8.

Vincoli architetturali (PROJECT.md §8, CLAUDE.md):

- Niente DB, niente rete, niente SDK Anthropic in questo modulo: solo
  stdlib + dataclass. La costruzione del contesto da DB e la chiamata
  al SDK vivono in `app/coach/`.
- Il `SYSTEM_PROMPT` e' il "contratto" §8: vieta esplicitamente di
  calcolare o stimare numeri, impone tono non giudicante, ricorda che
  l'assistente non sostituisce un medico.
- Pattern di prompting: system statico (cache-friendly) + primo
  messaggio "user" con `<context>` JSON dei dati reali + storico
  della conversazione troncato.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Sequence


SYSTEM_PROMPT = """\
Sei un assistente di supporto sull'alimentazione per un'app di diario
nutrizionale. NON sei un medico, NON sei un nutrizionista, NON sostituisci un
professionista qualificato: dichiaralo apertamente se l'utente chiede consigli
clinici, e in caso di dubbi seri rimandalo a un professionista.

Regole non negoziabili:

1) NON calcolare e NON stimare numeri. Le calorie, i macronutrienti, il
   fabbisogno (BMR/TDEE/target), il bilancio giornaliero e settimanale e i
   totali sono GIA' presenti nel blocco <context> come dati gia' calcolati
   dal motore deterministico dell'app. Riprendi quei valori cosi' come sono.
   Se un dato non c'e' nel contesto, di' esplicitamente "non ho questo dato"
   — non inventarlo, non dedurlo, non approssimarlo.

2) Tono non giudicante. Niente cibi "buoni" o "cattivi", niente colpa, niente
   celebrazione del deficit calorico, niente shaming. L'obiettivo dell'app
   e' aiutare la persona a sentirsi bene, non a dimagrire a tutti i costi.
   Il default e' il mantenimento. Se la differenza calorica del giorno e'
   positiva o negativa, raccontala come fatto neutro, non come voto.

3) Sii concreto sui cibi: proponi solo tra le preferenze "graditi" dell'utente
   e/o gli alimenti disponibili nel database (quelli citati nel contesto).
   NON inventare piatti di cui non hai composizione: se ne suggerisci uno
   nuovo, di' chiaramente che le calorie/macro non sono note finche' non lo
   si aggiunge al database.

4) Niente linguaggio diagnostico o prescrittivo. Non dire "hai una carenza
   di...", non dire "devi mangiare X". Usa formulazioni di supporto.

5) Rispondi in italiano, in modo asciutto e umano. Niente liste lunghe se
   non servono. Se l'utente fa una domanda generica, rispondi brevemente e
   chiedi cosa gli interessa davvero.

6) Tool disponibili (function calling). Usali quando servono:
   - `get_daily_balance(date)` per il bilancio di un giorno specifico;
   - `get_weekly_summary(from_date?)` per i 7 giorni;
   - `search_food(query, category?, limit?)` per cercare un alimento prima di
     consigliarlo o di aggiungerlo al diario;
   - `add_diary_entry(food_id, grams, meal, confirmed?)` per registrare una
     voce nel diario.
   Il blocco `<context>` in testa ha gia' un riassunto: usa i tool quando
   serve un dato specifico che li' non c'e' (un giorno diverso da oggi, un
   alimento da cercare per id, ecc.). Non duplicare richieste se l'informazione
   e' gia' nel contesto.

7) PROTOCOLLO DI CONFERMA per le azioni di scrittura.
   `add_diary_entry` modifica i dati dell'utente. Devi:
   a) chiamarla PRIMA con `confirmed=false` (o omesso): il tool ritorna una
      *preview* (kcal/macro che si registrerebbero) senza scrivere nulla;
   b) mostrare la preview all'utente in linguaggio naturale e chiedere
      conferma esplicita ("aggiungo questa voce? si'/no");
   c) richiamare il tool con `confirmed=true` SOLO dopo un consenso chiaro
      dell'utente nel messaggio successivo.
   Non scrivere mai senza questo doppio passo. In caso di ambiguita',
   chiedi.
"""


@dataclass(frozen=True)
class ProfileSummary:
    age_years: int | None
    sex_identity: str | None       # F/M/other (identita')
    calc_basis: str | None         # F/M (Mifflin)
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    goal: str                      # default "maintain"


@dataclass(frozen=True)
class NeedsSummary:
    bmr: float
    tdee: float
    target_kcal: float
    goal_applied: str
    calc_basis_assumed: bool
    activity_assumed: bool


@dataclass(frozen=True)
class MacroSummary:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float


@dataclass(frozen=True)
class DailyBalanceSummary:
    date: date
    totals: MacroSummary
    target_kcal: float
    kcal_difference: float
    protein_pct: float
    carbs_pct: float
    fat_pct: float


@dataclass(frozen=True)
class DiaryItemSummary:
    consumed_at: str   # ISO 8601, gia' formattato
    meal: str
    food_name: str
    grams: float


@dataclass(frozen=True)
class PreferencesSummary:
    liked: tuple[str, ...]
    avoided: tuple[str, ...]


@dataclass(frozen=True)
class HistoryMessage:
    role: str          # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class CoachContext:
    """Tutto quello che la chat sa dell'utente al momento del messaggio."""

    today: date
    profile: ProfileSummary
    needs: NeedsSummary | None
    needs_missing: str | None        # se needs e' None, il campo mancante
    today_balance: DailyBalanceSummary | None
    week_balances: tuple[DailyBalanceSummary, ...] = ()
    recent_diary: tuple[DiaryItemSummary, ...] = ()
    preferences: PreferencesSummary = field(
        default_factory=lambda: PreferencesSummary(liked=(), avoided=())
    )
    history: tuple[HistoryMessage, ...] = ()


# ---------- Serializzazione del contesto per il prompt ----------


def _json_default(obj):
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {type(obj)!r}")


def build_context_payload(context: CoachContext) -> str:
    """Serializza il contesto in un blocco JSON dentro `<context>...</context>`
    da iniettare come primo messaggio user prima dei messaggi reali.

    L'LLM e' istruito (system prompt) a leggere i numeri da qui senza
    ricalcolarli.
    """
    payload = {
        "today": context.today,
        "profile": asdict(context.profile),
        "needs": asdict(context.needs) if context.needs else None,
        "needs_missing": context.needs_missing,
        "today_balance": (
            asdict(context.today_balance) if context.today_balance else None
        ),
        "week_balances": [asdict(b) for b in context.week_balances],
        "recent_diary": [asdict(it) for it in context.recent_diary],
        "preferences": asdict(context.preferences),
    }
    body = json.dumps(payload, ensure_ascii=False, default=_json_default, indent=2)
    return f"<context>\n{body}\n</context>"


def truncate_history(
    messages: Sequence[HistoryMessage], max_messages: int
) -> tuple[HistoryMessage, ...]:
    """Mantiene solo gli ultimi `max_messages` messaggi (in ordine
    cronologico). Una finestra ragionevole evita di gonfiare i token.
    """
    if max_messages <= 0:
        return ()
    return tuple(messages[-max_messages:])


def build_messages(
    context: CoachContext, user_message: str
) -> list[dict[str, str]]:
    """Costruisce la lista di messaggi `[{role, content}]` per l'API
    Anthropic, **senza chiamare nulla**: e' una funzione pura.

    Ordine: primo "user" col blocco di contesto, poi lo storico tronco,
    poi il messaggio utente corrente.
    """
    messages: list[dict[str, str]] = [
        {"role": "user", "content": build_context_payload(context)},
        {
            "role": "assistant",
            "content": (
                "Ricevuto. Ho letto il contesto e non calcolero' numeri da "
                "solo: usero' i valori gia' presenti."
            ),
        },
    ]
    for m in context.history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})
    return messages
