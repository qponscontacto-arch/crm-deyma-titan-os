"""
V3.5: Panel de Seguimiento a Cotizaciones — backend tests.

Coverage:
- Regression: login director + GET /api/cotizaciones >=3 + folio DEY-YYYY-####
- GET /api/cotizaciones/{id}/email-template
- POST /api/cotizaciones/{id}/aprobar-enviar (director, comercial, operaciones 403)
- Bloquea re-aprobación en estado final
- POST /api/cotizaciones/{id}/respuesta (director/comercial OK, operaciones 403)
- POST /api/cotizaciones/{id}/marcar (director/comercial)
- GET /api/cotizaciones/{id}/seguimiento (verifica counts)
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opp-detector.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "director": {"email": "director@deyma.mx", "password": "Deyma2026!"},
    "comercial": {"email": "comercial@deyma.mx", "password": "Comercial2026!"},
    "operaciones": {"email": "operaciones@deyma.mx", "password": "Operaciones2026!"},
}

FOLIO_RE = re.compile(r"^DEY-\d{4}-\d{4}$")


def _login(role: str) -> str:
    r = requests.post(f"{API}/auth/login", json=CREDS[role], timeout=30)
    assert r.status_code == 200, f"login {role} failed {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tokens():
    return {role: _login(role) for role in CREDS}


@pytest.fixture(scope="module")
def cotizaciones(tokens):
    r = requests.get(f"{API}/cotizaciones", headers=_h(tokens["director"]), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    return data


# ---------- Regression ----------
def test_director_login_and_list_cotizaciones(cotizaciones):
    assert len(cotizaciones) >= 3, f"Expected >=3 seed cotizaciones, got {len(cotizaciones)}"
    for c in cotizaciones[:5]:
        assert FOLIO_RE.match(c["folio"]), f"folio fmt invalid: {c.get('folio')}"


# ---------- Email template ----------
def test_email_template_shape(tokens, cotizaciones):
    cid = cotizaciones[0]["id"]
    folio = cotizaciones[0]["folio"]
    r = requests.get(f"{API}/cotizaciones/{cid}/email-template", headers=_h(tokens["director"]), timeout=30)
    assert r.status_code == 200, r.text
    t = r.json()
    for k in ("to", "cc", "subject", "body_html", "body_text"):
        assert k in t, f"missing key {k}"
    assert folio in t["subject"] and "Cotización" in t["subject"]
    bh = t["body_html"]
    assert "<table" in bh and "<h2" in bh and "<p>" in bh
    assert t["body_text"].lstrip().startswith("Estimado(a)")


# ---------- Aprobar-enviar director ----------
def _create_borrador(tokens, cotizaciones, suffix: str) -> str:
    emp_id = cotizaciones[0]["empresa_id"]
    payload = {
        "empresa_id": emp_id,
        "proyecto_titulo": f"TEST_v35 {suffix}",
        "items": [{"descripcion": "Mano de obra", "cantidad": 10, "unidad": "hr", "precio_unitario": 500}],
        "iva_pct": 16,
        "validez_dias": 30,
        "notas": "test",
    }
    r = requests.post(f"{API}/cotizaciones", json=payload,
                      headers=_h(tokens["director"]), timeout=30)
    assert r.status_code == 200, f"create cot failed: {r.status_code} {r.text}"
    return r.json()["id"]


@pytest.fixture(scope="module")
def borrador_id(tokens, cotizaciones):
    return _create_borrador(tokens, cotizaciones, "director-aprob")


@pytest.fixture(scope="module")
def borrador_id_2(tokens, cotizaciones):
    return _create_borrador(tokens, cotizaciones, "comercial-aprob")


def _build_payload(template: dict) -> dict:
    return {
        "to": template["to"] or "cliente@example.com",
        "cc": [],
        "subject": template["subject"],
        "body_html": template["body_html"],
        "body_text": template["body_text"],
        "adjuntar_pdf": True,
    }


def test_aprobar_enviar_director(tokens, borrador_id):
    tpl = requests.get(f"{API}/cotizaciones/{borrador_id}/email-template",
                       headers=_h(tokens["director"]), timeout=30).json()
    payload = _build_payload(tpl)
    r = requests.post(f"{API}/cotizaciones/{borrador_id}/aprobar-enviar",
                      json=payload, headers=_h(tokens["director"]), timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["mock"] is True
    ob = j["outbound"]
    assert ob["status"] == "queued_mock"
    assert ob["mock"] is True
    assert ob.get("sent_by_name")
    assert ob.get("sent_by_role") == "director"
    assert any(a["filename"].startswith("cotizacion_") and a["filename"].endswith(".pdf")
               and a["content_type"] == "application/pdf" for a in ob["attachments"])
    # estado cambió
    seg = requests.get(f"{API}/cotizaciones/{borrador_id}/seguimiento",
                       headers=_h(tokens["director"]), timeout=30).json()
    assert seg["cotizacion"]["estado"] == "aprobada_direccion"


def test_aprobar_enviar_comercial(tokens, borrador_id_2):
    tpl = requests.get(f"{API}/cotizaciones/{borrador_id_2}/email-template",
                       headers=_h(tokens["comercial"]), timeout=30).json()
    payload = _build_payload(tpl)
    r = requests.post(f"{API}/cotizaciones/{borrador_id_2}/aprobar-enviar",
                      json=payload, headers=_h(tokens["comercial"]), timeout=60)
    assert r.status_code == 200, r.text
    ob = r.json()["outbound"]
    assert ob["sent_by_role"] == "comercial"


def test_aprobar_enviar_operaciones_403(tokens, cotizaciones):
    # use any cotizacion (even already approved is fine — auth check first)
    cid = cotizaciones[0]["id"]
    tpl = {"to": "x@example.com", "cc": [], "subject": "x", "body_html": "<p>x</p>", "body_text": "x"}
    payload = {**tpl, "adjuntar_pdf": False}
    r = requests.post(f"{API}/cotizaciones/{cid}/aprobar-enviar",
                      json=payload, headers=_h(tokens["operaciones"]), timeout=30)
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


# ---------- Respuesta cliente ----------
@pytest.fixture(scope="module")
def respuesta_cot_id(borrador_id):
    return borrador_id  # the one approved by director


def test_registrar_respuesta_comercial(tokens, respuesta_cot_id):
    body = {
        "de": "Juan Pérez",
        "de_email": "juan@cliente.com",
        "asunto": "RE: Cotización",
        "contenido": "Gracias por la cotización, la revisamos.",
        "sentimiento": "neutro",
    }
    r = requests.post(f"{API}/cotizaciones/{respuesta_cot_id}/respuesta",
                      json=body, headers=_h(tokens["comercial"]), timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "id" in j and j.get("registrado_por_name")
    assert j["sentimiento"] == "neutro"


def test_registrar_respuesta_operaciones_403(tokens, respuesta_cot_id):
    body = {"de": "x", "asunto": "x", "contenido": "x", "sentimiento": "neutro"}
    r = requests.post(f"{API}/cotizaciones/{respuesta_cot_id}/respuesta",
                      json=body, headers=_h(tokens["operaciones"]), timeout=30)
    assert r.status_code == 403


# ---------- Marcar estado ----------
def test_marcar_aceptada_director(tokens, respuesta_cot_id):
    r = requests.post(f"{API}/cotizaciones/{respuesta_cot_id}/marcar",
                      json={"estado": "aceptada", "nota": "Cliente confirmó"},
                      headers=_h(tokens["director"]), timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True and j["estado"] == "aceptada"


def test_block_reaprobar_estado_final(tokens, respuesta_cot_id):
    tpl = {"to": "x@example.com", "cc": [], "subject": "x", "body_html": "<p>x</p>",
           "body_text": "x", "adjuntar_pdf": False}
    r = requests.post(f"{API}/cotizaciones/{respuesta_cot_id}/aprobar-enviar",
                      json=tpl, headers=_h(tokens["director"]), timeout=30)
    assert r.status_code == 400
    assert "estado final" in r.text.lower()


# ---------- Seguimiento completo ----------
def test_seguimiento_counts(tokens, respuesta_cot_id):
    r = requests.get(f"{API}/cotizaciones/{respuesta_cot_id}/seguimiento",
                     headers=_h(tokens["director"]), timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["sendgrid_enabled"] is False
    assert j["sendgrid_from"] is None
    assert len(j["outbound_emails"]) >= 1
    assert len(j["inbound_replies"]) >= 1
    # historia must include the 3 expected types
    tipos = {h["tipo"] for h in j["historia"]}
    assert {"aprobacion_envio", "respuesta_cliente", "cambio_estado"}.issubset(tipos), tipos
    assert len(j["historia"]) >= 3
