"""Test del motore di calcolo (PROJECT.md §7, vincolo duro §2).

Coperti: Mifflin uomo/donna, TDEE per ogni livello, target per ogni goal,
somma diario, edge case, requisito etico §7 (default maintain, niente
deficit aggressivo, niente giudizi), purezza del modulo (no DB/LLM/rete).
"""
from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from app.models import ActivityLevel as AppActivity
from app.models import CalcBasis as AppCalcBasis
from app.models import Goal as AppGoal
from core.nutrition import (
    ACTIVITY_FACTORS,
    GOAL_FACTORS,
    ActivityLevel,
    DailyBalance,
    DiaryItem,
    FoodNutrients,
    Goal,
    MacroBreakdown,
    MacrosPercent,
    Needs,
    Profile,
    ProfileIncompleteError,
    Sex,
    compute_bmr,
    compute_daily_balance,
    compute_item_nutrients,
    compute_needs,
    compute_tdee,
    sum_items,
)


# ---------- Mifflin-St Jeor ----------


def test_mifflin_woman_known_case() -> None:
    # Donna 30 anni, 60 kg, 165 cm:
    # 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
    p = Profile(weight_kg=60, height_cm=165, age_years=30, calc_basis=Sex.F)
    bmr, assumed = compute_bmr(p)
    assert bmr == pytest.approx(1320.25)
    assert assumed is False


def test_mifflin_man_known_case() -> None:
    # Uomo 30 anni, 75 kg, 180 cm:
    # 10*75 + 6.25*180 - 5*30 + 5 = 750 + 1125 - 150 + 5 = 1730
    p = Profile(weight_kg=75, height_cm=180, age_years=30, calc_basis=Sex.M)
    bmr, assumed = compute_bmr(p)
    assert bmr == pytest.approx(1730.0)
    assert assumed is False


def test_mifflin_man_another_case() -> None:
    # Uomo 25 anni, 80 kg, 180 cm:
    # 10*80 + 6.25*180 - 5*25 + 5 = 800 + 1125 - 125 + 5 = 1805
    p = Profile(weight_kg=80, height_cm=180, age_years=25, calc_basis=Sex.M)
    assert compute_bmr(p)[0] == pytest.approx(1805.0)


def test_mifflin_woman_another_case() -> None:
    # Donna 25 anni, 65 kg, 170 cm:
    # 10*65 + 6.25*170 - 5*25 - 161 = 650 + 1062.5 - 125 - 161 = 1426.5
    p = Profile(weight_kg=65, height_cm=170, age_years=25, calc_basis=Sex.F)
    assert compute_bmr(p)[0] == pytest.approx(1426.5)


def test_mifflin_calc_basis_assumed_is_average(  # noqa: D401
) -> None:
    """Se calc_basis e' None: media F/M, flag assumed=True (§14)."""
    p = Profile(weight_kg=70, height_cm=170, age_years=30, calc_basis=None)
    bmr, assumed = compute_bmr(p)
    male = compute_bmr(
        Profile(weight_kg=70, height_cm=170, age_years=30, calc_basis=Sex.M)
    )[0]
    female = compute_bmr(
        Profile(weight_kg=70, height_cm=170, age_years=30, calc_basis=Sex.F)
    )[0]
    assert bmr == pytest.approx((male + female) / 2)
    assert assumed is True


# ---------- TDEE per ogni livello ----------


@pytest.mark.parametrize(
    "level,expected_factor",
    [
        (ActivityLevel.SEDENTARY, 1.2),
        (ActivityLevel.LIGHT, 1.375),
        (ActivityLevel.MODERATE, 1.55),
        (ActivityLevel.ACTIVE, 1.725),
        (ActivityLevel.VERY_ACTIVE, 1.9),
    ],
)
def test_tdee_for_each_activity_level(level: ActivityLevel, expected_factor: float) -> None:
    p = Profile(
        weight_kg=60, height_cm=165, age_years=30,
        calc_basis=Sex.F, activity_level=level,
    )
    bmr = compute_bmr(p)[0]
    tdee, basis_assumed, activity_assumed = compute_tdee(p)
    assert tdee == pytest.approx(bmr * expected_factor)
    assert basis_assumed is False
    assert activity_assumed is False


