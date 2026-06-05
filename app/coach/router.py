from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coach.context_builder import build_coach_context
from app.coach.deps import get_coach_client, get_rate_limiter
from app.coach.llm import CoachClient, CoachUnavailableError
from app.coach.rate_limit import SlidingWindowLimiter
from app.deps import get_current_user, get_db
from app.models import ChatMessage, ChatRole, User
from app.schemas.coach import ChatIn, ChatMessageOut, ChatOut
from core.coach import SYSTEM_PROMPT, build_messages

router = APIRouter(prefix="/coach", tags=["coach"])

HISTORY_MAX_LIMIT = 200
HISTORY_DEFAULT_LIMIT = 50


@router.post("/chat", response_model=ChatOut)
def chat(
    payload: ChatIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # Ordine: il client prima del limiter. Se manca la chiave o il
    # client e' indisponibile, la dependency alza 503 prima di consumare
    # uno slot di rate limit.
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
    messages = build_messages(context, payload.message)

    try:
        reply = client.complete(system=SYSTEM_PROMPT, messages=messages)
    except CoachUnavailableError as exc:
        # Non leak della chiave: il messaggio dell'eccezione e' gia' neutro.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None

    assistant_msg = ChatMessage(
        user_id=current_user.id,
        role=ChatRole.ASSISTANT.value,
        content=reply,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ChatOut(
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        reply=reply,
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
