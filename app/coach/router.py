"""Rotte del coach: chat con function calling, history.

Flusso di `/coach/chat`:
1. Salva il messaggio user.
2. Costruisce il contesto iniettato (PROJECT.md §8: contesto + tool insieme).
3. Loop di tool-use (max 5 iter): chiama Claude con i tool definiti in
   `core.coach_tools`; finche' la risposta contiene `tool_use`, esegue i
   tool tramite `ToolRunner` e rilancia coi `tool_result`.
4. Salva la risposta finale (il testo dell'assistente) e ritorna ChatOut.

`add_diary_entry` e' un'azione di scrittura: il `ToolRunner` la gestisce
con un protocollo di "preview + conferma" (vedi `tool_runner.py`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coach.context_builder import build_coach_context
from app.coach.deps import get_coach_client, get_rate_limiter
from app.coach.llm import CoachClient, CoachUnavailableError
from app.coach.rate_limit import SlidingWindowLimiter
from app.coach.tool_runner import ToolError, ToolRunner
from app.deps import get_current_user, get_db
from app.models import ChatMessage, ChatRole, User
from app.schemas.coach import ChatIn, ChatMessageOut, ChatOut
from core.coach import SYSTEM_PROMPT, build_messages
from core.coach_tools import TOOLS

import json

logger = logging.getLogger("nutricoach.coach")

router = APIRouter(prefix="/coach", tags=["coach"])

HISTORY_MAX_LIMIT = 200
HISTORY_DEFAULT_LIMIT = 50

MAX_TOOL_ITERATIONS = 5


def _extract_blocks(message: Any) -> tuple[list[Any], list[Any], str]:
    """Da un messaggio del SDK, separa i blocchi tool_use, tool_result-irrelevant
    e ricava il testo concatenato. Ritorna (tool_use_blocks, all_blocks, text).
    """
    tool_uses: list[Any] = []
    text_chunks: list[str] = []
    all_blocks: list[Any] = []
    for block in getattr(message, "content", []):
        all_blocks.append(block)
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            tool_uses.append(block)
        elif block_type == "text":
            text_chunks.append(getattr(block, "text", "") or "")
    return tool_uses, all_blocks, "".join(text_chunks).strip()


def _serialize_assistant_content(blocks: list[Any]) -> list[dict[str, Any]]:
    """Ricostruisce il content dell'assistant per il messaggio successivo
    nel formato dict atteso dal SDK Anthropic (per i blocchi `tool_use`
    teniamo id/name/input; per i `text` il testo)."""
    out: list[dict[str, Any]] = []
    for block in blocks:
        btype = getattr(block, "type", None)
        if btype == "text":
            out.append({"type": "text", "text": getattr(block, "text", "") or ""})
        elif btype == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id"),
                    "name": getattr(block, "name"),
                    "input": getattr(block, "input", {}) or {},
                }
            )
    return out


def _run_tool_safely(runner: ToolRunner, name: str, tool_input: dict) -> str:
    """Esegue il tool e serializza il risultato in stringa JSON per
    `tool_result.content`. Gli errori "di dominio" diventano payload
    `{error: ...}` ben formati (l'LLM puo' reagire senza crashare la
    chat). Le eccezioni inattese fanno fallire la chat con un 500
    standard.
    """
    try:
        result = runner.run(name, tool_input)
    except ToolError as exc:
        result = {"error": str(exc)}
    return json.dumps(result, ensure_ascii=False, default=str)


@router.post("/chat", response_model=ChatOut)
def chat(
    payload: ChatIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    client: CoachClient = Depends(get_coach_client),
    limiter: SlidingWindowLimiter = Depends(get_rate_limiter),
) -> ChatOut:
    if not limiter.acquire(current_user.id):
        wait = limiter.seconds_until_next_slot(current_user.id)
        minutes = max(1, ceil(wait / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"limite messaggi raggiunto, riprova fra ~{minutes} minuti",
        )

    user_msg = ChatMessage(
        user_id=current_user.id,
        role=ChatRole.USER.value,
        content=payload.message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    today = datetime.now(timezone.utc).date()
    context = build_coach_context(db, current_user, today)
    messages: list[dict[str, Any]] = build_messages(context, payload.message)
    runner = ToolRunner(db=db, user=current_user, today=today)

    final_text = ""
    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            response = client.complete_with_tools(
                system=SYSTEM_PROMPT, messages=messages, tools=TOOLS
            )
            tool_uses, all_blocks, text = _extract_blocks(response)
            stop_reason = getattr(response, "stop_reason", None)

            if stop_reason != "tool_use" or not tool_uses:
                final_text = text
                break

            # Inietta il turno assistant nei messaggi (con i blocchi tool_use)
            # e prepara il tool_result per ogni tool richiesto.
            messages.append(
                {"role": "assistant", "content": _serialize_assistant_content(all_blocks)}
            )
            tool_result_blocks: list[dict[str, Any]] = []
            for tu in tool_uses:
                name = getattr(tu, "name", "")
                tu_id = getattr(tu, "id", "")
                tu_input = getattr(tu, "input", {}) or {}
                logger.info("coach: tool=%s status=running", name)
                result_str = _run_tool_safely(runner, name, tu_input)
                logger.info("coach: tool=%s status=done", name)
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu_id,
                        "content": result_str,
                    }
                )
            messages.append({"role": "user", "content": tool_result_blocks})
        else:
            # Loop finito senza un final_text: errore neutro all'utente.
            raise CoachUnavailableError(
                "coach non disponibile (troppe iterazioni tool)"
            )
    except CoachUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None

    if not final_text:
        final_text = "(nessuna risposta)"

    assistant_msg = ChatMessage(
        user_id=current_user.id,
        role=ChatRole.ASSISTANT.value,
        content=final_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ChatOut(
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        reply=final_text,
        needs_missing=context.needs_missing,
    )


@router.get("/history", response_model=list[ChatMessageOut])
def history(
    limit: int = Query(default=HISTORY_DEFAULT_LIMIT, ge=1, le=HISTORY_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessageOut]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .limit(limit)
        .offset(offset)
    )
    messages = db.execute(stmt).scalars().all()
    return [ChatMessageOut.model_validate(m) for m in messages]