def test_tdee_activity_assumed_when_missing() -> None:
    p = Profile(
        weight_kg=60, height_cm=165, age_years=30,
        calc_basis=Sex.F, activity_level=None,
    )
    tdee, _, activity_assumed = compute_tdee(p)
    assert activity_assumed is True
    # Sedentary e' il fallback (1.2): valore piu' conservativo.
    assert tdee == pytest.approx(1320.25 * 1.2)


# ---------- Goal e target ----------


def test_goal_maintain_target_equals_tdee() -> None:
    p = Profile(
        weight_kg=60, height_cm=165, age_years=30,
        calc_basis=Sex.F, activity_level=ActivityLevel.MODERATE,
        goal=Goal.MAINTAIN,
    )
    n = compute_needs(p)
    assert n.target_kcal == pytest.approx(n.tdee)
    assert n.goal_applied is Goal.MAINTAIN


def test_goal_gentle_loss_is_minus_15_percent() -> None:
    p = Profile(
        weight_kg=60, height_cm=165, age_years=30,
        calc_basis=Sex.F, activity_level=ActivityLevel.MODERATE,
        goal=Goal.GENTLE_LOSS,
    )
    n = compute_needs(p)
    assert n.target_kcal == pytest.approx(n.tdee * 0.85)


def test_goal_gentle_gain_is_plus_10_percent() -> None:
    p = Profile(
        weight_kg=60, height_cm=165, age_years=30,
        calc_basis=Sex.F, activity_level=ActivityLevel.MODERATE,
        goal=Goal.GENTLE_GAIN,
    )
    n = compute_needs(p)
    assert n.target_kcal == pytest.approx(n.tdee * 1.10)


def test_goal_default_is_maintain_when_missing() -> None:
    """Requisito etico §7: il default e' mantenimento, non perdita."""
    p = Profile(
        weight_kg=60, height_cm=165, age_years=30,
        calc_basis=Sex.F, activity_level=ActivityLevel.MODERATE,
        goal=None,
    )
    n = compute_needs(p)
    assert n.goal_applied is Goal.MAINTAIN
    assert n.target_kcal == pytest.approx(n.tdee)


# ---------- Diario / item nutrients ----------


def _pasta() -> FoodNutrients:
    # Coerente col seed CSV.
    return FoodNutrients(
        kcal_100g=353.0, protein_100g=12.5, carbs_100g=71.2,
        fat_100g=1.4, fiber_100g=2.7,
    )


def _oil() -> FoodNutrients:
    return FoodNutrients(
        kcal_100g=899.0, protein_100g=0.0, carbs_100g=0.0,
        fat_100g=99.9, fiber_100g=None,
    )


def _chicken() -> FoodNutrients:
    return FoodNutrients(
        kcal_100g=100.0, protein_100g=23.3, carbs_100g=0.0,
        fat_100g=0.8, fiber_100g=None,
    )


@pytest.mark.parametrize("grams", [0, 50, 80, 100, 150, 250])
def test_compute_item_nutrients_scales_linearly(grams: int) -> None:
    item = DiaryItem(food=_pasta(), grams=grams)
    out = compute_item_nutrients(item)
    factor = grams / 100.0
    assert out.kcal == pytest.approx(353.0 * factor)
    assert out.protein_g == pytest.approx(12.5 * factor)
    assert out.carbs_g == pytest.approx(71.2 * factor)
    assert out.fat_g == pytest.approx(1.4 * factor)
    assert out.fiber_g == pytest.approx(2.7 * factor)


def test_compute_item_nutrients_rejects_negative_grams() -> None:
    with pytest.raises(ValueError):
        compute_item_nutrients(DiaryItem(food=_pasta(), grams=-10))


