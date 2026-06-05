"""Verifica purezza di `core/coach.py` (PROJECT.md §8).

Non deve importare anthropic, sqlalchemy, fastapi, httpx, ne' app.*.
La costruzione del contesto da DB e la chiamata al SDK vivono
in app/coach/.
"""
import ast
from pathlib import Path

import pytest

FORBIDDEN = {
    "anthropic", "httpx", "requests", "urllib3",
    "sqlalchemy", "alembic",
    "fastapi", "starlette", "pydantic", "pydantic_settings",
    "app",
}


def _imported_top_level(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize("relative_path", [
    "core/coach.py",
    "core/coach_tools.py",
])
def test_core_coach_modules_are_pure(relative_path: str) -> None:
    root = Path(__file__).resolve().parents[1]
    leaks = _imported_top_level(root / relative_path) & FORBIDDEN
    assert not leaks, f"{relative_path} importa moduli vietati: {leaks}"
