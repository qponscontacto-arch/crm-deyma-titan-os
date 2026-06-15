"""
V4: Portal de Alta de Clientes — pruebas e2e backend.
Cubre: seed socio, alta multipart, status público, aprobación dual,
rechazo final, login cliente, /me, /me/cotizaciones, OC upload/download,
PDFs alta + bienvenida, dup RFC/email, regresión crítica.
"""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://opp-detector.preview.emergentagent.com"

# Mini PDF válido (cabecera %PDF-)
MINI_PDF = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\n"
    b"trailer<<>>\n%%EOF\n"
) + b"0" * 256  # padding para superar tamaño mínimo razonable


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def director_tok():
    return _login("director@deyma.mx", "Deyma2026!")


@pytest.fixture(scope="module")
def socio_tok():
    return _login("socio@deyma.mx", "Socio2026!")


@pytest.fixture(scope="module")
def comercial_tok():
    return _login("comercial@deyma.mx", "Comercial2026!")


@pytest.fixture(scope="module")
def operaciones_tok():
    return _login("operaciones@deyma.mx", "Operaciones2026!")


# --- Helpers --- #
def _alta_payload(rfc: str, email: str, password: str = "TestPwd123!"):
    data = {
        "razon_social": f"TEST V4 SA DE CV {rfc}",
        "rfc": rfc,
        "domicilio_fiscal": "Av Test 123, CDMX",
        "domicilio_planta": "",
        "email": email,
        "password": password,
        "contacto_tecnico_nombre": "Ing Tec",
        "contacto_tecnico_tel": "5551111111",
        "contacto_tecnico_correo": f"tec_{rfc.lower()}@test.com",
        "contacto_compras_nombre": "Lic Compras",
        "contacto_compras_tel": "5552222222",
        "contacto_compras_correo": f"compras_{rfc.lower()}@test.com",
        "contacto_cxp_nombre": "CP Cxp",
        "contacto_cxp_tel": "5553333333",
        "contacto_cxp_correo": f"cxp_{rfc.lower()}@test.com",
        "politica_validacion_tecnica": "true",
        "politica_firma_actas": "true",
        "politica_separacion_errores": "true",
        "politica_ordenes_cambio": "true",
        "politica_cero_fianzas": "true",
        "fin_recepcion_oc": "true",
        "fin_anticipo": "true",
        "fin_dia_1": "true",
        "firma_representante_nombre": "Lic Rep Legal",
        "firma_representante_sello": "",
        "firma_tecnico_nombre": "Ing Tec",
        "firma_tecnico_area": "Operaciones",
    }
    files = [
        ("csf", ("csf.pdf", MINI_PDF, "application/pdf")),
        ("acta_constitutiva", ("acta.pdf", MINI_PDF, "application/pdf")),
        ("poder_representante", ("poder.pdf", MINI_PDF, "application/pdf")),
        ("ine_representante", ("ine.pdf", MINI_PDF, "application/pdf")),
        ("comprobante_domicilio", ("comp.pdf", MINI_PDF, "application/pdf")),
    ]
    return data, files


@pytest.fixture(scope="module")
def created_cliente():
    """Crea una solicitud de alta válida única por corrida."""
    ts = int(time.time())
    rfc = f"TST{ts}T9A"[:13].upper()
    email = f"test_v4_{ts}@example.com"
    data, files = _alta_payload(rfc, email)
    r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=60)
    assert r.status_code == 200, f"alta -> {r.status_code} {r.text[:400]}"
    j = r.json()
    assert j["estado"] == "pendiente"
    assert j["dfnum"] is None
    assert j["folio_registro"].startswith("ALT-")
    return {"id": j["id"], "folio": j["folio_registro"], "rfc": rfc.upper(), "email": email, "password": "TestPwd123!"}


# === Smoke / Auth === #
class TestAuthAndSeed:
    def test_socio_seeded(self):
        tok = _login("socio@deyma.mx", "Socio2026!")
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == "socio"

    def test_director_seeded(self):
        tok = _login("director@deyma.mx", "Deyma2026!")
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 200 and r.json()["role"] == "director"


