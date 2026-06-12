"""DEYMA RADAR Backend API Tests"""
import os
import pytest
import requests

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


# ---------- Health & Auth ----------
def test_health(s):
    r = s.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_login_returns_role(s):
    for role, (email, pw) in CREDS.items():
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["role"] == role
        assert data["user"]["email"] == email


def test_login_bad_creds(s):
    r = s.post(f"{API}/auth/login", json={"email": "x@x.com", "password": "bad"}, timeout=10)
    assert r.status_code == 401


def test_auth_guard_unauth(s):
    r = s.get(f"{API}/empresas", timeout=10)
    assert r.status_code in (401, 403)


def test_auth_me(s, hdr):
    r = s.get(f"{API}/auth/me", headers=hdr, timeout=10)
    assert r.status_code == 200
    assert r.json()["email"] == "director@deyma.mx"


# ---------- CRM Empresas / Contactos ----------
def test_empresas_list(s, hdr):
    r = s.get(f"{API}/empresas", headers=hdr, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 10


def test_empresa_create_and_get(s, hdr):
    body = {"nombre": "TEST_Empresa_Auto", "sector": "manufactura", "ciudad": "Querétaro", "estado": "Querétaro"}
    r = s.post(f"{API}/empresas", json=body, headers=hdr, timeout=15)
    assert r.status_code == 200
    created = r.json()
    assert created["nombre"] == "TEST_Empresa_Auto"
    # verify in list
    r2 = s.get(f"{API}/empresas", headers=hdr, timeout=15)
    ids = [e["id"] for e in r2.json()]
    assert created["id"] in ids
    # cleanup
    s.delete(f"{API}/empresas/{created['id']}", headers=hdr, timeout=10)


def test_contactos_list(s, hdr):
    r = s.get(f"{API}/contactos", headers=hdr, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- Oportunidades ----------
def test_oportunidades_seed(s, hdr):
    r = s.get(f"{API}/oportunidades", headers=hdr, timeout=15)
    assert r.status_code == 200
    ops = r.json()
    assert len(ops) >= 12, f"expected >=12 ops, got {len(ops)}"


def test_oportunidad_create_and_patch(s, hdr):
    # need an empresa
    emp = s.get(f"{API}/empresas", headers=hdr).json()[0]
    body = {
        "empresa_id": emp["id"],
        "titulo": "TEST_op_auto",
        "sector": "manufactura",
        "descripcion": "prueba auto",
        "monto_estimado": 100000,
        "stage": "prospeccion",
        "probabilidad": 20,
    }
    r = s.post(f"{API}/oportunidades", json=body, headers=hdr, timeout=15)
    assert r.status_code == 200
    op = r.json()
    oid = op["id"]
    # PATCH stage
    r2 = s.patch(f"{API}/oportunidades/{oid}", json={"stage": "negociacion"}, headers=hdr, timeout=10)
    assert r2.status_code == 200
    # verify
    ops = s.get(f"{API}/oportunidades", headers=hdr).json()
    o = next(x for x in ops if x["id"] == oid)
    assert o["stage"] == "negociacion"


# ---------- Radar ----------
def test_radar_seed(s, hdr):
    r = s.get(f"{API}/radar", headers=hdr, timeout=15)
    assert r.status_code == 200
    assert len(r.json()) >= 12


# ---------- Cotizaciones ----------
def test_cotizaciones_seed(s, hdr):
    r = s.get(f"{API}/cotizaciones", headers=hdr, timeout=15)
    assert r.status_code == 200
    cots = r.json()
    assert len(cots) >= 3
    for c in cots:
        assert c["folio"].startswith("DEY-")


def test_cotizacion_create_computes_totals(s, hdr):
    emp = s.get(f"{API}/empresas", headers=hdr).json()[0]
    body = {
        "empresa_id": emp["id"],
        "proyecto_titulo": "TEST_cot_auto",
        "items": [{"descripcion": "Piso 1000m2", "cantidad": 1000, "unidad": "m2", "precio_unitario": 500}],
        "iva_pct": 16.0,
        "notas": "auto",
        "validez_dias": 15,
    }
    r = s.post(f"{API}/cotizaciones", json=body, headers=hdr, timeout=15)
    assert r.status_code == 200, r.text
    cot = r.json()
    assert cot["subtotal"] == 500000
    assert cot["iva_monto"] == 80000
    assert cot["total"] == 580000
    assert cot["folio"].startswith("DEY-")


# ---------- Obras (role guard) ----------
def test_obras_list(s, hdr):
    r = s.get(f"{API}/obras", headers=hdr, timeout=15)
    assert r.status_code == 200
    obras = r.json()
    assert len(obras) >= 4
    assert all("avance_pct" in o for o in obras)


def test_obras_comercial_forbidden(s, tokens):
    h = {"Authorization": f"Bearer {tokens['comercial']}"}
    emp = s.get(f"{API}/empresas", headers=h).json()[0]
    body = {
        "empresa_id": emp["id"], "nombre": "TEST_obra", "monto_contratado": 1000,
        "fecha_inicio": "2026-01-01T00:00:00+00:00", "fecha_fin_estimada": "2026-06-01T00:00:00+00:00",
        "ciudad": "Querétaro",
    }
    r = s.post(f"{API}/obras", json=body, headers=h, timeout=10)
    assert r.status_code == 403


# ---------- Dashboard ----------
def test_dashboard_kpis(s, hdr):
    r = s.get(f"{API}/dashboard/kpis", headers=hdr, timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ["pipeline_total", "ingresos_ganados", "forecast_ponderado", "hot_ops_count",
              "cotizaciones_mes", "obras_activas", "radar_count", "by_stage", "by_sector"]:
        assert k in d, f"missing {k}"
    assert d["pipeline_total"] > 0
    assert len(d["by_stage"].keys()) >= 6


# ---------- Mapa ----------
def test_mapa_puntos(s, hdr):
    r = s.get(f"{API}/mapa/puntos", headers=hdr, timeout=15)
    assert r.status_code == 200
    pts = r.json()["points"]
    assert len(pts) >= 10
    p = pts[0]
    for k in ["lat", "lng", "tipo", "sector", "monto", "score", "hotness", "ciudad"]:
        assert k in p


# ---------- AI Endpoints (slower) ----------
def test_ai_score_oportunidad(s, hdr):
    op = s.get(f"{API}/oportunidades", headers=hdr).json()[0]
    r = s.post(f"{API}/oportunidades/{op['id']}/score", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 0 <= d["score"] <= 100
    assert d["hotness"] in ("hot", "warm", "cold")
    assert isinstance(d["reasons"], list)


def test_ai_score_radar(s, hdr):
    p = s.get(f"{API}/radar", headers=hdr).json()[0]
    r = s.post(f"{API}/radar/{p['id']}/score", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 0 <= d["score"] <= 100


def test_ai_executive_summary(s, hdr):
    r = s.get(f"{API}/dashboard/executive-summary", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("summary") and len(d["summary"]) > 20
    assert "generated_at" in d


def test_ai_forecast(s, hdr):
    r = s.get(f"{API}/dashboard/forecast", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "forecast_amount" in d
    assert d.get("confidence") in ("baja", "media", "alta")


def test_ai_followup_email(s, hdr):
    op = s.get(f"{API}/oportunidades", headers=hdr).json()[0]
    r = s.post(f"{API}/oportunidades/{op['id']}/followup-email", headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("subject") and d.get("body")
