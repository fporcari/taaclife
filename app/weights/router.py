from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User, WeightLog
from app.schemas.weights import WeightLogIn, WeightLogOut

router = APIRouter(prefix="/weights", tags=["weights"])

MAX_LIMIT = 365


@router.post("", response_model=WeightLogOut, status_code=status.HTTP_201_CREATED)
def upsert_weight(
    payload: WeightLogIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeightLogOut:
    """Registra il peso. Upsert per `(user_id, measured_at)`:
    pesarsi due volte lo stesso giorno sovrascrive il valore."""
    measured_at = payload.measured_at or datetime.now(timezone.utc).date()

    existing = db.execute(
        select(WeightLog).where(
            WeightLog.user_id == current_user.id,
            WeightLog.measured_at == measured_at,
        )
    ).scalar_one_or_none()

    if existing is None:
        log = WeightLog(
            user_id=current_user.id,
            measured_at=measured_at,
            weight_kg=payload.weight_kg,
        )
        db.add(log)
    else:
        existing.weight_kg = payload.weight_kg
        log = existing

    db.commit()
    db.refresh(log)
    return WeightLogOut.model_validate(log)


@router.get("", response_model=list[WeightLogOut])
def list_weights(
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WeightLogOut]:
    stmt = (
        select(WeightLog)
        .where(WeightLog.user_id == current_user.id)
        .order_by(WeightLog.measured_at.desc(), WeightLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = db.execute(stmt).scalars().all()
    return [WeightLogOut.model_validate(log) for log in logs]
