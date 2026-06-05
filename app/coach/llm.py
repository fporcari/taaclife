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


class AnthropicCoachClient:
    """Implementazione reale: chiama Anthropic con la chiave di sistema."""

    def __init__(self, *, api_key: str, model: str, max_tokens: int) -> None:
        if not api_key:
            raise CoachUnavailableError("coach non disponibile (chiave assente)")
        self._client = anthropic.Anthropic(api_key=api_key)
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
        except anthropic.AuthenticationError as exc:
            # Non logghiamo `exc` direttamente: gli headers possono contenere
            # la chiave. Solo un messaggio neutro.
            logger.warning("coach: errore autenticazione Anthropic")
            raise CoachUnavailableError(
                "coach non disponibile (autenticazione fallita)"
            ) from None
        except anthropic.APIConnectionError:
            logger.warning("coach: errore di rete verso Anthropic")
            raise CoachUnavailableError(
                "coach non disponibile (rete)"
            ) from None
        except anthropic.RateLimitError:
            logger.warning("coach: rate limit lato Anthropic")
            raise CoachUnavailableError(
                "coach non disponibile (rate limit upstream)"
            ) from None
        except anthropic.APIError as exc:
            # Logghiamo solo lo status code, non il body (potrebbe ripetere
            # parti della richiesta o headers).
            status = getattr(exc, "status_code", "?")
            logger.warning("coach: API error status=%s", status)
            raise CoachUnavailableError(
                "coach non disponibile (errore upstream)"
            ) from None

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
        except anthropic.AuthenticationError:
            logger.warning("coach: errore autenticazione Anthropic")
            raise CoachUnavailableError(
                "coach non disponibile (autenticazione fallita)"
            ) from None
        except anthropic.APIConnectionError:
            logger.warning("coach: errore di rete verso Anthropic")
            raise CoachUnavailableError("coach non disponibile (rete)") from None
        except anthropic.RateLimitError:
            logger.warning("coach: rate limit lato Anthropic")
            raise CoachUnavailableError(
                "coach non disponibile (rate limit upstream)"
            ) from None
        except anthropic.APIError as exc:
            status = getattr(exc, "status_code", "?")
            logger.warning("coach: API error status=%s", status)
            raise CoachUnavailableError(
                "coach non disponibile (errore upstream)"
            ) from None
