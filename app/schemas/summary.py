from datetime import date

from pydantic import BaseModel

from core.nutrition import DailyBalance, MacroBreakdown, MacrosPercent, Needs


class MacroBreakdownOut(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float

    @classmethod
    def from_core(cls, mb: MacroBreakdown) -> "MacroBreakdownOut":
        return cls(
            kcal=mb.kcal,
            protein_g=mb.protein_g,
            carbs_g=mb.carbs_g,
            fat_g=mb.fat_g,
            fiber_g=mb.fiber_g,
        )


class MacrosPercentOut(BaseModel):
    protein_pct: float
    carbs_pct: float
    fat_pct: float

    @classmethod
    def from_core(cls, mp: MacrosPercent) -> "MacrosPercentOut":
        return cls(
            protein_pct=mp.protein_pct,
            carbs_pct=mp.carbs_pct,
            fat_pct=mp.fat_pct,
        )


class NeedsOut(BaseModel):
    bmr: float
    tdee: float
    target_kcal: float
    goal_applied: str
    calc_basis_assumed: bool
    activity_assumed: bool

    @classmethod
    def from_core(cls, n: Needs) -> "NeedsOut":
        return cls(
            bmr=n.bmr,
            tdee=n.tdee,
            target_kcal=n.target_kcal,
            goal_applied=n.goal_applied.value,
            calc_basis_assumed=n.calc_basis_assumed,
            activity_assumed=n.activity_assumed,
        )


class DailyBalanceOut(BaseModel):
    date: date
    totals: MacroBreakdownOut
    target_kcal: float
    kcal_difference: float
    macros_percent: MacrosPercentOut

    @classmethod
    def from_core(cls, day: date, bal: DailyBalance) -> "DailyBalanceOut":
        return cls(
            date=day,
            totals=MacroBreakdownOut.from_core(bal.totals),
            target_kcal=bal.target_kcal,
            kcal_difference=bal.kcal_difference,
            macros_percent=MacrosPercentOut.from_core(bal.macros_percent),
        )


class WeekSummaryOut(BaseModel):
    from_date: date
    to_date: date
    needs: NeedsOut
    days: list[DailyBalanceOut]
