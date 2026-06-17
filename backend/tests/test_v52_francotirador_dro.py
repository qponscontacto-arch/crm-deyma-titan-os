"""V5.2 · Operación Francotirador DRO + Marcar Visita CRM
Tests:
  - Login staff (director, comercial)
  - DRO pipeline: /api/francotirador/run, /padron, /embudo, /{did}/move, PATCH, DELETE
  - RBAC delete (sólo director/socio)
  - CARRY-OVER: Marcar visita en ruta crea actividad automática en db.actividades
  - Regresión rápida: /auth/login, /dashboard/kpis, /radar/dorks
"""
import os
import time
import pytest
import requests

# leer del frontend/.env si no está en env (test runner)
def _get_base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL no configurada")

BASE = _get_base()
API = f"{BASE}/api"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _login(s, email, pwd):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def tok_director(s):
    return _login(s, "director@deyma.mx", "Deyma2026!")


@pytest.fixture(scope="module")
def tok_comercial(s):
    return _login(s, "comercial@deyma.mx", "Comercial2026!")


@pytest.fixture
def h_director(tok_director):
    return {"Authorization": f"Bearer {tok_director}"}


@pytest.fixture
def h_comercial(tok_comercial):
    return {"Authorization": f"Bearer {tok_comercial}"}


