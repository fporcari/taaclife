"""Rate limit per le rotte di autenticazione (anti brute-force).

Le rotte sono pubbliche (l'utente non e' ancora autenticato), quindi la
chiave non puo' essere `user_id`. Usiamo l'IP del client come bucket.
In-memory, single-process, come il limiter del coach.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status

from app.coach.rate_limit import SlidingWindowLimiter
from app.settings import Settings, get_settings

WINDOW_15_MIN = 15 * 60.0


@lru_cache(maxsize=1)
def _login_limiter(max_calls: int) -> SlidingWindowLimiter:
    return SlidingWindowLimiter(max_calls=max_calls, window_seconds=WINDOW_15_MIN)


@lru_cache(maxsize=1)
def _register_limiter(max_calls: int) -> SlidingWindowLimiter:
    return SlidingWindowLimiter(max_calls=max_calls, window_seconds=WINDOW_15_MIN)


def get_login_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowLimiter:
    return _login_limiter(settings.auth_login_rate_limit_per_15min)


def get_register_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowLimiter:
    return _register_limiter(settings.auth_register_rate_limit_per_15min)


def _client_ip(request: Request) -> str:
    """Estrae un identificativo IP del client. Se non disponibile,
    usa 'unknown' (in test/CI puo' capitare)."""
    client = request.client
    if client and client.host:
        return client.host
    return "unknown"


def enforce_limit(limiter: SlidingWindowLimiter, request: Request) -> None:
    """Alza 429 se la finestra IP e' satura."""
    ip = _client_ip(request)
    if not limiter.acquire(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="troppe richieste, riprova piu' tardi",
        )
