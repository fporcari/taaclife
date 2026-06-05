from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Food, FoodSource, Portion
from app.seed import load_foods_from_csv, seed_foods


def test_csv_loads_and_validates() -> None:
    foods = load_foods_from_csv()
    assert len(foods) >= 80  # PROJECT.md §6: ~80-120
    # Tutti devono avere almeno una porzione e numeri non negativi.
    for f in foods:
        assert f.name
        assert f.kcal_100g >= 0
        assert f.protein_100g >= 0
        assert f.carbs_100g >= 0
        assert f.fat_100g >= 0
        assert f.fiber_100g is None or f.fiber_100g >= 0
        assert f.portions, f"{f.name}: nessuna porzione"


def test_seed_populates_empty_db(db_session: Session) -> None:
    assert db_session.query(Food).count() == 0
    inserted = seed_foods(db_session)
    assert inserted > 0
    assert db_session.query(Food).count() == inserted
    # Le porzioni sono state inserite collegate ai foods.
    assert db_session.query(Portion).count() > 0


def test_seed_is_idempotent(db_session: Session) -> None:
    first = seed_foods(db_session)
    assert first > 0
    count_after_first = db_session.query(Food).count()
    portions_after_first = db_session.query(Portion).count()

    second = seed_foods(db_session)
    assert second == 0  # nessun nuovo inserimento
    assert db_session.query(Food).count() == count_after_first
    assert db_session.query(Portion).count() == portions_after_first


def test_seeded_foods_are_public_crea_no_owner(db_session: Session) -> None:
    seed_foods(db_session)
    foods = db_session.query(Food).all()
    for f in foods:
        assert f.source == FoodSource.CREA.value
        assert f.is_public is True
        assert f.created_by is None


def test_seed_includes_raw_convention_in_labels(db_session: Session) -> None:
    """Almeno gli alimenti che richiedono cottura/idratazione devono avere
    porzioni etichettate "cruda" o "secca" (convenzione DA CRUDO §6/§14).
    """
    seed_foods(db_session)
    pasta = db_session.query(Food).filter(Food.name == "Pasta di semola").one()
    labels = [p.label.lower() for p in pasta.portions]
    assert any("crud" in label for label in labels), labels


def test_csv_path_exists() -> None:
    csv_path = Path(__file__).resolve().parents[1] / "seed" / "foods.csv"
    assert csv_path.exists(), f"CSV di seed mancante: {csv_path}"
    text = csv_path.read_text(encoding="utf-8")
    # Verifica che le note di fonte e convenzione siano in testa al file.
    assert "CREA" in text
    assert "CRUDO" in text or "crudo" in text
