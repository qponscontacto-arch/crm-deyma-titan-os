"""V4.7 PDF Membrete Tests
Validates that GET /api/cotizaciones/{cid}/pdf supports marca=deyma|frecciamd,
embeds header images, and includes 10 observaciones + correct footer per marca.
Also smoke regression on key endpoints.
"""
import os
import io
import subprocess
import tempfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opp-detector.preview.emergentagent.com").rstrip("/")
DIRECTOR_EMAIL = "director@deyma.mx"
DIRECTOR_PASSWORD = "Deyma2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def cot_id(headers):
    """Return id of an existing cotizacion (any)."""
    r = requests.get(f"{BASE_URL}/api/cotizaciones", headers=headers, timeout=15)
    assert r.status_code == 200, f"list cotizaciones failed: {r.status_code}"
    items = r.json()
    if not items:
        pytest.skip("No existing cotizaciones to test PDF generation")
    # Prefer item with items > 0
    target = next((c for c in items if c.get("items")), items[0])
    return target["id"], target.get("folio", "")


def _pdftotext(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        path = f.name
    try:
        out = subprocess.check_output(["pdftotext", "-layout", path, "-"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    finally:
        os.unlink(path)


# ---------- 1. PDF marca=deyma ----------
class TestPdfDeyma:
    def test_pdf_deyma_200_and_headers(self, headers, cot_id):
        cid, folio = cot_id
        r = requests.get(f"{BASE_URL}/api/cotizaciones/{cid}/pdf?marca=deyma",
                         headers=headers, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert "DEYMA" in cd, f"Content-Disposition missing DEYMA: {cd}"
        assert len(r.content) >= 50 * 1024, f"PDF too small ({len(r.content)} bytes) - image probably not embedded"

    def test_pdf_deyma_content(self, headers, cot_id):
        cid, folio = cot_id
        r = requests.get(f"{BASE_URL}/api/cotizaciones/{cid}/pdf?marca=deyma",
                         headers=headers, timeout=30)
        assert r.status_code == 200
        text = _pdftotext(r.content)
        # folio
        if folio:
            assert folio in text, f"folio {folio} missing from PDF text"
        # tabla headers
        for kw in ("CONCEPTO", "UNIDAD", "CÓDIGO", "TOTAL"):
            assert kw in text, f"keyword '{kw}' missing in PDF text"
        # observaciones (3 representativas)
        assert "Para iniciar el trabajo requeriremos orden de compra" in text
        assert "Vigencia de cotización" in text
        assert "retroalimentación" in text or "retroalimentacion" in text
        # Footer DEYMA razón social
        assert "DEYMA CONSTRUCCIONES S.A. DE C.V." in text


# ---------- 2. PDF marca=frecciamd ----------
class TestPdfFrecciaMD:
    def test_pdf_frecciamd_200_and_headers(self, headers, cot_id):
        cid, folio = cot_id
        r = requests.get(f"{BASE_URL}/api/cotizaciones/{cid}/pdf?marca=frecciamd",
                         headers=headers, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert "FRECCIAMD" in cd, f"Content-Disposition missing FRECCIAMD: {cd}"
        assert len(r.content) >= 50 * 1024, f"PDF too small ({len(r.content)} bytes)"

    def test_pdf_frecciamd_footer(self, headers, cot_id):
        cid, _ = cot_id
        r = requests.get(f"{BASE_URL}/api/cotizaciones/{cid}/pdf?marca=frecciamd",
                         headers=headers, timeout=30)
        assert r.status_code == 200
        text = _pdftotext(r.content)
        assert "FRECCIA MD S.A. DE C.V." in text
        # Ensure DEYMA footer not present (mutually exclusive)
        assert "DEYMA CONSTRUCCIONES S.A. DE C.V." not in text, "FRECCIAMD PDF should NOT contain DEYMA razón social"


# ---------- 3. PDF default + invalid ----------
class TestPdfDefaults:
    def test_pdf_default_marca_is_deyma(self, headers, cot_id):
        cid, _ = cot_id
        r = requests.get(f"{BASE_URL}/api/cotizaciones/{cid}/pdf",
                         headers=headers, timeout=30)
        assert r.status_code == 200
        cd = r.headers.get("content-disposition", "")
        assert "DEYMA" in cd

    def test_pdf_invalid_marca_returns_400(self, headers, cot_id):
        cid, _ = cot_id
        r = requests.get(f"{BASE_URL}/api/cotizaciones/{cid}/pdf?marca=otra",
                         headers=headers, timeout=15)
        assert r.status_code == 400
        body = r.json()
        detail = body.get("detail", "")
        assert "marca" in detail.lower()
        assert "deyma" in detail.lower() and "frecciamd" in detail.lower()


# ---------- 4. Regression: aprobar_enviar still works with default PDF ----------
class TestRegresionEnviar:
    def test_enviar_endpoint_alive(self, headers, cot_id):
        cid, _ = cot_id
        # We don't want to mutate state if cot is already aprobada/enviada,
        # but we just test the endpoint responds (200 or 4xx with reasonable detail).
        r = requests.post(f"{BASE_URL}/api/cotizaciones/{cid}/enviar",
                          headers=headers,
                          json={"email_destino": "qa+test@deyma.mx", "asunto": "QA test", "mensaje": "Test"},
                          timeout=30)
        # Accept 200 (sent/mocked) or 400/409 (status not allowed) - just ensure not 500
        assert r.status_code != 500, f"enviar endpoint 500: {r.text[:300]}"


# ---------- 5. Smoke regression ----------
class TestSmokeRegresion:
    def test_dashboard_kpis(self, headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/kpis", headers=headers, timeout=15)
        assert r.status_code == 200

    def test_cotizaciones_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/cotizaciones", headers=headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_empresas_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/empresas", headers=headers, timeout=15)
        assert r.status_code == 200

    def test_auth_login_again(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD},
                          timeout=10)
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_clientes_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/clientes", headers=headers, timeout=15)
        assert r.status_code == 200

    def test_rh_empleados_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/rh/empleados", headers=headers, timeout=15)
        assert r.status_code == 200
