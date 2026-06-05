"""Verifica purezza di `core/coach.py` (PROJECT.md §8).

Non deve importare anthropic, sqlalchemy, fastapi, httpx, ne' app.*.
La costruzione del contesto da DB e la chiamata al SDK vivono
in app/coach/.
"""
import ast
from pathlib import Path


def test_core_coach_is_pure() -> None:
    src = (Path(__file__).resolve().parents[1] / "core" / "coach.py").read_text()
    tree = ast.parse(src)

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])

    forbidden = {
        "anthropic", "httpx", "requests", "urllib3",
        "sqlalchemy", "alembic",
        "fastapi", "starlette", "pydantic", "pydantic_settings",
        "app",
    }
    leaks = modules & forbidden
    assert not leaks, f"core/coach.py importa moduli vietati: {leaks}"
