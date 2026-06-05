"""Rate limit in-memory per utente, sliding window.

Implementazione semplice (PROJECT.md self-host single-process): dizionario
`{user_id: list[timestamps]}`. Non thread-safe: FastAPI gira con uvicorn
in un loop singolo, il caso d'uso e' coperto. Se in futuro si scala a
piu' processi, sostituibile con Redis dietro la stessa interfaccia.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class SlidingWindowLimiter:
    def __init__(self, max_calls: int, window_seconds: float) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls deve essere > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds deve essere > 0")
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _prune(self, key: str, now: float) -> None:
        threshold = now - self.window_seconds
        self._buckets[key] = [t for t in self._buckets[key] if t > threshold]

    def acquire(self, key: str) -> bool:
        """Tenta di consumare una chiamata. True se accolta, False se sopra
        il limite."""
        with self._lock:
            now = self._now()
            self._prune(key, now)
            if len(self._buckets[key]) >= self.max_calls:
                return False
            self._buckets[key].append(now)
            return True

    def seconds_until_next_slot(self, key: str) -> float:
        """Quanto manca al prossimo slot disponibile (0 se gia' disponibile)."""
        with self._lock:
            now = self._now()
            self._prune(key, now)
            if len(self._buckets[key]) < self.max_calls:
                return 0.0
            oldest = self._buckets[key][0]
            return max(0.0, self.window_seconds - (now - oldest))
