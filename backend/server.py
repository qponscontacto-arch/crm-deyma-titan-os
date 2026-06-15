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
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator

# ----------------------------------------------------------------------------
# DB & app setup
# ----------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
gridfs_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="cliente_files")

app = FastAPI(title="DEYMA RADAR API", version="1.0.0")
api = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

JWT_ALGO = "HS256"
JWT_SECRET = os.environ['JWT_SECRET']
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Twilio WhatsApp (mock when keys missing)
TWILIO_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM = os.environ.get('TWILIO_WHATSAPP_FROM', '')
DEYMA_ALERT_PHONE = os.environ.get('DEYMA_ALERT_PHONE', '')
TWILIO_ENABLED = bool(TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and DEYMA_ALERT_PHONE)

# SendGrid (mock when keys missing)
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDGRID_FROM_EMAIL = os.environ.get('SENDGRID_FROM_EMAIL', '')
SENDGRID_FROM_NAME = os.environ.get('SENDGRID_FROM_NAME', 'DEYMA Cotizaciones')
SENDGRID_ENABLED = bool(SENDGRID_API_KEY and SENDGRID_FROM_EMAIL)

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
    estado: Literal["borrador", "aprobada_direccion", "enviada", "aceptada", "rechazada"] = "borrador"
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
    if result["score"] >= 85:
        emp = await db.empresas.find_one({"id": op["empresa_id"]}, {"_id": 0}) or {}
        await create_hot_alert("oportunidad", oid, op["titulo"], result["score"],
                               op["monto_estimado"], op["sector"], emp.get("ciudad", "Querétaro"))
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
    if result["score"] >= 85:
        await create_hot_alert("radar", rid, p["titulo"], result["score"],
                               p["monto_estimado"], p["sector"], p.get("ciudad", "Bajío"))
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
    {"nombre": "Tesla Gigafactory Nuevo León", "rfc": "TSL230515NLE", "sector": "nearshoring", "ciudad": "Santa Catarina", "estado": "Nuevo León", "lat": 25.6731, "lng": -100.4583, "sitio_web": "tesla.com", "notas": "Gigafactory México - construcción 2026"},
    {"nombre": "Kia Motors Pesquería", "rfc": "KIA140311NLE", "sector": "manufactura", "ciudad": "Pesquería", "estado": "Nuevo León", "lat": 25.7886, "lng": -100.0497, "sitio_web": "kia.com", "notas": "Planta automotriz Norte"},
    {"nombre": "FEMSA Heineken Toluca", "rfc": "HEI820906MEX", "sector": "manufactura", "ciudad": "Toluca", "estado": "Estado de México", "lat": 19.2833, "lng": -99.6500, "sitio_web": "heineken.com", "notas": "Planta cervecera"},
    {"nombre": "Volkswagen Puebla", "rfc": "VWP671023PUE", "sector": "expansion_planta", "ciudad": "Cuautlancingo", "estado": "Puebla", "lat": 19.0921, "lng": -98.3007, "sitio_web": "vw.com.mx", "notas": "Planta automotriz histórica"},
    {"nombre": "Audi México San José Chiapa", "rfc": "AUD150116PUE", "sector": "manufactura", "ciudad": "San José Chiapa", "estado": "Puebla", "lat": 19.3033, "lng": -97.8197, "sitio_web": "audi.com.mx", "notas": "Planta premium"},
    {"nombre": "Hofusan Industrial Park", "rfc": "HOF180201NLE", "sector": "parques_industriales", "ciudad": "Salinas Victoria", "estado": "Nuevo León", "lat": 25.9690, "lng": -100.3008, "sitio_web": "hofusan.com", "notas": "Parque chino-mexicano nearshoring"},
    {"nombre": "Tijuana East Industrial Park", "rfc": "TIJ190405BCN", "sector": "nearshoring", "ciudad": "Tijuana", "estado": "Baja California", "lat": 32.4150, "lng": -116.8970, "sitio_web": "tijuanaep.com", "notas": "Nearshoring corredor Tijuana"},
    {"nombre": "Equinix MX1 Data Center", "rfc": "EQX160708CDMX", "sector": "data_centers", "ciudad": "Querétaro", "estado": "Querétaro", "lat": 20.6080, "lng": -100.4060, "sitio_web": "equinix.com", "notas": "Data center hyperescala"},
    {"nombre": "Toyota Guanajuato Apaseo", "rfc": "TOY160601GTO", "sector": "manufactura", "ciudad": "Apaseo el Grande", "estado": "Guanajuato", "lat": 20.5478, "lng": -100.7039, "sitio_web": "toyota.com.mx", "notas": "Planta Tacoma"},
    {"nombre": "Honda El Salto Jalisco", "rfc": "HON141015JAL", "sector": "manufactura", "ciudad": "El Salto", "estado": "Jalisco", "lat": 20.5167, "lng": -103.1833, "sitio_web": "honda.mx", "notas": "Motocicletas y autos"},
    {"nombre": "Ford Hermosillo", "rfc": "FOR860115SON", "sector": "expansion_planta", "ciudad": "Hermosillo", "estado": "Sonora", "lat": 29.0892, "lng": -110.9613, "sitio_web": "ford.com.mx", "notas": "Planta automotriz Norte"},
    {"nombre": "Cemex Planta Yucatán", "rfc": "CEM060421YUC", "sector": "manufactura", "ciudad": "Mérida", "estado": "Yucatán", "lat": 20.9674, "lng": -89.5926, "sitio_web": "cemex.com", "notas": "Cementera Sureste"},
    {"nombre": "Pemex Refinería Dos Bocas", "rfc": "PEM190322TAB", "sector": "expansion_planta", "ciudad": "Paraíso", "estado": "Tabasco", "lat": 18.4036, "lng": -93.1944, "sitio_web": "pemex.com", "notas": "Refinería Olmeca - mantenimiento"},
    {"nombre": "Mabe Saltillo", "rfc": "MAB710310COA", "sector": "manufactura", "ciudad": "Saltillo", "estado": "Coahuila", "lat": 25.4232, "lng": -100.9966, "sitio_web": "mabe.com.mx", "notas": "Electrodomésticos"},
    {"nombre": "Bachoco Mérida Sureste", "rfc": "BAC520809YUC", "sector": "manufactura", "ciudad": "Mérida", "estado": "Yucatán", "lat": 20.9700, "lng": -89.6200, "sitio_web": "bachoco.com.mx", "notas": "Planta avícola"},
]

