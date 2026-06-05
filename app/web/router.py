"""Rotte HTML del frontend.

Servono le pagine + i partial HTMX. L'auth viene gestita lato client
(token JWT in localStorage, redirect a /login se manca). Quindi tutte
le rotte qui sono pubbliche: rendono solo lo "shell" delle pagine,
i dati li recuperano via API JSON gia' esistenti.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["web"], include_in_schema=False)


def _render(request: Request, name: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, name, ctx)


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return _render(request, "shell.html", initial_section="oggi")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return _render(request, "auth.html", mode="login")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    return _render(request, "auth.html", mode="register")