def test_sum_items_mix() -> None:
    items = [
        DiaryItem(food=_pasta(), grams=80),     # 282.4 kcal
        DiaryItem(food=_oil(), grams=10),       # 89.9 kcal
        DiaryItem(food=_chicken(), grams=150),  # 150.0 kcal
    ]
    out = sum_items(items)
    assert out.kcal == pytest.approx(282.4 + 89.9 + 150.0)
    assert out.protein_g == pytest.approx(12.5 * 0.8 + 0 + 23.3 * 1.5)
    assert out.carbs_g == pytest.approx(71.2 * 0.8 + 0 + 0)
    assert out.fat_g == pytest.approx(1.4 * 0.8 + 99.9 * 0.1 + 0.8 * 1.5)
    # fiber: pasta ha fiber=2.7, olio e pollo None -> contano 0.
    assert out.fiber_g == pytest.approx(2.7 * 0.8)


def test_sum_items_empty_is_all_zero() -> None:
    out = sum_items([])
    assert out == MacroBreakdown(kcal=0.0, protein_g=0.0, carbs_g=0.0, fat_g=0.0, fiber_g=0.0)


def test_sum_items_with_only_none_fiber_does_not_crash() -> None:
    out = sum_items([
        DiaryItem(food=_oil(), grams=10),
        DiaryItem(food=_chicken(), grams=200),
    ])
    assert out.fiber_g == 0.0


# ---------- DailyBalance ----------


def _needs_2000() -> Needs:
    return Needs(
        bmr=1500.0, tdee=2000.0, target_kcal=2000.0,
        goal_applied=Goal.MAINTAIN,
    )


def test_daily_balance_below_target() -> None:
    bal = compute_daily_balance(
        [DiaryItem(food=_pasta(), grams=100)],  # 353 kcal
        _needs_2000(),
    )
    assert bal.totals.kcal == pytest.approx(353.0)
    assert bal.target_kcal == 2000.0
    assert bal.kcal_difference == pytest.approx(353.0 - 2000.0)
    assert bal.kcal_difference < 0


def test_daily_balance_above_target() -> None:
    huge = FoodNutrients(kcal_100g=500, protein_100g=0, carbs_100g=0, fat_100g=55)
    bal = compute_daily_balance(
        [DiaryItem(food=huge, grams=500)],  # 2500 kcal
        _needs_2000(),
    )
    assert bal.kcal_difference == pytest.approx(500.0)
    assert bal.kcal_difference > 0


def test_daily_balance_equal_to_target() -> None:
    on_target = FoodNutrients(kcal_100g=200, protein_100g=10, carbs_100g=30, fat_100g=5)
    bal = compute_daily_balance(
        [DiaryItem(food=on_target, grams=1000)],
        _needs_2000(),
    )
    assert bal.kcal_difference == pytest.approx(0.0)


def test_daily_balance_macros_percent_known_case() -> None:
    # Solo proteine, 1000 kcal: 250 g di proteine *4 = 1000 kcal -> 100% prot.
    only_prot = FoodNutrients(kcal_100g=400, protein_100g=100, carbs_100g=0, fat_100g=0)
    bal = compute_daily_balance(
        [DiaryItem(food=only_prot, grams=250)],
        _needs_2000(),
    )
    assert bal.macros_percent.protein_pct == pytest.approx(100.0)
    assert bal.macros_percent.carbs_pct == pytest.approx(0.0)
    assert bal.macros_percent.fat_pct == pytest.approx(0.0)


def test_daily_balance_zero_kcal_macros_percent_zero() -> None:
    bal = compute_daily_balance([], _needs_2000())
    assert bal.macros_percent.protein_pct == 0.0
    assert bal.macros_percent.carbs_pct == 0.0
    assert bal.macros_percent.fat_pct == 0.0


# ---------- Edge case profilo incompleto ----------


def test_missing_weight_raises_profile_incomplete() -> None:
    p = Profile(weight_kg=None, height_cm=170, age_years=30, calc_basis=Sex.M)
    with pytest.raises(ProfileIncompleteError) as exc:
        compute_bmr(p)
    assert exc.value.missing == "weight_kg"


def test_missing_height_raises_profile_incomplete() -> None:
    p = Profile(weight_kg=70, height_cm=None, age_years=30, calc_basis=Sex.M)
    with pytest.raises(ProfileIncompleteError) as exc:
        compute_bmr(p)
    assert exc.value.missing == "height_cm"


