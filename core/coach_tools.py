"""Definizioni dei tool esposti al coach (function calling).

Vincolo architetturale (PROJECT.md §8): questo modulo e' PURO.
Niente SDK Anthropic, niente DB, niente FastAPI. Espone solo le
*definizioni* dei tool (schema JSON in formato Anthropic). La
loro *execution* vive in `app/coach/tool_runner.py`, che ha
accesso al DB e al motore.
"""
from __future__ import annotations

TOOL_GET_DAILY_BALANCE = "get_daily_balance"
TOOL_GET_WEEKLY_SUMMARY = "get_weekly_summary"
TOOL_SEARCH_FOOD = "search_food"
TOOL_ADD_DIARY_ENTRY = "add_diary_entry"


TOOLS: list[dict] = [
    {
        "name": TOOL_GET_DAILY_BALANCE,
        "description": (
            "Restituisce il bilancio giornaliero (totali kcal/macro, target, "
            "differenza) per una data specifica. Numeri prodotti dal motore "
            "deterministico dell'app: non ricalcolarli."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Data ISO (YYYY-MM-DD). Default: oggi (UTC).",
                },
            },
            "required": [],
        },
    },
    {
        "name": TOOL_GET_WEEKLY_SUMMARY,
        "description": (
            "Restituisce 7 bilanci giornalieri consecutivi a partire da una "
            "data. Utile per raccontare l'andamento della settimana."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "format": "date",
                    "description": (
                        "Data ISO di partenza. Default: 6 giorni fa, cosi' la "
                        "finestra di 7 giorni include oggi."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": TOOL_SEARCH_FOOD,
        "description": (
            "Cerca alimenti nel database visibili all'utente (pubblici dal "
            "seed CREA + alimenti personali dell'utente). NON inventare "
            "alimenti che non risultano qui."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Sottostringa da cercare nel nome (case-insensitive).",
                },
                "category": {
                    "type": "string",
                    "description": (
                        "Categoria da filtrare (es. 'cereali', 'legumi', "
                        "'pesce'). Opzionale."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Numero massimo di risultati (default 10).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": TOOL_ADD_DIARY_ENTRY,
        "description": (
            "Aggiunge una voce al diario alimentare dell'utente. AZIONE DI "
            "SCRITTURA: va usata SOLO dopo aver chiesto e ottenuto conferma "
            "esplicita dall'utente nel messaggio precedente.\n\n"
            "Protocollo: 1) prima chiamata con `confirmed=false` (o omesso) "
            "-> il tool ritorna una preview senza scrivere; mostra la "
            "preview all'utente e chiedi conferma a parole; "
            "2) solo dopo che l'utente conferma esplicitamente, richiama "
            "il tool con `confirmed=true` per scrivere davvero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "food_id": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "ID dell'alimento (da search_food).",
                },
                "grams": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Quantita' consumata in grammi.",
                },
                "meal": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                    "description": "Pasto in cui registrare la voce.",
                },
                "consumed_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "Timestamp ISO 8601 in UTC. Default: ora.",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": (
                        "DEVE essere true SOLO dopo conferma esplicita "
                        "dell'utente. Se false/assente: preview senza "
                        "scrittura."
                    ),
                },
            },
            "required": ["food_id", "grams", "meal"],
        },
    },
]

TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOLS)
