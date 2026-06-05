"""Motore di calcolo nutrizionale (puro, deterministico).

Regole architetturali (PROJECT.md §2/§7, CLAUDE.md):

- Niente DB, niente rete, niente LLM in questo modulo. Solo standard
  library. L'adapter "modelli SQLAlchemy -> dataclass core" vive
  altrove (es. nelle rotte di summary/diary).
- Tutti i numeri (kcal, macro, BMR, TDEE, target, bilanci) escono da
  qui. L'LLM li riceve gia' calcolati; non li ricalcola, non li
  inventa.
- Se manca un dato necessario, alziamo `ProfileIncompleteError`. Non
  ritorniamo mai un numero finto.
- Default `Goal.MAINTAIN`. Niente deficit aggressivo: `GENTLE_LOSS`
  e' fissato a -15% (limite del range "10-15%") e `GENTLE_GAIN` a
  +10%. Nessun parametro libero.
- Nessun "giudizio" nel dato grezzo: `DailyBalance` ha numeri e
  differenza grezza (segnata). Niente status "over"/"under"/"warning".
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterable, Sequence


class Sex(str, enum.Enum):
    """Sesso biologico usato dalla formula Mifflin-St Jeor.

    Corrisponde al `calc_basis` del profilo (§14 di PROJECT.md):
    identita' di genere e parametro di calcolo sono distinti.
    """

    F = "F"
    M = "M"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class Goal(str, enum.Enum):
    MAINTAIN = "maintain"
    GENTLE_LOSS = "gentle_loss"
    GENTLE_GAIN = "gentle_gain"


ACTIVITY_FACTORS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}


GOAL_FACTORS: dict[Goal, float] = {
    Goal.MAINTAIN: 1.00,
    Goal.GENTLE_LOSS: 0.85,
    Goal.GENTLE_GAIN: 1.10,
}


class ProfileIncompleteError(ValueError):
    """Alzata quando i dati del profilo non bastano per calcolare il
    fabbisogno. Mai sostituire un dato mancante con un numero finto."""

    def __init__(self, missing: str) -> None:
        super().__init__(f"dato mancante per il calcolo: {missing}")
        self.missing = missing


@dataclass(frozen=True)
class Profile:
    """Profilo per il calcolo del fabbisogno.

    `calc_basis` puo' essere None: in quel caso il BMR viene calcolato
    come media tra la formula maschile e quella femminile, e Needs
    riporta `calc_basis_assumed=True` (vedi §14).
    `activity_level` puo' essere None: fallback `SEDENTARY` con
    `activity_assumed=True`.
    `goal` puo' essere None: default `MAINTAIN` (requisito etico §7).
    """

    weight_kg: float | None
    height_cm: float | None
    age_years: int | None
    calc_basis: Sex | None = None
    activity_level: ActivityLevel | None = None
    goal: Goal | None = None


@dataclass(frozen=True)
class FoodNutrients:
    """Composizione di un alimento per 100 g (da crudo / peso secco)."""

    kcal_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    fiber_100g: float | None = None


@dataclass(frozen=True)
class DiaryItem:
    """Una voce del diario nella forma minima per il calcolo."""

    food: FoodNutrients
    grams: float


@dataclass(frozen=True)
class MacroBreakdown:
    """Totali calorici e macronutrienti.

    `fiber_g` somma solo i contributi disponibili (food con
    `fiber_100g=None` contribuiscono 0). E' una scelta documentata: il
    valore e' una stima inferiore, non un'invenzione.
    """

    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float


@dataclass(frozen=True)
class Needs:
    """Fabbisogno energetico per un profilo."""

    bmr: float
    tdee: float
    target_kcal: float
    goal_applied: Goal
    calc_basis_assumed: bool = False
    activity_assumed: bool = False


@dataclass(frozen=True)
class DailyBalance:
    """Bilancio giornaliero: totali assunti vs target.

    `kcal_difference = totals.kcal - target_kcal`. Segnata: positiva =
    sopra il target, negativa = sotto. NESSUN campo di giudizio:
    e' un fatto numerico, non un voto.
    """

    totals: MacroBreakdown
    target_kcal: float
    kcal_difference: float
    macros_percent: "MacrosPercent"


@dataclass(frozen=True)
class MacrosPercent:
    """Ripartizione percentuale dei macro sull'energia totale assunta.

    Convenzione: proteine 4 kcal/g, carboidrati 4 kcal/g, grassi 9 kcal/g.
    Se le kcal totali sono 0, tutte le percentuali sono 0.
    """

    protein_pct: float
    carbs_pct: float
    fat_pct: float


# ---------- Calcoli ----------


def _require(value: float | int | None, name: str) -> float:
    if value is None:
        raise ProfileIncompleteError(name)
    return float(value)


def _mifflin_bmr(sex: Sex, weight_kg: float, height_cm: float, age_years: float) -> float:
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age_years
    if sex is Sex.M:
        return base + 5.0
    return base - 161.0


def compute_bmr(profile: Profile) -> tuple[float, bool]:
    """Ritorna `(bmr, calc_basis_assumed)`.

    Se `calc_basis` e' None, BMR e' la media delle due formule e il
    flag `calc_basis_assumed` e' True (vedi §14).
    """
    weight = _require(profile.weight_kg, "weight_kg")
    height = _require(profile.height_cm, "height_cm")
    age = _require(profile.age_years, "age_years")

    if profile.calc_basis is None:
        male = _mifflin_bmr(Sex.M, weight, height, age)
        female = _mifflin_bmr(Sex.F, weight, height, age)
        return (male + female) / 2.0, True

    return _mifflin_bmr(profile.calc_basis, weight, height, age), False


def compute_tdee(profile: Profile) -> tuple[float, bool, bool]:
    """Ritorna `(tdee, calc_basis_assumed, activity_assumed)`."""
    bmr, basis_assumed = compute_bmr(profile)
    level = profile.activity_level
    activity_assumed = False
    if level is None:
        level = ActivityLevel.SEDENTARY
        activity_assumed = True
    return bmr * ACTIVITY_FACTORS[level], basis_assumed, activity_assumed


def compute_needs(profile: Profile) -> Needs:
    """Calcola fabbisogno + target kcal in base al goal del profilo.

    Goal default: `MAINTAIN` (requisito etico §7 — il deficit non e'
    il default).
    """
    bmr, basis_assumed = compute_bmr(profile)
    level = profile.activity_level
    activity_assumed = False
    if level is None:
        level = ActivityLevel.SEDENTARY
        activity_assumed = True
    tdee = bmr * ACTIVITY_FACTORS[level]

    goal = profile.goal if profile.goal is not None else Goal.MAINTAIN
    target_kcal = tdee * GOAL_FACTORS[goal]

    return Needs(
        bmr=bmr,
        tdee=tdee,
        target_kcal=target_kcal,
        goal_applied=goal,
        calc_basis_assumed=basis_assumed,
        activity_assumed=activity_assumed,
    )


def compute_item_nutrients(item: DiaryItem) -> MacroBreakdown:
    """kcal e macro per una voce di diario = food * grams / 100."""
    if item.grams < 0:
        raise ValueError(f"grams non puo' essere negativo: {item.grams}")
    factor = item.grams / 100.0
    fiber_100 = item.food.fiber_100g if item.food.fiber_100g is not None else 0.0
    return MacroBreakdown(
        kcal=item.food.kcal_100g * factor,
        protein_g=item.food.protein_100g * factor,
        carbs_g=item.food.carbs_100g * factor,
        fat_g=item.food.fat_100g * factor,
        fiber_g=fiber_100 * factor,
    )


def sum_items(items: Iterable[DiaryItem]) -> MacroBreakdown:
    """Somma le voci. Lista vuota -> totali a zero (non e' un errore)."""
    kcal = protein = carbs = fat = fiber = 0.0
    for item in items:
        contribution = compute_item_nutrients(item)
        kcal += contribution.kcal
        protein += contribution.protein_g
        carbs += contribution.carbs_g
        fat += contribution.fat_g
        fiber += contribution.fiber_g
    return MacroBreakdown(
        kcal=kcal,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        fiber_g=fiber,
    )


def _macros_percent(totals: MacroBreakdown) -> MacrosPercent:
    if totals.kcal <= 0:
        return MacrosPercent(protein_pct=0.0, carbs_pct=0.0, fat_pct=0.0)
    return MacrosPercent(
        protein_pct=(totals.protein_g * 4.0) / totals.kcal * 100.0,
        carbs_pct=(totals.carbs_g * 4.0) / totals.kcal * 100.0,
        fat_pct=(totals.fat_g * 9.0) / totals.kcal * 100.0,
    )


def compute_daily_balance(items: Sequence[DiaryItem], needs: Needs) -> DailyBalance:
    """Bilancio giornaliero: totali assunti vs target.

    Niente "verdetti" nel risultato: solo numeri e una differenza
    segnata. L'eventuale tono di supporto e' a carico del layer LLM,
    su queste basi numeriche.
    """
    totals = sum_items(items)
    return DailyBalance(
        totals=totals,
        target_kcal=needs.target_kcal,
        kcal_difference=totals.kcal - needs.target_kcal,
        macros_percent=_macros_percent(totals),
    )
