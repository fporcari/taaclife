"""create core schema (profiles, weight_logs, foods, portions, diary_entries,
preference_items, chat_messages)

Revision ID: 0002_create_core_schema
Revises: 0001_create_users
Create Date: 2026-06-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_core_schema"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEX_VALUES = ("F", "M", "other")
CALC_BASIS_VALUES = ("F", "M")
ACTIVITY_LEVEL_VALUES = ("sedentary", "light", "moderate", "active", "very_active")
GOAL_VALUES = ("maintain", "gentle_loss", "gentle_gain")
MEAL_VALUES = ("breakfast", "lunch", "dinner", "snack")
FOOD_SOURCE_VALUES = ("CREA", "user", "off")
CHAT_ROLE_VALUES = ("user", "assistant")
PREF_KIND_VALUES = ("liked", "avoided")


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    rendered = ",".join(f"'{v}'" for v in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("sex", sa.String(length=8), nullable=True),
        sa.Column("calc_basis", sa.String(length=1), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("activity_level", sa.String(length=16), nullable=True),
        sa.Column("goal", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_profiles_user", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
        sa.CheckConstraint(_in_clause("sex", SEX_VALUES), name="ck_profiles_sex"),
        sa.CheckConstraint(
            _in_clause("calc_basis", CALC_BASIS_VALUES), name="ck_profiles_calc_basis"
        ),
        sa.CheckConstraint(
            _in_clause("activity_level", ACTIVITY_LEVEL_VALUES),
            name="ck_profiles_activity_level",
        ),
        sa.CheckConstraint(_in_clause("goal", GOAL_VALUES), name="ck_profiles_goal"),
        sa.CheckConstraint("height_cm IS NULL OR height_cm > 0", name="ck_profiles_height_pos"),
    )

    op.create_table(
        "weight_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("measured_at", sa.Date(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_weight_logs_user", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "measured_at", name="uq_weight_logs_user_date"),
        sa.CheckConstraint("weight_kg > 0", name="ck_weight_logs_weight_pos"),
    )
    op.create_index("ix_weight_logs_user_id", "weight_logs", ["user_id"])

    op.create_table(
        "foods",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("kcal_100g", sa.Float(), nullable=False),
        sa.Column("protein_100g", sa.Float(), nullable=False),
        sa.Column("carbs_100g", sa.Float(), nullable=False),
        sa.Column("fat_100g", sa.Float(), nullable=False),
        sa.Column("fiber_100g", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_foods_created_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint(_in_clause("source", FOOD_SOURCE_VALUES), name="ck_foods_source"),
        sa.CheckConstraint("kcal_100g >= 0", name="ck_foods_kcal_nonneg"),
        sa.CheckConstraint("protein_100g >= 0", name="ck_foods_protein_nonneg"),
        sa.CheckConstraint("carbs_100g >= 0", name="ck_foods_carbs_nonneg"),
        sa.CheckConstraint("fat_100g >= 0", name="ck_foods_fat_nonneg"),
        sa.CheckConstraint(
            "fiber_100g IS NULL OR fiber_100g >= 0", name="ck_foods_fiber_nonneg"
        ),
    )
    op.create_index("ix_foods_name", "foods", ["name"])
    op.create_index("ix_foods_created_by", "foods", ["created_by"])

    op.create_table(
        "portions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["food_id"], ["foods.id"], name="fk_portions_food", ondelete="CASCADE"
        ),
        sa.CheckConstraint("grams > 0", name="ck_portions_grams_pos"),
    )
    op.create_index("ix_portions_food_id", "portions", ["food_id"])

    op.create_table(
        "diary_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meal", sa.String(length=16), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_diary_entries_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["food_id"], ["foods.id"], name="fk_diary_entries_food", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(_in_clause("meal", MEAL_VALUES), name="ck_diary_entries_meal"),
        sa.CheckConstraint("grams > 0", name="ck_diary_entries_grams_pos"),
    )
    op.create_index("ix_diary_entries_user_id", "diary_entries", ["user_id"])
    op.create_index("ix_diary_entries_food_id", "diary_entries", ["food_id"])
    op.create_index("ix_diary_entries_consumed_at", "diary_entries", ["consumed_at"])

    op.create_table(
        "preference_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_preference_items_user", ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "user_id", "kind", "value", name="uq_preference_items_user_kind_value"
        ),
        sa.CheckConstraint(
            _in_clause("kind", PREF_KIND_VALUES), name="ck_preference_items_kind"
        ),
    )
    op.create_index("ix_preference_items_user_id", "preference_items", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_chat_messages_user", ondelete="CASCADE"
        ),
        sa.CheckConstraint(_in_clause("role", CHAT_ROLE_VALUES), name="ck_chat_messages_role"),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_user_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_preference_items_user_id", table_name="preference_items")
    op.drop_table("preference_items")

    op.drop_index("ix_diary_entries_consumed_at", table_name="diary_entries")
    op.drop_index("ix_diary_entries_food_id", table_name="diary_entries")
    op.drop_index("ix_diary_entries_user_id", table_name="diary_entries")
    op.drop_table("diary_entries")

    op.drop_index("ix_portions_food_id", table_name="portions")
    op.drop_table("portions")

    op.drop_index("ix_foods_created_by", table_name="foods")
    op.drop_index("ix_foods_name", table_name="foods")
    op.drop_table("foods")

    op.drop_index("ix_weight_logs_user_id", table_name="weight_logs")
    op.drop_table("weight_logs")

    op.drop_table("profiles")
