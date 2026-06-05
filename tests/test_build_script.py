"""Test di `build.sh` (Fase 0, PROJECT.md §15).

Verifichiamo:
- esiste, e' eseguibile;
- `--help` stampa l'aiuto e esce 0;
- argomenti sconosciuti producono exit code 2;
- una build con risposte sbagliate (cotto/OFF=s/lingua=en) viene
  rifiutata con exit 2 e messaggio chiaro.

NON testiamo il vero `docker build` (lento, dipende da Docker).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SH = REPO_ROOT / "build.sh"


def _run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    """Esegue build.sh disabilitando il vero docker build via PATH stub."""
    env = os.environ.copy()
    # Stub di `docker` cosi' l'eventuale ramo di build non chiama Docker reale.
    stub_dir = REPO_ROOT / ".tmp_test_stubs"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "docker"
    stub.write_text("#!/bin/sh\necho '[stub-docker] ignored'\nexit 0\n")
    stub.chmod(0o755)
    env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
    return subprocess.run(
        [str(BUILD_SH), *args],
        cwd=str(REPO_ROOT),
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_script_exists_and_executable() -> None:
    assert BUILD_SH.exists()
    assert os.access(BUILD_SH, os.X_OK)


def test_help_exits_zero() -> None:
    r = _run(["--help"])
    assert r.returncode == 0
    assert "build.sh" in r.stdout.lower()


def test_unknown_arg_exits_two() -> None:
    r = _run(["--asdfgh"])
    assert r.returncode == 2


def test_yes_flag_writes_default_config_and_invokes_build() -> None:
    """--yes accetta tutti i default; non chiede nulla; scrive build.config
    e (col docker stubbato) esce 0."""
    config_file = REPO_ROOT / "build.config"
    if config_file.exists():
        config_file.unlink()
    r = _run(["--yes"])
    assert r.returncode == 0, r.stderr
    assert config_file.exists()
    content = config_file.read_text()
    assert "APP_NAME=nutricoach" in content
    assert "FOOD_CONVENTION=crudo" in content
    assert "COACH_MODEL_NAME=haiku" in content
    assert "COACH_MODEL_ID=claude-haiku-4-5-20251001" in content
    assert "INCLUDE_OFF=no" in content
    assert "SEED_LANG=it" in content
    # Niente VALORI di segreti nel config: la parola "ANTHROPIC"/"JWT_SECRET"
    # puo' apparire solo come parte del commento esplicativo, mai come
    # `ANTHROPIC_API_KEY=...` o `JWT_SECRET=...` con un valore.
    for forbidden in ("ANTHROPIC_API_KEY=", "JWT_SECRET=", "JWT_REFRESH_SECRET="):
        for line in content.splitlines():
            if line.startswith("#"):
                continue
            assert not line.startswith(forbidden), (
                f"build.config contiene un segreto: {forbidden}"
            )
    config_file.unlink()


def test_cotto_rejected() -> None:
    r = _run([], stdin="\ncotto\n\nn\nit\n")
    assert r.returncode == 2
    assert "cotto" in (r.stdout + r.stderr).lower()


def test_off_yes_rejected() -> None:
    r = _run([], stdin="\ncrudo\nhaiku\ns\nit\n")
    assert r.returncode == 2
    assert "off" in (r.stdout + r.stderr).lower()


def test_lang_en_rejected() -> None:
    r = _run([], stdin="\ncrudo\nhaiku\nn\nen\n")
    assert r.returncode == 2


def test_interactive_defaults_via_blank_answers() -> None:
    config_file = REPO_ROOT / "build.config"
    if config_file.exists():
        config_file.unlink()
    # Cinque righe vuote -> tutti i default.
    r = _run([], stdin="\n\n\n\n\n")
    assert r.returncode == 0, r.stderr
    assert config_file.exists()
    assert "APP_NAME=nutricoach" in config_file.read_text()
    config_file.unlink()


@pytest.fixture(autouse=True)
def _cleanup_stub_dir():
    yield
    stub_dir = REPO_ROOT / ".tmp_test_stubs"
    if stub_dir.exists():
        for f in stub_dir.iterdir():
            f.unlink()
        stub_dir.rmdir()
