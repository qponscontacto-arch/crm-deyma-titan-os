from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ----------------------------------------------------------------------------
# DB & app setup
# ----------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="DEYMA RADAR API", version="1.0.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

JWT_ALGO = "HS256"
JWT_SECRET = os.environ['JWT_SECRET']
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("deyma")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ----------------------------------------------------------------------------
# Auth utils
# ----------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": now_utc() + timedelta(hours=12),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def require_roles(*roles: str):
    async def guard(user: dict = Depends(get_current_user)) -> dict:
        if roles and user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return user
    return guard


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
Role = Literal["director", "comercial", "operaciones"]
Sector = Literal["nearshoring", "parques_industriales", "cedis_logistica", "manufactura", "data_centers", "expansion_planta", "otro"]
Stage = Literal["prospeccion", "calificada", "propuesta", "negociacion", "ganada", "perdida"]
Hotness = Literal["hot", "warm", "cold"]


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Role = "comercial"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role
    created_at: str


class EmpresaIn(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    sector: Sector
    ciudad: str = "Querétaro"
    estado: str = "Querétaro"
    sitio_web: Optional[str] = None
    notas: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class Empresa(EmpresaIn):
    id: str
    created_at: str


class ContactoIn(BaseModel):
    empresa_id: str
    nombre: str
    puesto: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None


class Contacto(ContactoIn):
    id: str
    created_at: str


class OportunidadIn(BaseModel):
    empresa_id: str
    titulo: str
    sector: Sector
    descripcion: str
    monto_estimado: float
    stage: Stage = "prospeccion"
    probabilidad: int = 20
    fecha_cierre: Optional[str] = None
    owner_id: Optional[str] = None


class Oportunidad(OportunidadIn):
    id: str
    score: int = 0
    hotness: Hotness = "cold"
    score_reasons: List[str] = []
    created_at: str
    updated_at: str


class ProyectoRadarIn(BaseModel):
    titulo: str
    fuente: str  # licitacion, noticia, referencia, prospección
    sector: Sector
    ciudad: str
    estado: str
    monto_estimado: float
    descripcion: str
    url_fuente: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class ProyectoRadar(ProyectoRadarIn):
    id: str
    score: int = 0
    hotness: Hotness = "cold"
    score_reasons: List[str] = []
    detected_at: str


class CotizacionItem(BaseModel):
    descripcion: str
    cantidad: float
    unidad: str = "m2"
    precio_unitario: float

    @property
    def subtotal(self) -> float:
        return round(self.cantidad * self.precio_unitario, 2)


class CotizacionIn(BaseModel):
    empresa_id: str
    proyecto_titulo: str
    items: List[CotizacionItem]
    iva_pct: float = 16.0
    notas: Optional[str] = None
    validez_dias: int = 15


class Cotizacion(BaseModel):
    id: str
    folio: str
    empresa_id: str
    proyecto_titulo: str
    items: List[CotizacionItem]
    subtotal: float
    iva_pct: float
    iva_monto: float
    total: float
    notas: Optional[str] = None
    validez_dias: int
    estado: Literal["borrador", "enviada", "aceptada", "rechazada"] = "borrador"
    owner_id: str
    created_at: str


class ObraIn(BaseModel):
    empresa_id: str
    cotizacion_id: Optional[str] = None
    nombre: str
    monto_contratado: float
    fecha_inicio: str
    fecha_fin_estimada: str
    estado: Literal["planeacion", "ejecucion", "pausada", "completada"] = "planeacion"
    avance_pct: int = 0
    ciudad: str
    estado_geo: str = "Querétaro"


class Obra(ObraIn):
    id: str
    created_at: str


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
async def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


def hotness_from_score(score: int) -> Hotness:
    if score >= 75:
        return "hot"
    if score >= 50:
        return "warm"
    return "cold"


# ----------------------------------------------------------------------------
# AI service (Emergent LLM Key, GPT-5.2)
# ----------------------------------------------------------------------------
async def _llm_call(system: str, user_text: str, session_id: str = None) -> str:
    """Single-shot LLM call using emergentintegrations + GPT-5.2."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        logger.exception("emergentintegrations import error")
        raise HTTPException(status_code=500, detail=f"LLM lib error: {e}")
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY no configurada")
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id or new_id(),
        system_message=system,
    ).with_model("openai", "gpt-5.2")
    msg = UserMessage(text=user_text)
    try:
        resp = await asyncio.wait_for(chat.send_message(msg), timeout=45.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout LLM (45s)")
    if isinstance(resp, str):
        return resp
    # fallback
    return str(resp)


def _parse_json_block(text: str) -> dict:
    """Extract first JSON object/array from a text response."""
    import json
    import re
    text = text.strip()
    # remove fences
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # find first { ... }
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"No JSON in response: {text[:200]}")
    return json.loads(m.group(0))


async def ai_score_opportunity(titulo: str, sector: str, descripcion: str, monto: float) -> dict:
    system = (
        "Eres un analista comercial senior de DEYMA, constructora mexicana especializada en pisos industriales, "
        "concreto hidráulico, pavimentación, mantenimiento industrial y canastillas, con foco en Querétaro y el Bajío. "
        "Evalúas oportunidades según: encaje sectorial (nearshoring, parques industriales, CEDIS, manufactura, data centers, "
        "expansión de planta), monto, urgencia y región. Respondes SOLO en JSON estricto."
    )
    user = (
        f"Evalúa la siguiente oportunidad y devuelve JSON con campos: "
        f'{{"score": int 0-100, "hotness": "hot|warm|cold", "reasons": [3 razones cortas en español]}}.\n\n'
        f"Título: {titulo}\nSector: {sector}\nMonto MXN: {monto}\nDescripción: {descripcion}"
    )
    text = await _llm_call(system, user)
    data = _parse_json_block(text)
    score = max(0, min(100, int(data.get("score", 0))))
    return {
        "score": score,
        "hotness": data.get("hotness") or hotness_from_score(score),
        "reasons": data.get("reasons", [])[:5],
    }


async def ai_executive_summary(items: List[dict]) -> str:
    system = (
        "Eres el asistente del Director General de DEYMA. Generas resúmenes ejecutivos breves, "
        "claros y accionables en español neutro mexicano. Sin emojis. 4-6 oraciones."
    )
    payload = "\n".join(
        f"- {it.get('titulo','(s/t)')} | Sector: {it.get('sector','-')} | Monto MXN {it.get('monto_estimado',0):,.0f} | Score {it.get('score',0)} | Etapa {it.get('stage','-')}"
        for it in items[:20]
    )
    user = f"Genera un resumen ejecutivo del pipeline comercial actual:\n{payload}"
    return (await _llm_call(system, user)).strip()


async def ai_followup_email(empresa: str, contacto: str, titulo: str, descripcion: str) -> dict:
    system = (
        "Redactas correos comerciales en español neutro mexicano para DEYMA. Tono profesional, conciso, orientado a cerrar "
        "una reunión. Sin emojis. Devuelves JSON estricto {subject, body}."
    )
    user = (
        f"Empresa: {empresa}\nContacto: {contacto}\nProyecto: {titulo}\nContexto: {descripcion}\n"
        "Devuelve JSON con subject (max 80 chars) y body (4-7 párrafos cortos, firma 'Equipo DEYMA')."
    )
    text = await _llm_call(system, user)
    data = _parse_json_block(text)
    return {"subject": data.get("subject", ""), "body": data.get("body", "")}


async def ai_sales_forecast(items: List[dict]) -> dict:
    system = (
        "Eres analista financiero de DEYMA. Estimas pronóstico de cierre del trimestre actual. "
        "Devuelves JSON estricto {forecast_amount: number (MXN), confidence: 'baja|media|alta', narrative: string corto en español}."
    )
    payload = "\n".join(
        f"- {it.get('titulo','(s/t)')} | Monto MXN {it.get('monto_estimado',0):,.0f} | Prob {it.get('probabilidad',0)}% | Etapa {it.get('stage','-')}"
        for it in items[:30]
    )
    user = f"Pipeline:\n{payload}\nDevuelve JSON."
    text = await _llm_call(system, user)
    data = _parse_json_block(text)
    return {
        "forecast_amount": float(data.get("forecast_amount", 0)),
        "confidence": data.get("confidence", "media"),
        "narrative": data.get("narrative", ""),
    }


# ----------------------------------------------------------------------------
# Auth endpoints
# ----------------------------------------------------------------------------
@api.post("/auth/register")
async def register(body: RegisterIn):
    email = body.email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    user_id = new_id()
    user_doc = {
        "id": user_id,
        "email": email,
        "name": body.name,
        "role": body.role,
        "password_hash": hash_password(body.password),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user_doc)
    token = create_access_token(user_id, email, body.role)
    user_doc.pop("password_hash", None)
    user_doc.pop("_id", None)
    return {"access_token": token, "user": user_doc}


@api.post("/auth/login")
async def login(body: LoginIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_access_token(user["id"], user["email"], user["role"])
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"access_token": token, "user": user}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ----------------------------------------------------------------------------
# CRM: Empresas, Contactos, Oportunidades
# ----------------------------------------------------------------------------
@api.get("/empresas", response_model=List[Empresa])
async def list_empresas(user: dict = Depends(get_current_user)):
    cur = db.empresas.find({}, {"_id": 0}).sort("created_at", -1)
    return await cur.to_list(1000)


@api.post("/empresas", response_model=Empresa)
async def create_empresa(body: EmpresaIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = iso(now_utc())
    await db.empresas.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/empresas/{empresa_id}")
async def delete_empresa(empresa_id: str, user: dict = Depends(require_roles("director", "comercial"))):
    await db.empresas.delete_one({"id": empresa_id})
    return {"ok": True}


@api.get("/contactos", response_model=List[Contacto])
async def list_contactos(empresa_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"empresa_id": empresa_id} if empresa_id else {}
    return await db.contactos.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/contactos", response_model=Contacto)
async def create_contacto(body: ContactoIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = iso(now_utc())
    await db.contactos.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/oportunidades", response_model=List[Oportunidad])
async def list_oportunidades(user: dict = Depends(get_current_user)):
    return await db.oportunidades.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@api.post("/oportunidades", response_model=Oportunidad)
async def create_oportunidad(body: OportunidadIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["score"] = 0
    doc["hotness"] = "cold"
    doc["score_reasons"] = []
    doc["created_at"] = iso(now_utc())
    doc["updated_at"] = iso(now_utc())
    doc["owner_id"] = doc.get("owner_id") or user["id"]
    await db.oportunidades.insert_one(doc)
    doc.pop("_id", None)
    return doc


class StageUpdate(BaseModel):
    stage: Stage
    probabilidad: Optional[int] = None


@api.patch("/oportunidades/{oid}")
async def update_oportunidad_stage(oid: str, body: StageUpdate, user: dict = Depends(get_current_user)):
    update = {"stage": body.stage, "updated_at": iso(now_utc())}
    if body.probabilidad is not None:
        update["probabilidad"] = body.probabilidad
    res = await db.oportunidades.update_one({"id": oid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return {"ok": True}


@api.post("/oportunidades/{oid}/score")
async def score_oportunidad(oid: str, user: dict = Depends(get_current_user)):
    op = await db.oportunidades.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    result = await ai_score_opportunity(op["titulo"], op["sector"], op["descripcion"], op["monto_estimado"])
    await db.oportunidades.update_one(
        {"id": oid},
        {"$set": {"score": result["score"], "hotness": result["hotness"],
                  "score_reasons": result["reasons"], "updated_at": iso(now_utc())}},
    )
    return result


@api.post("/oportunidades/{oid}/followup-email")
async def followup_email(oid: str, user: dict = Depends(get_current_user)):
    op = await db.oportunidades.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    emp = await db.empresas.find_one({"id": op["empresa_id"]}, {"_id": 0}) or {}
    cont = await db.contactos.find_one({"empresa_id": op["empresa_id"]}, {"_id": 0}) or {}
    return await ai_followup_email(emp.get("nombre", "Cliente"), cont.get("nombre", "Estimado(a)"),
                                   op["titulo"], op["descripcion"])


# ----------------------------------------------------------------------------
# Radar de Proyectos
# ----------------------------------------------------------------------------
@api.get("/radar", response_model=List[ProyectoRadar])
async def list_radar(user: dict = Depends(get_current_user)):
    return await db.radar.find({}, {"_id": 0}).sort("detected_at", -1).to_list(2000)


@api.post("/radar", response_model=ProyectoRadar)
async def create_radar(body: ProyectoRadarIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["score"] = 0
    doc["hotness"] = "cold"
    doc["score_reasons"] = []
    doc["detected_at"] = iso(now_utc())
    await db.radar.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.post("/radar/{rid}/score")
async def score_radar(rid: str, user: dict = Depends(get_current_user)):
    p = await db.radar.find_one({"id": rid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    result = await ai_score_opportunity(p["titulo"], p["sector"], p["descripcion"], p["monto_estimado"])
    await db.radar.update_one(
        {"id": rid},
        {"$set": {"score": result["score"], "hotness": result["hotness"], "score_reasons": result["reasons"]}},
    )
    return result


# ----------------------------------------------------------------------------
# Cotizador
# ----------------------------------------------------------------------------
def _cot_totals(items: List[CotizacionItem], iva_pct: float):
    subtotal = sum(it.cantidad * it.precio_unitario for it in items)
    subtotal = round(subtotal, 2)
    iva = round(subtotal * (iva_pct / 100.0), 2)
    total = round(subtotal + iva, 2)
    return subtotal, iva, total


@api.get("/cotizaciones", response_model=List[Cotizacion])
async def list_cotizaciones(user: dict = Depends(get_current_user)):
    return await db.cotizaciones.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/cotizaciones", response_model=Cotizacion)
async def create_cotizacion(body: CotizacionIn, user: dict = Depends(get_current_user)):
    subtotal, iva, total = _cot_totals(body.items, body.iva_pct)
    count = await db.cotizaciones.count_documents({})
    folio = f"DEY-{datetime.now().year}-{count+1:04d}"
    doc = {
        "id": new_id(),
        "folio": folio,
        "empresa_id": body.empresa_id,
        "proyecto_titulo": body.proyecto_titulo,
        "items": [it.model_dump() for it in body.items],
        "subtotal": subtotal,
        "iva_pct": body.iva_pct,
        "iva_monto": iva,
        "total": total,
        "notas": body.notas,
        "validez_dias": body.validez_dias,
        "estado": "borrador",
        "owner_id": user["id"],
        "created_at": iso(now_utc()),
    }
    await db.cotizaciones.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ----------------------------------------------------------------------------
# Obras
# ----------------------------------------------------------------------------
@api.get("/obras", response_model=List[Obra])
async def list_obras(user: dict = Depends(get_current_user)):
    return await db.obras.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/obras", response_model=Obra)
async def create_obra(body: ObraIn, user: dict = Depends(require_roles("director", "operaciones"))):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = iso(now_utc())
    await db.obras.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ----------------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------------
@api.get("/dashboard/kpis")
async def dashboard_kpis(user: dict = Depends(get_current_user)):
    ops = await db.oportunidades.find({}, {"_id": 0}).to_list(5000)
    cots = await db.cotizaciones.find({}, {"_id": 0}).to_list(5000)
    obras = await db.obras.find({}, {"_id": 0}).to_list(2000)
    radar = await db.radar.find({}, {"_id": 0}).to_list(2000)

    pipeline_total = sum(o.get("monto_estimado", 0) for o in ops if o.get("stage") not in ("ganada", "perdida"))
    ganadas = [o for o in ops if o.get("stage") == "ganada"]
    ingresos_ganados = sum(o.get("monto_estimado", 0) for o in ganadas)
    hot_ops = [o for o in ops if (o.get("hotness") == "hot" or o.get("score", 0) >= 75)]
    cot_mes = [c for c in cots if c.get("created_at", "")[:7] == datetime.now().strftime("%Y-%m")]
    obras_activas = [o for o in obras if o.get("estado") in ("planeacion", "ejecucion")]

    forecast = 0.0
    for o in ops:
        if o.get("stage") in ("ganada", "perdida"):
            continue
        forecast += (o.get("monto_estimado", 0) * o.get("probabilidad", 0) / 100.0)

    # pipeline por etapa
    stages = ["prospeccion", "calificada", "propuesta", "negociacion", "ganada", "perdida"]
    by_stage = {s: {"count": 0, "monto": 0.0} for s in stages}
    for o in ops:
        s = o.get("stage", "prospeccion")
        by_stage.setdefault(s, {"count": 0, "monto": 0.0})
        by_stage[s]["count"] += 1
        by_stage[s]["monto"] += o.get("monto_estimado", 0)

    # sector breakdown
    by_sector = {}
    for o in ops:
        s = o.get("sector", "otro")
        by_sector[s] = by_sector.get(s, 0) + o.get("monto_estimado", 0)

    return {
        "pipeline_total": round(pipeline_total, 2),
        "ingresos_ganados": round(ingresos_ganados, 2),
        "forecast_ponderado": round(forecast, 2),
        "hot_ops_count": len(hot_ops),
        "cotizaciones_mes": len(cot_mes),
        "cotizaciones_mes_monto": round(sum(c.get("total", 0) for c in cot_mes), 2),
        "obras_activas": len(obras_activas),
        "obras_activas_monto": round(sum(o.get("monto_contratado", 0) for o in obras_activas), 2),
        "radar_count": len(radar),
        "radar_hot": len([p for p in radar if p.get("hotness") == "hot" or p.get("score", 0) >= 75]),
        "conversion_rate": round(
            (len(ganadas) / len(ops) * 100.0) if ops else 0.0, 1
        ),
        "by_stage": by_stage,
        "by_sector": by_sector,
        "total_oportunidades": len(ops),
    }


@api.get("/dashboard/executive-summary")
async def exec_summary(user: dict = Depends(get_current_user)):
    ops = await db.oportunidades.find({}, {"_id": 0}).sort("score", -1).to_list(20)
    text = await ai_executive_summary(ops)
    return {"summary": text, "generated_at": iso(now_utc())}


@api.get("/dashboard/forecast")
async def forecast_endpoint(user: dict = Depends(get_current_user)):
    ops = await db.oportunidades.find({"stage": {"$nin": ["ganada", "perdida"]}}, {"_id": 0}).to_list(50)
    if not ops:
        return {"forecast_amount": 0, "confidence": "baja", "narrative": "Sin oportunidades activas en pipeline."}
    return await ai_sales_forecast(ops)


# ----------------------------------------------------------------------------
# Mapa de Oportunidades
# ----------------------------------------------------------------------------
@api.get("/mapa/puntos")
async def mapa_puntos(user: dict = Depends(get_current_user)):
    radar = await db.radar.find({}, {"_id": 0}).to_list(2000)
    # Sumar coords de empresas para oportunidades
    empresas = {e["id"]: e for e in await db.empresas.find({}, {"_id": 0}).to_list(2000)}
    ops = await db.oportunidades.find({}, {"_id": 0}).to_list(2000)

    points = []
    for p in radar:
        if p.get("lat") and p.get("lng"):
            points.append({
                "id": p["id"], "tipo": "radar", "titulo": p["titulo"], "sector": p["sector"],
                "monto": p["monto_estimado"], "score": p.get("score", 0),
                "hotness": p.get("hotness", "cold"), "lat": p["lat"], "lng": p["lng"],
                "ciudad": p["ciudad"], "estado": p["estado"],
            })
    for o in ops:
        emp = empresas.get(o["empresa_id"], {})
        lat = emp.get("lat")
        lng = emp.get("lng")
        if lat and lng:
            points.append({
                "id": o["id"], "tipo": "oportunidad", "titulo": o["titulo"], "sector": o["sector"],
                "monto": o["monto_estimado"], "score": o.get("score", 0),
                "hotness": o.get("hotness", "cold"), "lat": lat, "lng": lng,
                "ciudad": emp.get("ciudad", ""), "estado": emp.get("estado", ""),
            })
    return {"points": points}


# ----------------------------------------------------------------------------
# Seed (idempotent)
# ----------------------------------------------------------------------------
SEED_EMPRESAS = [
    {"nombre": "Bombardier Aerospace México", "rfc": "BAM920321ABC", "sector": "manufactura", "ciudad": "Querétaro", "estado": "Querétaro", "lat": 20.6160, "lng": -100.1853, "sitio_web": "bombardier.com", "notas": "Planta aeroespacial - expansión 2026"},
    {"nombre": "Mercado Libre CEDIS Bajío", "rfc": "MEL110815XYZ", "sector": "cedis_logistica", "ciudad": "San Juan del Río", "estado": "Querétaro", "lat": 20.3878, "lng": -99.9962, "sitio_web": "mercadolibre.com", "notas": "Nuevo centro logístico 80,000 m²"},
    {"nombre": "Foxconn Querétaro", "rfc": "FOX070612QRO", "sector": "nearshoring", "ciudad": "El Marqués", "estado": "Querétaro", "lat": 20.7062, "lng": -100.2911, "sitio_web": "foxconn.com", "notas": "Manufactura electrónica - relocalización Asia"},
    {"nombre": "Microsoft Data Center Bajío", "rfc": "MSF200101AAA", "sector": "data_centers", "ciudad": "Querétaro", "estado": "Querétaro", "lat": 20.5888, "lng": -100.3899, "sitio_web": "microsoft.com", "notas": "Hyperscale data center"},
    {"nombre": "Grupo Vesta Industrial", "rfc": "VES980211ABC", "sector": "parques_industriales", "ciudad": "Querétaro", "estado": "Querétaro", "lat": 20.5500, "lng": -100.3900, "sitio_web": "vesta.com", "notas": "Desarrollador de parques industriales"},
    {"nombre": "BMW San Luis Potosí", "rfc": "BMW140909QRO", "sector": "expansion_planta", "ciudad": "San Luis Potosí", "estado": "San Luis Potosí", "lat": 22.1565, "lng": -100.9855, "sitio_web": "bmw.com", "notas": "Expansión planta automotriz"},
    {"nombre": "Nestlé Planta León", "rfc": "NES850712GTO", "sector": "manufactura", "ciudad": "León", "estado": "Guanajuato", "lat": 21.1250, "lng": -101.6850, "sitio_web": "nestle.com.mx", "notas": "Planta lácteos"},
    {"nombre": "Amazon CEDIS Tepotzotlán", "rfc": "AMZ150601MEX", "sector": "cedis_logistica", "ciudad": "Tepotzotlán", "estado": "Estado de México", "lat": 19.7150, "lng": -99.2230, "sitio_web": "amazon.com", "notas": "Centro de distribución"},
    {"nombre": "FINSA Parque Industrial", "rfc": "FIN770512GTO", "sector": "parques_industriales", "ciudad": "Silao", "estado": "Guanajuato", "lat": 20.9489, "lng": -101.4291, "sitio_web": "finsa.net", "notas": "Parque industrial Bajío"},
    {"nombre": "Continental Tire Aguascalientes", "rfc": "CON060312AGS", "sector": "manufactura", "ciudad": "Aguascalientes", "estado": "Aguascalientes", "lat": 21.8853, "lng": -102.2916, "sitio_web": "continental.com", "notas": "Planta llantera"},
]

SEED_RADAR = [
    {"titulo": "Construcción nuevo CEDIS Walmart Bajío 65,000 m²", "fuente": "licitacion", "sector": "cedis_logistica", "ciudad": "Querétaro", "estado": "Querétaro", "monto_estimado": 38_500_000, "descripcion": "Licitación pública para construcción de centro de distribución Walmart, incluye piso industrial de alto tránsito, juntas tipo Omega, acabado pulido brillante.", "url_fuente": "compranet.gob.mx", "lat": 20.6300, "lng": -100.3800},
    {"titulo": "Expansión planta Stellantis 32,000 m²", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "Saltillo", "estado": "Coahuila", "monto_estimado": 22_000_000, "descripcion": "Ampliación nave industrial para nueva línea de vehículos eléctricos. Requiere pisos industriales de alta resistencia y pavimentación de estacionamientos.", "url_fuente": "elfinanciero.com.mx", "lat": 25.4232, "lng": -100.9966},
    {"titulo": "Microsoft AI Data Center Fase 2", "fuente": "referencia", "sector": "data_centers", "ciudad": "Querétaro", "estado": "Querétaro", "monto_estimado": 58_000_000, "descripcion": "Segunda fase del data center hiperescala. Requiere pisos antiestáticos, juntas de control y mantenimiento perimetral.", "url_fuente": "interno", "lat": 20.5888, "lng": -100.3899},
    {"titulo": "CEDIS Coppel Norte Bajío 45,000 m²", "fuente": "licitacion", "sector": "cedis_logistica", "ciudad": "León", "estado": "Guanajuato", "monto_estimado": 26_400_000, "descripcion": "Nuevo centro de distribución regional. Pisos industriales con armaduras dobles y acabado superficial endurecido.", "url_fuente": "compranet.gob.mx", "lat": 21.1180, "lng": -101.6760},
    {"titulo": "Parque industrial WTC Industrial San Luis", "fuente": "noticia", "sector": "parques_industriales", "ciudad": "San Luis Potosí", "estado": "San Luis Potosí", "monto_estimado": 41_000_000, "descripcion": "Desarrollo greenfield de parque industrial. Vialidades internas, plataformas y banquetas industriales.", "url_fuente": "elheraldo.mx", "lat": 22.1300, "lng": -100.9700},
    {"titulo": "Planta Tesla Megafactory México (rumor)", "fuente": "noticia", "sector": "nearshoring", "ciudad": "Monterrey", "estado": "Nuevo León", "monto_estimado": 95_000_000, "descripcion": "Especulación sobre relocalización - alta incertidumbre pero proyecto mega. Pisos especializados gigafactoría.", "url_fuente": "bloomberg.com", "lat": 25.6866, "lng": -100.3161},
    {"titulo": "Mantenimiento pisos CEDIS DHL Cuautitlán", "fuente": "referencia", "sector": "cedis_logistica", "ciudad": "Cuautitlán", "estado": "Estado de México", "monto_estimado": 4_800_000, "descripcion": "Repulido, rehabilitación de juntas y reparación de losas dañadas. Contrato anual.", "url_fuente": "interno", "lat": 19.6766, "lng": -99.1817},
    {"titulo": "Ampliación nave Continental Aguascalientes", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "Aguascalientes", "estado": "Aguascalientes", "monto_estimado": 18_200_000, "descripcion": "Expansión 12,000 m² de planta llantera. Pisos industriales, montaje de canastillas y mantenimiento.", "url_fuente": "milenio.com", "lat": 21.8853, "lng": -102.2916},
    {"titulo": "Nearshoring Mahle componentes Celaya", "fuente": "licitacion", "sector": "nearshoring", "ciudad": "Celaya", "estado": "Guanajuato", "monto_estimado": 14_700_000, "descripcion": "Construcción nave 9,500 m² proveedor automotriz Tier 1. Concreto hidráulico y canastillas.", "url_fuente": "compranet.gob.mx", "lat": 20.5167, "lng": -100.8167},
    {"titulo": "Mantenimiento canastillas Heineken Toluca", "fuente": "referencia", "sector": "manufactura", "ciudad": "Toluca", "estado": "Estado de México", "monto_estimado": 2_300_000, "descripcion": "Sustitución y mantenimiento de canastillas en planta cervecera. Trabajo recurrente trimestral.", "url_fuente": "interno", "lat": 19.2833, "lng": -99.6500},
    {"titulo": "Pavimentación interior parque FINSA Silao", "fuente": "licitacion", "sector": "parques_industriales", "ciudad": "Silao", "estado": "Guanajuato", "monto_estimado": 11_900_000, "descripcion": "Pavimentación con concreto hidráulico de vialidades interiores 18,000 m².", "url_fuente": "finsa.net", "lat": 20.9489, "lng": -101.4291},
    {"titulo": "Nuevo CEDIS Mercado Libre Texcoco", "fuente": "noticia", "sector": "cedis_logistica", "ciudad": "Texcoco", "estado": "Estado de México", "monto_estimado": 33_500_000, "descripcion": "Construcción CEDIS 50,000 m² con piso industrial superplano para racks selectivos.", "url_fuente": "expansion.mx", "lat": 19.5050, "lng": -98.8830},
]


async def seed_data():
    # Indexes
    try:
        await db.users.create_index("email", unique=True)
        await db.empresas.create_index("nombre")
        await db.oportunidades.create_index("stage")
    except Exception:
        pass

    # Admin users
    admin_email = os.environ.get("ADMIN_EMAIL", "director@deyma.mx")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "Deyma2026!")
    existing = await db.users.find_one({"email": admin_email.lower()})
    if not existing:
        await db.users.insert_one({
            "id": new_id(), "email": admin_email.lower(), "name": "Director General DEYMA",
            "role": "director", "password_hash": hash_password(admin_pw), "created_at": iso(now_utc()),
        })
    else:
        if not verify_password(admin_pw, existing.get("password_hash", "")):
            await db.users.update_one({"email": admin_email.lower()},
                                      {"$set": {"password_hash": hash_password(admin_pw), "role": "director"}})

    # Test users for other roles
    extras = [
        {"email": "comercial@deyma.mx", "name": "Ana López (Comercial)", "role": "comercial", "pw": "Comercial2026!"},
        {"email": "operaciones@deyma.mx", "name": "Carlos Ruiz (Operaciones)", "role": "operaciones", "pw": "Operaciones2026!"},
    ]
    for u in extras:
        if not await db.users.find_one({"email": u["email"]}):
            await db.users.insert_one({
                "id": new_id(), "email": u["email"], "name": u["name"], "role": u["role"],
                "password_hash": hash_password(u["pw"]), "created_at": iso(now_utc()),
            })

    # Empresas
    if await db.empresas.count_documents({}) == 0:
        emp_docs = []
        for e in SEED_EMPRESAS:
            d = dict(e)
            d["id"] = new_id()
            d["created_at"] = iso(now_utc())
            emp_docs.append(d)
        await db.empresas.insert_many(emp_docs)
    empresas_db = await db.empresas.find({}, {"_id": 0}).to_list(1000)
    by_name = {e["nombre"]: e for e in empresas_db}

    # Contactos
    if await db.contactos.count_documents({}) == 0:
        contactos = [
            ("Bombardier Aerospace México", "Ing. Roberto Méndez", "Gerente de Proyectos", "r.mendez@bombardier.com", "+52 442 211 3344"),
            ("Mercado Libre CEDIS Bajío", "Lic. Mariana Torres", "Directora de Operaciones", "m.torres@meli.com", "+52 427 555 1234"),
            ("Foxconn Querétaro", "Ing. Wei Chen", "Plant Manager", "w.chen@foxconn.com", "+52 442 700 8800"),
            ("Microsoft Data Center Bajío", "Ing. David Park", "Site Lead", "d.park@microsoft.com", "+52 442 900 1100"),
            ("Grupo Vesta Industrial", "Arq. Sofía Ramírez", "VP Desarrollo", "s.ramirez@vesta.com", "+52 442 500 6677"),
            ("BMW San Luis Potosí", "Ing. Klaus Weber", "Director de Planta", "k.weber@bmw.com", "+52 444 222 8899"),
            ("Nestlé Planta León", "Ing. Patricia Gómez", "Gerente de Mantenimiento", "p.gomez@nestle.com.mx", "+52 477 333 4455"),
            ("Amazon CEDIS Tepotzotlán", "Lic. Jorge Salinas", "Operations Manager", "j.salinas@amazon.com", "+52 55 4848 9999"),
        ]
        cont_docs = []
        for nombre_emp, n, p, e, t in contactos:
            if nombre_emp in by_name:
                cont_docs.append({
                    "id": new_id(), "empresa_id": by_name[nombre_emp]["id"], "nombre": n,
                    "puesto": p, "email": e, "telefono": t, "created_at": iso(now_utc()),
                })
        if cont_docs:
            await db.contactos.insert_many(cont_docs)

    # Oportunidades
    if await db.oportunidades.count_documents({}) == 0:
        ops_seed = [
            ("Bombardier Aerospace México", "Piso industrial nave 5 expansión", "expansion_planta", "Construcción de piso industrial superplano de 8,500 m² para nueva nave de ensamble aeroespacial. Acabado pulido brillante con endurecedor superficial.", 12_500_000, "negociacion", 70),
            ("Mercado Libre CEDIS Bajío", "CEDIS Bajío - piso 80,000 m²", "cedis_logistica", "Piso industrial de alto tránsito con juntas Omega y curado químico. Plazo 5 meses.", 38_000_000, "propuesta", 55),
            ("Foxconn Querétaro", "Mantenimiento integral pisos 2026", "nearshoring", "Contrato anual de mantenimiento, repulido y reparación de juntas en 3 naves industriales.", 4_200_000, "calificada", 40),
            ("Microsoft Data Center Bajío", "Pisos antiestáticos Hyperscale", "data_centers", "Pisos antiestáticos especializados, juntas de control y plataformas técnicas para data center Tier IV.", 28_000_000, "prospeccion", 25),
            ("Grupo Vesta Industrial", "Pavimentación vialidades parque industrial", "parques_industriales", "Pavimentación con concreto hidráulico MR-45 de 15,000 m² en parque industrial Querétaro Sur.", 9_800_000, "ganada", 100),
            ("BMW San Luis Potosí", "Piso industrial expansión planta motores", "expansion_planta", "Piso superplano para nueva línea de ensamble de motores eléctricos. Tolerancias FF/FL alto.", 18_500_000, "propuesta", 50),
            ("Nestlé Planta León", "Mantenimiento pisos y canastillas", "manufactura", "Contrato anual de mantenimiento integral. Sustitución de canastillas dañadas.", 3_400_000, "negociacion", 75),
            ("Amazon CEDIS Tepotzotlán", "Piso CEDIS 60,000 m² Fulfillment Center", "cedis_logistica", "Piso superplano para racks de gran altura. Especificación FM2 con láser screed.", 31_000_000, "calificada", 35),
            ("FINSA Parque Industrial", "Banquetas y plataformas Silao", "parques_industriales", "Construcción de banquetas industriales y plataformas perimetrales.", 5_600_000, "prospeccion", 20),
            ("Continental Tire Aguascalientes", "Piso industrial nueva línea SUV", "manufactura", "Piso industrial 11,000 m² nueva línea producción llantas SUV.", 14_800_000, "prospeccion", 30),
            ("Bombardier Aerospace México", "Canastillas hangar fase 3", "expansion_planta", "Suministro e instalación de canastillas para fase 3 del hangar.", 2_100_000, "ganada", 100),
            ("Mercado Libre CEDIS Bajío", "Pavimentación patio maniobras", "cedis_logistica", "Pavimentación de patio de maniobras de tractocamiones 22,000 m².", 13_900_000, "perdida", 0),
        ]
        op_docs = []
        for nombre_emp, titulo, sector, desc, monto, stage, prob in ops_seed:
            if nombre_emp not in by_name:
                continue
            op_docs.append({
                "id": new_id(),
                "empresa_id": by_name[nombre_emp]["id"],
                "titulo": titulo, "sector": sector, "descripcion": desc,
                "monto_estimado": monto, "stage": stage, "probabilidad": prob,
                "score": 0, "hotness": "cold", "score_reasons": [],
                "fecha_cierre": None, "owner_id": None,
                "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
            })
        if op_docs:
            await db.oportunidades.insert_many(op_docs)

    # Radar
    if await db.radar.count_documents({}) == 0:
        rdocs = []
        for r in SEED_RADAR:
            d = dict(r)
            d["id"] = new_id()
            d["score"] = 0
            d["hotness"] = "cold"
            d["score_reasons"] = []
            d["detected_at"] = iso(now_utc())
            rdocs.append(d)
        await db.radar.insert_many(rdocs)

    # Obras
    if await db.obras.count_documents({}) == 0:
        obras_seed = [
            ("Grupo Vesta Industrial", "Pavimentación Parque Querétaro Sur", 9_800_000, "ejecucion", 42, "Querétaro"),
            ("Bombardier Aerospace México", "Canastillas hangar fase 3", 2_100_000, "ejecucion", 78, "Querétaro"),
            ("Foxconn Querétaro", "Mantenimiento pisos Q1 2026", 1_050_000, "completada", 100, "El Marqués"),
            ("FINSA Parque Industrial", "Banquetas Silao zona B", 1_800_000, "planeacion", 5, "Silao"),
        ]
        obras_docs = []
        for nombre_emp, n, monto, estado, pct, ciudad in obras_seed:
            if nombre_emp not in by_name:
                continue
            obras_docs.append({
                "id": new_id(), "empresa_id": by_name[nombre_emp]["id"],
                "cotizacion_id": None, "nombre": n,
                "monto_contratado": monto,
                "fecha_inicio": iso(now_utc() - timedelta(days=60)),
                "fecha_fin_estimada": iso(now_utc() + timedelta(days=90)),
                "estado": estado, "avance_pct": pct, "ciudad": ciudad, "estado_geo": "Querétaro",
                "created_at": iso(now_utc()),
            })
        if obras_docs:
            await db.obras.insert_many(obras_docs)

    # Cotizaciones
    if await db.cotizaciones.count_documents({}) == 0:
        cots_seed = [
            ("Bombardier Aerospace México", "Piso industrial nave 5", [
                {"descripcion": "Piso industrial superplano 8,500 m² acabado pulido", "cantidad": 8500, "unidad": "m2", "precio_unitario": 1280},
                {"descripcion": "Endurecedor superficial cuarzo", "cantidad": 8500, "unidad": "m2", "precio_unitario": 95},
                {"descripcion": "Juntas tipo Omega lineal", "cantidad": 420, "unidad": "ml", "precio_unitario": 320},
            ], "enviada"),
            ("Mercado Libre CEDIS Bajío", "CEDIS Bajío 80,000 m²", [
                {"descripcion": "Piso industrial superplano FM2", "cantidad": 80000, "unidad": "m2", "precio_unitario": 440},
                {"descripcion": "Curado químico de superficie", "cantidad": 80000, "unidad": "m2", "precio_unitario": 32},
            ], "borrador"),
            ("Nestlé Planta León", "Mantenimiento pisos y canastillas", [
                {"descripcion": "Repulido superficie de losas", "cantidad": 4200, "unidad": "m2", "precio_unitario": 280},
                {"descripcion": "Reemplazo canastillas dañadas", "cantidad": 86, "unidad": "pza", "precio_unitario": 12500},
                {"descripcion": "Sello y restitución de juntas", "cantidad": 580, "unidad": "ml", "precio_unitario": 180},
            ], "aceptada"),
        ]
        ccount = 0
        ccdocs = []
        for nombre_emp, proyecto, items, estado in cots_seed:
            if nombre_emp not in by_name:
                continue
            ccount += 1
            items_obj = [CotizacionItem(**it) for it in items]
            subtotal, iva, total = _cot_totals(items_obj, 16.0)
            ccdocs.append({
                "id": new_id(),
                "folio": f"DEY-{datetime.now().year}-{ccount:04d}",
                "empresa_id": by_name[nombre_emp]["id"],
                "proyecto_titulo": proyecto,
                "items": [it.model_dump() for it in items_obj],
                "subtotal": subtotal, "iva_pct": 16.0, "iva_monto": iva, "total": total,
                "notas": "Cotización generada automáticamente desde DEYMA RADAR.",
                "validez_dias": 15, "estado": estado,
                "owner_id": "seed", "created_at": iso(now_utc()),
            })
        if ccdocs:
            await db.cotizaciones.insert_many(ccdocs)


# ----------------------------------------------------------------------------
# Health & root
# ----------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"service": "DEYMA RADAR", "version": "1.0.0", "status": "ok"}


@api.get("/health")
async def health():
    return {"ok": True, "ts": iso(now_utc())}


# ----------------------------------------------------------------------------
# Mount & startup
# ----------------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    try:
        await seed_data()
        logger.info("Seed completado")
    except Exception:
        logger.exception("Error en seed")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
