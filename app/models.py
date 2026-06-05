import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Enum (stringhe; CHECK constraint sui campi che li usano) ----------


class Sex(str, enum.Enum):
    F = "F"
    M = "M"
    OTHER = "other"


class CalcBasis(str, enum.Enum):
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


class Meal(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class FoodSource(str, enum.Enum):
    CREA = "CREA"
    USER = "user"
    OFF = "off"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class PrefKind(str, enum.Enum):
    LIKED = "liked"
    AVOIDED = "avoided"


def _enum_check(column: str, members: type[enum.Enum], name: str) -> CheckConstraint:
    values = ",".join(f"'{m.value}'" for m in members)
    return CheckConstraint(f"{column} IN ({values})", name=name)


# ---------- Tabelle ----------


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    weight_logs: Mapped[list["WeightLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    diary_entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preference_items: Mapped[list["PreferenceItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        _enum_check("sex", Sex, "ck_profiles_sex"),
        _enum_check("calc_basis", CalcBasis, "ck_profiles_calc_basis"),
        _enum_check("activity_level", ActivityLevel, "ck_profiles_activity_level"),
        _enum_check("goal", Goal, "ck_profiles_goal"),
        CheckConstraint("height_cm IS NULL OR height_cm > 0", name="ck_profiles_height_pos"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    calc_basis: Mapped[str | None] = mapped_column(String(1), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    goal: Mapped[str] = mapped_column(String(16), nullable=False, default=Goal.MAINTAIN.value)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="profile")


class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="ck_weight_logs_weight_pos"),
        UniqueConstraint("user_id", "measured_at", name="uq_weight_logs_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    measured_at: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)

    user: Mapped[User] = relationship(back_populates="weight_logs")


class Food(Base):
    __tablename__ = "foods"
    __table_args__ = (
        _enum_check("source", FoodSource, "ck_foods_source"),
        CheckConstraint("kcal_100g >= 0", name="ck_foods_kcal_nonneg"),
        CheckConstraint("protein_100g >= 0", name="ck_foods_protein_nonneg"),
        CheckConstraint("carbs_100g >= 0", name="ck_foods_carbs_nonneg"),
        CheckConstraint("fat_100g >= 0", name="ck_foods_fat_nonneg"),
        CheckConstraint(
            "fiber_100g IS NULL OR fiber_100g >= 0", name="ck_foods_fiber_nonneg"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Tutti i valori sono per 100 g di alimento CRUDO / peso secco (vincolo §14).
    kcal_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_100g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_100g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_100g: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    is_public: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    portions: Mapped[list["Portion"]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )


class Portion(Base):
    __tablename__ = "portions"
    __table_args__ = (
        CheckConstraint("grams > 0", name="ck_portions_grams_pos"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    food_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    grams: Mapped[float] = mapped_column(Float, nullable=False)

    food: Mapped[Food] = relationship(back_populates="portions")


class DiaryEntry(Base):
    """Voce del diario alimentare.

    Nota: niente kcal/macro qui. I numeri si calcolano da food+grams via
    `core/nutrition.py` (vincolo duro PROJECT.md §2/§5).
    """

    __tablename__ = "diary_entries"
    __table_args__ = (
        _enum_check("meal", Meal, "ck_diary_entries_meal"),
        CheckConstraint("grams > 0", name="ck_diary_entries_grams_pos"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    meal: Mapped[str] = mapped_column(String(16), nullable=False)
    food_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("foods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    grams: Mapped[float] = mapped_column(Float, nullable=False)

    user: Mapped[User] = relationship(back_populates="diary_entries")
    food: Mapped[Food] = relationship()


class PreferenceItem(Base):
    __tablename__ = "preference_items"
    __table_args__ = (
        _enum_check("kind", PrefKind, "ck_preference_items_kind"),
        UniqueConstraint("user_id", "kind", "value", name="uq_preference_items_user_kind_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)

    user: Mapped[User] = relationship(back_populates="preference_items")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        _enum_check("role", ChatRole, "ck_chat_messages_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    user: Mapped[User] = relationship(back_populates="chat_messages")