def test_missing_age_raises_profile_incomplete() -> None:
    p = Profile(weight_kg=70, height_cm=170, age_years=None, calc_basis=Sex.M)
    with pytest.raises(ProfileIncompleteError) as exc:
        compute_bmr(p)
    assert exc.value.missing == "age_years"


def test_compute_needs_propagates_profile_incomplete() -> None:
    p = Profile(weight_kg=None, height_cm=170, age_years=30)
    with pytest.raises(ProfileIncompleteError):
        compute_needs(p)


# ---------- Vincoli architetturali e prodotto ----------


def test_module_is_pure_no_db_no_llm_no_network() -> None:
    """`core/nutrition.py` non deve importare DB, rete o LLM.

    Parsing AST: ispeziona gli `import ...` e `from ... import ...`
    e fallisce se compaiono moduli vietati.
    """
    src = (Path(__file__).resolve().parents[1] / "core" / "nutrition.py").read_text()
    tree = ast.parse(src)

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    forbidden = {
        "sqlalchemy", "alembic",
        "fastapi", "starlette", "pydantic", "pydantic_settings",
        "httpx", "requests", "urllib3",
        "anthropic",
        "app",  # core non deve dipendere dal layer applicativo
    }
    leaks = imported_modules & forbidden
    assert not leaks, f"core/nutrition.py importa moduli vietati: {leaks}"


def test_goal_has_exactly_three_values_no_extreme_loss() -> None:
    """Requisito etico §7: niente deficit aggressivo."""
    assert {g.name for g in Goal} == {"MAINTAIN", "GENTLE_LOSS", "GENTLE_GAIN"}
    # I fattori sono moderati.
    assert GOAL_FACTORS[Goal.GENTLE_LOSS] >= 0.85  # max -15%
    assert GOAL_FACTORS[Goal.GENTLE_GAIN] <= 1.10  # max +10%
    assert GOAL_FACTORS[Goal.MAINTAIN] == 1.0


def test_daily_balance_contains_no_judgment_fields() -> None:
    """`DailyBalance` non deve avere campi che esprimano giudizi.

    Nessun campo stringa di status/label/warning/judgment/etichetta.
    Solo numeri (e dataclass annidate di numeri).
    """
    bad_field_substrings = (
        "status", "label", "judgment", "judg", "warning",
        "good", "bad", "over", "under", "ok",
    )
    for fld in fields(DailyBalance):
        lower = fld.name.lower()
        for sub in bad_field_substrings:
            assert sub not in lower, (
                f"DailyBalance.{fld.name} sembra esprimere un giudizio: vietato §7"
            )


def test_dataclass_field_types_are_numeric_only() -> None:
    """I bilanci non contengono stringhe (niente etichette nascoste)."""
    for cls in (MacroBreakdown, Needs, DailyBalance, MacrosPercent):
        for fld in fields(cls):
            assert fld.type not in ("str", "Optional[str]"), (
                f"{cls.__name__}.{fld.name} ha tipo {fld.type}: niente stringhe nei bilanci"
            )


def test_core_enum_values_match_app_models_enums() -> None:
    """L'adapter delle fasi successive funzionera' senza traduzioni.

    I valori string di Sex/ActivityLevel/Goal in core devono coincidere
    con quelli di app.models (CalcBasis, ActivityLevel, Goal).
    """
    assert {s.value for s in Sex} == {b.value for b in AppCalcBasis}
    assert {a.value for a in ActivityLevel} == {a.value for a in AppActivity}
    assert {g.value for g in Goal} == {g.value for g in AppGoal}


def test_activity_factors_match_project_spec() -> None:
    # Numeri esatti dal §7 di PROJECT.md.
    assert ACTIVITY_FACTORS[ActivityLevel.SEDENTARY] == 1.2
    assert ACTIVITY_FACTORS[ActivityLevel.LIGHT] == 1.375
    assert ACTIVITY_FACTORS[ActivityLevel.MODERATE] == 1.55
    assert ACTIVITY_FACTORS[ActivityLevel.ACTIVE] == 1.725
    assert ACTIVITY_FACTORS[ActivityLevel.VERY_ACTIVE] == 1.9