SEED_RADAR = [
    {"titulo": "Construcción nuevo CEDIS Walmart Bajío 65,000 m²", "fuente": "licitacion", "sector": "cedis_logistica", "ciudad": "Querétaro", "estado": "Querétaro", "monto_estimado": 38_500_000, "descripcion": "Licitación pública para construcción de centro de distribución Walmart, incluye piso industrial de alto tránsito, juntas tipo Omega, acabado pulido brillante.", "url_fuente": "compranet.gob.mx", "lat": 20.6300, "lng": -100.3800},
    {"titulo": "Expansión planta Stellantis 32,000 m²", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "Saltillo", "estado": "Coahuila", "monto_estimado": 22_000_000, "descripcion": "Ampliación nave industrial para nueva línea de vehículos eléctricos. Requiere pisos industriales de alta resistencia y pavimentación de estacionamientos.", "url_fuente": "elfinanciero.com.mx", "lat": 25.4232, "lng": -100.9966},
    {"titulo": "Microsoft AI Data Center Fase 2", "fuente": "referencia", "sector": "data_centers", "ciudad": "Querétaro", "estado": "Querétaro", "monto_estimado": 58_000_000, "descripcion": "Segunda fase del data center hiperescala. Requiere pisos antiestáticos, juntas de control y mantenimiento perimetral.", "url_fuente": "interno", "lat": 20.5888, "lng": -100.3899},
    {"titulo": "CEDIS Coppel Norte Bajío 45,000 m²", "fuente": "licitacion", "sector": "cedis_logistica", "ciudad": "León", "estado": "Guanajuato", "monto_estimado": 26_400_000, "descripcion": "Nuevo centro de distribución regional. Pisos industriales con armaduras dobles y acabado superficial endurecido.", "url_fuente": "compranet.gob.mx", "lat": 21.1180, "lng": -101.6760},
    {"titulo": "Parque industrial WTC Industrial San Luis", "fuente": "noticia", "sector": "parques_industriales", "ciudad": "San Luis Potosí", "estado": "San Luis Potosí", "monto_estimado": 41_000_000, "descripcion": "Desarrollo greenfield de parque industrial. Vialidades internas, plataformas y banquetas industriales.", "url_fuente": "elheraldo.mx", "lat": 22.1300, "lng": -100.9700},
    {"titulo": "Planta Tesla Gigafactory Santa Catarina", "fuente": "noticia", "sector": "nearshoring", "ciudad": "Santa Catarina", "estado": "Nuevo León", "monto_estimado": 95_000_000, "descripcion": "Gigafactoría de vehículos eléctricos. Pisos industriales especializados para línea de baterías y ensamble.", "url_fuente": "bloomberg.com", "lat": 25.6731, "lng": -100.4583},
    {"titulo": "Mantenimiento pisos CEDIS DHL Cuautitlán", "fuente": "referencia", "sector": "cedis_logistica", "ciudad": "Cuautitlán", "estado": "Estado de México", "monto_estimado": 4_800_000, "descripcion": "Repulido, rehabilitación de juntas y reparación de losas dañadas. Contrato anual.", "url_fuente": "interno", "lat": 19.6766, "lng": -99.1817},
    {"titulo": "Ampliación nave Continental Aguascalientes", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "Aguascalientes", "estado": "Aguascalientes", "monto_estimado": 18_200_000, "descripcion": "Expansión 12,000 m² de planta llantera. Pisos industriales, montaje de canastillas y mantenimiento.", "url_fuente": "milenio.com", "lat": 21.8853, "lng": -102.2916},
    {"titulo": "Nearshoring Mahle componentes Celaya", "fuente": "licitacion", "sector": "nearshoring", "ciudad": "Celaya", "estado": "Guanajuato", "monto_estimado": 14_700_000, "descripcion": "Construcción nave 9,500 m² proveedor automotriz Tier 1. Concreto hidráulico y canastillas.", "url_fuente": "compranet.gob.mx", "lat": 20.5167, "lng": -100.8167},
    {"titulo": "Mantenimiento canastillas Heineken Toluca", "fuente": "referencia", "sector": "manufactura", "ciudad": "Toluca", "estado": "Estado de México", "monto_estimado": 2_300_000, "descripcion": "Sustitución y mantenimiento de canastillas en planta cervecera. Trabajo recurrente trimestral.", "url_fuente": "interno", "lat": 19.2833, "lng": -99.6500},
    {"titulo": "Pavimentación interior parque FINSA Silao", "fuente": "licitacion", "sector": "parques_industriales", "ciudad": "Silao", "estado": "Guanajuato", "monto_estimado": 11_900_000, "descripcion": "Pavimentación con concreto hidráulico de vialidades interiores 18,000 m².", "url_fuente": "finsa.net", "lat": 20.9489, "lng": -101.4291},
    {"titulo": "Nuevo CEDIS Mercado Libre Texcoco", "fuente": "noticia", "sector": "cedis_logistica", "ciudad": "Texcoco", "estado": "Estado de México", "monto_estimado": 33_500_000, "descripcion": "Construcción CEDIS 50,000 m² con piso industrial superplano para racks selectivos.", "url_fuente": "expansion.mx", "lat": 19.5050, "lng": -98.8830},
    {"titulo": "Parque Industrial Hofusan Salinas Victoria fase 4", "fuente": "noticia", "sector": "parques_industriales", "ciudad": "Salinas Victoria", "estado": "Nuevo León", "monto_estimado": 52_000_000, "descripcion": "Cuarta fase del parque chino-mexicano. Vialidades, banquetas, pisos industriales y canastillas.", "url_fuente": "elhorizonte.mx", "lat": 25.9690, "lng": -100.3008},
    {"titulo": "Audi planta SUVs eléctricos San José Chiapa", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "San José Chiapa", "estado": "Puebla", "monto_estimado": 68_000_000, "descripcion": "Ampliación 25,000 m² para línea de SUVs eléctricos premium. Tolerancias FF/FL premium.", "url_fuente": "expansion.mx", "lat": 19.3033, "lng": -97.8197},
    {"titulo": "Refinería Dos Bocas mantenimiento integral", "fuente": "licitacion", "sector": "expansion_planta", "ciudad": "Paraíso", "estado": "Tabasco", "monto_estimado": 31_000_000, "descripcion": "Mantenimiento pisos industriales, plataformas técnicas y canastillas en refinería Olmeca.", "url_fuente": "compranet.gob.mx", "lat": 18.4036, "lng": -93.1944},
    {"titulo": "Tijuana East Industrial Park naves nearshoring", "fuente": "licitacion", "sector": "nearshoring", "ciudad": "Tijuana", "estado": "Baja California", "monto_estimado": 44_500_000, "descripcion": "Construcción de 6 naves industriales de 5,000 m² c/u para empresas asiáticas.", "url_fuente": "compranet.gob.mx", "lat": 32.4150, "lng": -116.8970},
    {"titulo": "Ford Hermosillo expansión eléctrica", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "Hermosillo", "estado": "Sonora", "monto_estimado": 49_000_000, "descripcion": "Ampliación planta para Mustang Mach-E. Pisos superplanos, pavimentación y canastillas.", "url_fuente": "reforma.com", "lat": 29.0892, "lng": -110.9613},
    {"titulo": "Cemex Mérida modernización Yucatán", "fuente": "referencia", "sector": "manufactura", "ciudad": "Mérida", "estado": "Yucatán", "monto_estimado": 15_600_000, "descripcion": "Rehabilitación de pisos y plataformas en planta cementera. Tren Maya impulsa demanda.", "url_fuente": "interno", "lat": 20.9674, "lng": -89.5926},
    {"titulo": "Toyota Apaseo expansión Tacoma 2027", "fuente": "noticia", "sector": "manufactura", "ciudad": "Apaseo el Grande", "estado": "Guanajuato", "monto_estimado": 27_300_000, "descripcion": "Expansión 14,000 m² para nueva generación Tacoma híbrida.", "url_fuente": "elfinanciero.com.mx", "lat": 20.5478, "lng": -100.7039},
    {"titulo": "Honda El Salto Jalisco línea SUV", "fuente": "licitacion", "sector": "manufactura", "ciudad": "El Salto", "estado": "Jalisco", "monto_estimado": 23_500_000, "descripcion": "Piso superplano 11,500 m² para nueva línea SUVs híbridas. Acabado especializado.", "url_fuente": "compranet.gob.mx", "lat": 20.5167, "lng": -103.1833},
    {"titulo": "Equinix MX2 Querétaro Tier IV", "fuente": "noticia", "sector": "data_centers", "ciudad": "Querétaro", "estado": "Querétaro", "monto_estimado": 71_000_000, "descripcion": "Segundo data center Equinix en Querétaro. Pisos antiestáticos + raised floors técnicos.", "url_fuente": "datacenterdynamics.com", "lat": 20.6080, "lng": -100.4060},
    {"titulo": "Mabe Saltillo modernización pisos", "fuente": "referencia", "sector": "manufactura", "ciudad": "Saltillo", "estado": "Coahuila", "monto_estimado": 8_400_000, "descripcion": "Repulido y restitución de juntas en planta de electrodomésticos.", "url_fuente": "interno", "lat": 25.4232, "lng": -100.9966},
    {"titulo": "Parque industrial Vesta Mérida sureste", "fuente": "noticia", "sector": "parques_industriales", "ciudad": "Mérida", "estado": "Yucatán", "monto_estimado": 35_800_000, "descripcion": "Nuevo parque industrial 25 hectáreas en corredor Tren Maya. Greenfield.", "url_fuente": "vesta.com", "lat": 20.9300, "lng": -89.6500},
    {"titulo": "Kia Pesquería ampliación EV", "fuente": "noticia", "sector": "expansion_planta", "ciudad": "Pesquería", "estado": "Nuevo León", "monto_estimado": 41_200_000, "descripcion": "Ampliación 18,000 m² para línea de SUVs eléctricos K3.", "url_fuente": "milenio.com", "lat": 25.7886, "lng": -100.0497},
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

    # Radar (incremental: insert items missing by titulo)
    existing_radar = {d["titulo"] for d in await db.radar.find({}, {"_id": 0, "titulo": 1}).to_list(5000)}
    rdocs_new = []
    for r in SEED_RADAR:
        if r["titulo"] not in existing_radar:
            d = dict(r)
            d["id"] = new_id()
            d["score"] = 0
            d["hotness"] = "cold"
            d["score_reasons"] = []
            d["detected_at"] = iso(now_utc())
            rdocs_new.append(d)
    if rdocs_new:
        await db.radar.insert_many(rdocs_new)

    # Empresas (incremental: agregar las que falten por nombre)
    existing_emp = {d["nombre"] for d in await db.empresas.find({}, {"_id": 0, "nombre": 1}).to_list(5000)}
    emp_new = []
    for e in SEED_EMPRESAS:
        if e["nombre"] not in existing_emp:
            d = dict(e)
            d["id"] = new_id()
            d["created_at"] = iso(now_utc())
            emp_new.append(d)
    if emp_new:
        await db.empresas.insert_many(emp_new)

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
# V2: WhatsApp Alerts (Twilio with MOCK fallback)
# ----------------------------------------------------------------------------
async def send_whatsapp(to: str, body: str) -> dict:
    """Send WhatsApp. Falls back to MOCK (log only) if Twilio creds missing."""
    if not TWILIO_ENABLED:
        logger.info(f"[WHATSAPP MOCK] → {to}: {body[:80]}…")
        return {"mock": True, "to": to, "status": "queued_mock"}
    try:
        from twilio.rest import Client as TwClient
        cli = TwClient(TWILIO_SID, TWILIO_TOKEN)
        # Twilio SDK is sync - run in thread to avoid blocking event loop
        msg = await asyncio.to_thread(
            lambda: cli.messages.create(from_=TWILIO_FROM, to=to, body=body)
        )
        return {"mock": False, "sid": msg.sid, "status": msg.status, "to": to}
    except Exception as e:
        logger.exception("Twilio send error")
        return {"mock": False, "error": str(e), "status": "failed", "to": to}


async def create_hot_alert(entity_type: str, entity_id: str, titulo: str, score: int, monto: float, sector: str, ciudad: str):
    """Persist alert + dispatch WhatsApp when an opportunity/radar hits HOT (>=85)."""
    body = (
        f"DEYMA RADAR · ALERTA HOT ({score}/100)\n"
        f"{titulo}\n"
        f"Sector: {sector} · {ciudad}\n"
        f"Monto: MXN ${monto:,.0f}\n"
        f"Acción: revisa el sistema y asigna comercial."
    )
    alert_doc = {
        "id": new_id(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "titulo": titulo,
        "score": score,
        "monto": monto,
        "sector": sector,
        "ciudad": ciudad,
        "body": body,
        "created_at": iso(now_utc()),
        "channel": "whatsapp",
        "to": DEYMA_ALERT_PHONE or "MOCK",
        "status": "pending",
        "mock": not TWILIO_ENABLED,
    }
    if DEYMA_ALERT_PHONE or not TWILIO_ENABLED:
        result = await send_whatsapp(DEYMA_ALERT_PHONE or "whatsapp:+0000000000", body)
        alert_doc["status"] = result.get("status", "unknown")
        alert_doc["mock"] = result.get("mock", True)
        if result.get("sid"):
            alert_doc["sid"] = result["sid"]
        if result.get("error"):
            alert_doc["error"] = result["error"]
    await db.alertas.insert_one(alert_doc)
    alert_doc.pop("_id", None)
    return alert_doc


@api.get("/alertas")
async def list_alertas(user: dict = Depends(get_current_user)):
    items = await db.alertas.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"items": items, "twilio_enabled": TWILIO_ENABLED, "alert_phone": DEYMA_ALERT_PHONE or None}


@api.post("/alertas/test")
async def test_alerta(user: dict = Depends(require_roles("director"))):
    """Manual test of WhatsApp pipeline."""
    return await create_hot_alert("test", "manual", "Prueba manual de alerta HOT", 90, 1_000_000, "manufactura", "Querétaro")


# ----------------------------------------------------------------------------
# V2: Convertir oportunidad ganada → obra
# ----------------------------------------------------------------------------
class ConvertirObraIn(BaseModel):
    nombre: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin_estimada: Optional[str] = None
    ciudad: Optional[str] = None


@api.post("/oportunidades/{oid}/convertir-obra")
async def convertir_a_obra(oid: str, body: ConvertirObraIn, user: dict = Depends(get_current_user)):
    op = await db.oportunidades.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    if op.get("stage") != "ganada":
        raise HTTPException(status_code=400, detail="La oportunidad debe estar en etapa 'ganada'")
    existing = await db.obras.find_one({"_op_id": oid})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una obra creada desde esta oportunidad")
    emp = await db.empresas.find_one({"id": op["empresa_id"]}, {"_id": 0}) or {}
    obra_doc = {
        "id": new_id(),
        "_op_id": oid,
        "empresa_id": op["empresa_id"],
        "cotizacion_id": None,
        "nombre": body.nombre or op["titulo"],
        "monto_contratado": op["monto_estimado"],
        "fecha_inicio": body.fecha_inicio or iso(now_utc()),
        "fecha_fin_estimada": body.fecha_fin_estimada or iso(now_utc() + timedelta(days=120)),
        "estado": "planeacion",
        "avance_pct": 0,
        "ciudad": body.ciudad or emp.get("ciudad", "Querétaro"),
        "estado_geo": emp.get("estado", "Querétaro"),
        "created_at": iso(now_utc()),
    }
    await db.obras.insert_one(obra_doc)
    obra_doc.pop("_id", None)
    obra_doc.pop("_op_id", None)
    # Registrar actividad automática
    await db.actividades.insert_one({
        "id": new_id(),
        "oportunidad_id": oid,
        "tipo": "nota",
        "fecha": iso(now_utc()),
        "descripcion": f"Oportunidad convertida a obra: {obra_doc['nombre']}",
        "owner_id": user["id"],
        "completada": True,
        "created_at": iso(now_utc()),
    })
    return obra_doc


# ----------------------------------------------------------------------------
# V2: Importar proyecto del Radar al CRM como Oportunidad
# ----------------------------------------------------------------------------
class ImportarRadarIn(BaseModel):
    empresa_id: str
    probabilidad: int = 25
    stage: Stage = "prospeccion"


@api.post("/radar/{rid}/importar")
async def importar_radar(rid: str, body: ImportarRadarIn, user: dict = Depends(get_current_user)):
    p = await db.radar.find_one({"id": rid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto radar no encontrado")
    emp = await db.empresas.find_one({"id": body.empresa_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    op = {
        "id": new_id(),
        "empresa_id": body.empresa_id,
        "titulo": p["titulo"],
        "sector": p["sector"],
        "descripcion": p["descripcion"],
        "monto_estimado": p["monto_estimado"],
        "stage": body.stage,
        "probabilidad": body.probabilidad,
        "score": p.get("score", 0),
        "hotness": p.get("hotness", "cold"),
        "score_reasons": p.get("score_reasons", []),
        "owner_id": user["id"],
        "fecha_cierre": None,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
        "_from_radar": rid,
    }
    await db.oportunidades.insert_one(op)
    op.pop("_id", None)
    op.pop("_from_radar", None)
    return op


# ----------------------------------------------------------------------------
# V2: Actividades / Tareas por oportunidad
# ----------------------------------------------------------------------------
ActividadTipo = Literal["llamada", "correo", "reunion", "visita", "nota", "tarea"]


class ActividadIn(BaseModel):
    oportunidad_id: str
    tipo: ActividadTipo
    fecha: str  # ISO datetime
    descripcion: str
    completada: bool = False


class Actividad(ActividadIn):
    id: str
    owner_id: str
    created_at: str


@api.get("/actividades")
async def list_actividades(oportunidad_id: Optional[str] = None, mias: bool = False,
                           pendientes: bool = False, user: dict = Depends(get_current_user)):
    q = {}
    if oportunidad_id:
        q["oportunidad_id"] = oportunidad_id
    if mias:
        q["owner_id"] = user["id"]
    if pendientes:
        q["completada"] = False
    items = await db.actividades.find(q, {"_id": 0}).sort("fecha", -1).to_list(500)
    return items


@api.post("/actividades")
async def create_actividad(body: ActividadIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["owner_id"] = user["id"]
    doc["created_at"] = iso(now_utc())
    await db.actividades.insert_one(doc)
    doc.pop("_id", None)
    return doc


class ActividadToggle(BaseModel):
    completada: bool


@api.patch("/actividades/{aid}")
async def toggle_actividad(aid: str, body: ActividadToggle, user: dict = Depends(get_current_user)):
    res = await db.actividades.update_one({"id": aid}, {"$set": {"completada": body.completada}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return {"ok": True}


@api.delete("/actividades/{aid}")
async def delete_actividad(aid: str, user: dict = Depends(get_current_user)):
    await db.actividades.delete_one({"id": aid})
    return {"ok": True}


# ----------------------------------------------------------------------------
# V2: Documentos (metadata mock — no binary storage)
# ----------------------------------------------------------------------------
class DocumentoIn(BaseModel):
    entidad_tipo: Literal["oportunidad", "empresa", "obra", "cotizacion"]
    entidad_id: str
    nombre: str
    tipo: str  # pdf, jpg, dwg, xlsx, etc.
    tamano_bytes: int = 0
    url: Optional[str] = None  # placeholder when real storage is added


@api.get("/documentos")
async def list_documentos(entidad_tipo: Optional[str] = None, entidad_id: Optional[str] = None,
                          user: dict = Depends(get_current_user)):
    q = {}
    if entidad_tipo:
        q["entidad_tipo"] = entidad_tipo
    if entidad_id:
        q["entidad_id"] = entidad_id
    return await db.documentos.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/documentos")
async def create_documento(body: DocumentoIn, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = new_id()
    doc["uploaded_by"] = user["id"]
    doc["uploaded_by_name"] = user.get("name", "")
    doc["created_at"] = iso(now_utc())
    doc["mock"] = True  # signal no real storage yet
    await db.documentos.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/documentos/{did}")
async def delete_documento(did: str, user: dict = Depends(get_current_user)):
    await db.documentos.delete_one({"id": did})
    return {"ok": True}


# ----------------------------------------------------------------------------
# V2: PDF de Cotización (ReportLab con membrete DEYMA)
# ----------------------------------------------------------------------------
@api.get("/cotizaciones/{cid}/pdf")
async def cotizacion_pdf(cid: str, user: dict = Depends(get_current_user)):
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    emp = await db.empresas.find_one({"id": cot["empresa_id"]}, {"_id": 0}) or {}
    cont = await db.contactos.find_one({"empresa_id": cot["empresa_id"]}, {"_id": 0}) or {}
    pdf_bytes = await asyncio.to_thread(_build_cotizacion_pdf, cot, emp, cont, user)
    import io
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cotizacion_{cot["folio"]}.pdf"'},
    )


def _build_cotizacion_pdf(cot: dict, emp: dict, cont: dict, user: dict) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    import io as _io

    AMBER = colors.HexColor("#f59e0b")
    DARK = colors.HexColor("#18181b")
    GRAY = colors.HexColor("#71717a")
    LIGHT = colors.HexColor("#f4f4f5")

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=f"Cotización {cot['folio']}")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=DARK)
    body_sm = ParagraphStyle("bs", parent=body, fontSize=8, leading=10)

    story = []

    # Header / membrete
    header_data = [
        [
            Paragraph(
                '<font color="#f59e0b" size="22"><b>DEYMA</b></font>'
                '<font color="#71717a" size="22"> · RADAR</font>'
                '<br/><font color="#71717a" size="7">SISTEMA DE INTELIGENCIA COMERCIAL · CONSTRUCCIÓN INDUSTRIAL</font>',
                body,
            ),
            Paragraph(
                f'<b>COTIZACIÓN</b><br/>'
                f'<font color="#f59e0b"><b>{cot["folio"]}</b></font><br/>'
                f'<font size="7" color="#71717a">FECHA: {datetime.fromisoformat(cot["created_at"].replace("Z","+00:00")).strftime("%d/%m/%Y") if isinstance(cot["created_at"], str) else ""}</font>',
                ParagraphStyle("hd", parent=body, alignment=TA_RIGHT, fontSize=10, leading=12),
            ),
        ]
    ]
    h_tbl = Table(header_data, colWidths=[11 * cm, 6 * cm])
    h_tbl.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, AMBER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(h_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # Cliente
    cli_data = [[
        Paragraph(
            '<font color="#71717a"><b>CLIENTE</b></font><br/>'
            f'<b>{emp.get("nombre","—")}</b><br/>'
            f'{emp.get("ciudad","")}, {emp.get("estado","")}<br/>'
            f'<font color="#71717a">{emp.get("rfc","RFC s/inf.")}</font>',
            body,
        ),
        Paragraph(
            '<font color="#71717a"><b>CONTACTO</b></font><br/>'
            f'<b>{cont.get("nombre","—")}</b><br/>'
            f'{cont.get("puesto","")}<br/>'
            f'<font color="#71717a">{cont.get("email","")} · {cont.get("telefono","")}</font>',
            body,
        ),
        Paragraph(
            '<font color="#71717a"><b>PROYECTO</b></font><br/>'
            f'<b>{cot["proyecto_titulo"]}</b><br/>'
            f'<font color="#71717a">Validez: {cot["validez_dias"]} días</font><br/>'
            f'<font color="#71717a">Estado: {cot["estado"].upper()}</font>',
            body,
        ),
    ]]
    cli_tbl = Table(cli_data, colWidths=[5.5 * cm, 5.5 * cm, 6 * cm])
    cli_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(cli_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # Items table
    items_data = [["#", "DESCRIPCIÓN", "CANT.", "UNIDAD", "P. UNIT.", "SUBTOTAL"]]
    for i, it in enumerate(cot["items"], 1):
        subt = it["cantidad"] * it["precio_unitario"]
        items_data.append([
            str(i),
            Paragraph(it["descripcion"], body_sm),
            f"{it['cantidad']:,.2f}",
            it["unidad"],
            f"${it['precio_unitario']:,.2f}",
            f"${subt:,.2f}",
        ])
    it_tbl = Table(items_data, colWidths=[0.8 * cm, 8.5 * cm, 2 * cm, 1.5 * cm, 2 * cm, 2.5 * cm])
    it_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, 0), 1, AMBER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(it_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Totals
    totals_data = [
        ["", "SUBTOTAL", f"${cot['subtotal']:,.2f}"],
        ["", f"IVA ({cot['iva_pct']}%)", f"${cot['iva_monto']:,.2f}"],
        ["", "TOTAL MXN", f"${cot['total']:,.2f}"],
    ]
    tot_tbl = Table(totals_data, colWidths=[10 * cm, 4 * cm, 3.3 * cm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (-1, 1), 9),
        ("TEXTCOLOR", (1, 0), (-1, 1), GRAY),
        ("FONTSIZE", (1, 2), (-1, 2), 13),
        ("TEXTCOLOR", (1, 2), (-1, 2), AMBER),
        ("LINEABOVE", (1, 2), (-1, 2), 1, AMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 0.7 * cm))

    # Notas
    if cot.get("notas"):
        story.append(Paragraph('<font color="#71717a"><b>NOTAS</b></font>', body))
        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(cot["notas"], body_sm))
        story.append(Spacer(1, 0.4 * cm))

    # Condiciones
    cond_text = (
        "<b>CONDICIONES COMERCIALES</b><br/>"
        f"• Vigencia de la cotización: <b>{cot['validez_dias']} días naturales</b> a partir de la fecha de emisión.<br/>"
        "• Precios en pesos mexicanos (MXN), no incluyen otros impuestos distintos al IVA indicado.<br/>"
        "• Forma de pago: 50% anticipo, 50% contra entrega (sujeto a negociación).<br/>"
        "• Tiempo de entrega: a convenir según calendario de obra.<br/>"
        "• Garantía: pisos industriales 12 meses, mantenimiento 6 meses contra defectos de instalación.<br/>"
    )
    story.append(Paragraph(cond_text, body_sm))
    story.append(Spacer(1, 1.2 * cm))

    # Firma
    firma_data = [[
        Paragraph(
            '<para alignment="center">'
            '_______________________________<br/>'
            f'<b>{user.get("name","DEYMA")}</b><br/>'
            f'<font size="7" color="#71717a">{user.get("email","")}</font><br/>'
            '<font size="7" color="#71717a">DEYMA CONSTRUCCIONES S.A. DE C.V.</font>'
            '</para>',
            body_sm,
        ),
        Paragraph(
            '<para alignment="center">'
            '_______________________________<br/>'
            f'<b>{cont.get("nombre","Cliente")}</b><br/>'
            f'<font size="7" color="#71717a">{emp.get("nombre","")}</font><br/>'
            '<font size="7" color="#71717a">ACEPTACIÓN DE COTIZACIÓN</font>'
            '</para>',
            body_sm,
        ),
    ]]
    f_tbl = Table(firma_data, colWidths=[8.5 * cm, 8.5 * cm])
    f_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(f_tbl)

    # Footer
    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY)
        canvas.drawString(1.8 * cm, 1 * cm, "DEYMA · RADAR  ·  Sistema de Inteligencia Comercial")
        canvas.drawRightString(20 * cm, 1 * cm, f"Folio {cot['folio']}  ·  Página {_doc.page}")
        canvas.setStrokeColor(AMBER)
        canvas.setLineWidth(1.2)
        canvas.line(1.8 * cm, 1.3 * cm, 20 * cm, 1.3 * cm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Auto-trigger HOT alerts on scoring updates
# ----------------------------------------------------------------------------
@api.post("/oportunidades/{oid}/score-and-alert")
async def score_and_alert(oid: str, user: dict = Depends(get_current_user)):
    """Wrapper: score the opportunity and dispatch alert if HOT (>=85)."""
    op = await db.oportunidades.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    result = await ai_score_opportunity(op["titulo"], op["sector"], op["descripcion"], op["monto_estimado"])
    await db.oportunidades.update_one(
        {"id": oid},
        {"$set": {"score": result["score"], "hotness": result["hotness"],
                  "score_reasons": result["reasons"], "updated_at": iso(now_utc())}},
    )
    alert = None
    if result["score"] >= 85:
        emp = await db.empresas.find_one({"id": op["empresa_id"]}, {"_id": 0}) or {}
        alert = await create_hot_alert("oportunidad", oid, op["titulo"], result["score"],
                                       op["monto_estimado"], op["sector"], emp.get("ciudad", "Querétaro"))
    return {"score": result, "alert": alert}


# ----------------------------------------------------------------------------
# V3.5: SendGrid email service (with MOCK fallback)
# ----------------------------------------------------------------------------
async def send_email_sendgrid(to: str, subject: str, html: str, plain: str = None,
                              cc: List[str] = None, attachments: List[dict] = None) -> dict:
    """Send transactional email via SendGrid. Falls back to MOCK if creds missing."""
    if not SENDGRID_ENABLED:
        logger.info(f"[EMAIL MOCK] → {to} | {subject[:50]}")
        return {"mock": True, "to": to, "subject": subject, "status": "queued_mock"}
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (Mail, Email, To, Cc, Content, Attachment,
                                            FileContent, FileName, FileType, Disposition)
        import base64
        message = Mail(
            from_email=Email(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
            to_emails=To(to),
            subject=subject,
            html_content=Content("text/html", html or "") if html else None,
            plain_text_content=Content("text/plain", plain) if plain else None,
        )
        if cc:
            for c in cc:
                message.add_cc(Cc(c))
        if attachments:
            for att in attachments:
                content_b64 = att.get("content_base64") or base64.b64encode(att.get("content", b"")).decode()
                a = Attachment(
                    FileContent(content_b64),
                    FileName(att.get("filename", "attachment")),
                    FileType(att.get("content_type", "application/octet-stream")),
                    Disposition("attachment"),
                )
                message.add_attachment(a)

        def _send():
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            return sg.send(message)

        resp = await asyncio.to_thread(_send)
        return {"mock": False, "status_code": resp.status_code, "to": to, "status": "sent" if resp.status_code in (200, 201, 202) else "failed"}
    except Exception as e:
        logger.exception("SendGrid send error")
        return {"mock": False, "error": str(e), "status": "failed", "to": to}


# ----------------------------------------------------------------------------
# V3.5: Panel de Seguimiento a Cotizaciones
# ----------------------------------------------------------------------------
class AprobarEnviarIn(BaseModel):
    to: EmailStr
    cc: Optional[List[EmailStr]] = []
    subject: str
    body_html: str
    body_text: Optional[str] = None
    adjuntar_pdf: bool = True


class RegistrarRespuestaIn(BaseModel):
    de: str  # nombre o correo del remitente
    de_email: Optional[EmailStr] = None
    asunto: str
    contenido: str
    fecha: Optional[str] = None  # ISO; default ahora
    adjuntos: Optional[List[dict]] = []  # [{nombre, tipo, tamano_bytes}]
    sentimiento: Optional[Literal["positivo", "neutro", "negativo"]] = "neutro"

    @field_validator("de_email", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class MarcarEstadoIn(BaseModel):
    estado: Literal["aceptada", "rechazada"]
    nota: Optional[str] = None


def _history_entry(actor: dict, tipo: str, detalle: str, meta: dict = None) -> dict:
    return {
        "id": new_id(),
        "tipo": tipo,
        "detalle": detalle,
        "actor_id": actor.get("id"),
        "actor_name": actor.get("name", ""),
        "actor_role": actor.get("role", ""),
        "ts": iso(now_utc()),
        "meta": meta or {},
    }


@api.get("/cotizaciones/{cid}/email-template")
async def get_email_template(cid: str, user: dict = Depends(get_current_user)):
    """Returns a prefilled template (subject + html + text) that the user can edit before sending."""
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    emp = await db.empresas.find_one({"id": cot["empresa_id"]}, {"_id": 0}) or {}
    cont = await db.contactos.find_one({"empresa_id": cot["empresa_id"]}, {"_id": 0}) or {}
    subject = f"Cotización {cot['folio']} — {cot['proyecto_titulo']} · DEYMA"
    saludo = (cont.get("nombre") or emp.get("nombre") or "Estimado(a) cliente").split()[0]
    items_html = "".join(
        f"<tr><td style='padding:6px 8px;border-bottom:1px solid #eee'>{it['descripcion']}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee;text-align:right;font-family:monospace'>{it['cantidad']:,.2f} {it['unidad']}</td>"
        f"<td style='padding:6px 8px;border-bottom:1px solid #eee;text-align:right;font-family:monospace'>${it['cantidad']*it['precio_unitario']:,.2f}</td></tr>"
        for it in cot["items"]
    )
    body_html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;color:#222;max-width:640px;margin:auto">
<div style="border-top:4px solid #f59e0b;padding-top:18px">
  <h2 style="margin:0 0 4px"><span style="color:#f59e0b">DEYMA</span> <span style="color:#71717a">· RADAR</span></h2>
  <p style="color:#71717a;font-size:11px;letter-spacing:.12em;margin:0">CONSTRUCCIÓN INDUSTRIAL · QUERÉTARO · BAJÍO</p>
</div>
<p>Estimado(a) {saludo}:</p>
<p>Le hacemos llegar nuestra <b>cotización formal {cot['folio']}</b> para el proyecto <b>{cot['proyecto_titulo']}</b>.</p>
<p>Resumen de partidas:</p>
<table style="border-collapse:collapse;width:100%;font-size:13px;margin:8px 0">
<thead><tr style="background:#18181b;color:#fff"><th style="padding:8px;text-align:left">Concepto</th><th style="padding:8px;text-align:right">Cantidad</th><th style="padding:8px;text-align:right">Subtotal</th></tr></thead>
<tbody>{items_html}</tbody>
</table>
<table style="width:100%;font-size:13px;margin-top:8px"><tbody>
<tr><td style="text-align:right;padding:4px;color:#71717a">Subtotal</td><td style="text-align:right;padding:4px;font-family:monospace;width:140px">${cot['subtotal']:,.2f}</td></tr>
<tr><td style="text-align:right;padding:4px;color:#71717a">IVA ({cot['iva_pct']}%)</td><td style="text-align:right;padding:4px;font-family:monospace">${cot['iva_monto']:,.2f}</td></tr>
<tr><td style="text-align:right;padding:6px;font-weight:bold;color:#f59e0b">TOTAL MXN</td><td style="text-align:right;padding:6px;font-family:monospace;font-weight:bold;color:#f59e0b;font-size:16px">${cot['total']:,.2f}</td></tr>
</tbody></table>
<p>Vigencia: <b>{cot['validez_dias']} días naturales</b>. Adjunto encontrará el PDF formal con condiciones comerciales completas.</p>
<p>Quedo atento a sus comentarios para agendar una visita técnica y avanzar con la programación de la obra.</p>
<p style="margin-top:24px">Saludos cordiales,<br/><b>{cot.get('owner_name') or 'Equipo DEYMA'}</b><br/>
<span style="color:#71717a;font-size:12px">DEYMA Construcciones S.A. de C.V. · cotizaciones@deyma.mx</span></p>
</body></html>"""
    body_text = (
        f"Estimado(a) {saludo}:\n\n"
        f"Le hacemos llegar nuestra cotización formal {cot['folio']} para el proyecto {cot['proyecto_titulo']}.\n\n"
        f"Subtotal: ${cot['subtotal']:,.2f}\nIVA ({cot['iva_pct']}%): ${cot['iva_monto']:,.2f}\nTOTAL MXN: ${cot['total']:,.2f}\n\n"
        f"Vigencia: {cot['validez_dias']} días. Adjunto el PDF formal.\n\n"
        "Saludos cordiales,\nEquipo DEYMA"
    )
    return {
        "to": cont.get("email") or "",
        "cc": [],
        "subject": subject,
        "body_html": body_html,
        "body_text": body_text,
    }


@api.post("/cotizaciones/{cid}/aprobar-enviar")
async def aprobar_enviar(cid: str, body: AprobarEnviarIn,
                         user: dict = Depends(require_roles("director", "comercial"))):
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if cot.get("estado") in ("aceptada", "rechazada"):
        raise HTTPException(status_code=400, detail=f"Cotización ya está en estado final ({cot.get('estado')})")

    # Preparar adjuntos: PDF cotización
    attachments = []
    if body.adjuntar_pdf:
        emp = await db.empresas.find_one({"id": cot["empresa_id"]}, {"_id": 0}) or {}
        cont = await db.contactos.find_one({"empresa_id": cot["empresa_id"]}, {"_id": 0}) or {}
        pdf_bytes = await asyncio.to_thread(_build_cotizacion_pdf, cot, emp, cont, user)
        import base64 as _b64
        attachments.append({
            "content_base64": _b64.b64encode(pdf_bytes).decode(),
            "filename": f"cotizacion_{cot['folio']}.pdf",
            "content_type": "application/pdf",
        })

    cc_list = list(body.cc or [])
    send_result = await send_email_sendgrid(
        to=body.to, subject=body.subject, html=body.body_html, plain=body.body_text,
        cc=cc_list, attachments=attachments,
    )

    outbound = {
        "id": new_id(),
        "to": body.to,
        "cc": cc_list,
        "subject": body.subject,
        "body_html": body.body_html,
        "body_text": body.body_text or "",
        "sent_at": iso(now_utc()),
        "sent_by": user.get("id"),
        "sent_by_name": user.get("name"),
        "sent_by_role": user.get("role"),
        "status": send_result.get("status", "unknown"),
        "mock": send_result.get("mock", True),
        "attachments": [{"filename": a["filename"], "content_type": a["content_type"]} for a in attachments],
        "error": send_result.get("error"),
    }

    historia_entry = _history_entry(
        user, "aprobacion_envio",
        f"Cotización aprobada y enviada a {body.to}" + (" (MOCK)" if send_result.get("mock") else ""),
        {"to": body.to, "subject": body.subject, "status": outbound["status"]},
    )

    await db.cotizaciones.update_one(
        {"id": cid},
        {
            "$set": {"estado": "aprobada_direccion", "aprobada_at": iso(now_utc()),
                     "aprobada_por": user.get("id"), "aprobada_por_name": user.get("name")},
            "$push": {"outbound_emails": outbound, "historia": historia_entry},
        },
    )
    return {"ok": True, "outbound": outbound, "mock": send_result.get("mock", True)}


@api.post("/cotizaciones/{cid}/respuesta")
async def registrar_respuesta(cid: str, body: RegistrarRespuestaIn,
                              user: dict = Depends(require_roles("director", "comercial"))):
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    inbound = {
        "id": new_id(),
        "de": body.de,
        "de_email": body.de_email,
        "asunto": body.asunto,
        "contenido": body.contenido,
        "fecha": body.fecha or iso(now_utc()),
        "adjuntos": body.adjuntos or [],
        "sentimiento": body.sentimiento or "neutro",
        "registrado_por": user.get("id"),
        "registrado_por_name": user.get("name"),
        "registrado_at": iso(now_utc()),
    }
    historia_entry = _history_entry(
        user, "respuesta_cliente",
        f"Respuesta del cliente registrada: {body.asunto[:60]}",
        {"de": body.de, "sentimiento": body.sentimiento},
    )
    await db.cotizaciones.update_one(
        {"id": cid},
        {"$push": {"inbound_replies": inbound, "historia": historia_entry}},
    )
    return inbound


@api.post("/cotizaciones/{cid}/marcar")
async def marcar_estado(cid: str, body: MarcarEstadoIn,
                        user: dict = Depends(require_roles("director", "comercial"))):
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    historia_entry = _history_entry(
        user, "cambio_estado",
        f"Cotización marcada como {body.estado.upper()}" + (f": {body.nota}" if body.nota else ""),
        {"estado_anterior": cot.get("estado"), "estado_nuevo": body.estado},
    )
    upd = {"estado": body.estado, "cerrada_at": iso(now_utc()),
           "cerrada_por": user.get("id"), "cerrada_por_name": user.get("name")}
    if body.nota:
        upd["nota_cierre"] = body.nota
    await db.cotizaciones.update_one(
        {"id": cid},
        {"$set": upd, "$push": {"historia": historia_entry}},
    )
    return {"ok": True, "estado": body.estado}


@api.get("/cotizaciones/{cid}/seguimiento")
async def get_seguimiento(cid: str, user: dict = Depends(get_current_user)):
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    emp = await db.empresas.find_one({"id": cot["empresa_id"]}, {"_id": 0}) or {}
    cont = await db.contactos.find_one({"empresa_id": cot["empresa_id"]}, {"_id": 0}) or {}
    return {
        "cotizacion": cot,
        "empresa": emp,
        "contacto": cont,
        "outbound_emails": cot.get("outbound_emails", []),
        "inbound_replies": cot.get("inbound_replies", []),
        "historia": cot.get("historia", []),
        "sendgrid_enabled": SENDGRID_ENABLED,
        "sendgrid_from": SENDGRID_FROM_EMAIL or None,
    }


# ----------------------------------------------------------------------------
# V4: Portal de Alta de Clientes (público + flujo aprobación Director y Socio)
# ----------------------------------------------------------------------------
def _gen_dfnum() -> str:
    import random
    return f"DFNUM-{random.randint(100000, 999999)}"


def _gen_folio_alta(seq: int) -> str:
    return f"ALT-{datetime.now().year}-{seq:04d}"


async def get_current_cliente(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    if payload.get("type") != "client":
        raise HTTPException(status_code=403, detail="Token no es de cliente")
    cli = await db.clientes_alta.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cli


def create_client_token(client_id: str, dfnum: str) -> str:
    return jwt.encode({
        "sub": client_id, "dfnum": dfnum, "type": "client",
        "exp": now_utc() + timedelta(hours=12),
    }, JWT_SECRET, algorithm=JWT_ALGO)


@api.post("/clientes/alta")
async def alta_cliente(
    # Datos generales
    razon_social: str = Form(...),
    rfc: str = Form(...),
    domicilio_fiscal: str = Form(...),
    domicilio_planta: str = Form(""),
    # Login del cliente
    email: EmailStr = Form(...),
    password: str = Form(..., min_length=6),
    # Contactos
    contacto_tecnico_nombre: str = Form(...),
    contacto_tecnico_tel: str = Form(...),
    contacto_tecnico_correo: EmailStr = Form(...),
    contacto_compras_nombre: str = Form(...),
    contacto_compras_tel: str = Form(...),
    contacto_compras_correo: EmailStr = Form(...),
    contacto_cxp_nombre: str = Form(...),
    contacto_cxp_tel: str = Form(...),
    contacto_cxp_correo: EmailStr = Form(...),
    # Políticas (aceptación)
    politica_validacion_tecnica: bool = Form(...),
    politica_firma_actas: bool = Form(...),
    politica_separacion_errores: bool = Form(...),
    politica_ordenes_cambio: bool = Form(...),
    politica_cero_fianzas: bool = Form(...),
    # Financieras
    fin_recepcion_oc: bool = Form(...),
    fin_anticipo: bool = Form(...),
    fin_dia_1: bool = Form(...),
    # Firmas (texto)
    firma_representante_nombre: str = Form(...),
    firma_representante_sello: str = Form(""),  # opcional
    firma_tecnico_nombre: str = Form(...),
    firma_tecnico_area: str = Form(""),
    # Archivos (PDFs)
    csf: UploadFile = File(...),  # Constancia Situación Fiscal
    acta_constitutiva: UploadFile = File(...),
    poder_representante: UploadFile = File(...),
    ine_representante: UploadFile = File(...),
    comprobante_domicilio: UploadFile = File(...),
):
    # Validar duplicados por RFC o email
    if await db.clientes_alta.find_one({"rfc": rfc.upper()}):
        raise HTTPException(status_code=400, detail=f"Ya existe una solicitud con el RFC {rfc}")
    if await db.clientes_alta.find_one({"email": email.lower()}):
        raise HTTPException(status_code=400, detail=f"Ya existe una solicitud con el correo {email}")

    # Subir archivos a GridFS
    async def _upload(f: UploadFile, doc_type: str) -> dict:
        contents = await f.read()
        max_size = 10 * 1024 * 1024  # 10 MB por archivo
        if len(contents) > max_size:
            raise HTTPException(status_code=400, detail=f"{doc_type} excede 10 MB")
        if not f.content_type or "pdf" not in f.content_type.lower():
            # permitir image/* también para INE
            if not (f.content_type and "image" in f.content_type.lower()):
                raise HTTPException(status_code=400, detail=f"{doc_type} debe ser PDF (o imagen para INE)")
        fid = await gridfs_bucket.upload_from_stream(
            f.filename or doc_type,
            contents,
            metadata={"doc_type": doc_type, "content_type": f.content_type, "uploaded_at": iso(now_utc())},
        )
        return {"file_id": str(fid), "filename": f.filename, "content_type": f.content_type, "size": len(contents)}

    docs = {
        "csf": await _upload(csf, "csf"),
        "acta": await _upload(acta_constitutiva, "acta"),
        "poder": await _upload(poder_representante, "poder"),
        "ine": await _upload(ine_representante, "ine"),
        "comprobante": await _upload(comprobante_domicilio, "comprobante"),
    }

    seq = await db.clientes_alta.count_documents({}) + 1
    folio = _gen_folio_alta(seq)
    cliente_id = new_id()
    doc = {
        "id": cliente_id,
        "folio_registro": folio,
        "dfnum": None,  # se asigna al aprobarse
        "estado": "pendiente",
        "email": email.lower(),
        "password_hash": hash_password(password),
        "razon_social": razon_social,
        "rfc": rfc.upper(),
        "domicilio_fiscal": domicilio_fiscal,
        "domicilio_planta": domicilio_planta,
        "contactos": {
            "tecnico": {"nombre": contacto_tecnico_nombre, "tel": contacto_tecnico_tel, "correo": contacto_tecnico_correo},
            "compras": {"nombre": contacto_compras_nombre, "tel": contacto_compras_tel, "correo": contacto_compras_correo},
            "cuentas_por_pagar": {"nombre": contacto_cxp_nombre, "tel": contacto_cxp_tel, "correo": contacto_cxp_correo},
        },
        "politicas": {
            "validacion_tecnica": politica_validacion_tecnica,
            "firma_actas": politica_firma_actas,
            "separacion_errores": politica_separacion_errores,
            "ordenes_cambio": politica_ordenes_cambio,
            "cero_fianzas": politica_cero_fianzas,
        },
        "financieras": {"recepcion_oc": fin_recepcion_oc, "anticipo": fin_anticipo, "dia_1": fin_dia_1},
        "firmas": {
            "representante": {"nombre": firma_representante_nombre, "sello": firma_representante_sello},
            "tecnico": {"nombre": firma_tecnico_nombre, "area": firma_tecnico_area},
        },
        "documentos": docs,
        "aprobaciones": [],
        "ordenes_compra": [],
        "created_at": iso(now_utc()),
    }
    await db.clientes_alta.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return doc


@api.post("/clientes/login")
async def cliente_login(body: dict):
    dfnum = (body.get("dfnum") or "").strip().upper()
    password = body.get("password") or ""
    if not dfnum or not password:
        raise HTTPException(status_code=400, detail="DFNUM y contraseña requeridos")
    cli = await db.clientes_alta.find_one({"dfnum": dfnum})
    if not cli:
        raise HTTPException(status_code=401, detail="DFNUM o contraseña inválidos")
    if cli.get("estado") != "aprobado_completo":
        raise HTTPException(status_code=403, detail=f"Cliente aún en estado: {cli.get('estado')}. Solo clientes aprobados pueden ingresar.")
    if not verify_password(password, cli.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="DFNUM o contraseña inválidos")
    token = create_client_token(cli["id"], cli["dfnum"])
    cli.pop("password_hash", None)
    cli.pop("_id", None)
    return {"access_token": token, "cliente": cli}


@api.get("/clientes/me")
async def cliente_me(cli: dict = Depends(get_current_cliente)):
    return cli


@api.get("/clientes/status/{folio_or_dfnum}")
async def cliente_status(folio_or_dfnum: str):
    """Consulta pública (con folio o DFNUM) del estado del trámite."""
    q = folio_or_dfnum.strip().upper()
    cli = await db.clientes_alta.find_one({"$or": [{"folio_registro": q}, {"dfnum": q}]},
                                          {"_id": 0, "password_hash": 0, "documentos": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="No se encontró ninguna solicitud con ese folio o DFNUM")
    return {
        "folio_registro": cli["folio_registro"],
        "dfnum": cli.get("dfnum"),
        "razon_social": cli["razon_social"],
        "estado": cli["estado"],
        "aprobaciones": cli.get("aprobaciones", []),
        "created_at": cli["created_at"],
    }


@api.get("/clientes")
async def list_clientes(estado: Optional[str] = None, user: dict = Depends(require_roles("director", "socio", "comercial"))):
    q = {"estado": estado} if estado else {}
    items = await db.clientes_alta.find(q, {"_id": 0, "password_hash": 0, "documentos": 0}).sort("created_at", -1).to_list(500)
    return items


@api.get("/clientes/{cid}")
async def get_cliente(cid: str, user: dict = Depends(require_roles("director", "socio", "comercial"))):
    cli = await db.clientes_alta.find_one({"id": cid}, {"_id": 0, "password_hash": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cli


class AprobacionIn(BaseModel):
    nota: Optional[str] = ""


@api.post("/clientes/{cid}/aprobar")
async def aprobar_cliente(cid: str, body: AprobacionIn, user: dict = Depends(require_roles("director", "socio"))):
    cli = await db.clientes_alta.find_one({"id": cid}, {"_id": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if cli.get("estado") in ("aprobado_completo", "rechazado"):
        raise HTTPException(status_code=400, detail=f"Cliente ya está en estado final: {cli.get('estado')}")
    aprobaciones = cli.get("aprobaciones", [])
    if any(a["rol"] == user["role"] for a in aprobaciones):
        raise HTTPException(status_code=400, detail=f"Ya aprobaste esta solicitud como {user['role']}")
    aprob = {
        "rol": user["role"],
        "user_id": user["id"],
        "user_name": user["name"],
        "nota": body.nota or "",
        "ts": iso(now_utc()),
    }
    aprobaciones.append(aprob)
    # Lógica: necesita Y ambos roles
    roles_aprobados = {a["rol"] for a in aprobaciones}
    nuevo_estado = "pendiente"
    upd = {"aprobaciones": aprobaciones}
    if "director" in roles_aprobados and "socio" in roles_aprobados:
        nuevo_estado = "aprobado_completo"
        upd["dfnum"] = _gen_dfnum()
        upd["aprobado_at"] = iso(now_utc())
    elif "director" in roles_aprobados:
        nuevo_estado = "aprobado_director"
    elif "socio" in roles_aprobados:
        nuevo_estado = "aprobado_socio"
    upd["estado"] = nuevo_estado
    await db.clientes_alta.update_one({"id": cid}, {"$set": upd})
    return {"ok": True, "estado": nuevo_estado, "dfnum": upd.get("dfnum")}


@api.post("/clientes/{cid}/rechazar")
async def rechazar_cliente(cid: str, body: AprobacionIn, user: dict = Depends(require_roles("director", "socio"))):
    cli = await db.clientes_alta.find_one({"id": cid}, {"_id": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if cli.get("estado") in ("aprobado_completo", "rechazado"):
        raise HTTPException(status_code=400, detail=f"Cliente ya está en estado final: {cli.get('estado')}")
    aprobaciones = cli.get("aprobaciones", [])
    aprobaciones.append({
        "rol": user["role"], "user_id": user["id"], "user_name": user["name"],
        "nota": body.nota or "", "ts": iso(now_utc()), "decision": "rechazado",
    })
    await db.clientes_alta.update_one(
        {"id": cid},
        {"$set": {"estado": "rechazado", "rechazado_at": iso(now_utc()), "aprobaciones": aprobaciones}},
    )
    return {"ok": True, "estado": "rechazado"}


@api.get("/clientes/{cid}/file/{doc_key}")
async def get_cliente_file(cid: str, doc_key: str,
                           user: dict = Depends(require_roles("director", "socio", "comercial"))):
    """Sirve un archivo de la solicitud (csf|acta|poder|ine|comprobante)."""
    cli = await db.clientes_alta.find_one({"id": cid}, {"_id": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    docs = cli.get("documentos", {})
    if doc_key not in docs:
        raise HTTPException(status_code=404, detail=f"Documento {doc_key} no encontrado")
    file_meta = docs[doc_key]
    from bson import ObjectId
    try:
        stream = await gridfs_bucket.open_download_stream(ObjectId(file_meta["file_id"]))
    except Exception:
        raise HTTPException(status_code=404, detail="Archivo no disponible en storage")
    contents = await stream.read()
    import io as _io
    return StreamingResponse(
        _io.BytesIO(contents),
        media_type=file_meta.get("content_type") or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{file_meta.get("filename") or doc_key}"'},
    )


# ----- Órdenes de Compra (cliente sube PDF) -----
@api.post("/clientes/ordenes-compra")
async def upload_oc(
    referencia: str = Form(...),
    monto: float = Form(0),
    notas: str = Form(""),
    archivo: UploadFile = File(...),
    cli: dict = Depends(get_current_cliente),
):
    contents = await archivo.read()
    if len(contents) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo excede 15 MB")
    if "pdf" not in (archivo.content_type or "").lower():
        raise HTTPException(status_code=400, detail="La OC debe ser un PDF")
    fid = await gridfs_bucket.upload_from_stream(
        archivo.filename or "orden_compra.pdf",
        contents,
        metadata={"doc_type": "orden_compra", "cliente_id": cli["id"]},
    )
    oc = {
        "id": new_id(),
        "file_id": str(fid),
        "filename": archivo.filename,
        "referencia": referencia,
        "monto": float(monto or 0),
        "notas": notas,
        "size": len(contents),
        "uploaded_at": iso(now_utc()),
        "uploaded_by": "client",
    }
    await db.clientes_alta.update_one({"id": cli["id"]}, {"$push": {"ordenes_compra": oc}})
    return oc


@api.get("/clientes/ordenes-compra")
async def list_oc(cli: dict = Depends(get_current_cliente)):
    full = await db.clientes_alta.find_one({"id": cli["id"]}, {"_id": 0, "ordenes_compra": 1})
    return full.get("ordenes_compra", []) if full else []


@api.get("/clientes/ordenes-compra/{oc_id}/file")
async def download_oc(oc_id: str, cli: dict = Depends(get_current_cliente)):
    full = await db.clientes_alta.find_one({"id": cli["id"]}, {"_id": 0, "ordenes_compra": 1})
    oc = next((o for o in full.get("ordenes_compra", []) if o["id"] == oc_id), None)
    if not oc:
        raise HTTPException(status_code=404, detail="OC no encontrada")
    from bson import ObjectId
    stream = await gridfs_bucket.open_download_stream(ObjectId(oc["file_id"]))
    contents = await stream.read()
    import io as _io
    return StreamingResponse(
        _io.BytesIO(contents), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{oc.get("filename") or "orden_compra.pdf"}"'},
    )


# ----- PDFs (Alta exitosa + Bienvenida) -----
def _build_alta_pdf(cli: dict, kind: str = "alta") -> bytes:
    """kind = 'alta' (Recibido + en revisión) o 'bienvenida' (DFNUM asignado)."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    import io as _io

    AMBER = colors.HexColor("#f59e0b")
    DARK = colors.HexColor("#18181b")
    GRAY = colors.HexColor("#71717a")
    EMERALD = colors.HexColor("#10b981")

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            title=f"DEYMA - {kind.upper()} {cli.get('folio_registro')}")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=DARK)
    body_sm = ParagraphStyle("bs", parent=body, fontSize=8, leading=11, textColor=GRAY)
    story = []

    if kind == "alta":
        title = "EXPEDIENTE RECIBIDO"
        accent_color = AMBER
        msg = (
            "Hemos recibido exitosamente su expediente de alta como nuevo cliente DEYMA. "
            "Su documentación se encuentra <b>en revisión</b> por parte de la Dirección y la Sociedad de "
            "DEYMA Construcciones S.A. de C.V. Le notificaremos por correo cuando su trámite haya sido "
            "concluido. Conserve este comprobante."
        )
        leyenda_status = "EN REVISIÓN"
    else:
        title = "¡BIENVENIDO A DEYMA!"
        accent_color = EMERALD
        msg = (
            "<b>Le damos la más cordial bienvenida a la familia DEYMA.</b><br/><br/>"
            "Es para nosotros un honor que haya elegido a DEYMA Construcciones como su aliado estratégico en "
            "construcción industrial. Su solicitud ha sido <b>aprobada</b> por la Dirección y la Sociedad de "
            "DEYMA, y a partir de este momento usted forma parte de nuestra cartera oficial de clientes.<br/><br/>"
            "Agradecemos profundamente su tiempo y la confianza depositada en nosotros. Estamos comprometidos "
            "a entregar resultados de excelencia en cada uno de los proyectos que emprendamos juntos."
        )
        leyenda_status = "CLIENTE ACTIVO"

    # Header
    story.append(Paragraph(
        '<font color="#f59e0b" size="22"><b>DEYMA</b></font>'
        '<font color="#71717a" size="22"> · RADAR</font>',
        body))
    story.append(Paragraph('<font color="#71717a" size="8">CONSTRUCCIÓN INDUSTRIAL · CONCRETO HIDRÁULICO · PAVIMENTACIÓN · CANASTILLAS</font>', body))
    story.append(Spacer(1, 0.7 * cm))

    # Big banner
    banner_data = [[Paragraph(f'<para alignment="center"><font color="{"#f59e0b" if kind == "alta" else "#10b981"}" size="20"><b>{title}</b></font></para>', body)]]
    banner = Table(banner_data, colWidths=[17 * cm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("LINEABOVE", (0, 0), (-1, -1), 3, accent_color),
        ("LINEBELOW", (0, 0), (-1, -1), 3, accent_color),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))
    story.append(banner)
    story.append(Spacer(1, 0.6 * cm))

    # Folio / DFNUM block
    info_data = [
        [Paragraph('<font color="#71717a" size="8"><b>FOLIO DE REGISTRO</b></font>', body),
         Paragraph(f'<font color="#f59e0b" size="14"><b>{cli.get("folio_registro", "—")}</b></font>', body)],
    ]
    if kind == "bienvenida" and cli.get("dfnum"):
        info_data.append([
            Paragraph('<font color="#71717a" size="8"><b>NÚMERO DE CLIENTE</b></font>', body),
            Paragraph(f'<font color="#10b981" size="16"><b>{cli["dfnum"]}</b></font>', body),
        ])
    info_data.append([
        Paragraph('<font color="#71717a" size="8"><b>FECHA</b></font>', body),
        Paragraph(f'<font size="10">{datetime.now().strftime("%d de %B de %Y · %H:%M")}</font>', body),
    ])
    info_data.append([
        Paragraph('<font color="#71717a" size="8"><b>ESTATUS</b></font>', body),
        Paragraph(f'<font color="{"#f59e0b" if kind == "alta" else "#10b981"}" size="11"><b>{leyenda_status}</b></font>', body),
    ])
    info_tbl = Table(info_data, colWidths=[5 * cm, 12 * cm])
    info_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e4e4e7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # Datos del cliente
    story.append(Paragraph('<font color="#71717a" size="8"><b>DATOS DE LA EMPRESA</b></font>', body))
    story.append(Spacer(1, 0.1 * cm))
    cli_block = [
        ["Razón social:", cli.get("razon_social", "—")],
        ["RFC:", cli.get("rfc", "—")],
        ["Domicilio fiscal:", cli.get("domicilio_fiscal", "—")[:120]],
        ["Representante legal:", cli.get("firmas", {}).get("representante", {}).get("nombre", "—")],
    ]
    cli_tbl = Table(cli_block, colWidths=[4 * cm, 13 * cm])
    cli_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(cli_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # Mensaje
    story.append(Paragraph(msg, body))
    story.append(Spacer(1, 0.6 * cm))

    if kind == "alta":
        # Lista documentos cargados
        story.append(Paragraph('<font color="#71717a" size="8"><b>DOCUMENTOS RECIBIDOS</b></font>', body))
        doc_labels = {
            "csf": "Constancia de Situación Fiscal",
            "acta": "Carátula del Acta Constitutiva",
            "poder": "Poder del Representante Legal",
            "ine": "Identificación Oficial (INE/Pasaporte)",
            "comprobante": "Comprobante de Domicilio",
        }
        doc_rows = []
        for k, label in doc_labels.items():
            if cli.get("documentos", {}).get(k):
                doc_rows.append([f"✓  {label}", cli["documentos"][k].get("filename", "—")])
        doc_tbl = Table(doc_rows, colWidths=[9 * cm, 8 * cm])
        doc_tbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), EMERALD),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(doc_tbl)
    else:
        # Welcome message: contacto y siguientes pasos
        story.append(Paragraph('<font color="#71717a" size="8"><b>SIGUIENTES PASOS</b></font>', body))
        steps = (
            "1. Ingrese a su Portal Cliente DEYMA con su número de cliente "
            f"<b>{cli.get('dfnum', 'DFNUM-XXXXXX')}</b> y la contraseña que registró.<br/>"
            "2. Una vez dentro, podrá subir sus Órdenes de Compra (PDF) en el módulo "
            "<b>ÓRDENES DE COMPRA</b> para iniciar el arranque del proyecto.<br/>"
            "3. Recibirá comunicación directa de su contacto comercial asignado para programar visita técnica."
        )
        story.append(Paragraph(steps, body))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph('<font color="#71717a" size="8">Atentamente,<br/><b>DEYMA Construcciones S.A. de C.V.</b><br/>contacto@deyma.mx</font>', body_sm))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY)
        canvas.drawString(1.8 * cm, 1 * cm, "DEYMA · CONSTRUCCIÓN INDUSTRIAL · DOCUMENTO OFICIAL")
        canvas.drawRightString(20 * cm, 1 * cm, f"Folio {cli.get('folio_registro')} · Página {_doc.page}")
        canvas.setStrokeColor(accent_color)
        canvas.setLineWidth(1.5)
        canvas.line(1.8 * cm, 1.3 * cm, 20 * cm, 1.3 * cm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


@api.get("/clientes/{cid}/pdf-alta")
async def pdf_alta(cid: str):
    """PDF de Alta Exitosa — público para el folio del propio cliente (sin auth, solo conociendo el id)."""
    cli = await db.clientes_alta.find_one({"id": cid}, {"_id": 0, "password_hash": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="No encontrado")
    pdf_bytes = await asyncio.to_thread(_build_alta_pdf, cli, "alta")
    import io as _io
    return StreamingResponse(
        _io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DEYMA_alta_{cli["folio_registro"]}.pdf"'},
    )


@api.get("/clientes/{cid}/pdf-bienvenida")
async def pdf_bienvenida(cid: str):
    cli = await db.clientes_alta.find_one({"id": cid}, {"_id": 0, "password_hash": 0})
    if not cli:
        raise HTTPException(status_code=404, detail="No encontrado")
    if cli.get("estado") != "aprobado_completo":
        raise HTTPException(status_code=400, detail="El PDF de bienvenida solo está disponible cuando el cliente está aprobado")
    pdf_bytes = await asyncio.to_thread(_build_alta_pdf, cli, "bienvenida")
    import io as _io
    return StreamingResponse(
        _io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DEYMA_bienvenida_{cli["dfnum"]}.pdf"'},
    )


# ----------------------------------------------------------------------------
# V2: Scraper Nocturno (Compranet + Tenders MX vía AI) + Scheduler
# ----------------------------------------------------------------------------
SCRAPER_STATE = {
    "last_scrape": None,
    "last_scrape_added": 0,
    "last_scoring": None,
    "last_scoring_count": 0,
    "last_morning_alert": None,
    "last_morning_alert_top": [],
    "errors": [],
    "running": False,
}

SCRAPER_ESTADOS = [
    "Querétaro", "Guanajuato", "Nuevo León", "Jalisco", "Estado de México",
    "Aguascalientes", "San Luis Potosí", "Puebla", "Coahuila", "Baja California",
    "Sonora", "Yucatán", "Chihuahua", "Tamaulipas",
]

# Approximate state capital coords for scraped projects
ESTADO_COORDS = {
    "Querétaro": (20.5888, -100.3899), "Guanajuato": (21.0167, -101.2569),
    "Nuevo León": (25.6866, -100.3161), "Jalisco": (20.6597, -103.3496),
    "Estado de México": (19.4969, -99.7233), "Aguascalientes": (21.8853, -102.2916),
    "San Luis Potosí": (22.1565, -100.9855), "Puebla": (19.0414, -98.2063),
    "Coahuila": (25.4232, -100.9966), "Baja California": (32.5149, -117.0382),
    "Sonora": (29.0892, -110.9613), "Yucatán": (20.9674, -89.5926),
    "Chihuahua": (28.6353, -106.0889), "Tamaulipas": (25.5996, -100.0269),
    "Tabasco": (18.4036, -93.1944), "Veracruz": (19.1738, -96.1342),
    "CDMX": (19.4326, -99.1332), "Sinaloa": (24.8091, -107.3940),
    "Michoacán": (19.7008, -101.1844), "Hidalgo": (20.0911, -98.7624),
    "Morelos": (18.6813, -99.1013), "Tlaxcala": (19.3181, -98.2375),
    "Quintana Roo": (21.1619, -86.8515),
}


async def ai_scrape_compranet() -> List[dict]:
    """Use GPT-5.2 as a synthetic scraper that 'reads' compranet/tenders MX news
    and emits 5-8 realistic licitations for DEYMA's niche. Returns list of dicts
    ready to insert in `radar` collection."""
    import random
    system = (
        "Eres un agente de inteligencia comercial que monitorea diariamente Compranet "
        "(compranet.hacienda.gob.mx), tenders.mx, noticias industriales (El Financiero, Expansión, "
        "Bloomberg México) y comunicados de parques industriales para detectar licitaciones, "
        "construcciones y mantenimientos relevantes para DEYMA (pisos industriales, concreto hidráulico, "
        "pavimentación, mantenimiento industrial, canastillas) en TODA la República Mexicana. "
        "Generas 5 a 8 oportunidades nuevas (no repitas títulos comunes) basadas en tendencias actuales: "
        "nearshoring, parques industriales, CEDIS, manufactura, data centers, expansiones de planta. "
        "Distribúyelas por diferentes estados mexicanos. Devuelves SOLO JSON estricto."
    )
    user = (
        "Devuelve un JSON con un array `items`, cada uno con: "
        '{titulo, fuente: "licitacion"|"noticia"|"referencia", sector: "nearshoring|parques_industriales|cedis_logistica|manufactura|data_centers|expansion_planta", '
        'ciudad, estado (debe ser uno de: ' + ", ".join(SCRAPER_ESTADOS + ["Tabasco","Veracruz","CDMX","Sinaloa","Michoacán","Hidalgo","Morelos","Tlaxcala","Quintana Roo"]) + '), '
        'monto_estimado (MXN, número), descripcion (1-2 oraciones), url_fuente (ej. "compranet.gob.mx" o "expansion.mx")}. '
        "Genera oportunidades REALISTAS y diversificadas por estado. No repitas las mismas empresas constantemente."
    )
    text = await _llm_call(system, user)
    data = _parse_json_block(text)
    items = data.get("items") or data if isinstance(data, list) else data.get("items", [])
    if isinstance(items, dict):
        items = [items]
    out = []
    for it in items[:10]:
        estado = it.get("estado", "Querétaro")
        coords = ESTADO_COORDS.get(estado, ESTADO_COORDS["Querétaro"])
        # add small jitter so multiple items in same state don't overlap exactly
        lat = coords[0] + (random.random() - 0.5) * 0.4
        lng = coords[1] + (random.random() - 0.5) * 0.4
        out.append({
            "id": new_id(),
            "titulo": str(it.get("titulo", ""))[:200],
            "fuente": it.get("fuente", "noticia") if it.get("fuente") in ("licitacion", "noticia", "referencia") else "noticia",
            "sector": it.get("sector", "manufactura") if it.get("sector") in SECTOR_LABEL_KEYS else "manufactura",
            "ciudad": it.get("ciudad", estado),
            "estado": estado,
            "monto_estimado": float(it.get("monto_estimado", 5_000_000)),
            "descripcion": str(it.get("descripcion", ""))[:600],
            "url_fuente": it.get("url_fuente", "compranet.gob.mx"),
            "lat": lat,
            "lng": lng,
            "score": 0,
            "hotness": "cold",
            "score_reasons": [],
            "detected_at": iso(now_utc()),
            "_source": "ai_scraper",
        })
    return out


SECTOR_LABEL_KEYS = {"nearshoring", "parques_industriales", "cedis_logistica", "manufactura", "data_centers", "expansion_planta", "otro"}


async def run_scraper_once() -> dict:
    if SCRAPER_STATE["running"]:
        return {"skipped": True, "reason": "ya hay un scrape en curso"}
    SCRAPER_STATE["running"] = True
    try:
        items = await ai_scrape_compranet()
        if not items:
            SCRAPER_STATE["last_scrape"] = iso(now_utc())
            SCRAPER_STATE["last_scrape_added"] = 0
            return {"added": 0, "items": []}
        # avoid duplicates by titulo similitud simple
        existing_titles = {d["titulo"].lower() for d in await db.radar.find({}, {"_id": 0, "titulo": 1}).to_list(2000)}
        fresh = [it for it in items if it["titulo"].lower() not in existing_titles]
        if fresh:
            await db.radar.insert_many(fresh)
        SCRAPER_STATE["last_scrape"] = iso(now_utc())
        SCRAPER_STATE["last_scrape_added"] = len(fresh)
        return {"added": len(fresh), "items": [{"id": f["id"], "titulo": f["titulo"], "estado": f["estado"]} for f in fresh]}
    except Exception as e:
        logger.exception("Scraper error")
        SCRAPER_STATE["errors"].append({"ts": iso(now_utc()), "msg": str(e)[:200]})
        return {"error": str(e)}
    finally:
        SCRAPER_STATE["running"] = False


async def run_scoring_batch() -> dict:
    """Score all unscored radar items."""
    items = await db.radar.find({"score": 0}, {"_id": 0}).to_list(50)
    scored = 0
    for p in items:
        try:
            result = await ai_score_opportunity(p["titulo"], p["sector"], p["descripcion"], p["monto_estimado"])
            await db.radar.update_one(
                {"id": p["id"]},
                {"$set": {"score": result["score"], "hotness": result["hotness"], "score_reasons": result["reasons"]}},
            )
            scored += 1
            if result["score"] >= 85:
                await create_hot_alert("radar", p["id"], p["titulo"], result["score"],
                                       p["monto_estimado"], p["sector"], p.get("ciudad", ""))
        except Exception as e:
            logger.warning(f"Scoring failed for {p['id']}: {e}")
    SCRAPER_STATE["last_scoring"] = iso(now_utc())
    SCRAPER_STATE["last_scoring_count"] = scored
    return {"scored": scored}


async def run_morning_alert() -> dict:
    """Send WhatsApp with top 5 HOT radar items detected in last 24h."""
    cutoff = now_utc() - timedelta(hours=36)
    cutoff_iso = iso(cutoff)
    items = await db.radar.find({"detected_at": {"$gte": cutoff_iso}}, {"_id": 0}).sort("score", -1).to_list(50)
    top = items[:5]
    if not top:
        SCRAPER_STATE["last_morning_alert"] = iso(now_utc())
        SCRAPER_STATE["last_morning_alert_top"] = []
        return {"sent": 0, "reason": "sin proyectos recientes"}
    body_lines = ["DEYMA RADAR · BUENOS DÍAS", f"Top {len(top)} oportunidades detectadas (últimas 36h):"]
    for i, p in enumerate(top, 1):
        body_lines.append(
            f"{i}. [{p.get('score',0)}/100] {p['titulo'][:60]} · {p['estado']} · MXN ${p['monto_estimado']:,.0f}"
        )
    body_lines.append("Abre el Radar para detalles y asignación comercial.")
    body = "\n".join(body_lines)
    result = await send_whatsapp(DEYMA_ALERT_PHONE or "whatsapp:+0000000000", body)
    alert_doc = {
        "id": new_id(),
        "entity_type": "morning_digest",
        "entity_id": "daily",
        "titulo": f"Resumen matutino — Top {len(top)} oportunidades",
        "score": top[0].get("score", 0),
        "monto": sum(p["monto_estimado"] for p in top),
        "sector": "varios",
        "ciudad": "Nacional",
        "body": body,
        "created_at": iso(now_utc()),
        "channel": "whatsapp",
        "to": DEYMA_ALERT_PHONE or "MOCK",
        "status": result.get("status", "unknown"),
        "mock": result.get("mock", True),
    }
    await db.alertas.insert_one(alert_doc)
    SCRAPER_STATE["last_morning_alert"] = iso(now_utc())
    SCRAPER_STATE["last_morning_alert_top"] = [
        {"titulo": p["titulo"], "score": p.get("score", 0), "estado": p["estado"], "monto": p["monto_estimado"]}
        for p in top
    ]
    return {"sent": len(top), "mock": result.get("mock", True)}


@api.get("/scraper/status")
async def scraper_status(user: dict = Depends(get_current_user)):
    total = await db.radar.count_documents({})
    auto = await db.radar.count_documents({"_source": "ai_scraper"})
    return {**SCRAPER_STATE, "radar_total": total, "radar_auto_scraped": auto, "twilio_enabled": TWILIO_ENABLED}


@api.post("/scraper/run")
async def scraper_run(user: dict = Depends(require_roles("director"))):
    return await run_scraper_once()


@api.post("/scraper/score-batch")
async def scraper_score_batch(user: dict = Depends(require_roles("director"))):
    return await run_scoring_batch()


@api.post("/scraper/morning-alert")
async def scraper_morning(user: dict = Depends(require_roles("director"))):
    return await run_morning_alert()


# ----------------------------------------------------------------------------
# Background scheduler (CDMX timezone)
# ----------------------------------------------------------------------------
async def _scheduler_loop():
    """Runs forever. Triggers tasks at specific CDMX local hours (UTC-6)."""
    # CDMX = UTC-6
    while True:
        try:
            now = datetime.now(timezone.utc)
            cdmx_hour = (now.hour - 6) % 24
            today_key = now.strftime("%Y-%m-%d")
            # 02:00 CDMX → scraper
            if cdmx_hour == 2 and SCRAPER_STATE.get("_last_scrape_day") != today_key:
                logger.info("[SCHEDULER] Running nightly scraper")
                await run_scraper_once()
                SCRAPER_STATE["_last_scrape_day"] = today_key
            # 03:00 CDMX → scoring
            if cdmx_hour == 3 and SCRAPER_STATE.get("_last_scoring_day") != today_key:
                logger.info("[SCHEDULER] Running nightly scoring batch")
                await run_scoring_batch()
                SCRAPER_STATE["_last_scoring_day"] = today_key
            # 08:00 CDMX → morning digest
            if cdmx_hour == 8 and SCRAPER_STATE.get("_last_alert_day") != today_key:
                logger.info("[SCHEDULER] Sending morning digest")
                await run_morning_alert()
                SCRAPER_STATE["_last_alert_day"] = today_key
        except Exception:
            logger.exception("Scheduler tick error")
        await asyncio.sleep(60 * 5)  # check every 5 minutes


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
    # Launch scheduler in background
    asyncio.create_task(_scheduler_loop())
    logger.info("Scheduler iniciado (scraper 02:00 · scoring 03:00 · alerta 08:00 CDMX)")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
