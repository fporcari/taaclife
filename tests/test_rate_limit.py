import pytest

from app.coach.rate_limit import SlidingWindowLimiter


def test_acquire_under_limit() -> None:
    lim = SlidingWindowLimiter(max_calls=3, window_seconds=60)
    for _ in range(3):
        assert lim.acquire("alice") is True


def test_reject_above_limit() -> None:
    lim = SlidingWindowLimiter(max_calls=2, window_seconds=60)
    assert lim.acquire("alice")
    assert lim.acquire("alice")
    assert lim.acquire("alice") is False


def test_per_key_isolation() -> None:
    lim = SlidingWindowLimiter(max_calls=1, window_seconds=60)
    assert lim.acquire("alice")
    assert lim.acquire("alice") is False
    # Bob ha un suo bucket.
    assert lim.acquire("bob")


def test_window_slides(monkeypatch) -> None:
    lim = SlidingWindowLimiter(max_calls=2, window_seconds=1)
    base = 1000.0
    monkeypatch.setattr(lim, "_now", lambda: base)
    assert lim.acquire("alice")
    assert lim.acquire("alice")
    assert lim.acquire("alice") is False

    # Avanzo il tempo oltre la finestra.
    monkeypatch.setattr(lim, "_now", lambda: base + 1.1)
    assert lim.acquire("alice")


def test_seconds_until_next_slot(monkeypatch) -> None:
    lim = SlidingWindowLimiter(max_calls=1, window_seconds=10)
    base = 500.0
    monkeypatch.setattr(lim, "_now", lambda: base)
    lim.acquire("alice")
    # Subito dopo: ~10s di attesa.
    wait = lim.seconds_until_next_slot("alice")
    assert 9.9 <= wait <= 10.0

    monkeypatch.setattr(lim, "_now", lambda: base + 4)
    wait = lim.seconds_until_next_slot("alice")
    assert 5.9 <= wait <= 6.0


def test_invalid_construction() -> None:
    with pytest.raises(ValueError):
        SlidingWindowLimiter(max_calls=0, window_seconds=10)
    with pytest.raises(ValueError):
        SlidingWindowLimiter(max_calls=10, window_seconds=0)
