"""Smoke test del frontend: le pagine HTML rendono senza errori e
contengono i landmarks attesi (titolo, sezioni, footer disclaimer).
Non testiamo la logica JS qui (che gira nel browser): verifichiamo
solo che lo shell HTML sia corretto e che gli asset statici siano
serviti.
"""
from fastapi.testclient import TestClient


def test_home_renders_shell(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert "NutriCoach" in body
    assert "Oggi" in body
    assert "Profilo" in body
    assert "Gusti" in body
    assert "Peso" in body
    assert "Coach" in body
    # Toggle "nascondi calorie" presente.
    assert "nascondi le calorie" in body.lower()
    # Disclaimer footer.
    assert "non e' un dispositivo medico" in body or "non è un dispositivo medico" in body
    # Asset references.
    assert "/static/app.css" in body
    assert "/static/app.js" in body


def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/login")
    assert r.status_code == 200
    assert "bentornato" in r.text.lower()
    assert "auth-form" in r.text


def test_register_page_renders(client: TestClient) -> None:
    r = client.get("/register")
    assert r.status_code == 200
    assert "crea un account" in r.text.lower()


def test_static_css_served(client: TestClient) -> None:
    r = client.get("/static/app.css")
    assert r.status_code == 200
    assert "ctype" not in r.headers["content-type"].lower() or "text/css" in r.headers["content-type"].lower()
    # Deve contenere la palette editorial.
    assert "--accent" in r.text


def test_static_js_served(client: TestClient) -> None:
    r = client.get("/static/app.js")
    assert r.status_code == 200
    assert "bootstrapShell" in r.text


def test_section_modules_served(client: TestClient) -> None:
    for name in ["oggi", "profilo", "gusti", "peso", "coach"]:
        r = client.get(f"/static/sections/{name}.js")
        assert r.status_code == 200, f"sezione {name} non servita"
        assert "export" in r.text