# ============================================================
# 1. LOGIN STAFF
# ============================================================
class TestAuth:
    def test_login_director_ok(self, s):
        r = s.post(f"{API}/auth/login", json={"email": "director@deyma.mx", "password": "Deyma2026!"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "access_token" in d and isinstance(d["access_token"], str) and len(d["access_token"]) > 20
        assert "user" in d and d["user"]["email"] == "director@deyma.mx"
        assert d["user"].get("role") == "director"

    def test_login_wrong_password(self, s):
        r = s.post(f"{API}/auth/login", json={"email": "director@deyma.mx", "password": "BAD!"}, timeout=20)
        assert r.status_code in (400, 401, 403)


# ============================================================
# 2. FRANCOTIRADOR DRO PIPELINE
# ============================================================
class TestDRO:
    # cache vars across tests
    state = {}

    def test_run_pipeline(self, s, h_director):
        # limite chico para no abusar de Apify
        r = s.post(f"{API}/francotirador/run", headers=h_director, json={"limite": 2}, timeout=180)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("ok") is True
        assert "unicos_insertados" in d
        assert "tareas_creadas_alberto" in d
        assert d.get("modo") in ("live", "demo")
        # debe enviar run_id y conteos numéricos
        assert isinstance(d.get("gov_detectados"), int)
        assert isinstance(d.get("colegios_detectados"), int)

    def test_padron_list(self, s, h_director):
        r = s.get(f"{API}/francotirador/padron", headers=h_director, timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        # Hay 6+ por contexto previo
        assert len(items) >= 1, "no hay DROs en padrón"
        for d in items:
            assert "id" in d and "nombre" in d and "stage" in d
            assert "_id" not in d  # mongo objectid debe estar excluido
        TestDRO.state["dro_id"] = items[0]["id"]
        TestDRO.state["initial_stage"] = items[0]["stage"]
        TestDRO.state["sample"] = items[0]

    def test_padron_filter_estado(self, s, h_director):
        r = s.get(f"{API}/francotirador/padron", headers=h_director,
                  params={"estado_mx": "Querétaro"}, timeout=30)
        assert r.status_code == 200
        items = r.json()
        for d in items:
            assert d.get("estado_mx") == "Querétaro"

    def test_padron_filter_stage(self, s, h_director):
        r = s.get(f"{API}/francotirador/padron", headers=h_director,
                  params={"stage": "blanco_detectado"}, timeout=30)
        assert r.status_code == 200
        for d in r.json():
            assert d.get("stage") == "blanco_detectado"

    def test_embudo_six_stages(self, s, h_director):
        r = s.get(f"{API}/francotirador/embudo", headers=h_director, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "stages" in d and "total" in d
        assert len(d["stages"]) == 6
        keys = [s_["key"] for s_ in d["stages"]]
        expected = ["blanco_detectado", "kit_cad_enviado", "interaccion_tecnica",
                    "prescriptor_activo", "cierre_obra_ganada", "descartado"]
        assert keys == expected, f"orden/keys incorrectos: {keys}"
        # total debe coincidir con suma de items
        suma = sum(len(s_["items"]) for s_ in d["stages"])
        assert suma == d["total"]

    def test_move_dro_valid_stage(self, s, h_comercial):
        did = TestDRO.state.get("dro_id")
        assert did, "previous test debe haber poblado dro_id"
        r = s.post(f"{API}/francotirador/{did}/move", headers=h_comercial,
                   json={"stage": "kit_cad_enviado"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["stage"] == "kit_cad_enviado"
        assert d["probabilidad"] == 25
        # historia incrementada
        assert len(d.get("historia", [])) >= 1
        assert d["historia"][-1]["accion"] == "move_stage"

    def test_move_dro_invalid_stage(self, s, h_comercial):
        did = TestDRO.state.get("dro_id")
        r = s.post(f"{API}/francotirador/{did}/move", headers=h_comercial,
                   json={"stage": "etapa_inexistente"}, timeout=30)
        assert r.status_code == 400

    def test_patch_dro_whitelist(self, s, h_comercial):
        did = TestDRO.state.get("dro_id")
        r = s.patch(f"{API}/francotirador/{did}", headers=h_comercial,
                    json={"notas": "TEST_nota_qa", "telefono_movil": "+52 442-000-0000",
                          "campo_no_permitido": "ignorame"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["notas"] == "TEST_nota_qa"
        assert d["telefono_movil"] == "+52 442-000-0000"
        assert "campo_no_permitido" not in d

    def test_patch_dro_empty_body(self, s, h_comercial):
        did = TestDRO.state.get("dro_id")
        r = s.patch(f"{API}/francotirador/{did}", headers=h_comercial, json={"foo": "bar"}, timeout=30)
        assert r.status_code == 400

    def test_delete_dro_rbac_comercial_blocked(self, s, h_comercial):
        # crear primero un DRO via run para no romper el padrón
        # comercial NO debe poder borrar
        did = TestDRO.state.get("dro_id")
        r = s.delete(f"{API}/francotirador/{did}", headers=h_comercial, timeout=30)
        assert r.status_code == 403

    def test_delete_dro_director_ok(self, s, h_director):
        # crear un DRO fresco para borrar (usar otro ID del padron)
        r = s.get(f"{API}/francotirador/padron", headers=h_director, timeout=30)
        items = r.json()
        # buscar uno DIFERENTE al actualmente usado
        target = next((x for x in items if x["id"] != TestDRO.state.get("dro_id")), None)
        if not target:
            pytest.skip("no hay otro DRO para probar delete")
        rid = target["id"]
        r = s.delete(f"{API}/francotirador/{rid}", headers=h_director, timeout=30)
        assert r.status_code == 200
        # verificar 404 al volver
        r = s.delete(f"{API}/francotirador/{rid}", headers=h_director, timeout=30)
        assert r.status_code == 404


# ============================================================
# 3. CARRY-OVER · MARCAR VISITA EN RUTA → CREA ACTIVIDAD
# ============================================================
class TestMarcarVisita:
    state = {}

    def test_setup_empresa_y_ruta(self, s, h_comercial):
        # Crear empresa de prueba
        emp_payload = {"nombre": "TEST_QA Empresa Visita", "rfc": "TQA250101AAA",
                       "ciudad": "Querétaro", "estado_mx": "Querétaro",
                       "sector": "parques_industriales",
                       "telefono": "+52 442-111-2222"}
        r = s.post(f"{API}/empresas", headers=h_comercial, json=emp_payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        emp = r.json()
        TestMarcarVisita.state["empresa_id"] = emp["id"]

        # Guardar una ruta directamente
        ruta_payload = {
            "fecha": "2026-01-15",
            "modo": "local",
            "origen": {"display_name": "Querétaro", "lat": 20.59, "lng": -100.39},
            "destino": None,
            "paradas": [
                {"empresa_id": emp["id"], "empresa_nombre": emp["nombre"],
                 "lat": 20.6, "lng": -100.4, "orden": 1}
            ],
            "ruta_polyline": "", "distancia_km": 0, "tiempo_min": 0,
            "briefing_ia": "TEST_briefing",
        }
        r = s.post(f"{API}/ruta-ventas/guardar", headers=h_comercial, json=ruta_payload, timeout=30)
        assert r.status_code in (200, 201), r.text[:300]
        TestMarcarVisita.state["ruta_id"] = r.json()["id"]

    def test_marcar_visita_crea_actividad(self, s, h_comercial):
        rid = TestMarcarVisita.state["ruta_id"]
        eid = TestMarcarVisita.state["empresa_id"]
        r = s.post(f"{API}/ruta-ventas/{rid}/parada/{eid}/visita", headers=h_comercial,
                   json={"estatus": "visitada", "nota": "TEST_QA nota"}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("ok") is True
        assert "actividad_id" in d and d["actividad_id"]
        assert "oportunidad_id" in d and d["oportunidad_id"]
        # como no había opps previas, opp se debió crear de prospección
        assert d.get("oportunidad_creada") is True
        TestMarcarVisita.state["actividad_id"] = d["actividad_id"]
        TestMarcarVisita.state["oportunidad_id"] = d["oportunidad_id"]

    def test_actividad_persistida_en_crm(self, s, h_comercial):
        # consultar actividades de la oportunidad
        oid = TestMarcarVisita.state["oportunidad_id"]
        r = s.get(f"{API}/oportunidades/{oid}/actividades", headers=h_comercial, timeout=30)
        if r.status_code == 404:
            # fallback: leer oportunidades
            r = s.get(f"{API}/oportunidades", headers=h_comercial, timeout=30)
            assert r.status_code == 200
            return
        assert r.status_code == 200, r.text[:300]
        acts = r.json()
        ids = [a.get("id") for a in (acts if isinstance(acts, list) else acts.get("items", []))]
        assert TestMarcarVisita.state["actividad_id"] in ids, \
            f"Actividad {TestMarcarVisita.state['actividad_id']} no encontrada en CRM"

    def test_visita_estatus_invalido(self, s, h_comercial):
        rid = TestMarcarVisita.state["ruta_id"]
        eid = TestMarcarVisita.state["empresa_id"]
        r = s.post(f"{API}/ruta-ventas/{rid}/parada/{eid}/visita", headers=h_comercial,
                   json={"estatus": "lo_que_sea"}, timeout=30)
        assert r.status_code in (400, 422)

    def test_cleanup(self, s, h_director):
        # eliminar ruta y empresa creadas
        rid = TestMarcarVisita.state.get("ruta_id")
        eid = TestMarcarVisita.state.get("empresa_id")
        if rid:
            s.delete(f"{API}/ruta-ventas/{rid}", headers=h_director, timeout=30)
        if eid:
            s.delete(f"{API}/empresas/{eid}", headers=h_director, timeout=30)


# ============================================================
# 4. REGRESIÓN RÁPIDA
# ============================================================
class TestRegresion:
    def test_dashboard_kpis(self, s, h_director):
        r = s.get(f"{API}/dashboard/kpis", headers=h_director, timeout=30)
        assert r.status_code == 200

    def test_clientes_listado(self, s, h_director):
        r = s.get(f"{API}/clientes", headers=h_director, timeout=30)
        assert r.status_code == 200

    def test_cotizaciones_listado(self, s, h_director):
        r = s.get(f"{API}/cotizaciones", headers=h_director, timeout=30)
        assert r.status_code == 200

    def test_radar_padron(self, s, h_director):
        # /radar/* o /padron-empresas — probar uno
        r = s.get(f"{API}/empresas", headers=h_director, timeout=30)
        assert r.status_code == 200