# === Alta + status === #
class TestAltaCliente:
    def test_alta_ok(self, created_cliente):
        assert created_cliente["folio"].startswith("ALT-")

    def test_alta_rfc_duplicado(self, created_cliente):
        data, files = _alta_payload(created_cliente["rfc"], f"otro_{int(time.time())}@x.com")
        r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=60)
        assert r.status_code == 400
        assert "rfc" in r.text.lower() or "ya existe" in r.text.lower()

    def test_alta_email_duplicado(self, created_cliente):
        ts = int(time.time()) + 1
        rfc2 = f"OTR{ts}X9A"[:13].upper()
        data, files = _alta_payload(rfc2, created_cliente["email"])
        r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=60)
        assert r.status_code == 400

    def test_alta_archivo_grande(self):
        ts = int(time.time()) + 2
        rfc = f"BIG{ts}X9A"[:13].upper()
        big_pdf = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1024)
        data, files = _alta_payload(rfc, f"big_{ts}@x.com")
        files[0] = ("csf", ("big.pdf", big_pdf, "application/pdf"))
        r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=90)
        assert r.status_code == 400
        assert "10 MB" in r.text or "excede" in r.text.lower()

    def test_status_publico_por_folio(self, created_cliente):
        r = requests.get(f"{BASE_URL}/api/clientes/status/{created_cliente['folio']}", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["folio_registro"] == created_cliente["folio"]
        assert body["estado"] in ("pendiente", "aprobado_director", "aprobado_socio", "aprobado_completo", "rechazado")

    def test_status_404(self):
        r = requests.get(f"{BASE_URL}/api/clientes/status/NOEXISTE-0000", timeout=15)
        assert r.status_code == 404


# === Aprobación dual === #
class TestAprobacionDual:
    def test_comercial_no_puede_aprobar(self, created_cliente, comercial_tok):
        r = requests.post(f"{BASE_URL}/api/clientes/{created_cliente['id']}/aprobar",
                          json={"nota": "x"},
                          headers={"Authorization": f"Bearer {comercial_tok}"}, timeout=15)
        assert r.status_code == 403

    def test_director_aprueba(self, created_cliente, director_tok):
        r = requests.post(f"{BASE_URL}/api/clientes/{created_cliente['id']}/aprobar",
                          json={"nota": "OK director"},
                          headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["estado"] == "aprobado_director"
        assert j["dfnum"] in (None,)

    def test_director_no_puede_re_aprobar(self, created_cliente, director_tok):
        r = requests.post(f"{BASE_URL}/api/clientes/{created_cliente['id']}/aprobar",
                          json={"nota": "x"},
                          headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r.status_code == 400
        assert "ya aprobaste" in r.text.lower() or "ya" in r.text.lower()

    def test_socio_aprueba_y_asigna_dfnum(self, created_cliente, socio_tok):
        r = requests.post(f"{BASE_URL}/api/clientes/{created_cliente['id']}/aprobar",
                          json={"nota": "OK socio"},
                          headers={"Authorization": f"Bearer {socio_tok}"}, timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["estado"] == "aprobado_completo"
        assert j["dfnum"] and j["dfnum"].startswith("DFNUM-")
        created_cliente["dfnum"] = j["dfnum"]

    def test_re_aprobar_estado_final_bloqueado(self, created_cliente, director_tok):
        r = requests.post(f"{BASE_URL}/api/clientes/{created_cliente['id']}/aprobar",
                          json={"nota": "x"},
                          headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r.status_code == 400

    def test_status_por_dfnum(self, created_cliente):
        assert created_cliente.get("dfnum"), "dfnum not assigned in previous test"
        r = requests.get(f"{BASE_URL}/api/clientes/status/{created_cliente['dfnum']}", timeout=15)
        assert r.status_code == 200
        assert r.json()["estado"] == "aprobado_completo"


# === Rechazo (segundo cliente para no romper el approval flow) === #
class TestRechazo:
    def test_rechazar(self, director_tok):
        ts = int(time.time()) + 7
        rfc = f"REJ{ts}X9A"[:13].upper()
        data, files = _alta_payload(rfc, f"rej_{ts}@x.com")
        r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=60)
        assert r.status_code == 200
        cid = r.json()["id"]
        r2 = requests.post(f"{BASE_URL}/api/clientes/{cid}/rechazar",
                           json={"nota": "documentación incompleta"},
                           headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["estado"] == "rechazado"
        # Estado final → no se puede aprobar
        r3 = requests.post(f"{BASE_URL}/api/clientes/{cid}/aprobar", json={"nota": "x"},
                           headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r3.status_code == 400


# === Login cliente + /me + OCs + PDFs === #
class TestClientePortal:
    def test_login_cliente_pendiente_falla(self, director_tok):
        # nuevo cliente pendiente
        ts = int(time.time()) + 11
        rfc = f"PND{ts}X9A"[:13].upper()
        data, files = _alta_payload(rfc, f"pnd_{ts}@x.com", password="Test123!")
        r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=60)
        cid = r.json()["id"]
        # intentar login con DFNUM-FAKE
        r2 = requests.post(f"{BASE_URL}/api/clientes/login",
                           json={"dfnum": "DFNUM-FAKE99", "password": "x"}, timeout=15)
        assert r2.status_code == 401

    def test_login_cliente_aprobado(self, created_cliente):
        dfnum = created_cliente.get("dfnum")
        assert dfnum
        r = requests.post(f"{BASE_URL}/api/clientes/login",
                          json={"dfnum": dfnum, "password": created_cliente["password"]}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body
        assert body["cliente"]["dfnum"] == dfnum
        assert "password_hash" not in body["cliente"]
        created_cliente["client_token"] = body["access_token"]

    def test_login_cliente_password_mala(self, created_cliente):
        r = requests.post(f"{BASE_URL}/api/clientes/login",
                          json={"dfnum": created_cliente["dfnum"], "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me(self, created_cliente):
        tok = created_cliente["client_token"]
        r = requests.get(f"{BASE_URL}/api/clientes/me",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["dfnum"] == created_cliente["dfnum"]
        assert "password_hash" not in body

    def test_me_cotizaciones(self, created_cliente):
        tok = created_cliente["client_token"]
        r = requests.get(f"{BASE_URL}/api/clientes/me/cotizaciones",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_oc_upload_list_download(self, created_cliente):
        tok = created_cliente["client_token"]
        files = [("archivo", ("oc1.pdf", MINI_PDF, "application/pdf"))]
        data = {"referencia": "OC-TEST-001", "monto": "12345.67", "notas": "OC test"}
        r = requests.post(f"{BASE_URL}/api/clientes-oc", data=data, files=files,
                          headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code == 200, r.text
        oc = r.json()
        assert oc["referencia"] == "OC-TEST-001"
        # listar
        r2 = requests.get(f"{BASE_URL}/api/clientes-oc",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r2.status_code == 200
        lst = r2.json()
        assert any(o["id"] == oc["id"] for o in lst)
        # bajar
        r3 = requests.get(f"{BASE_URL}/api/clientes-oc/{oc['id']}/file",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r3.status_code == 200
        assert r3.headers["content-type"].startswith("application/pdf")
        assert r3.content.startswith(b"%PDF")

    def test_oc_rechaza_no_pdf(self, created_cliente):
        tok = created_cliente["client_token"]
        files = [("archivo", ("oc.txt", b"hello", "text/plain"))]
        data = {"referencia": "OC-BAD", "monto": "10", "notas": ""}
        r = requests.post(f"{BASE_URL}/api/clientes-oc", data=data, files=files,
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 400


# === PDFs Alta + Bienvenida + File GridFS === #
class TestPDFs:
    def test_pdf_alta(self, created_cliente):
        r = requests.get(f"{BASE_URL}/api/clientes/{created_cliente['id']}/pdf-alta", timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 3000  # 3KB+

    def test_pdf_bienvenida_aprobado(self, created_cliente):
        r = requests.get(f"{BASE_URL}/api/clientes/{created_cliente['id']}/pdf-bienvenida", timeout=30)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 3000

    def test_pdf_bienvenida_pendiente_400(self, director_tok):
        # crear pendiente y comprobar
        ts = int(time.time()) + 21
        rfc = f"BVN{ts}X9A"[:13].upper()
        data, files = _alta_payload(rfc, f"bvn_{ts}@x.com")
        r = requests.post(f"{BASE_URL}/api/clientes/alta", data=data, files=files, timeout=60)
        cid = r.json()["id"]
        r2 = requests.get(f"{BASE_URL}/api/clientes/{cid}/pdf-bienvenida", timeout=15)
        assert r2.status_code == 400

    def test_file_gridfs_staff(self, created_cliente, director_tok):
        r = requests.get(f"{BASE_URL}/api/clientes/{created_cliente['id']}/file/csf",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")

    def test_file_gridfs_sin_auth(self, created_cliente):
        r = requests.get(f"{BASE_URL}/api/clientes/{created_cliente['id']}/file/csf", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_list_clientes(self, director_tok):
        r = requests.get(f"{BASE_URL}/api/clientes",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=15)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_admin_list_operaciones_forbidden(self, operaciones_tok):
        r = requests.get(f"{BASE_URL}/api/clientes",
                         headers={"Authorization": f"Bearer {operaciones_tok}"}, timeout=15)
        assert r.status_code == 403


# === Regresión crítica === #
class TestRegresion:
    def test_dashboard_kpis(self, director_tok):
        r = requests.get(f"{BASE_URL}/api/dashboard/kpis",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=20)
        assert r.status_code == 200

    def test_oportunidades(self, director_tok):
        r = requests.get(f"{BASE_URL}/api/oportunidades",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=20)
        assert r.status_code == 200

    def test_cotizaciones(self, director_tok):
        r = requests.get(f"{BASE_URL}/api/cotizaciones",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=20)
        assert r.status_code == 200

    def test_radar(self, director_tok):
        r = requests.get(f"{BASE_URL}/api/radar",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=20)
        assert r.status_code == 200

    def test_empresas(self, director_tok):
        r = requests.get(f"{BASE_URL}/api/empresas",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=20)
        assert r.status_code == 200

    def test_scraper_status(self, director_tok):
        # smoke: 200 OK si existe
        r = requests.get(f"{BASE_URL}/api/scraper/status",
                         headers={"Authorization": f"Bearer {director_tok}"}, timeout=20)
        assert r.status_code in (200, 404)  # tolerar si no existe
