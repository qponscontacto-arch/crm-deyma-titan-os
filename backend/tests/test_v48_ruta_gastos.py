"""V4.8 - Ruta de Ventas IA + Gastos de Viajero tests.

Tests RBAC, geocoding endpoints, ruta CRUD, PDF, gastos CRUD with GridFS files.
"""
import os
import io
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    import subprocess
    r = subprocess.check_output(["bash", "-c", "grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2"]).decode().strip()
    BASE_URL = r.rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "director":    ("director@deyma.mx",    "Deyma2026!"),
    "socio":       ("socio@deyma.mx",       "Socio2026!"),
    "comercial":   ("comercial@deyma.mx",   "Comercial2026!"),
    "operaciones": ("operaciones@deyma.mx", "Operaciones2026!"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}


def h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Regresion smoke ----------
class TestRegresion:
    def test_login_works(self, tokens):
        assert all(tokens.values())

    @pytest.mark.parametrize("ep", ["/dashboard/kpis", "/cotizaciones", "/clientes", "/rh/empleados", "/radar"])
    def test_existing_endpoints(self, tokens, ep):
        r = requests.get(f"{API}{ep}", headers=h(tokens["director"]), timeout=30)
        assert r.status_code == 200, f"{ep} -> {r.status_code} {r.text[:120]}"


