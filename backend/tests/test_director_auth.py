"""
Regression tests for director auth after password reset (iteration 11).
Covers: login success/failure, protected endpoint access, IA leads route.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opp-detector.preview.emergentagent.com").rstrip("/")

DIRECTOR_EMAIL = "director@deyma.mx"
DIRECTOR_PW = "Deyma2026!"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def director_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": DIRECTOR_EMAIL,
        "password": DIRECTOR_PW,
    })
    assert r.status_code == 200, f"Director login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


# --- AUTH ---
class TestDirectorAuth:
    def test_login_success_returns_token_and_director_role(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DIRECTOR_EMAIL,
            "password": DIRECTOR_PW,
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str) and len(data["access_token"]) > 20
        assert "user" in data
        u = data["user"]
        assert u["email"] == DIRECTOR_EMAIL
        assert u["role"] == "director"
        assert u.get("active") is True
        assert u.get("failed_attempts", 0) == 0
        assert u.get("locked_until") in (None, "")

    def test_login_wrong_password_returns_401(self, session):
        r = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DIRECTOR_EMAIL,
            "password": "definitely-wrong-pw-XYZ",
        })
        assert r.status_code == 401
        body = r.json()
        # Should not leak token/user
        assert "access_token" not in body
        assert "user" not in body


# --- PROTECTED ENDPOINTS ---
class TestProtectedEndpointsWithDirectorToken:
    def test_condo_stats_returns_200(self, session, director_token):
        r = session.get(
            f"{BASE_URL}/api/condo/stats",
            headers={"Authorization": f"Bearer {director_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        # Validate core fields exist
        for key in ("leads_total", "leads_mega", "alertas_total"):
            assert key in data, f"missing key {key} in /api/condo/stats response"

    def test_condo_stats_without_token_returns_401_or_403(self, session):
        r = session.get(f"{BASE_URL}/api/condo/stats")
        assert r.status_code in (401, 403), f"unexpected status {r.status_code}"

    def test_ia_leads_list_accessible(self, session, director_token):
        r = session.get(
            f"{BASE_URL}/api/ia-leads",
            headers={"Authorization": f"Bearer {director_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
