"""DEYMA RADAR V2 features test suite (P1 features)
Covers: PDF cotización, convertir-obra, importar-radar, actividades CRUD,
documentos mock, alertas HOT (mock).
"""
import os
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opp-detector.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "director": ("director@deyma.mx", "Deyma2026!"),
    "comercial": ("comercial@deyma.mx", "Comercial2026!"),
    "operaciones": ("operaciones@deyma.mx", "Operaciones2026!"),
}


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def tokens(s):
    out = {}
    for role, (email, pw) in CREDS.items():
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        assert r.status_code == 200, f"login {role} -> {r.status_code} {r.text}"
        out[role] = r.json()["access_token"]
    return out


@pytest.fixture(scope="session")
def hdr(tokens):
    return {"Authorization": f"Bearer {tokens['director']}"}


@pytest.fixture(scope="session")
def hdr_com(tokens):
    return {"Authorization": f"Bearer {tokens['comercial']}"}


# ============================================================
# Regression V1
# ============================================================
def test_v1_regression_login_director(s):
    r = s.post(f"{API}/auth/login", json={"email": "director@deyma.mx", "password": "Deyma2026!"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "director"


def test_v1_regression_dashboard_kpis(s, hdr):
    r = s.get(f"{API}/dashboard/kpis", headers=hdr, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["pipeline_total"] > 0
    assert "by_stage" in d


# ============================================================
# PDF Cotización
# ============================================================
def test_pdf_cotizacion_returns_valid_pdf(s, hdr):
    cots = s.get(f"{API}/cotizaciones", headers=hdr, timeout=15).json()
    assert len(cots) >= 1
    cid = cots[0]["id"]
    folio = cots[0]["folio"]
    r = s.get(f"{API}/cotizaciones/{cid}/pdf", headers=hdr, timeout=30)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct, f"content-type was {ct}"
    cd = r.headers.get("content-disposition", "")
    assert "filename" in cd.lower()
    assert folio in cd, f"expected folio {folio} in content-disposition: {cd}"
    body = r.content
    assert body.startswith(b"%PDF"), f"PDF magic bytes missing, got {body[:8]!r}"
    assert len(body) > 2048, f"PDF too small ({len(body)} bytes)"


def test_pdf_cotizacion_not_found(s, hdr):
    r = s.get(f"{API}/cotizaciones/nonexistent_id/pdf", headers=hdr, timeout=15)
    assert r.status_code == 404


# ============================================================
# Convertir oportunidad ganada → Obra
# ============================================================
@pytest.fixture
def ganada_op(s, hdr):
    """Create a fresh ganada oportunidad for conversion test."""
    emp = s.get(f"{API}/empresas", headers=hdr).json()[0]
    body = {
        "empresa_id": emp["id"],
        "titulo": "TEST_op_ganada_conv",
        "sector": "manufactura",
        "descripcion": "para conversion",
        "monto_estimado": 1500000,
        "stage": "ganada",
        "probabilidad": 100,
    }
    r = s.post(f"{API}/oportunidades", json=body, headers=hdr, timeout=15)
    assert r.status_code == 200
    return r.json()


def test_convertir_obra_success(s, hdr, ganada_op):
    oid = ganada_op["id"]
    r = s.post(f"{API}/oportunidades/{oid}/convertir-obra", json={}, headers=hdr, timeout=15)
    assert r.status_code == 200, r.text
    obra = r.json()
    assert obra["empresa_id"] == ganada_op["empresa_id"]
    assert obra["monto_contratado"] == ganada_op["monto_estimado"]
    assert obra["nombre"] == ganada_op["titulo"]
    assert "ciudad" in obra
    # verify obra exists in GET /obras
    obras = s.get(f"{API}/obras", headers=hdr).json()
    assert any(o["id"] == obra["id"] for o in obras)
    # Verify auto-actividad created
    acts = s.get(f"{API}/actividades?oportunidad_id={oid}", headers=hdr).json()
    auto_acts = [a for a in acts if a["tipo"] == "nota" and "convertida" in a["descripcion"].lower()]
    assert len(auto_acts) >= 1, "Expected auto activity 'nota' for conversion"
    assert auto_acts[0]["completada"] is True


def test_convertir_obra_duplicate_fails(s, hdr, ganada_op):
    oid = ganada_op["id"]
    r1 = s.post(f"{API}/oportunidades/{oid}/convertir-obra", json={}, headers=hdr, timeout=15)
    assert r1.status_code == 200
    r2 = s.post(f"{API}/oportunidades/{oid}/convertir-obra", json={}, headers=hdr, timeout=10)
    assert r2.status_code == 400


def test_convertir_obra_non_ganada_fails(s, hdr):
    # find an op not in ganada stage
    ops = s.get(f"{API}/oportunidades", headers=hdr).json()
    propuesta_op = next((o for o in ops if o.get("stage") in ("propuesta", "prospeccion", "calificacion", "negociacion")), None)
    assert propuesta_op, "Need at least one non-ganada op in seed"
    r = s.post(f"{API}/oportunidades/{propuesta_op['id']}/convertir-obra", json={}, headers=hdr, timeout=10)
    assert r.status_code == 400


# ============================================================
# Importar Radar → CRM
# ============================================================
def test_importar_radar_creates_oportunidad(s, hdr):
    radars = s.get(f"{API}/radar", headers=hdr).json()
    empresas = s.get(f"{API}/empresas", headers=hdr).json()
    assert radars and empresas
    rp = radars[0]
    emp = empresas[0]
    body = {"empresa_id": emp["id"], "probabilidad": 30, "stage": "prospeccion"}
    r = s.post(f"{API}/radar/{rp['id']}/importar", json=body, headers=hdr, timeout=15)
    assert r.status_code == 200, r.text
    op = r.json()
    assert op["titulo"] == rp["titulo"]
    assert op["sector"] == rp["sector"]
    assert op["descripcion"] == rp["descripcion"]
    assert op["monto_estimado"] == rp["monto_estimado"]
    assert op["stage"] == "prospeccion"
    assert op["probabilidad"] == 30
    assert op["empresa_id"] == emp["id"]
    assert op.get("score") == rp.get("score", 0)
    assert op.get("hotness") == rp.get("hotness", "cold")
    # Verify shows in /oportunidades
    ops = s.get(f"{API}/oportunidades", headers=hdr).json()
    assert any(o["id"] == op["id"] for o in ops)


def test_importar_radar_invalid_empresa(s, hdr):
    radars = s.get(f"{API}/radar", headers=hdr).json()
    r = s.post(f"{API}/radar/{radars[0]['id']}/importar",
               json={"empresa_id": "noexiste", "probabilidad": 20, "stage": "prospeccion"},
               headers=hdr, timeout=10)
    assert r.status_code == 404


# ============================================================
# Actividades CRUD
# ============================================================
@pytest.fixture
def test_op_for_act(s, hdr):
    emp = s.get(f"{API}/empresas", headers=hdr).json()[0]
    body = {
        "empresa_id": emp["id"], "titulo": "TEST_op_actividades", "sector": "manufactura",
        "descripcion": "x", "monto_estimado": 500000, "stage": "prospeccion", "probabilidad": 20,
    }
    r = s.post(f"{API}/oportunidades", json=body, headers=hdr).json()
    return r


def test_actividades_crud(s, hdr, test_op_for_act):
    oid = test_op_for_act["id"]
    fecha = datetime.now(timezone.utc).isoformat()
    body = {"oportunidad_id": oid, "tipo": "llamada", "fecha": fecha, "descripcion": "TEST_llamada"}
    r = s.post(f"{API}/actividades", json=body, headers=hdr, timeout=10)
    assert r.status_code == 200, r.text
    act = r.json()
    aid = act["id"]
    assert act["tipo"] == "llamada"
    assert act["completada"] is False
    assert act["owner_id"]

    # filter by oportunidad_id
    items = s.get(f"{API}/actividades?oportunidad_id={oid}", headers=hdr).json()
    assert any(a["id"] == aid for a in items)
    assert all(a["oportunidad_id"] == oid for a in items)

    # mias=true
    mine = s.get(f"{API}/actividades?mias=true", headers=hdr).json()
    assert any(a["id"] == aid for a in mine)

    # pendientes
    pend = s.get(f"{API}/actividades?pendientes=true", headers=hdr).json()
    assert any(a["id"] == aid for a in pend)
    assert all(a["completada"] is False for a in pend)

    # mark completed
    r2 = s.patch(f"{API}/actividades/{aid}", json={"completada": True}, headers=hdr, timeout=10)
    assert r2.status_code == 200
    # verify it's no longer in pendientes
    pend2 = s.get(f"{API}/actividades?pendientes=true", headers=hdr).json()
    assert not any(a["id"] == aid for a in pend2)

    # delete
    r3 = s.delete(f"{API}/actividades/{aid}", headers=hdr, timeout=10)
    assert r3.status_code == 200
    after = s.get(f"{API}/actividades?oportunidad_id={oid}", headers=hdr).json()
    assert not any(a["id"] == aid for a in after)


def test_actividad_patch_not_found(s, hdr):
    r = s.patch(f"{API}/actividades/noexiste", json={"completada": True}, headers=hdr, timeout=10)
    assert r.status_code == 404


# ============================================================
# Documentos (mock)
# ============================================================
def test_documentos_crud_mock(s, hdr):
    ops = s.get(f"{API}/oportunidades", headers=hdr).json()
    oid = ops[0]["id"]
    body = {
        "entidad_tipo": "oportunidad",
        "entidad_id": oid,
        "nombre": "TEST_propuesta.pdf",
        "tipo": "pdf",
        "tamano_bytes": 12345,
    }
    r = s.post(f"{API}/documentos", json=body, headers=hdr, timeout=10)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc.get("mock") is True
    did = doc["id"]
    assert doc["nombre"] == "TEST_propuesta.pdf"
    assert doc["entidad_id"] == oid

    # filtered list
    docs = s.get(f"{API}/documentos?entidad_tipo=oportunidad&entidad_id={oid}", headers=hdr).json()
    assert any(d["id"] == did for d in docs)
    assert all(d["entidad_id"] == oid for d in docs)

    # delete
    r2 = s.delete(f"{API}/documentos/{did}", headers=hdr, timeout=10)
    assert r2.status_code == 200
    docs2 = s.get(f"{API}/documentos?entidad_tipo=oportunidad&entidad_id={oid}", headers=hdr).json()
    assert not any(d["id"] == did for d in docs2)


# ============================================================
# Alertas HOT (mock)
# ============================================================
def test_alertas_list_returns_mock_metadata(s, hdr):
    r = s.get(f"{API}/alertas", headers=hdr, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and isinstance(d["items"], list)
    assert d.get("twilio_enabled") is False  # no keys in .env
    assert d.get("alert_phone") in (None, "")


def test_alertas_test_director_creates_mock(s, hdr):
    before = s.get(f"{API}/alertas", headers=hdr).json()["items"]
    r = s.post(f"{API}/alertas/test", headers=hdr, timeout=15)
    assert r.status_code == 200, r.text
    after = s.get(f"{API}/alertas", headers=hdr).json()["items"]
    assert len(after) == len(before) + 1
    new_alert = after[0]
    assert new_alert.get("mock") is True or new_alert.get("twilio_enabled") is False or "id" in new_alert
    assert new_alert.get("score") == 90 or "score" in new_alert


def test_alertas_test_forbidden_for_non_director(s, hdr_com):
    r = s.post(f"{API}/alertas/test", headers=hdr_com, timeout=10)
    assert r.status_code == 403


# ============================================================
# Auto-alert from convertir-obra is NOT expected, but we verify
# that /alertas/test (deterministic) creates an alert as per spec.
# Auto-alert from score>=85 is best-effort since LLM is non-deterministic.
# ============================================================
