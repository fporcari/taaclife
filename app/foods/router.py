from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_user, get_db
from app.models import Food, FoodSource, Portion, User
from app.schemas.foods import FoodCreateIn, FoodOut

router = APIRouter(prefix="/foods", tags=["foods"])

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


@router.get("", response_model=list[FoodOut])
def list_foods(
    q: str | None = Query(default=None, max_length=255),
    category: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FoodOut]:
    """Lista alimenti visibili all'utente del token.

    Visibilita': `is_public=True` OR `created_by=current_user.id`. Gli
    alimenti personali di altri utenti non vengono mai esposti
    (vincolo CLAUDE.md §3).
    """
    stmt = (
        select(Food)
        .options(selectinload(Food.portions))
        .where(or_(Food.is_public.is_(True), Food.created_by == current_user.id))
    )
    if q:
        stmt = stmt.where(Food.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Food.category == category)
    stmt = stmt.order_by(Food.name).limit(limit).offset(offset)

    foods = db.execute(stmt).scalars().all()
    return [FoodOut.model_validate(f) for f in foods]


@router.post("", response_model=FoodOut, status_code=status.HTTP_201_CREATED)
def create_food(
    payload: FoodCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FoodOut:
    """Crea un alimento personale dell'utente del token.

    `source`, `is_public`, `created_by` sono fissati dal server, non dal
    client. Anche se il client li mette nel body vengono ignorati
    (lo schema `FoodCreateIn` non li espone).
    """
    food = Food(
        name=payload.name,
        category=payload.category,
        kcal_100g=payload.kcal_100g,
        protein_100g=payload.protein_100g,
        carbs_100g=payload.carbs_100g,
        fat_100g=payload.fat_100g,
        fiber_100g=payload.fiber_100g,
        source=FoodSource.USER.value,
        is_public=False,
        created_by=current_user.id,
    )
    for portion in payload.portions:
        food.portions.append(Portion(label=portion.label, grams=portion.grams))
    db.add(food)
    db.commit()
    db.refresh(food)
    return FoodOut.model_validate(food)
