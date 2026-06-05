"""Script di seed del database alimenti.

Convenzione: tutti i valori in `seed/foods.csv` sono per 100 g di alimento
CRUDO / a peso secco. Sbagliare questa convenzione raddoppia i totali del
diario (PROJECT.md §6 e §14, CLAUDE.md regola 4).

Esecuzione manuale: `python -m app.seed`.
Idempotente: se la tabella `foods` non e' vuota, non fa nulla.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Food, FoodSource, Portion

logger = logging.getLogger("nutricoach.seed")

SEED_CSV_PATH = Path(__file__).resolve().parents[1] / "seed" / "foods.csv"

EXPECTED_HEADER = [
    "name",
    "category",
    "kcal_100g",
    "protein_100g",
    "carbs_100g",
    "fat_100g",
    "fiber_100g",
    "portions",
]


@dataclass(frozen=True)
class SeedPortion:
    label: str
    grams: float


@dataclass(frozen=True)
class SeedFood:
    name: str
    category: str | None
    kcal_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    fiber_100g: float | None
    portions: tuple[SeedPortion, ...]


def _parse_optional_float(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    return float(raw)


def _parse_portions(raw: str) -> tuple[SeedPortion, ...]:
    raw = raw.strip()
    if not raw:
        return ()
    items: list[SeedPortion] = []
    for chunk in raw.split("|"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"porzione malformata (manca ':'): {chunk!r}")
        label, grams = chunk.rsplit(":", 1)
        items.append(SeedPortion(label=label.strip(), grams=float(grams.strip())))
    return tuple(items)


def load_foods_from_csv(path: Path = SEED_CSV_PATH) -> list[SeedFood]:
    foods: list[SeedFood] = []
    with path.open(encoding="utf-8") as fp:
        lines = (line for line in fp if not line.lstrip().startswith("#"))
        reader = csv.reader(lines)
        header = next(reader)
        if header != EXPECTED_HEADER:
            raise ValueError(
                f"CSV header inatteso: {header} (atteso {EXPECTED_HEADER})"
            )
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            if len(row) != len(EXPECTED_HEADER):
                raise ValueError(f"riga malformata: {row!r}")
            name, category, kcal, prot, carb, fat, fiber, portions = row
            food = SeedFood(
                name=name.strip(),
                category=category.strip() or None,
                kcal_100g=float(kcal),
                protein_100g=float(prot),
                carbs_100g=float(carb),
                fat_100g=float(fat),
                fiber_100g=_parse_optional_float(fiber),
                portions=_parse_portions(portions),
            )
            _sanity_check(food)
            foods.append(food)
    return foods


def _sanity_check(food: SeedFood) -> None:
    if not food.name:
        raise ValueError("nome alimento vuoto")
    for field in ("kcal_100g", "protein_100g", "carbs_100g", "fat_100g"):
        value = getattr(food, field)
        if value < 0:
            raise ValueError(f"{food.name}: {field}={value} negativo")
    if food.fiber_100g is not None and food.fiber_100g < 0:
        raise ValueError(f"{food.name}: fiber_100g negativo")
    for portion in food.portions:
        if portion.grams <= 0:
            raise ValueError(f"{food.name}: porzione {portion.label!r} grams<=0")


def seed_foods(db: Session, csv_path: Path = SEED_CSV_PATH) -> int:
    """Popola foods+portions dal CSV, se foods e' vuoto.

    Ritorna il numero di alimenti inseriti (0 se gia' popolato).
    """
    existing = db.execute(select(Food.id).limit(1)).first()
    if existing is not None:
        logger.info("foods gia' popolato, skip seed")
        return 0

    seed_data = load_foods_from_csv(csv_path)
    inserted = 0
    for sf in seed_data:
        food = Food(
            name=sf.name,
            category=sf.category,
            kcal_100g=sf.kcal_100g,
            protein_100g=sf.protein_100g,
            carbs_100g=sf.carbs_100g,
            fat_100g=sf.fat_100g,
            fiber_100g=sf.fiber_100g,
            source=FoodSource.CREA.value,
            is_public=True,
            created_by=None,
        )
        for sp in sf.portions:
            food.portions.append(Portion(label=sp.label, grams=sp.grams))
        db.add(food)
        inserted += 1
    db.commit()
    logger.info("seed completato: %d alimenti inseriti", inserted)
    return inserted


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SessionLocal() as db:
        count = seed_foods(db)
    print(f"seed: inseriti {count} alimenti (0 = gia' popolato)")


if __name__ == "__main__":
    main()
