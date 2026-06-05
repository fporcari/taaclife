"""Middleware applicativi.

`MedicalDisclaimerHeaderMiddleware`: aggiunge l'header
`X-Medical-Disclaimer` a ogni risposta, per ricordare ai client e a
chi consuma l'API che NutriCoach non e' un dispositivo medico.
Riferimento al testo completo via `/disclaimer`.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.disclaimer import DISCLAIMER_VERSION

DISCLAIMER_HEADER_NAME = "X-Medical-Disclaimer"
DISCLAIMER_HEADER_VALUE = (
    f"not-a-medical-device; version={DISCLAIMER_VERSION}; see /disclaimer"
)


class MedicalDisclaimerHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers[DISCLAIMER_HEADER_NAME] = DISCLAIMER_HEADER_VALUE
        return response