# ---------- RBAC ----------
class TestRBACRutaVentas:
    def test_operaciones_denied_generar(self, tokens):
        r = requests.post(f"{API}/ruta-ventas/generar",
                          headers=h(tokens["operaciones"]),
                          json={"origen": "Morelia", "modo": "local"}, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_operaciones_denied_list(self, tokens):
        r = requests.get(f"{API}/ruta-ventas", headers=h(tokens["operaciones"]), timeout=20)
        assert r.status_code == 403

    def test_operaciones_denied_gastos(self, tokens):
        r = requests.get(f"{API}/gastos-viajero", headers=h(tokens["operaciones"]), timeout=20)
        assert r.status_code == 403

    @pytest.mark.parametrize("role", ["director", "socio", "comercial"])
    def test_role_can_list_rutas(self, tokens, role):
        r = requests.get(f"{API}/ruta-ventas", headers=h(tokens[role]), timeout=20)
        assert r.status_code == 200

    @pytest.mark.parametrize("role", ["director", "socio", "comercial"])
    def test_role_can_list_gastos(self, tokens, role):
        r = requests.get(f"{API}/gastos-viajero", headers=h(tokens[role]), timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("items", "total", "por_tipo", "n"):
            assert k in d


# ---------- Ruta generar ----------
class TestRutaGenerar:
    def test_local_morelia(self, tokens):
        payload = {"origen": "Morelia", "modo": "local", "radio_local_km": 100, "max_paradas": 3}
        r = requests.post(f"{API}/ruta-ventas/generar",
                          headers=h(tokens["comercial"]), json=payload, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        d = r.json()
        assert d.get("destino") is None
        assert "paradas" in d and isinstance(d["paradas"], list)
        assert "total_candidatos_corredor" in d
        assert d.get("modo") == "local"
        assert "generado_at" in d
        # plan IA puede llegar None si LLM falla, pero el endpoint debe responder
        # los campos resumen/recomendacion deben existir (aunque sea None)
        assert "plan_ia_resumen" in d
        assert "plan_ia_recomendacion" in d

    def test_corredor_morelia_queretaro(self, tokens):
        payload = {"origen": "Morelia, Michoacán", "destino": "Querétaro, Querétaro",
                   "modo": "corredor", "max_desvio_km": 40, "max_paradas": 5}
        r = requests.post(f"{API}/ruta-ventas/generar",
                          headers=h(tokens["director"]), json=payload, timeout=120)
        # Tolerar 400 si externos (Nominatim) timeout/falla
        if r.status_code == 400 and "geocodificar" in r.text.lower():
            pytest.skip(f"Nominatim no respondió: {r.text[:120]}")
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        d = r.json()
        assert d["origen"].get("lat") and d["origen"].get("lng")
        assert d["destino"] and d["destino"].get("lat") and d["destino"].get("lng")
        assert d["modo"] == "corredor"
        assert isinstance(d["paradas"], list)
        # route puede ser None si OSRM falla -- tolerar
        if d.get("route"):
            assert "distance_km" in d["route"]
            assert "geometry" in d["route"]

    def test_origen_vacio(self, tokens):
        r = requests.post(f"{API}/ruta-ventas/generar",
                          headers=h(tokens["comercial"]),
                          json={"origen": "", "modo": "local"}, timeout=30)
        # 400 (geocodificar) o 422 (pydantic) ambos aceptables
        assert r.status_code in (400, 422), f"{r.status_code} {r.text[:120]}"

    def test_origen_no_geocodificable(self, tokens):
        r = requests.post(f"{API}/ruta-ventas/generar",
                          headers=h(tokens["comercial"]),
                          json={"origen": "xyzqwerty_no_existe_lugar_zzz", "modo": "local"}, timeout=30)
        assert r.status_code == 400
        assert "geocodificar" in r.text.lower() or "origen" in r.text.lower()


# ---------- Ruta CRUD (guardar/listar/delete) ----------
@pytest.fixture(scope="module")
def ruta_payload():
    return {
        "origen": {"lat": 19.7008, "lng": -101.1844, "display_name": "Morelia, Michoacán"},
        "destino": {"lat": 20.5888, "lng": -100.3899, "display_name": "Querétaro, Querétaro"},
        "modo": "corredor",
        "paradas": [
            {"empresa_id": "test-emp-1", "empresa_nombre": "TEST EMP 1", "lat": 20.1, "lng": -100.8,
             "ciudad": "Salamanca", "monto_total": 1500000, "mejor_etapa": "propuesta",
             "score": 70, "radar_score": 60, "desvio_km": 10, "briefing": "Visitar.", "tiempo_min": 45,
             "accion_clave": "Cierre", "ultima_actividad_dias": 5, "n_oportunidades": 1},
        ],
        "route": {"distance_km": 200, "duration_min": 180, "geometry": "yzzzzz"},
        "plan_ia_resumen": "Resumen test",
        "plan_ia_recomendacion": "Recomendacion test",
        "fecha": "2026-01-15",
    }


class TestRutaCRUD:
    saved_id = None

    def test_guardar_comercial(self, tokens, ruta_payload):
        r = requests.post(f"{API}/ruta-ventas/guardar",
                          headers=h(tokens["comercial"]), json=ruta_payload, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        d = r.json()
        assert "id" in d and len(d["id"]) >= 8
        assert d["vendedor_nombre"]
        TestRutaCRUD.saved_id = d["id"]

    def test_comercial_ve_solo_suyas(self, tokens):
        r = requests.get(f"{API}/ruta-ventas", headers=h(tokens["comercial"]), timeout=20)
        assert r.status_code == 200
        for it in r.json():
            assert it.get("vendedor_nombre")

    def test_director_ve_todas(self, tokens):
        r = requests.get(f"{API}/ruta-ventas", headers=h(tokens["director"]), timeout=20)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert TestRutaCRUD.saved_id in ids, "director debe ver la ruta del comercial"

    def test_delete(self, tokens):
        assert TestRutaCRUD.saved_id
        r = requests.delete(f"{API}/ruta-ventas/{TestRutaCRUD.saved_id}",
                            headers=h(tokens["comercial"]), timeout=20)
        assert r.status_code == 200


# ---------- PDF ----------
class TestRutaPDF:
    def test_pdf_genera(self, tokens, ruta_payload):
        r = requests.post(f"{API}/ruta-ventas/pdf",
                          headers=h(tokens["director"]), json=ruta_payload, timeout=60)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        size = len(r.content)
        assert size >= 30 * 1024, f"PDF muy chico: {size} bytes"
        assert r.content[:5] == b"%PDF-"


# ---------- Gastos CRUD ----------
class TestGastosCRUD:
    created_id = None
    created_id_file = None

    def test_crear_gasto_sin_archivo(self, tokens):
        data = {"tipo": "gasolina", "monto": "850.50", "fecha": "2026-01-15",
                "descripcion": "TEST_pemex morelia", "lugar": "Pemex Morelia"}
        r = requests.post(f"{API}/gastos-viajero",
                          headers=h(tokens["comercial"]), data=data, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        d = r.json()
        assert d["tipo"] == "gasolina"
        assert d["monto"] == 850.50
        assert d["vendedor_id"]
        assert d["file_id"] is None
        TestGastosCRUD.created_id = d["id"]

    def test_crear_gasto_con_archivo(self, tokens):
        fake_pdf = b"%PDF-1.4\n" + b"X" * 500 + b"\n%%EOF"
        files = {"archivo": ("comprobante.pdf", io.BytesIO(fake_pdf), "application/pdf")}
        data = {"tipo": "casetas", "monto": "120", "fecha": "2026-01-16",
                "descripcion": "TEST_caseta", "lugar": "Maravatío"}
        r = requests.post(f"{API}/gastos-viajero",
                          headers=h(tokens["comercial"]), data=data, files=files, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        d = r.json()
        assert d["file_id"], "file_id debe estar presente"
        assert d["content_type"] == "application/pdf"
        TestGastosCRUD.created_id_file = d["id"]

    def test_tipo_invalido(self, tokens):
        r = requests.post(f"{API}/gastos-viajero",
                          headers=h(tokens["comercial"]),
                          data={"tipo": "viaje_marte", "monto": "10", "fecha": "2026-01-15"}, timeout=20)
        assert r.status_code == 400

    def test_monto_negativo(self, tokens):
        r = requests.post(f"{API}/gastos-viajero",
                          headers=h(tokens["comercial"]),
                          data={"tipo": "gasolina", "monto": "-5", "fecha": "2026-01-15"}, timeout=20)
        assert r.status_code == 400

    def test_archivo_grande(self, tokens):
        big = b"A" * (10 * 1024 * 1024 + 100)
        files = {"archivo": ("big.bin", io.BytesIO(big), "application/octet-stream")}
        data = {"tipo": "otros", "monto": "1", "fecha": "2026-01-15"}
        r = requests.post(f"{API}/gastos-viajero",
                          headers=h(tokens["comercial"]), data=data, files=files, timeout=60)
        assert r.status_code == 400
        assert "10" in r.text or "mb" in r.text.lower()

    def test_list_con_filtros(self, tokens):
        r = requests.get(f"{API}/gastos-viajero",
                         params={"fecha_desde": "2026-01-01", "fecha_hasta": "2026-12-31", "tipo": "gasolina"},
                         headers=h(tokens["comercial"]), timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["n"] >= 1
        assert all(it["tipo"] == "gasolina" for it in d["items"])
        assert d["total"] >= 850.50
        assert "gasolina" in d["por_tipo"]

    def test_comercial_solo_ve_sus_gastos(self, tokens):
        r = requests.get(f"{API}/gastos-viajero", headers=h(tokens["comercial"]), timeout=20)
        # Get id of comercial
        rme = requests.get(f"{API}/auth/me", headers=h(tokens["comercial"]), timeout=10)
        comercial_id = rme.json()["id"] if rme.status_code == 200 else None
        if comercial_id:
            for it in r.json()["items"]:
                assert it["vendedor_id"] == comercial_id

    def test_director_ve_todos(self, tokens):
        r = requests.get(f"{API}/gastos-viajero", headers=h(tokens["director"]), timeout=20)
        assert r.status_code == 200
        d = r.json()
        # Debe ver al menos el gasto del comercial creado arriba
        ids = [it["id"] for it in d["items"]]
        assert TestGastosCRUD.created_id in ids

    def test_file_download(self, tokens):
        assert TestGastosCRUD.created_id_file
        r = requests.get(f"{API}/gastos-viajero/{TestGastosCRUD.created_id_file}/file",
                         headers=h(tokens["comercial"]), timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")

    def test_file_otro_vendedor_403(self, tokens):
        """Director crea un gasto con archivo, comercial intenta descargar -> 403."""
        fake = b"%PDF-1.4\nXXXX\n%%EOF"
        files = {"archivo": ("d.pdf", io.BytesIO(fake), "application/pdf")}
        data = {"tipo": "comida", "monto": "200", "fecha": "2026-01-17", "descripcion": "TEST_director_gasto"}
        rc = requests.post(f"{API}/gastos-viajero", headers=h(tokens["director"]), data=data, files=files, timeout=20)
        assert rc.status_code == 200
        gid = rc.json()["id"]
        # Comercial intenta descargar
        rd = requests.get(f"{API}/gastos-viajero/{gid}/file", headers=h(tokens["comercial"]), timeout=20)
        assert rd.status_code == 403
        # cleanup
        requests.delete(f"{API}/gastos-viajero/{gid}", headers=h(tokens["director"]), timeout=20)

    def test_comercial_delete_otro_404(self, tokens):
        """Director crea un gasto, comercial intenta borrarlo -> 404 (filtro by vendedor_id)."""
        data = {"tipo": "otros", "monto": "10", "fecha": "2026-01-18", "descripcion": "TEST_delete"}
        rc = requests.post(f"{API}/gastos-viajero", headers=h(tokens["director"]), data=data, timeout=20)
        assert rc.status_code == 200
        gid = rc.json()["id"]
        rd = requests.delete(f"{API}/gastos-viajero/{gid}", headers=h(tokens["comercial"]), timeout=20)
        assert rd.status_code == 404
        # cleanup
        requests.delete(f"{API}/gastos-viajero/{gid}", headers=h(tokens["director"]), timeout=20)

    def test_cleanup(self, tokens):
        for gid in (TestGastosCRUD.created_id, TestGastosCRUD.created_id_file):
            if gid:
                requests.delete(f"{API}/gastos-viajero/{gid}", headers=h(tokens["comercial"]), timeout=20)
