"""Dipendenze FastAPI per il coach: client LLM e rate limiter.

Single-source-of-truth: factory wrap-and-cache. Override-abili nei test
via `app.dependency_overrides[...]`.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status

from app.coach.llm import AnthropicCoachClient, CoachClient, CoachUnavailableError
from app.coach.rate_limit import SlidingWindowLimiter
from app.settings import Settings, get_settings


@lru_cache(maxsize=1)
def _build_limiter(max_calls: int, window_seconds: float) -> SlidingWindowLimiter:
    return SlidingWindowLimiter(max_calls=max_calls, window_seconds=window_seconds)


def get_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> SlidingWindowLimiter:
    return _build_limiter(settings.coach_rate_limit_per_hour, 3600.0)


def get_coach_client(
    settings: Settings = Depends(get_settings),
) -> CoachClient:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="coach non disponibile (chiave assente)",
        )
    try:
        return AnthropicCoachClient(
            api_key=settings.anthropic_api_key,
            model=settings.coach_model,
            max_tokens=settings.coach_max_tokens,
        )
    except CoachUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
