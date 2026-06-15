"""V4.5 RH · Personal Contratado - backend tests."""
import io
import os
import pytest
import requests
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # fallback: parse from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")

BASE_URL = _load_url()
API = f"{BASE_URL}/api"

CREDS = {
    "director": ("director@deyma.mx", "Deyma2026!"),
    "socio": ("socio@deyma.mx", "Socio2026!"),
    "comercial": ("comercial@deyma.mx", "Comercial2026!"),
    "operaciones": ("operaciones@deyma.mx", "Operaciones2026!"),
}

TOKENS: dict = {}


def _login(role: str) -> str:
    if role in TOKENS:
        return TOKENS[role]
    email, password = CREDS[role]
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login {role} failed: {r.status_code} {r.text}"
    TOKENS[role] = r.json()["access_token"]
    return TOKENS[role]


def _h(role: str) -> dict:
    return {"Authorization": f"Bearer {_login(role)}"}


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<<>>\n%%EOF"


# ----- RBAC -----
class TestRHRBAC:
    def test_comercial_forbidden_list(self):
        r = requests.get(f"{API}/rh/empleados", headers=_h("comercial"))
        assert r.status_code == 403

    def test_operaciones_forbidden_list(self):
        r = requests.get(f"{API}/rh/empleados", headers=_h("operaciones"))
        assert r.status_code == 403

    def test_director_ok_list(self):
        r = requests.get(f"{API}/rh/empleados", headers=_h("director"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_socio_ok_list(self):
        r = requests.get(f"{API}/rh/empleados", headers=_h("socio"))
        assert r.status_code == 200

    def test_alertas_rbac(self):
        assert requests.get(f"{API}/rh/alertas", headers=_h("comercial")).status_code == 403
        assert requests.get(f"{API}/rh/alertas", headers=_h("director")).status_code == 200


# ----- CRUD -----
@pytest.fixture(scope="module")
def empleado_id():
    payload = {
        "nombre": "TEST_RH_Juan Perez",
        "rfc": "PEPJ800101AB1",
        "curp": "PEPJ800101HDFRZN01",
        "nss": "12345678901",
        "puesto": "Albañil",
        "departamento": "Obra",
        "fecha_ingreso": (date.today() - relativedelta(years=6)).strftime("%Y-%m-%d"),
        "salario_diario": 350.0,
        "salario_mensual": 10500.0,
        "sueldo_integrado": 11000.0,
        "tel": "5551112233",
        "correo": "juan@test.mx",
        "domicilio": "Av. Test 123",
        "contacto_emergencia_nombre": "Maria",
        "contacto_emergencia_tel": "5559998877",
    }
    r = requests.post(f"{API}/rh/empleados", json=payload, headers=_h("director"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "activo"
    assert body["documentos_count"] == 0
    assert body["id"]
    yield body["id"]
    # cleanup
    requests.delete(f"{API}/rh/empleados/{body['id']}", headers=_h("director"))


class TestCRUD:
    def test_get_empleado_has_prestaciones(self, empleado_id):
        r = requests.get(f"{API}/rh/empleados/{empleado_id}", headers=_h("director"))
        assert r.status_code == 200
        e = r.json()
        assert "prestaciones" in e
        assert "documentos" in e and isinstance(e["documentos"], list)
        assert "vacaciones" in e and isinstance(e["vacaciones"], list)
        # 6 años => 22 vacaciones
        assert e["prestaciones"]["vacaciones_anuales_periodo_actual"] == 22

    def test_list_filters(self, empleado_id):
        r = requests.get(f"{API}/rh/empleados?q=TEST_RH_Juan", headers=_h("director"))
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert empleado_id in ids

        r2 = requests.get(f"{API}/rh/empleados?departamento=Obra&status=activo", headers=_h("director"))
        assert r2.status_code == 200
        assert any(x["id"] == empleado_id for x in r2.json())

    def test_patch_updates_partial(self, empleado_id):
        r = requests.patch(f"{API}/rh/empleados/{empleado_id}",
                           json={"puesto": "Maestro de obra"}, headers=_h("director"))
        assert r.status_code == 200
        g = requests.get(f"{API}/rh/empleados/{empleado_id}", headers=_h("director")).json()
        assert g["puesto"] == "Maestro de obra"

    def test_patch_fecha_ingreso_recalc(self, empleado_id):
        nueva = (date.today() - relativedelta(years=11)).strftime("%Y-%m-%d")
        r = requests.patch(f"{API}/rh/empleados/{empleado_id}",
                           json={"fecha_ingreso": nueva}, headers=_h("director"))
        assert r.status_code == 200
        g = requests.get(f"{API}/rh/empleados/{empleado_id}", headers=_h("director")).json()
        # 11 años => 24 vacaciones
        assert g["prestaciones"]["vacaciones_anuales_periodo_actual"] == 24
        # restore 6 years
        seis = (date.today() - relativedelta(years=6)).strftime("%Y-%m-%d")
        requests.patch(f"{API}/rh/empleados/{empleado_id}",
                       json={"fecha_ingreso": seis}, headers=_h("director"))


# ----- Prestaciones LFT 2023 -----
@pytest.mark.parametrize("anios,expected", [(1, 12), (5, 20), (6, 22), (11, 24), (21, 28), (31, 32)])
def test_prestaciones_tabla_lft(anios, expected):
    fi = (date.today() - relativedelta(years=anios)).strftime("%Y-%m-%d")
    payload = {
        "nombre": f"TEST_RH_LFT_{anios}",
        "puesto": "Test", "departamento": "RH",
        "fecha_ingreso": fi,
    }
    r = requests.post(f"{API}/rh/empleados", json=payload, headers=_h("director"))
    assert r.status_code == 200
    eid = r.json()["id"]
    g = requests.get(f"{API}/rh/empleados/{eid}", headers=_h("director")).json()
    try:
        assert g["prestaciones"]["vacaciones_anuales_periodo_actual"] == expected, \
            f"anios={anios} expected={expected} got={g['prestaciones']['vacaciones_anuales_periodo_actual']}"
        assert g["prestaciones"]["aguinaldo_dias"] == 15
        assert g["prestaciones"]["prima_vacacional_pct"] == 25
        assert g["prestaciones"]["proximo_aniversario"] is not None
        assert g["prestaciones"]["dias_para_aniversario"] is not None
    finally:
        requests.delete(f"{API}/rh/empleados/{eid}", headers=_h("director"))


# ----- Vacaciones -----
class TestVacaciones:
    def test_add_and_balance(self, empleado_id):
        # 6 años => 22 días
        payload = {
            "fecha_inicio": "2025-07-01", "fecha_fin": "2025-07-05",
            "dias": 5, "estatus": "gozadas", "nota": "TEST_RH",
        }
        r = requests.post(f"{API}/rh/empleados/{empleado_id}/vacaciones",
                          json=payload, headers=_h("director"))
        assert r.status_code == 200
        vid = r.json()["id"]
        g = requests.get(f"{API}/rh/empleados/{empleado_id}", headers=_h("director")).json()
        assert g["prestaciones"]["vacaciones_gozadas"] == 5
        assert g["prestaciones"]["vacaciones_pendientes"] == 22 - 5
        # delete
        d = requests.delete(f"{API}/rh/empleados/{empleado_id}/vacaciones/{vid}",
                            headers=_h("director"))
        assert d.status_code == 200


# ----- Documentos -----
class TestDocumentos:
    def test_upload_invalid_tipo(self, empleado_id):
        files = {"archivo": ("x.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")}
        data = {"tipo": "invalido"}
        r = requests.post(f"{API}/rh/empleados/{empleado_id}/documentos",
                          files=files, data=data, headers=_h("director"))
        assert r.status_code == 400

    def test_upload_and_download_and_delete(self, empleado_id):
        files = {"archivo": ("contrato.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")}
        data = {"tipo": "contrato", "descripcion": "TEST_RH"}
        r = requests.post(f"{API}/rh/empleados/{empleado_id}/documentos",
                          files=files, data=data, headers=_h("director"))
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["tipo"] == "contrato"
        did = doc["id"]
        # download
        rd = requests.get(f"{API}/rh/empleados/{empleado_id}/documentos/{did}",
                         headers=_h("director"))
        assert rd.status_code == 200
        assert rd.headers.get("content-type", "").startswith("application/pdf")
        assert b"%PDF" in rd.content
        # GET empleado increments documentos_count
        g = requests.get(f"{API}/rh/empleados/{empleado_id}", headers=_h("director")).json()
        assert g["documentos_count"] >= 1
        assert any(d["id"] == did for d in g["documentos"])
        # delete
        dl = requests.delete(f"{API}/rh/empleados/{empleado_id}/documentos/{did}",
                             headers=_h("director"))
        assert dl.status_code == 200

    def test_doc_rbac_comercial(self, empleado_id):
        files = {"archivo": ("x.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")}
        data = {"tipo": "general"}
        r = requests.post(f"{API}/rh/empleados/{empleado_id}/documentos",
                          files=files, data=data, headers=_h("comercial"))
        assert r.status_code == 403


# ----- Expediente PDF -----
class TestExpedientePDF:
    def test_expediente_empty(self, empleado_id):
        r = requests.get(f"{API}/rh/empleados/{empleado_id}/expediente",
                         headers=_h("director"))
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "")
        assert len(r.content) >= 3 * 1024
        assert r.content.startswith(b"%PDF")

    def test_expediente_rbac(self, empleado_id):
        r = requests.get(f"{API}/rh/empleados/{empleado_id}/expediente",
                         headers=_h("operaciones"))
        assert r.status_code == 403


# ----- Alertas -----
class TestAlertas:
    def test_alertas_aniversario(self):
        # Empleado con aniversario en 10 días
        fi = (date.today() - relativedelta(years=2) + timedelta(days=10)).strftime("%Y-%m-%d")
        # corrige: ingreso hace ~2 años - 10 días así su aniversario es en 10 dias
        fi = (date.today() - relativedelta(years=2) + timedelta(days=10)).strftime("%Y-%m-%d")
        # asegurar fecha en pasado
        r = requests.post(f"{API}/rh/empleados", json={
            "nombre": "TEST_RH_Aniv", "puesto": "X", "departamento": "RH",
            "fecha_ingreso": fi,
        }, headers=_h("director"))
        assert r.status_code == 200
        eid = r.json()["id"]
        try:
            a = requests.get(f"{API}/rh/alertas", headers=_h("director"))
            assert a.status_code == 200
            arr = a.json()
            assert any(x.get("empleado_id") == eid and x.get("tipo") == "aniversario" for x in arr)
        finally:
            requests.delete(f"{API}/rh/empleados/{eid}", headers=_h("director"))


# ----- Baja lógica -----
class TestBajaLogica:
    def test_delete_marks_baja(self):
        r = requests.post(f"{API}/rh/empleados", json={
            "nombre": "TEST_RH_Baja", "puesto": "X", "departamento": "RH",
            "fecha_ingreso": (date.today() - relativedelta(years=1)).strftime("%Y-%m-%d"),
        }, headers=_h("director"))
        eid = r.json()["id"]
        d = requests.delete(f"{API}/rh/empleados/{eid}", headers=_h("director"))
        assert d.status_code == 200
        g = requests.get(f"{API}/rh/empleados/{eid}", headers=_h("director")).json()
        assert g["status"] == "baja"
        assert g.get("fecha_baja")


# ----- Regression smoke -----
class TestRegression:
    def test_dashboard_kpis(self):
        r = requests.get(f"{API}/dashboard/kpis", headers=_h("director"))
        assert r.status_code == 200

    def test_clientes_list(self):
        r = requests.get(f"{API}/clientes", headers=_h("director"))
        assert r.status_code == 200

    def test_oportunidades(self):
        r = requests.get(f"{API}/oportunidades", headers=_h("director"))
        assert r.status_code == 200

    def test_cotizaciones(self):
        r = requests.get(f"{API}/cotizaciones", headers=_h("director"))
        assert r.status_code == 200

    def test_radar(self):
        r = requests.get(f"{API}/radar", headers=_h("director"))
        assert r.status_code == 200
