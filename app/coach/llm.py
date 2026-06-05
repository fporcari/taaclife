"""Wrapper sul SDK Anthropic.

Vincolo CLAUDE.md §3: la chiave Anthropic sta solo nel backend, mai
esposta al client, mai loggata. Le eccezioni del SDK possono contenere
header/diagnostica; qui le rimappiamo in un messaggio neutro
`CoachUnavailableError` prima di lasciarle uscire.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

import anthropic

logger = logging.getLogger("nutricoach.coach")


class CoachUnavailableError(RuntimeError):
    """Alzata quando la chat non e' utilizzabile: chiave mancante,
    chiave non valida, errore di rete persistente. Il router la
    traduce in 503 con messaggio per l'utente, senza mai rivelare
    la chiave o il dettaglio interno."""


class CoachClient(Protocol):
    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str: ...

    def complete_with_tools(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict]
    ) -> Any:
        """Ritorna l'oggetto messaggio del SDK (con `.content` blocks
        e `.stop_reason`). Usato nel loop di tool-use."""
        ...


def _translate_anthropic_error(exc: Exception) -> "CoachUnavailableError":
    """Mappa un'eccezione del SDK Anthropic in un `CoachUnavailableError`
    con messaggio NEUTRO. Niente body/headers nei log: solo classe e,
    se disponibile, lo status code. Mai la chiave."""
    if isinstance(exc, anthropic.AuthenticationError):
        logger.warning("coach: errore autenticazione Anthropic")
        return CoachUnavailableError("coach non disponibile (autenticazione fallita)")
    if isinstance(exc, anthropic.APITimeoutError):
        logger.warning("coach: timeout verso Anthropic")
        return CoachUnavailableError("coach non disponibile (timeout)")
    if isinstance(exc, anthropic.APIConnectionError):
        logger.warning("coach: errore di rete verso Anthropic")
        return CoachUnavailableError("coach non disponibile (rete)")
    if isinstance(exc, anthropic.RateLimitError):
        logger.warning("coach: rate limit lato Anthropic")
        return CoachUnavailableError("coach non disponibile (rate limit upstream)")
    if isinstance(exc, anthropic.APIStatusError):
        status_code = getattr(exc, "status_code", "?")
        logger.warning("coach: API status error status=%s", status_code)
        return CoachUnavailableError("coach non disponibile (errore upstream)")
    # APIError generico (catch-all): non logghiamo `exc`, solo la classe.
    logger.warning("coach: API error (%s)", type(exc).__name__)
    return CoachUnavailableError("coach non disponibile (errore upstream)")


class AnthropicCoachClient:
    """Implementazione reale: chiama Anthropic con la chiave di sistema.

    Tutti gli errori del SDK vengono rimappati a `CoachUnavailableError`
    con messaggi neutri: la chiave non finisce mai in eccezioni propagate
    ne' nei log (logghiamo solo lo status code, non il body/headers).
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise CoachUnavailableError("coach non disponibile (chiave assente)")
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=messages,
            )
        except (
            anthropic.AuthenticationError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.APIStatusError,
            anthropic.APIError,
        ) as exc:
            raise _translate_anthropic_error(exc) from None

        # Estrae il testo concatenando i blocchi text del messaggio.
        chunks: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                chunks.append(text)
        return "".join(chunks).strip()

    def complete_with_tools(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict]
    ) -> Any:
        try:
            return self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=messages,
                tools=tools,
            )
        except (
            anthropic.AuthenticationError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.APIStatusError,
            anthropic.APIError,
        ) as exc:
            raise _translate_anthropic_error(exc) from None
