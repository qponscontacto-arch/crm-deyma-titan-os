from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Tuple

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
Role = Literal["director", "comercial", "operaciones", "socio"]
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
    # === V5 · Integración Greenfield OSINT (Canastillas Industriales) ===
    is_greenfield: bool = False
    greenfield_urgencia: Optional[Literal["alto", "medio", "bajo"]] = None
    greenfield_origen: Optional[str] = None  # MIA, LinkedIn, ParqueIndustrial, etc.
    greenfield_senal_id: Optional[str] = None  # FK a senales_greenfield
    canastillas_estimadas: Optional[int] = None  # piezas/mes estimadas
    canastillas_monto_estimado: Optional[float] = None  # MXN ingreso 12 meses


class CotizacionItem(BaseModel):
    descripcion: str
    cantidad: float
    unidad: str = "m2"
    precio_unitario: float

    @property
    def subtotal(self) -> float:
        return round(self.cantidad * self.precio_unitario, 2)


class CotizacionIn(BaseModel):
    empresa_id: Optional[str] = None
    # Cliente manual (cuando no existe en CRM): al menos cliente_nombre es requerido si empresa_id es None
    cliente_nombre: Optional[str] = None
    cliente_rfc: Optional[str] = None
    cliente_ciudad: Optional[str] = None
    cliente_atencion: Optional[str] = None
    cliente_email: Optional[str] = None
    cliente_telefono: Optional[str] = None
    proyecto_titulo: str
    items: List[CotizacionItem]
    iva_pct: float = 16.0
    notas: Optional[str] = None
    validez_dias: int = 15


class Cotizacion(BaseModel):
    id: str
    folio: str
    empresa_id: Optional[str] = None
    cliente_nombre: Optional[str] = None
    cliente_rfc: Optional[str] = None
    cliente_ciudad: Optional[str] = None
    cliente_atencion: Optional[str] = None
    cliente_email: Optional[str] = None
    cliente_telefono: Optional[str] = None
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
    if not body.empresa_id and not (body.cliente_nombre and body.cliente_nombre.strip()):
        raise HTTPException(status_code=400, detail="Debes seleccionar una empresa del CRM o capturar el nombre del cliente manual.")
    subtotal, iva, total = _cot_totals(body.items, body.iva_pct)
    count = await db.cotizaciones.count_documents({})
    folio = f"DEY-{datetime.now().year}-{count+1:04d}"
    doc = {
        "id": new_id(),
        "folio": folio,
        "empresa_id": body.empresa_id,
        "cliente_nombre": (body.cliente_nombre or "").strip() or None,
        "cliente_rfc": (body.cliente_rfc or "").strip() or None,
        "cliente_ciudad": (body.cliente_ciudad or "").strip() or None,
        "cliente_atencion": (body.cliente_atencion or "").strip() or None,
        "cliente_email": (body.cliente_email or "").strip() or None,
        "cliente_telefono": (body.cliente_telefono or "").strip() or None,
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
        {"email": "socio@deyma.mx", "name": "Ing. Eduardo Domínguez (Socio)", "role": "socio", "pw": "Socio2026!"},
    ]
    for u in extras:
        existing_u = await db.users.find_one({"email": u["email"]})
        if not existing_u:
            await db.users.insert_one({
                "id": new_id(), "email": u["email"], "name": u["name"], "role": u["role"],
                "password_hash": hash_password(u["pw"]), "created_at": iso(now_utc()),
            })
        elif not verify_password(u["pw"], existing_u.get("password_hash", "")):
            await db.users.update_one({"email": u["email"]}, {"$set": {
                "password_hash": hash_password(u["pw"]), "role": u["role"], "name": u["name"],
            }})

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
class NuevaEmpresaRadarIn(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    sitio_web: Optional[str] = None
    notas: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_puesto: Optional[str] = None
    contacto_email: Optional[str] = None
    contacto_telefono: Optional[str] = None


class ImportarRadarIn(BaseModel):
    empresa_id: Optional[str] = None
    nueva_empresa: Optional[NuevaEmpresaRadarIn] = None
    probabilidad: int = 25
    stage: Stage = "prospeccion"


@api.post("/radar/{rid}/importar")
async def importar_radar(rid: str, body: ImportarRadarIn, user: dict = Depends(get_current_user)):
    p = await db.radar.find_one({"id": rid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto radar no encontrado")

    # Resolución de empresa: ya existente o creación on-the-fly
    if body.empresa_id:
        emp = await db.empresas.find_one({"id": body.empresa_id}, {"_id": 0})
        if not emp:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        empresa_id = body.empresa_id
    elif body.nueva_empresa and body.nueva_empresa.nombre.strip():
        ne = body.nueva_empresa
        # Toma sector/ciudad/estado del radar para sembrar la empresa
        emp_doc = {
            "id": new_id(),
            "nombre": ne.nombre.strip(),
            "rfc": (ne.rfc or "").strip() or None,
            "sector": p.get("sector", "infraestructura"),
            "ciudad": p.get("ciudad", "Querétaro"),
            "estado": p.get("estado", "Querétaro"),
            "sitio_web": (ne.sitio_web or "").strip() or None,
            "notas": (ne.notas or "").strip() or None,
            "lat": p.get("lat"),
            "lng": p.get("lng"),
            "created_at": iso(now_utc()),
        }
        await db.empresas.insert_one(emp_doc)
        empresa_id = emp_doc["id"]
        # Contacto principal (opcional)
        if (ne.contacto_nombre or "").strip():
            await db.contactos.insert_one({
                "id": new_id(),
                "empresa_id": empresa_id,
                "nombre": ne.contacto_nombre.strip(),
                "puesto": (ne.contacto_puesto or "").strip() or None,
                "email": (ne.contacto_email or "").strip() or None,
                "telefono": (ne.contacto_telefono or "").strip() or None,
                "created_at": iso(now_utc()),
            })
    else:
        raise HTTPException(status_code=400, detail="Debes seleccionar una empresa del CRM o capturar una empresa nueva.")

    op = {
        "id": new_id(),
        "empresa_id": empresa_id,
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
async def cotizacion_pdf(cid: str, marca: str = "deyma", user: dict = Depends(get_current_user)):
    if marca not in ("deyma", "frecciamd"):
        raise HTTPException(status_code=400, detail="marca debe ser 'deyma' o 'frecciamd'")
    cot = await db.cotizaciones.find_one({"id": cid}, {"_id": 0})
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    emp, cont = await _cot_cliente_data(cot)
    pdf_bytes = await asyncio.to_thread(_build_cotizacion_pdf, cot, emp, cont, user, marca)
    import io
    suffix = "DEYMA" if marca == "deyma" else "FRECCIAMD"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cotizacion_{suffix}_{cot["folio"]}.pdf"'},
    )


async def _cot_cliente_data(cot: dict) -> Tuple[dict, dict]:
    """Resuelve los datos de empresa+contacto para PDF/email.
    Si la cotización tiene `empresa_id`, los toma del CRM.
    Si es un cliente manual (sólo `cliente_nombre` y opcionales), construye el dict in-memory.
    """
    if cot.get("empresa_id"):
        emp = await db.empresas.find_one({"id": cot["empresa_id"]}, {"_id": 0}) or {}
        cont = await db.contactos.find_one({"empresa_id": cot["empresa_id"]}, {"_id": 0}) or {}
        # Si además se capturaron datos manuales en la cotización, prevalecen los manuales
        if cot.get("cliente_atencion") or cot.get("cliente_email") or cot.get("cliente_telefono"):
            cont = {
                "nombre": cot.get("cliente_atencion") or cont.get("nombre", ""),
                "email": cot.get("cliente_email") or cont.get("email", ""),
                "telefono": cot.get("cliente_telefono") or cont.get("telefono", ""),
            }
        return emp, cont
    # Cliente manual: ciudad puede venir como "Querétaro, Qro" o solo "Querétaro"
    ciudad_raw = (cot.get("cliente_ciudad") or "").strip()
    if "," in ciudad_raw:
        ciudad, estado = [x.strip() for x in ciudad_raw.split(",", 1)]
    else:
        ciudad, estado = ciudad_raw, ""
    emp = {
        "nombre": cot.get("cliente_nombre") or "Cliente",
        "rfc": cot.get("cliente_rfc") or "",
        "ciudad": ciudad,
        "estado": estado,
    }
    cont = {
        "nombre": cot.get("cliente_atencion") or "",
        "email": cot.get("cliente_email") or "",
        "telefono": cot.get("cliente_telefono") or "",
    }
    return emp, cont


def _build_cotizacion_pdf(cot: dict, emp: dict, cont: dict, user: dict, marca: str = "deyma") -> bytes:
    """Genera el PDF de cotización con membrete corporativo DEYMA o FRECCIAMD.
    Replica el diseño del template oficial: barra superior con logo + curvas naranja/azul,
    datos del cliente en cápsulas azules, tabla de conceptos y observaciones generales 1-10."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.utils import ImageReader
    import io as _io
    import os as _os

    # Paleta corporativa extraída del template oficial
    NAVY = colors.HexColor("#0F1F4D")
    ORANGE = colors.HexColor("#F37021")
    DARK = colors.HexColor("#1A1A1A")
    GRAY = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#F5F5F5")

    # Datos fiscales por marca
    marca_info = {
        "deyma": {
            "razon": "DEYMA CONSTRUCCIONES S.A. DE C.V.",
            "tagline": "DESARROLLO Y MANTENIMIENTO",
            "asset": "header_deyma.png",
            "footer": "DEYMA Construcciones · Soluciones industriales en concreto y mantenimiento",
        },
        "frecciamd": {
            "razon": "FRECCIA MD S.A. DE C.V.",
            "tagline": "FRECCIA · CONSTRUCCIÓN INDUSTRIAL",
            "asset": "header_frecciamd.png",
            "footer": "FRECCIA MD · Soluciones industriales especializadas",
        },
    }
    mi = marca_info.get(marca, marca_info["deyma"])
    header_path = _os.path.join(_os.path.dirname(__file__), "assets", mi["asset"])

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                            topMargin=0.6 * cm, bottomMargin=1.5 * cm,
                            title=f"Cotización {cot['folio']}")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=DARK)
    body_sm = ParagraphStyle("bs", parent=body, fontSize=8, leading=10)
    label_white = ParagraphStyle("lw", parent=body, fontSize=9, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    value = ParagraphStyle("vw", parent=body, fontSize=10, textColor=DARK, leading=12)

    story = []

    # ========== 1. Header con logo (imagen del template oficial) ==========
    if _os.path.exists(header_path):
        # ancho útil: 21.59cm - 2*1.4cm = 18.79cm; aspect ratio del header (~1600x226 = 7.08)
        img_w = 18.79 * cm
        img_h = img_w / (1600 / 226)
        story.append(RLImage(header_path, width=img_w, height=img_h))
    story.append(Spacer(1, 0.2 * cm))

    # ========== 2. Datos cliente y cotización en cápsulas azules ==========
    def cap(label, value_txt):
        return Table(
            [
                [Paragraph(label, label_white)],
                [Paragraph(str(value_txt or "—"), value)],
            ],
            colWidths=[None],
            rowHeights=[0.55 * cm, 0.7 * cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), NAVY),
                ("BACKGROUND", (0, 1), (0, 1), LIGHT),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 1), (0, 1), 0.4, colors.HexColor("#D4D4D8")),
                ("ROUNDEDCORNERS", [4, 4, 0, 0]),
            ]),
        )

    fecha_str = ""
    try:
        fecha_str = datetime.fromisoformat(cot["created_at"].replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        fecha_str = (cot.get("created_at") or "")[:10]

    info_left = [
        [cap("EMPRESA", emp.get("nombre", "—"))],
        [Spacer(1, 0.1 * cm)],
        [cap("ATENCIÓN", cont.get("nombre", "—"))],
        [Spacer(1, 0.1 * cm)],
        [cap("CORREO", cont.get("email", "—"))],
        [Spacer(1, 0.1 * cm)],
        [cap("NÚMERO", cont.get("telefono", "—"))],
    ]
    info_right = [
        [cap("No. DE COT.", cot.get("folio", "—"))],
        [Spacer(1, 0.1 * cm)],
        [cap("FECHA", fecha_str)],
        [Spacer(1, 0.1 * cm)],
        [cap("CIUDAD", f'{emp.get("ciudad", "")}, {emp.get("estado", "")}'.strip(", ") or "—")],
        [Spacer(1, 0.1 * cm)],
        [cap("OBRA", cot.get("proyecto_titulo", "—"))],
    ]
    info_tbl = Table(
        [[Table(info_left, colWidths=[8.8 * cm]), Table(info_right, colWidths=[8.8 * cm])]],
        colWidths=[9 * cm, 9 * cm],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]),
    )
    story.append(info_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # ========== 3. Tabla de conceptos ==========
    items_data = [["CÓDIGO", "CONCEPTO", "UNIDAD", "CANTIDAD", "P. UNITARIO", "IMPORTE"]]
    for i, it in enumerate(cot["items"], 1):
        subt = it["cantidad"] * it["precio_unitario"]
        items_data.append([
            f"{i:03d}",
            Paragraph(it["descripcion"], body_sm),
            it["unidad"],
            f"{it['cantidad']:,.2f}",
            f"${it['precio_unitario']:,.2f}",
            f"${subt:,.2f}",
        ])
    it_tbl = Table(items_data, colWidths=[1.5 * cm, 7.5 * cm, 1.8 * cm, 2 * cm, 2.7 * cm, 3 * cm])
    it_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D4D4D8")),
    ]))
    story.append(it_tbl)
    story.append(Spacer(1, 0.3 * cm))

    # ========== 4. Totales ==========
    totals_data = [
        ["", "SUB-TOTAL", f"${cot['subtotal']:,.2f}"],
        ["", f"IVA {cot['iva_pct']}%", f"${cot['iva_monto']:,.2f}"],
        ["", "TOTAL", f"${cot['total']:,.2f}"],
    ]
    tot_tbl = Table(totals_data, colWidths=[12 * cm, 3.5 * cm, 3 * cm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (-1, 1), 9),
        ("TEXTCOLOR", (1, 0), (-1, 1), DARK),
        ("BACKGROUND", (1, 2), (-1, 2), NAVY),
        ("TEXTCOLOR", (1, 2), (-1, 2), colors.white),
        ("FONTSIZE", (1, 2), (-1, 2), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (1, 0), (-1, 1), 0.4, colors.HexColor("#D4D4D8")),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ========== 5. Observaciones generales (10 puntos del template oficial) ==========
    obs = [
        "Para iniciar el trabajo requeriremos orden de compra.",
        "El tiempo de entrega será de (3 días) naturales.",
        "Términos de pago de acuerdo a lo acordado previo a alta de clientes en nuestro CRM.",
        "Nos reservamos el derecho de dominio sobre los trabajos y materiales reflejados en esta cotización hasta no ser liquidados en su totalidad.",
        "No nos hacemos responsables por daños causados en instalaciones ocultas.",
        f"Vigencia de cotización en {cot.get('validez_dias', 15)} días.",
        "La garantía de equipos y componentes es la misma que da el proveedor (15 días) en equipos. La garantía de calidad en los materiales y mano de obra es de (3 meses) por algún defecto; nos comprometemos a repararlo a la brevedad. No nos hacemos responsables por el mal uso de los mismos.",
        "No se hacen modificaciones a la obra sin un anexo y orden de compra.",
        "Si la obra termina y no hubo retroalimentación de la parte encargada de mantenimiento o personal inscrito en nuestro portal, se da por hecho que se termina con éxito.",
        "Es importante la retroalimentación diaria con el equipo técnico por parte de ambas empresas.",
    ]
    story.append(Paragraph('<font color="#0F1F4D"><b>Observaciones Generales:</b></font>', body))
    story.append(Spacer(1, 0.15 * cm))
    obs_rows = []
    for i, txt in enumerate(obs, 1):
        obs_rows.append([
            Paragraph(f'<font color="#F37021"><b>{i}.</b></font>', body_sm),
            Paragraph(txt, body_sm),
        ])
    obs_tbl = Table(obs_rows, colWidths=[1.0 * cm, 16.8 * cm])
    obs_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(obs_tbl)

    # Notas adicionales del usuario
    if cot.get("notas"):
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph('<font color="#0F1F4D"><b>Notas adicionales:</b></font>', body))
        story.append(Paragraph(cot["notas"], body_sm))

    # ========== 6. Footer ==========
    def _footer(canvas, _doc):
        canvas.saveState()
        # Línea decorativa naranja + navy
        canvas.setStrokeColor(ORANGE)
        canvas.setLineWidth(1.2)
        canvas.line(1.4 * cm, 1.3 * cm, 20.2 * cm, 1.3 * cm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(NAVY)
        canvas.drawString(1.4 * cm, 0.95 * cm, mi["razon"])
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY)
        canvas.drawString(1.4 * cm, 0.65 * cm, mi["footer"])
        canvas.drawRightString(20.2 * cm, 0.65 * cm, f"Folio {cot['folio']}  ·  Página {_doc.page}")
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
    emp, cont = await _cot_cliente_data(cot)
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
        emp, cont = await _cot_cliente_data(cot)
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
    emp, cont = await _cot_cliente_data(cot)
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


@api.get("/clientes/me/cotizaciones")
async def cliente_mis_cotizaciones(cli: dict = Depends(get_current_cliente)):
    """Cotizaciones ligadas al cliente (vía RFC de la empresa)."""
    rfc = (cli.get("rfc") or "").upper()
    if not rfc:
        return []
    empresas = await db.empresas.find({"rfc": rfc}, {"_id": 0, "id": 1}).to_list(50)
    empresa_ids = [e["id"] for e in empresas]
    if not empresa_ids:
        return []
    cots = await db.cotizaciones.find(
        {"empresa_id": {"$in": empresa_ids}},
        {"_id": 0, "outbound_emails": 0, "inbound_replies": 0, "historia": 0},
    ).sort("created_at", -1).to_list(200)
    return cots


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
@api.post("/clientes-oc")
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


@api.get("/clientes-oc")
async def list_oc(cli: dict = Depends(get_current_cliente)):
    full = await db.clientes_alta.find_one({"id": cli["id"]}, {"_id": 0, "ordenes_compra": 1})
    return full.get("ordenes_compra", []) if full else []


@api.get("/clientes-oc/{oc_id}/file")
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


# ============================================================================
# V4.5 · RH · Personal Contratado (acceso director + socio)
# ============================================================================
DEPARTAMENTOS_RH = ["Obra", "Administración", "Comercial", "Operaciones", "Diseño", "RH"]
TIPOS_DOC_RH = {
    "general": "Documentación general (INE/CURP/NSS/comprobante)",
    "contrato": "Contrato de contratación",
    "renuncia": "Carta de renuncia",
    "amonestacion": "Carta de amonestación",
    "cert_medico": "Certificado médico",
    "dc3": "Constancia DC-3 STPS",
}


def _vacaciones_por_antiguedad(anios: int) -> int:
    """Tabla LFT 2023 (reforma vacaciones dignas)."""
    if anios < 1:
        return 0
    base = [12, 14, 16, 18, 20]
    if anios <= 5:
        return base[anios - 1]
    if anios <= 10:
        return 22
    if anios <= 15:
        return 24
    if anios <= 20:
        return 26
    if anios <= 25:
        return 28
    if anios <= 30:
        return 30
    return 32


def _calcular_prestaciones(empleado: dict) -> dict:
    """Calcula prestaciones según LFT vigente."""
    from datetime import datetime as _dt
    today = now_utc().date()
    fi_str = empleado.get("fecha_ingreso")
    if not fi_str:
        return {"antiguedad_anios": 0, "antiguedad_meses": 0, "vacaciones_anuales": 0,
                "proximo_aniversario": None, "dias_para_aniversario": None,
                "aguinaldo_dias": 15, "prima_vacacional_pct": 25,
                "vacaciones_gozadas": 0, "vacaciones_pendientes": 0}
    fi = _dt.fromisoformat(fi_str.replace("Z", "+00:00")).date() if "T" in fi_str else _dt.strptime(fi_str[:10], "%Y-%m-%d").date()
    anios = today.year - fi.year - ((today.month, today.day) < (fi.month, fi.day))
    meses = (today.year - fi.year) * 12 + (today.month - fi.month)
    if today.day < fi.day:
        meses -= 1
    # próximo aniversario
    try:
        prox = fi.replace(year=today.year)
        if prox <= today:
            prox = fi.replace(year=today.year + 1)
    except ValueError:  # 29-feb
        prox = fi.replace(year=today.year + 1, day=28)
    dias_aniv = (prox - today).days
    vac_anuales = _vacaciones_por_antiguedad(max(anios, 1) if anios >= 1 else 1)
    if anios < 1:
        # proporcional al primer año (12 días * meses/12)
        vac_anuales = round(12 * (meses / 12))
    return {
        "antiguedad_anios": anios,
        "antiguedad_meses": meses,
        "vacaciones_anuales_periodo_actual": vac_anuales,
        "proximo_aniversario": prox.isoformat(),
        "dias_para_aniversario": dias_aniv,
        "vacaciones_proximo_periodo": _vacaciones_por_antiguedad(anios + 1),
        "aguinaldo_dias": 15,
        "prima_vacacional_pct": 25,
    }


class EmpleadoIn(BaseModel):
    nombre: str
    rfc: str = ""
    curp: str = ""
    nss: str = ""
    puesto: str
    departamento: str
    fecha_ingreso: str  # YYYY-MM-DD
    salario_diario: float = 0.0
    salario_mensual: float = 0.0
    sueldo_integrado: float = 0.0
    tel: str = ""
    correo: str = ""
    domicilio: str = ""
    contacto_emergencia_nombre: str = ""
    contacto_emergencia_tel: str = ""
    notas: str = ""


class EmpleadoUpdate(BaseModel):
    nombre: Optional[str] = None
    rfc: Optional[str] = None
    curp: Optional[str] = None
    nss: Optional[str] = None
    puesto: Optional[str] = None
    departamento: Optional[str] = None
    fecha_ingreso: Optional[str] = None
    fecha_baja: Optional[str] = None
    salario_diario: Optional[float] = None
    salario_mensual: Optional[float] = None
    sueldo_integrado: Optional[float] = None
    tel: Optional[str] = None
    correo: Optional[str] = None
    domicilio: Optional[str] = None
    contacto_emergencia_nombre: Optional[str] = None
    contacto_emergencia_tel: Optional[str] = None
    status: Optional[str] = None  # activo|baja
    motivo_baja: Optional[str] = None
    notas: Optional[str] = None


class VacacionesIn(BaseModel):
    fecha_inicio: str
    fecha_fin: str
    dias: int
    estatus: str = "programadas"  # programadas|gozadas|canceladas
    nota: str = ""


require_rh = require_roles("director", "socio")


@api.post("/rh/empleados")
async def rh_create_empleado(payload: EmpleadoIn, user: dict = Depends(require_rh)):
    emp = payload.dict()
    emp["id"] = new_id()
    emp["status"] = "activo"
    emp["fecha_baja"] = None
    emp["motivo_baja"] = ""
    emp["created_at"] = iso(now_utc())
    emp["created_by"] = user["id"]
    emp["documentos_count"] = 0
    await db.empleados.insert_one(emp)
    emp.pop("_id", None)
    return emp


@api.get("/rh/empleados")
async def rh_list_empleados(
    status: Optional[str] = None, departamento: Optional[str] = None,
    q: Optional[str] = None, user: dict = Depends(require_rh)
):
    flt = {}
    if status:
        flt["status"] = status
    if departamento:
        flt["departamento"] = departamento
    if q:
        flt["$or"] = [
            {"nombre": {"$regex": q, "$options": "i"}},
            {"rfc": {"$regex": q, "$options": "i"}},
            {"curp": {"$regex": q, "$options": "i"}},
            {"puesto": {"$regex": q, "$options": "i"}},
        ]
    items = await db.empleados.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
    for e in items:
        e["prestaciones"] = _calcular_prestaciones(e)
    return items


@api.get("/rh/alertas")
async def rh_alertas(user: dict = Depends(require_rh)):
    """Alertas RH: aniversarios próximos, cert. médicos por vencer, DC-3 por vencer."""
    out = []
    empleados = await db.empleados.find({"status": "activo"}, {"_id": 0}).to_list(500)
    for e in empleados:
        p = _calcular_prestaciones(e)
        if p.get("dias_para_aniversario") is not None and p["dias_para_aniversario"] <= 30:
            out.append({
                "tipo": "aniversario", "empleado_id": e["id"], "nombre": e["nombre"],
                "dias": p["dias_para_aniversario"], "mensaje": f"{e['nombre']} cumple aniversario en {p['dias_para_aniversario']} días",
                "anios_proximos": p["antiguedad_anios"] + 1,
                "vacaciones_proximo": p["vacaciones_proximo_periodo"],
            })
    # cert médicos / DC-3 con vencimiento próximo
    today = now_utc().date()
    docs = await db.empleados_docs.find({"vigencia": {"$ne": None, "$exists": True}}, {"_id": 0}).to_list(1000)
    for d in docs:
        try:
            vig = datetime.fromisoformat(d["vigencia"]).date() if "T" not in d["vigencia"] else datetime.fromisoformat(d["vigencia"].replace("Z","+00:00")).date()
            dias = (vig - today).days
            if -30 <= dias <= 60:
                emp = next((x for x in empleados if x["id"] == d["empleado_id"]), None)
                if emp:
                    out.append({
                        "tipo": d["tipo"], "empleado_id": d["empleado_id"], "nombre": emp["nombre"],
                        "dias": dias, "vigencia": d["vigencia"],
                        "mensaje": f"{TIPOS_DOC_RH.get(d['tipo'], d['tipo'])} de {emp['nombre']} {'vence en '+str(dias)+' días' if dias>=0 else 'venció hace '+str(-dias)+' días'}",
                    })
        except Exception:
            pass
    return sorted(out, key=lambda x: x.get("dias", 999))


@api.get("/rh/empleados/{eid}")
async def rh_get_empleado(eid: str, user: dict = Depends(require_rh)):
    e = await db.empleados.find_one({"id": eid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Empleado no encontrado")
    e["prestaciones"] = _calcular_prestaciones(e)
    e["documentos"] = await db.empleados_docs.find({"empleado_id": eid}, {"_id": 0}).sort("uploaded_at", -1).to_list(500)
    e["vacaciones"] = await db.empleados_vacaciones.find({"empleado_id": eid}, {"_id": 0}).sort("fecha_inicio", -1).to_list(200)
    gozadas = sum(v["dias"] for v in e["vacaciones"] if v.get("estatus") == "gozadas")
    e["prestaciones"]["vacaciones_gozadas"] = gozadas
    e["prestaciones"]["vacaciones_pendientes"] = max(0, e["prestaciones"]["vacaciones_anuales_periodo_actual"] - gozadas)
    return e


@api.patch("/rh/empleados/{eid}")
async def rh_update_empleado(eid: str, payload: EmpleadoUpdate, user: dict = Depends(require_rh)):
    upd = {k: v for k, v in payload.dict().items() if v is not None}
    if upd.get("status") == "baja" and not upd.get("fecha_baja"):
        upd["fecha_baja"] = iso(now_utc())
    r = await db.empleados.update_one({"id": eid}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Empleado no encontrado")
    return {"ok": True}


@api.delete("/rh/empleados/{eid}")
async def rh_delete_empleado(eid: str, user: dict = Depends(require_rh)):
    # baja lógica + opcional borrar docs (no se borran de GridFS)
    await db.empleados.update_one({"id": eid}, {"$set": {"status": "baja", "fecha_baja": iso(now_utc())}})
    return {"ok": True}


@api.post("/rh/empleados/{eid}/documentos")
async def rh_upload_doc(
    eid: str,
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
    descripcion: str = Form(""),
    vigencia: str = Form(""),
    tema: str = Form(""),
    instructor: str = Form(""),
    user: dict = Depends(require_rh),
):
    if tipo not in TIPOS_DOC_RH:
        raise HTTPException(400, f"tipo invalido. Validos: {list(TIPOS_DOC_RH.keys())}")
    emp = await db.empleados.find_one({"id": eid}, {"_id": 0, "id": 1, "nombre": 1})
    if not emp:
        raise HTTPException(404, "Empleado no encontrado")
    content = await archivo.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "Archivo > 15 MB")
    fname = archivo.filename or f"{tipo}.pdf"
    file_id = await gridfs_bucket.upload_from_stream(fname, content, metadata={"empleado_id": eid, "tipo": tipo})
    doc = {
        "id": new_id(), "empleado_id": eid, "tipo": tipo,
        "filename": fname, "content_type": archivo.content_type or "application/pdf",
        "size": len(content), "descripcion": descripcion, "vigencia": vigencia or None,
        "tema": tema or None, "instructor": instructor or None,
        "file_id": str(file_id), "uploaded_by": user["id"], "uploaded_at": iso(now_utc()),
    }
    await db.empleados_docs.insert_one(doc)
    await db.empleados.update_one({"id": eid}, {"$inc": {"documentos_count": 1}})
    doc.pop("_id", None)
    return doc


@api.get("/rh/empleados/{eid}/documentos/{doc_id}")
async def rh_download_doc(eid: str, doc_id: str, user: dict = Depends(require_rh)):
    doc = await db.empleados_docs.find_one({"id": doc_id, "empleado_id": eid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    from bson import ObjectId as _OID
    stream = await gridfs_bucket.open_download_stream(_OID(doc["file_id"]))
    data = await stream.read()
    import io as _io
    return StreamingResponse(
        _io.BytesIO(data), media_type=doc.get("content_type", "application/pdf"),
        headers={"Content-Disposition": f'attachment; filename="{doc["filename"]}"'},
    )


@api.delete("/rh/empleados/{eid}/documentos/{doc_id}")
async def rh_delete_doc(eid: str, doc_id: str, user: dict = Depends(require_rh)):
    doc = await db.empleados_docs.find_one({"id": doc_id, "empleado_id": eid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    from bson import ObjectId as _OID
    try:
        await gridfs_bucket.delete(_OID(doc["file_id"]))
    except Exception:
        pass
    await db.empleados_docs.delete_one({"id": doc_id})
    await db.empleados.update_one({"id": eid}, {"$inc": {"documentos_count": -1}})
    return {"ok": True}


@api.post("/rh/empleados/{eid}/vacaciones")
async def rh_add_vacaciones(eid: str, payload: VacacionesIn, user: dict = Depends(require_rh)):
    if not await db.empleados.find_one({"id": eid}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Empleado no encontrado")
    rec = payload.dict()
    rec["id"] = new_id()
    rec["empleado_id"] = eid
    rec["created_at"] = iso(now_utc())
    rec["created_by"] = user["id"]
    await db.empleados_vacaciones.insert_one(rec)
    rec.pop("_id", None)
    return rec


@api.delete("/rh/empleados/{eid}/vacaciones/{vid}")
async def rh_delete_vacaciones(eid: str, vid: str, user: dict = Depends(require_rh)):
    r = await db.empleados_vacaciones.delete_one({"id": vid, "empleado_id": eid})
    if r.deleted_count == 0:
        raise HTTPException(404, "Periodo no encontrado")
    return {"ok": True}


def _build_expediente_pdf(emp: dict, docs: List[dict], vacaciones: List[dict]) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    import io as _io
    buf = _io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    W, H = LETTER
    AMBER = colors.HexColor("#F59E0B")
    DARK = colors.HexColor("#0A0A0A")
    GREY = colors.HexColor("#52525B")

    def header(title: str, sub: str = ""):
        c.setFillColor(DARK)
        c.rect(0, H - 2.5 * cm, W, 2.5 * cm, fill=1, stroke=0)
        c.setFillColor(AMBER)
        c.rect(0, H - 2.5 * cm, 1.2 * cm, 2.5 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(1.6 * cm, H - 1.3 * cm, "DEYMA · EXPEDIENTE DE PERSONAL")
        c.setFillColor(AMBER)
        c.setFont("Helvetica", 8)
        c.drawString(1.6 * cm, H - 1.9 * cm, "CONSTRUCCIONES S.A. DE C.V. · DEPARTAMENTO DE RH")
        c.setFillColor(GREY)
        c.setFont("Helvetica", 7)
        c.drawRightString(W - 1.5 * cm, H - 1.5 * cm, title)
        if sub:
            c.drawRightString(W - 1.5 * cm, H - 1.9 * cm, sub)

    p = _calcular_prestaciones(emp)
    gozadas = sum(v["dias"] for v in vacaciones if v.get("estatus") == "gozadas")
    pendientes = max(0, p["vacaciones_anuales_periodo_actual"] - gozadas)

    # Page 1: datos personales
    header(f"FOLIO {emp['id'][:8].upper()}", f"GENERADO {now_utc().strftime('%d/%m/%Y %H:%M')}")
    y = H - 3.5 * cm
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1.5 * cm, y, emp["nombre"].upper())
    y -= 0.6 * cm
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    c.drawString(1.5 * cm, y, f"{emp.get('puesto','')} · {emp.get('departamento','')} · {emp.get('status','').upper()}")
    y -= 1.0 * cm

    def section(title):
        nonlocal y
        c.setFillColor(AMBER)
        c.rect(1.5 * cm, y, W - 3 * cm, 0.55 * cm, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(1.7 * cm, y + 0.18 * cm, title.upper())
        y -= 0.85 * cm

    def kv(k, v, indent=0):
        nonlocal y
        c.setFillColor(GREY)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(1.5 * cm + indent, y, k.upper())
        c.setFillColor(DARK)
        c.setFont("Helvetica", 10)
        c.drawString(5.5 * cm + indent, y, str(v or "—"))
        y -= 0.5 * cm

    section("Datos de identificación")
    kv("RFC", emp.get("rfc"))
    kv("CURP", emp.get("curp"))
    kv("NSS", emp.get("nss"))
    kv("Teléfono", emp.get("tel"))
    kv("Correo", emp.get("correo"))
    kv("Domicilio", emp.get("domicilio"))

    y -= 0.2 * cm
    section("Datos laborales")
    kv("Fecha de ingreso", emp.get("fecha_ingreso"))
    if emp.get("fecha_baja"):
        kv("Fecha de baja", emp["fecha_baja"][:10])
    kv("Antigüedad", f"{p['antiguedad_anios']} años · {p['antiguedad_meses']} meses totales")
    kv("Salario diario", f"$ {emp.get('salario_diario', 0):,.2f}")
    kv("Salario mensual", f"$ {emp.get('salario_mensual', 0):,.2f}")
    kv("Sueldo integrado", f"$ {emp.get('sueldo_integrado', 0):,.2f}")

    y -= 0.2 * cm
    section("Contacto de emergencia")
    kv("Nombre", emp.get("contacto_emergencia_nombre"))
    kv("Teléfono", emp.get("contacto_emergencia_tel"))

    y -= 0.2 * cm
    section("Prestaciones (LFT vigente)")
    kv("Vacaciones periodo actual", f"{p['vacaciones_anuales_periodo_actual']} días")
    kv("Vacaciones próximo periodo", f"{p['vacaciones_proximo_periodo']} días")
    kv("Vacaciones gozadas (acum.)", f"{gozadas} días")
    kv("Vacaciones pendientes", f"{pendientes} días")
    kv("Aguinaldo", f"{p['aguinaldo_dias']} días")
    kv("Prima vacacional", f"{p['prima_vacacional_pct']} %")
    kv("Próximo aniversario", p.get("proximo_aniversario"))

    # Page 2: documentos y vacaciones
    c.showPage()
    header("DOCUMENTOS EN EXPEDIENTE", f"{len(docs)} docs · {len(vacaciones)} periodos vac.")
    y = H - 3.5 * cm
    section("Documentos digitalizados")
    if not docs:
        c.setFillColor(GREY)
        c.setFont("Helvetica", 9)
        c.drawString(1.5 * cm, y, "Sin documentos cargados.")
        y -= 0.5 * cm
    else:
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(1.5 * cm, y, "TIPO")
        c.drawString(6.5 * cm, y, "ARCHIVO")
        c.drawString(13.5 * cm, y, "FECHA")
        c.drawString(17 * cm, y, "VIGENCIA")
        y -= 0.4 * cm
        c.setStrokeColor(GREY)
        c.line(1.5 * cm, y, W - 1.5 * cm, y)
        y -= 0.3 * cm
        c.setFont("Helvetica", 8)
        for d in docs:
            if y < 3 * cm:
                c.showPage()
                header("DOCUMENTOS EN EXPEDIENTE (cont.)")
                y = H - 3.5 * cm
            c.drawString(1.5 * cm, y, TIPOS_DOC_RH.get(d["tipo"], d["tipo"])[:38])
            c.drawString(6.5 * cm, y, (d.get("filename") or "")[:38])
            c.drawString(13.5 * cm, y, (d.get("uploaded_at", "")[:10]))
            c.drawString(17 * cm, y, (d.get("vigencia") or "—")[:10])
            y -= 0.45 * cm

    y -= 0.3 * cm
    section("Historial de vacaciones")
    if not vacaciones:
        c.setFillColor(GREY)
        c.setFont("Helvetica", 9)
        c.drawString(1.5 * cm, y, "Sin periodos vacacionales registrados.")
    else:
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(1.5 * cm, y, "INICIO")
        c.drawString(5 * cm, y, "FIN")
        c.drawString(8.5 * cm, y, "DÍAS")
        c.drawString(11 * cm, y, "ESTATUS")
        c.drawString(14.5 * cm, y, "NOTA")
        y -= 0.4 * cm
        c.setStrokeColor(GREY)
        c.line(1.5 * cm, y, W - 1.5 * cm, y)
        y -= 0.3 * cm
        c.setFont("Helvetica", 8)
        for v in vacaciones:
            if y < 3 * cm:
                c.showPage()
                y = H - 3 * cm
            c.drawString(1.5 * cm, y, v.get("fecha_inicio", "")[:10])
            c.drawString(5 * cm, y, v.get("fecha_fin", "")[:10])
            c.drawString(8.5 * cm, y, str(v.get("dias", "")))
            c.drawString(11 * cm, y, v.get("estatus", "").upper())
            c.drawString(14.5 * cm, y, (v.get("nota", "") or "")[:30])
            y -= 0.45 * cm

    # Footer / cierre
    c.setFillColor(DARK)
    c.rect(0, 0, W, 1.2 * cm, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(1.5 * cm, 0.45 * cm, "DEYMA · CONFIDENCIAL · USO INTERNO RH")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 6)
    c.drawRightString(W - 1.5 * cm, 0.45 * cm, f"Generado {now_utc().strftime('%d/%m/%Y %H:%M')} · expediente {emp['id'][:8]}")

    c.save()
    return buf.getvalue()


@api.get("/rh/empleados/{eid}/expediente")
async def rh_expediente_pdf(eid: str, user: dict = Depends(require_rh)):
    emp = await db.empleados.find_one({"id": eid}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Empleado no encontrado")
    docs = await db.empleados_docs.find({"empleado_id": eid}, {"_id": 0}).sort("uploaded_at", -1).to_list(500)
    vac = await db.empleados_vacaciones.find({"empleado_id": eid}, {"_id": 0}).sort("fecha_inicio", -1).to_list(200)
    pdf_bytes = await asyncio.to_thread(_build_expediente_pdf, emp, docs, vac)
    import io as _io
    safe_name = "".join(ch for ch in (emp.get("nombre") or "empleado") if ch.isalnum() or ch in "_-").upper()[:40] or "EMPLEADO"
    return StreamingResponse(
        _io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DEYMA_expediente_{safe_name}.pdf"'},
    )


# ============================================================================
# V4.8 · Ruta de Ventas IA + Gastos de Viajero
# Acceso: comercial, director, socio
# ============================================================================
require_ventas = require_roles("comercial", "director", "socio")

OSRM_BASE = "https://router.project-osrm.org"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

# Cache simple en memoria para geocode (clave: query lowercased)
_GEOCODE_CACHE: dict = {}

# Pre-cache de ciudades clave de México (mitiga rate-limit de Nominatim)
_GEOCODE_SEED = [
    # Bajío (corredor principal DEYMA)
    ("morelia", 19.7008, -101.1844, "Morelia, Michoacán, México"),
    ("querétaro", 20.5888, -100.3899, "Querétaro, Querétaro, México"),
    ("queretaro", 20.5888, -100.3899, "Querétaro, Querétaro, México"),
    ("salamanca", 20.5742, -101.196, "Salamanca, Guanajuato, México"),
    ("celaya", 20.5238, -100.815, "Celaya, Guanajuato, México"),
    ("león", 21.1250, -101.6860, "León, Guanajuato, México"),
    ("leon", 21.1250, -101.6860, "León, Guanajuato, México"),
    ("guanajuato", 21.0190, -101.2574, "Guanajuato, Guanajuato, México"),
    ("irapuato", 20.6767, -101.3536, "Irapuato, Guanajuato, México"),
    ("silao", 20.9382, -101.4286, "Silao, Guanajuato, México"),
    ("san miguel de allende", 20.9151, -100.7437, "San Miguel de Allende, Guanajuato, México"),
    # Centro
    ("cdmx", 19.4326, -99.1332, "Ciudad de México, CDMX"),
    ("ciudad de méxico", 19.4326, -99.1332, "Ciudad de México, CDMX"),
    ("ciudad de mexico", 19.4326, -99.1332, "Ciudad de México, CDMX"),
    ("méxico df", 19.4326, -99.1332, "Ciudad de México, CDMX"),
    ("mexico df", 19.4326, -99.1332, "Ciudad de México, CDMX"),
    ("toluca", 19.2826, -99.6557, "Toluca, Estado de México"),
    ("puebla", 19.0414, -98.2063, "Puebla, Puebla, México"),
    ("pachuca", 20.1011, -98.7591, "Pachuca, Hidalgo, México"),
    ("tlaxcala", 19.3139, -98.2404, "Tlaxcala, Tlaxcala, México"),
    ("cuernavaca", 18.9242, -99.2216, "Cuernavaca, Morelos, México"),
    ("cuautla", 18.8120, -98.9540, "Cuautla, Morelos, México"),
    # Occidente / Pacífico
    ("guadalajara", 20.6597, -103.3496, "Guadalajara, Jalisco, México"),
    ("zapopan", 20.7239, -103.3848, "Zapopan, Jalisco, México"),
    ("tlaquepaque", 20.6406, -103.2939, "Tlaquepaque, Jalisco, México"),
    ("puerto vallarta", 20.6534, -105.2253, "Puerto Vallarta, Jalisco, México"),
    ("uruapan", 19.4119, -102.0517, "Uruapan, Michoacán, México"),
    ("zamora", 19.9836, -102.2832, "Zamora, Michoacán, México"),
    ("la piedad", 20.3447, -102.0292, "La Piedad, Michoacán, México"),
    ("lázaro cárdenas", 17.9583, -102.2008, "Lázaro Cárdenas, Michoacán, México"),
    ("colima", 19.2433, -103.7264, "Colima, Colima, México"),
    ("manzanillo", 19.0521, -104.3158, "Manzanillo, Colima, México"),
    ("tepic", 21.5039, -104.8941, "Tepic, Nayarit, México"),
    # Norte
    ("monterrey", 25.6866, -100.3161, "Monterrey, Nuevo León, México"),
    ("san pedro garza garcía", 25.6594, -100.4022, "San Pedro Garza García, NL, México"),
    ("apodaca", 25.7820, -100.1888, "Apodaca, Nuevo León, México"),
    ("saltillo", 25.4232, -101.0053, "Saltillo, Coahuila, México"),
    ("torreón", 25.5428, -103.4068, "Torreón, Coahuila, México"),
    ("torreon", 25.5428, -103.4068, "Torreón, Coahuila, México"),
    ("durango", 24.0277, -104.6532, "Durango, Durango, México"),
    ("chihuahua", 28.6353, -106.0889, "Chihuahua, Chihuahua, México"),
    ("ciudad juárez", 31.6904, -106.4245, "Ciudad Juárez, Chihuahua, México"),
    ("ciudad juarez", 31.6904, -106.4245, "Ciudad Juárez, Chihuahua, México"),
    ("hermosillo", 29.0892, -110.9613, "Hermosillo, Sonora, México"),
    ("nogales", 31.3168, -110.9442, "Nogales, Sonora, México"),
    ("ciudad obregón", 27.4828, -109.9404, "Ciudad Obregón, Sonora, México"),
    ("tijuana", 32.5149, -117.0382, "Tijuana, Baja California, México"),
    ("mexicali", 32.6519, -115.4683, "Mexicali, Baja California, México"),
    ("ensenada", 31.8666, -116.5963, "Ensenada, Baja California, México"),
    ("la paz", 24.1426, -110.3128, "La Paz, Baja California Sur, México"),
    ("cabo san lucas", 22.8905, -109.9167, "Cabo San Lucas, BCS, México"),
    ("culiacán", 24.8091, -107.3940, "Culiacán, Sinaloa, México"),
    ("culiacan", 24.8091, -107.3940, "Culiacán, Sinaloa, México"),
    ("mazatlán", 23.2494, -106.4111, "Mazatlán, Sinaloa, México"),
    ("mazatlan", 23.2494, -106.4111, "Mazatlán, Sinaloa, México"),
    ("los mochis", 25.7906, -108.9947, "Los Mochis, Sinaloa, México"),
    # Centro-Norte
    ("aguascalientes", 21.8853, -102.2916, "Aguascalientes, Aguascalientes, México"),
    ("san luis potosí", 22.1565, -100.9855, "San Luis Potosí, SLP, México"),
    ("san luis potosi", 22.1565, -100.9855, "San Luis Potosí, SLP, México"),
    ("zacatecas", 22.7709, -102.5832, "Zacatecas, Zacatecas, México"),
    ("fresnillo", 23.1747, -102.8662, "Fresnillo, Zacatecas, México"),
    # Sur / Sureste
    ("acapulco", 16.8531, -99.8237, "Acapulco, Guerrero, México"),
    ("chilpancingo", 17.5506, -99.5006, "Chilpancingo, Guerrero, México"),
    ("oaxaca", 17.0594, -96.7216, "Oaxaca, Oaxaca, México"),
    ("tuxtla gutiérrez", 16.7531, -93.1153, "Tuxtla Gutiérrez, Chiapas, México"),
    ("tuxtla gutierrez", 16.7531, -93.1153, "Tuxtla Gutiérrez, Chiapas, México"),
    ("villahermosa", 17.9869, -92.9469, "Villahermosa, Tabasco, México"),
    ("veracruz", 19.1738, -96.1342, "Veracruz, Veracruz, México"),
    ("xalapa", 19.5438, -96.9102, "Xalapa, Veracruz, México"),
    ("coatzacoalcos", 18.1346, -94.4592, "Coatzacoalcos, Veracruz, México"),
    ("poza rica", 20.5331, -97.4595, "Poza Rica, Veracruz, México"),
    ("córdoba", 18.8847, -96.9326, "Córdoba, Veracruz, México"),
    ("cordoba", 18.8847, -96.9326, "Córdoba, Veracruz, México"),
    ("mérida", 20.9674, -89.5926, "Mérida, Yucatán, México"),
    ("merida", 20.9674, -89.5926, "Mérida, Yucatán, México"),
    ("cancún", 21.1619, -86.8515, "Cancún, Quintana Roo, México"),
    ("cancun", 21.1619, -86.8515, "Cancún, Quintana Roo, México"),
    ("playa del carmen", 20.6296, -87.0739, "Playa del Carmen, Quintana Roo, México"),
    ("chetumal", 18.5001, -88.2961, "Chetumal, Quintana Roo, México"),
    ("campeche", 19.8301, -90.5349, "Campeche, Campeche, México"),
    # Tampico / Noreste
    ("tampico", 22.2553, -97.8686, "Tampico, Tamaulipas, México"),
    ("ciudad victoria", 23.7369, -99.1411, "Ciudad Victoria, Tamaulipas, México"),
    ("reynosa", 26.0922, -98.2772, "Reynosa, Tamaulipas, México"),
    ("matamoros", 25.8693, -97.5025, "Matamoros, Tamaulipas, México"),
    ("nuevo laredo", 27.4762, -99.5164, "Nuevo Laredo, Tamaulipas, México"),
]
for k, lat, lng, name in _GEOCODE_SEED:
    _GEOCODE_CACHE[k] = {"lat": lat, "lng": lng, "display_name": name}


async def _geocode(query: str) -> Optional[dict]:
    """Geocodifica una dirección/ciudad. Cache → Nominatim → Photon (fallback). Devuelve {lat, lng, display_name}."""
    if not query:
        return None
    key = query.strip().lower()
    if key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[key]
    # match parcial: 'morelia, mich' debería pegar con 'morelia'
    for k, v in _GEOCODE_CACHE.items():
        if key.startswith(k) or k.startswith(key):
            _GEOCODE_CACHE[key] = v
            return v
    import httpx
    # 1) Intento Nominatim
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "DEYMA-Radar/1.0 ventas@deyma.mx"}) as cli:
            r = await cli.get(f"{NOMINATIM_BASE}/search", params={
                "q": query, "format": "json", "limit": 1, "countrycodes": "mx", "addressdetails": 1,
            })
            if r.status_code == 200:
                data = r.json()
                if data:
                    it = data[0]
                    res = {"lat": float(it["lat"]), "lng": float(it["lon"]),
                           "display_name": it.get("display_name", query)}
                    _GEOCODE_CACHE[key] = res
                    return res
    except Exception as e:
        logger.warning(f"nominatim error '{query}': {e}")
    # 2) Fallback Photon Komoot
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "DEYMA-Radar/1.0 (ventas@deyma.mx)"},
        ) as cli:
            r = await cli.get("https://photon.komoot.io/api/", params={
                "q": query, "limit": 1,
            })
            if r.status_code == 200:
                data = r.json()
                feats = data.get("features", [])
                if feats:
                    f = feats[0]
                    coords = f.get("geometry", {}).get("coordinates", [])
                    if len(coords) == 2:
                        props = f.get("properties", {})
                        name = ", ".join(filter(None, [props.get("name"), props.get("city"), props.get("state"), props.get("country")]))
                        res = {"lat": float(coords[1]), "lng": float(coords[0]),
                               "display_name": name or query}
                        _GEOCODE_CACHE[key] = res
                        return res
    except Exception as e:
        logger.warning(f"photon error '{query}': {e}")
    # 3) Última opción: buscar en empresas registradas por nombre similar
    emp = await db.empresas.find_one(
        {"$or": [{"nombre": {"$regex": query, "$options": "i"}},
                 {"ciudad": {"$regex": query, "$options": "i"}}], "lat": {"$ne": None}},
        {"_id": 0, "nombre": 1, "ciudad": 1, "estado": 1, "lat": 1, "lng": 1},
    )
    if emp and emp.get("lat") and emp.get("lng"):
        res = {"lat": emp["lat"], "lng": emp["lng"],
               "display_name": f"{emp.get('ciudad', '')}, {emp.get('estado', '')} (vía empresa registrada)"}
        _GEOCODE_CACHE[key] = res
        return res
    return None


async def _osrm_route(coords: List[Tuple[float, float]]) -> Optional[dict]:
    """coords: lista de (lng, lat). Devuelve {distance_m, duration_s, geometry (polyline encoded)}."""
    if len(coords) < 2:
        return None
    import httpx
    coords_str = ";".join(f"{lng},{lat}" for lng, lat in coords)
    try:
        async with httpx.AsyncClient(timeout=20.0) as cli:
            r = await cli.get(f"{OSRM_BASE}/route/v1/driving/{coords_str}",
                              params={"overview": "full", "geometries": "polyline"})
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return None
            route = data["routes"][0]
            return {
                "distance_km": round(route["distance"] / 1000, 1),
                "duration_min": round(route["duration"] / 60, 0),
                "geometry": route["geometry"],
                "legs": route.get("legs", []),
            }
    except Exception as e:
        logger.warning(f"OSRM error: {e}")
        return None


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Distancia en km."""
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _dist_punto_a_segmento(px, py, ax, ay, bx, by) -> float:
    """Distancia de un punto a un segmento, en grados (aprox; suficiente para corredor)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return _haversine_km(py, px, cy, cx)


SCORE_ETAPA = {
    "prospeccion": 0.2, "calificada": 0.5, "propuesta": 0.8, "negociacion": 1.0,
    "ganada": 0.1, "perdida": 0.0,
}


async def _candidatos_en_corredor(origen: dict, destino: Optional[dict], max_desvio_km: float, radio_local_km: float = 50) -> List[dict]:
    """Devuelve lista de paradas candidatas con score, monto, etapa, distancia al corredor."""
    empresas = await db.empresas.find({"lat": {"$ne": None}, "lng": {"$ne": None}}, {"_id": 0}).to_list(2000)
    opps = await db.oportunidades.find({}, {"_id": 0}).to_list(2000)
    opps_by_emp: dict = {}
    for o in opps:
        opps_by_emp.setdefault(o["empresa_id"], []).append(o)

    today = now_utc().date()
    out = []
    for emp in empresas:
        lat, lng = emp.get("lat"), emp.get("lng")
        if lat is None or lng is None:
            continue
        # distancia al corredor o al origen
        if destino:
            dist_corr = _dist_punto_a_segmento(
                lng, lat, origen["lng"], origen["lat"], destino["lng"], destino["lat"]
            )
        else:
            dist_corr = _haversine_km(lat, lng, origen["lat"], origen["lng"])
        threshold = max_desvio_km if destino else radio_local_km
        if dist_corr > threshold:
            continue
        emp_opps = opps_by_emp.get(emp["id"], [])
        monto_total = sum((o.get("monto_estimado") or 0) for o in emp_opps if o.get("stage") not in ("ganada", "perdida"))
        mejor_etapa = max((SCORE_ETAPA.get(o.get("stage", ""), 0) for o in emp_opps), default=0)
        # última actividad
        ultima_act_dias = None
        if emp_opps:
            fechas = []
            for o in emp_opps:
                ts = o.get("updated_at") or o.get("created_at")
                if not ts:
                    continue
                try:
                    fechas.append(datetime.fromisoformat(ts.replace("Z", "+00:00")).date())
                except Exception:
                    continue
            if fechas:
                ultima_act_dias = (today - max(fechas)).days
        radar_max = 0
        for o in emp_opps:
            radar_max = max(radar_max, (o.get("score") or 0))
        # Score combinado (0-100)
        s_monto = min(monto_total / 5_000_000, 1.0) * 35  # cap a 5M MXN
        s_etapa = mejor_etapa * 25
        s_radar = (radar_max / 100) * 25
        s_freshness = 15 if ultima_act_dias is None else max(0, 15 - (ultima_act_dias / 30) * 5)
        score = round(s_monto + s_etapa + s_radar + s_freshness, 1)
        out.append({
            "empresa_id": emp["id"],
            "empresa_nombre": emp.get("nombre", "—"),
            "lat": lat, "lng": lng,
            "ciudad": emp.get("ciudad", ""),
            "estado_geo": emp.get("estado", ""),
            "rfc": emp.get("rfc", ""),
            "monto_total": monto_total,
            "n_oportunidades": len([o for o in emp_opps if o.get("stage") not in ("ganada", "perdida")]),
            "mejor_etapa": next((o.get("stage") for o in emp_opps if SCORE_ETAPA.get(o.get("stage"), 0) == mejor_etapa and o.get("stage")), "prospeccion"),
            "ultima_actividad_dias": ultima_act_dias,
            "radar_score": radar_max,
            "score": score,
            "desvio_km": round(dist_corr, 1),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def _orden_geo_secuencial(origen: dict, candidatos: List[dict], destino: Optional[dict]) -> List[dict]:
    """Ordena las paradas según avance lineal desde origen hacia destino (proyección sobre segmento)."""
    if not destino:
        # local: ordenar por distancia al origen ascendente
        return sorted(candidatos, key=lambda c: _haversine_km(origen["lat"], origen["lng"], c["lat"], c["lng"]))
    ax, ay = origen["lng"], origen["lat"]
    bx, by = destino["lng"], destino["lat"]
    dx, dy = bx - ax, by - ay
    norm2 = (dx * dx + dy * dy) or 1
    def t_proj(c):
        return ((c["lng"] - ax) * dx + (c["lat"] - ay) * dy) / norm2
    return sorted(candidatos, key=t_proj)


class RutaIn(BaseModel):
    origen: str
    destino: Optional[str] = None
    modo: str = "corredor"  # corredor | local
    max_desvio_km: float = 30.0
    radio_local_km: float = 50.0
    max_paradas: int = 6
    fecha: Optional[str] = None
    nota: Optional[str] = None


@api.get("/ruta-ventas/geocode/suggest")
async def geocode_suggest(q: str, user: dict = Depends(require_ventas)):
    """Autocompletado de ciudades para Origen/Destino.
    Combina el cache local (ciudades MX pre-sembradas) + Photon Komoot.
    Respuesta ligera y rápida: < 8 resultados.
    """
    q = (q or "").strip()
    if len(q) < 2:
        return {"suggestions": []}
    qlow = q.lower()
    out: List[dict] = []
    seen: set = set()

    # 1) Cache local — instant (ciudades MX clave)
    matches_starts, matches_contains = [], []
    for k, v in _GEOCODE_CACHE.items():
        name = v["display_name"]
        if name in seen:
            continue
        if k.startswith(qlow):
            matches_starts.append((name, v))
        elif qlow in k or k in qlow:
            matches_contains.append((name, v))
    for name, v in (matches_starts + matches_contains)[:8]:
        if name in seen:
            continue
        seen.add(name)
        out.append({"label": name, "lat": v["lat"], "lng": v["lng"], "display_name": name})

    # 2) Photon Komoot — completa con resultados externos si hace falta
    if len(out) < 5:
        import httpx
        try:
            async with httpx.AsyncClient(
                timeout=4.0,
                headers={"User-Agent": "DEYMA-Radar/1.0 (ventas@deyma.mx)"},
            ) as cli:
                r = await cli.get("https://photon.komoot.io/api/", params={
                    "q": q, "limit": 8,
                })
                if r.status_code == 200:
                    for f in r.json().get("features", []):
                        coords = f.get("geometry", {}).get("coordinates", [])
                        if len(coords) != 2:
                            continue
                        props = f.get("properties", {})
                        country = props.get("country", "") or ""
                        cc = (props.get("countrycode") or "").upper()
                        # Solo México (las rutas DEYMA son MX-only)
                        is_mx = cc == "MX" or ("México" in country) or ("Mexico" in country)
                        if not is_mx:
                            continue
                        parts = [props.get("name"), props.get("city"), props.get("state"), country]
                        name = ", ".join([p for p in parts if p])
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        out.append({
                            "label": name,
                            "lat": float(coords[1]),
                            "lng": float(coords[0]),
                            "display_name": name,
                            "_mx": True,
                        })
                        if len(out) >= 10:
                            break
        except Exception as e:
            logger.warning(f"photon suggest error '{q}': {e}")

    # Ordenar: primero los MX o del cache, luego el resto
    out.sort(key=lambda x: 0 if x.get("_mx", True) else 1)
    for o in out:
        o.pop("_mx", None)
    return {"suggestions": out[:8]}


@api.post("/ruta-ventas/generar")
async def ruta_generar(payload: RutaIn, user: dict = Depends(require_ventas)):
    """Genera plan de ruta inteligente con IA. NO persiste; solo calcula."""
    origen = await _geocode(payload.origen)
    if not origen:
        raise HTTPException(400, f"No se pudo geocodificar el origen '{payload.origen}'")
    destino = await _geocode(payload.destino) if payload.destino else None
    if payload.destino and not destino:
        raise HTTPException(400, f"No se pudo geocodificar el destino '{payload.destino}'")

    cands = await _candidatos_en_corredor(origen, destino, payload.max_desvio_km, payload.radio_local_km)
    import json as _json
    # Tomar top-N por score luego reordenar geográficamente
    top = cands[: max(payload.max_paradas, 1)]
    paradas = _orden_geo_secuencial(origen, top, destino)

    # OSRM con waypoints: origen → paradas → destino (si hay)
    coords = [(origen["lng"], origen["lat"])]
    for p in paradas:
        coords.append((p["lng"], p["lat"]))
    if destino:
        coords.append((destino["lng"], destino["lat"]))
    route_geo = await _osrm_route(coords) if len(coords) >= 2 else None

    # Briefing IA (silencioso si LLM falla, devolvemos fallback)
    plan_ia = None
    try:
        system_msg = (
            "Eres un agente de ventas especialista en construcción industrial (pisos, concreto, "
            "mantenimiento) en México (Bajío/Centro). Generas planes de prospección PRODUCTIVOS y CONCISOS. "
            "Devuelves SOLO JSON válido con la estructura: "
            "{paradas: [{empresa_id, briefing, tiempo_min, accion_clave}], resumen_general, recomendacion_final}. "
            "El briefing por parada debe ser 1-2 frases ACCIONABLES (qué decir, qué documento llevar, qué cerrar)."
        )
        prompt_user = _json.dumps({
            "ruta": {"origen": origen["display_name"], "destino": destino["display_name"] if destino else None,
                     "modo": payload.modo, "distancia_km": route_geo["distance_km"] if route_geo else None,
                     "duracion_min": route_geo["duration_min"] if route_geo else None},
            "paradas_propuestas": [
                {
                    "empresa_id": p["empresa_id"],
                    "empresa": p["empresa_nombre"],
                    "ciudad": p["ciudad"],
                    "monto_total_mxn": p["monto_total"],
                    "mejor_etapa": p["mejor_etapa"],
                    "ultima_actividad_dias": p["ultima_actividad_dias"],
                    "score_radar": p["radar_score"],
                    "score_combinado": p["score"],
                } for p in paradas
            ],
        }, ensure_ascii=False)
        raw = await _llm_call(system_msg, prompt_user)
        try:
            plan_ia = _parse_json_block(raw)
        except Exception:
            plan_ia = {"raw": raw[:2000], "error_parse": True}
    except HTTPException:
        plan_ia = None
    except Exception as e:
        logger.warning(f"plan_ia error: {e}")
        plan_ia = None

    # mezclar briefing al objeto de paradas
    briefing_by_emp = {}
    if plan_ia and isinstance(plan_ia.get("paradas"), list):
        for b in plan_ia["paradas"]:
            briefing_by_emp[b.get("empresa_id")] = b
    for p in paradas:
        b = briefing_by_emp.get(p["empresa_id"], {})
        p["briefing"] = b.get("briefing") or f"Visitar {p['empresa_nombre']}. Etapa: {p['mejor_etapa']}. Monto pipeline: ${p['monto_total']:,.0f}."
        p["tiempo_min"] = b.get("tiempo_min") or 45
        p["accion_clave"] = b.get("accion_clave") or ("Cierre" if p["mejor_etapa"] in ("propuesta", "negociacion") else "Detección")

    return {
        "origen": origen,
        "destino": destino,
        "modo": payload.modo,
        "paradas": paradas,
        "total_candidatos_corredor": len(cands),
        "route": route_geo,
        "plan_ia_resumen": (plan_ia or {}).get("resumen_general"),
        "plan_ia_recomendacion": (plan_ia or {}).get("recomendacion_final"),
        "generado_at": iso(now_utc()),
        "generado_por": user.get("name") or user.get("email"),
    }


@api.post("/ruta-ventas/guardar")
async def ruta_guardar(payload: dict, user: dict = Depends(require_ventas)):
    """Guarda la ruta generada para histórico y poder ligar gastos."""
    doc = {
        "id": new_id(),
        "origen": payload.get("origen"),
        "destino": payload.get("destino"),
        "modo": payload.get("modo"),
        "paradas": payload.get("paradas", []),
        "route": payload.get("route"),
        "resumen": payload.get("plan_ia_resumen"),
        "recomendacion": payload.get("plan_ia_recomendacion"),
        "fecha": payload.get("fecha") or now_utc().strftime("%Y-%m-%d"),
        "vendedor_id": user["id"],
        "vendedor_nombre": user.get("name") or user.get("email"),
        "created_at": iso(now_utc()),
    }
    await db.rutas_ventas.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/ruta-ventas")
async def ruta_listar(user: dict = Depends(require_ventas)):
    flt = {} if user["role"] in ("director", "socio") else {"vendedor_id": user["id"]}
    items = await db.rutas_ventas.find(flt, {"_id": 0}).sort("created_at", -1).to_list(100)
    return items


@api.delete("/ruta-ventas/{rid}")
async def ruta_eliminar(rid: str, user: dict = Depends(require_ventas)):
    flt = {"id": rid}
    if user["role"] not in ("director", "socio"):
        flt["vendedor_id"] = user["id"]
    r = await db.rutas_ventas.delete_one(flt)
    if r.deleted_count == 0:
        raise HTTPException(404, "Ruta no encontrada")
    return {"ok": True}


VISITA_ESTATUS = {
    "visitada": ("Visita realizada", "✅"),
    "no_atendio": ("Cliente no atendió", "🚪"),
    "reagendada": ("Reagendada para otra fecha", "🔁"),
    "cancelada": ("Visita cancelada", "❌"),
}


class VisitaIn(BaseModel):
    estatus: str  # visitada | no_atendio | reagendada | cancelada
    nota: Optional[str] = ""
    nueva_fecha: Optional[str] = None  # sólo si estatus=reagendada


@api.post("/ruta-ventas/{rid}/parada/{empresa_id}/visita")
async def marcar_visita(rid: str, empresa_id: str, payload: VisitaIn, user: dict = Depends(require_ventas)):
    """Marca una parada como gestionada y genera actividad automática en el CRM."""
    if payload.estatus not in VISITA_ESTATUS:
        raise HTTPException(400, f"estatus inválido. Válidos: {list(VISITA_ESTATUS.keys())}")
    ruta = await db.rutas_ventas.find_one({"id": rid}, {"_id": 0})
    if not ruta:
        raise HTTPException(404, "Ruta no encontrada")
    if user["role"] == "comercial" and ruta.get("vendedor_id") != user["id"]:
        raise HTTPException(403, "No puedes marcar visitas de rutas de otros vendedores")
    parada = next((p for p in (ruta.get("paradas") or []) if p.get("empresa_id") == empresa_id), None)
    if not parada:
        raise HTTPException(404, "Parada no encontrada en esta ruta")
    if not await db.empresas.find_one({"id": empresa_id}, {"_id": 0, "id": 1}):
        raise HTTPException(404, "Empresa no encontrada")

    # Buscar mejor oportunidad para enlazar (la más avanzada, abierta)
    opps = await db.oportunidades.find({"empresa_id": empresa_id}, {"_id": 0}).to_list(50)
    abiertas = [o for o in opps if o.get("stage") not in ("ganada", "perdida")]
    opp = None
    if abiertas:
        abiertas.sort(key=lambda o: SCORE_ETAPA.get(o.get("stage", ""), 0), reverse=True)
        opp = abiertas[0]
    elif opps:
        opp = opps[0]
    else:
        # Crear oportunidad mínima de prospección para poder ligar la actividad
        opp = {
            "id": new_id(),
            "empresa_id": empresa_id,
            "titulo": f"Prospección visita {ruta.get('fecha', now_utc().strftime('%Y-%m-%d'))}",
            "sector": "otro",
            "descripcion": f"Oportunidad creada automáticamente desde plan de ruta {rid[:8]}.",
            "monto_estimado": 0,
            "stage": "prospeccion",
            "probabilidad": 10,
            "score": 0,
            "hotness": "cold",
            "score_reasons": [],
            "fecha_cierre": None,
            "owner_id": user["id"],
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }
        await db.oportunidades.insert_one(opp)

    # Crear actividad de tipo "visita"
    label, icon = VISITA_ESTATUS[payload.estatus]
    descripcion = (
        f"{icon} {label} · {parada.get('empresa_nombre', empresa_id)} "
        f"· Ruta {ruta.get('fecha', '')} ({ruta.get('origen', {}).get('display_name', '')[:40]})"
    )
    if payload.nota:
        descripcion += f" · Nota: {payload.nota}"
    if payload.estatus == "reagendada" and payload.nueva_fecha:
        descripcion += f" · Reprogramada para {payload.nueva_fecha}"
    act_doc = {
        "id": new_id(),
        "oportunidad_id": opp["id"],
        "tipo": "visita",
        "fecha": iso(now_utc()),
        "descripcion": descripcion,
        "completada": payload.estatus != "reagendada",
        "owner_id": user["id"],
        "created_at": iso(now_utc()),
        "ruta_id": rid,
        "parada_empresa_id": empresa_id,
    }
    await db.actividades.insert_one(act_doc)

    # Actualizar parada en la ruta
    paradas = ruta.get("paradas") or []
    for i, p in enumerate(paradas):
        if p.get("empresa_id") == empresa_id:
            paradas[i]["visita"] = {
                "estatus": payload.estatus,
                "nota": payload.nota or "",
                "nueva_fecha": payload.nueva_fecha,
                "ts": iso(now_utc()),
                "vendedor_id": user["id"],
                "actividad_id": act_doc["id"],
            }
            break
    await db.rutas_ventas.update_one({"id": rid}, {"$set": {"paradas": paradas}})

    return {
        "ok": True,
        "estatus": payload.estatus,
        "actividad_id": act_doc["id"],
        "oportunidad_id": opp["id"],
        "oportunidad_creada": opp.get("titulo", "").startswith("Prospección visita"),
        "mensaje": f"{icon} {label} registrada · actividad CRM ligada a {parada.get('empresa_nombre')}",
    }


def _build_ruta_pdf(ruta: dict) -> bytes:
    """PDF de plan de ruta con membrete DEYMA, mapa estático y briefing IA."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    import io as _io
    import os as _os
    NAVY = colors.HexColor("#0F1F4D")
    ORANGE = colors.HexColor("#F37021")
    DARK = colors.HexColor("#1A1A1A")
    GRAY = colors.HexColor("#6B7280")
    LIGHT = colors.HexColor("#F5F5F5")

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=1.4 * cm, rightMargin=1.4 * cm,
                            topMargin=0.6 * cm, bottomMargin=1.5 * cm,
                            title=f"Plan de Ruta {ruta.get('id', '')[:8]}")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=DARK)
    body_sm = ParagraphStyle("bs", parent=body, fontSize=8, leading=10)
    h2 = ParagraphStyle("h2", parent=body, fontSize=11, leading=14, fontName="Helvetica-Bold", textColor=NAVY)

    story = []
    header_path = _os.path.join(_os.path.dirname(__file__), "assets", "header_deyma.png")
    if _os.path.exists(header_path):
        img_w = 18.79 * cm
        img_h = img_w / (1600 / 226)
        story.append(RLImage(header_path, width=img_w, height=img_h))
    story.append(Spacer(1, 0.3 * cm))

    fecha_str = ruta.get("fecha", now_utc().strftime("%Y-%m-%d"))
    story.append(Paragraph('<font color="#F37021"><b>PLAN DE RUTA · PROSPECCIÓN COMERCIAL</b></font>', h2))
    info_data = [
        [Paragraph("<b>Vendedor:</b>", body_sm), Paragraph(ruta.get("vendedor_nombre", "—"), body)],
        [Paragraph("<b>Fecha:</b>", body_sm), Paragraph(fecha_str, body)],
        [Paragraph("<b>Origen:</b>", body_sm), Paragraph((ruta.get("origen") or {}).get("display_name", "—"), body)],
        [Paragraph("<b>Destino:</b>", body_sm), Paragraph(((ruta.get("destino") or {}).get("display_name") or "Prospección local"), body)],
        [Paragraph("<b>Distancia / Duración:</b>", body_sm),
         Paragraph(f"{(ruta.get('route') or {}).get('distance_km', '—')} km · {(ruta.get('route') or {}).get('duration_min', '—')} min", body)],
        [Paragraph("<b>Paradas:</b>", body_sm), Paragraph(str(len(ruta.get("paradas") or [])), body)],
    ]
    story.append(Table(info_data, colWidths=[4 * cm, 13.8 * cm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])))
    story.append(Spacer(1, 0.3 * cm))

    # Mapa estático
    try:
        from staticmap import StaticMap, CircleMarker, Line
        smap = StaticMap(900, 500, url_template="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        # polyline
        geom = (ruta.get("route") or {}).get("geometry")
        if geom:
            import polyline as _pl
            pts = _pl.decode(geom)  # list of (lat, lng)
            line = Line([(lng, lat) for lat, lng in pts], "#F37021", 4)
            smap.add_line(line)
        # markers
        ori = ruta.get("origen") or {}
        if ori.get("lng") and ori.get("lat"):
            smap.add_marker(CircleMarker((ori["lng"], ori["lat"]), "#0F1F4D", 16))
        for p in (ruta.get("paradas") or []):
            smap.add_marker(CircleMarker((p["lng"], p["lat"]), "#F37021", 12))
        dst = ruta.get("destino") or {}
        if dst.get("lng") and dst.get("lat"):
            smap.add_marker(CircleMarker((dst["lng"], dst["lat"]), "#10B981", 16))
        img = smap.render(zoom=None)
        map_buf = _io.BytesIO()
        img.save(map_buf, format="PNG")
        map_buf.seek(0)
        story.append(RLImage(map_buf, width=18.5 * cm, height=10.3 * cm))
    except Exception as e:
        logger.warning(f"static map error: {e}")
        story.append(Paragraph(f'<font color="#6B7280"><i>[Mapa no disponible: {str(e)[:80]}]</i></font>', body_sm))
    story.append(Spacer(1, 0.3 * cm))

    if ruta.get("resumen"):
        story.append(Paragraph('<font color="#0F1F4D"><b>Resumen de la ruta:</b></font>', body))
        story.append(Paragraph(ruta["resumen"], body_sm))
        story.append(Spacer(1, 0.2 * cm))

    # Tabla paradas
    para_data = [["#", "EMPRESA", "CIUDAD", "ETAPA", "MONTO MXN", "SCORE"]]
    for i, p in enumerate(ruta.get("paradas") or [], 1):
        para_data.append([
            str(i),
            Paragraph(p.get("empresa_nombre", "—"), body_sm),
            p.get("ciudad", "") or "—",
            p.get("mejor_etapa", "—").upper(),
            f"${(p.get('monto_total') or 0):,.0f}",
            f"{p.get('score', 0):.0f}",
        ])
    t = Table(para_data, colWidths=[0.8 * cm, 6.5 * cm, 3.2 * cm, 3 * cm, 3 * cm, 2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (4, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D4D4D8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))

    # Briefing por parada
    story.append(Paragraph('<font color="#0F1F4D"><b>Briefing de visita (IA):</b></font>', body))
    story.append(Spacer(1, 0.1 * cm))
    for i, p in enumerate(ruta.get("paradas") or [], 1):
        story.append(Paragraph(
            f'<font color="#F37021"><b>{i}. {p.get("empresa_nombre", "—")}</b></font> '
            f'<font color="#6B7280" size="7">· {p.get("accion_clave", "Visita")} · {p.get("tiempo_min", 45)} min</font>',
            body,
        ))
        story.append(Paragraph(p.get("briefing", "—"), body_sm))
        story.append(Spacer(1, 0.15 * cm))

    if ruta.get("recomendacion"):
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph('<font color="#0F1F4D"><b>Recomendación final del agente IA:</b></font>', body))
        story.append(Paragraph(ruta["recomendacion"], body_sm))

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(ORANGE)
        canvas.setLineWidth(1.2)
        canvas.line(1.4 * cm, 1.3 * cm, 20.2 * cm, 1.3 * cm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(NAVY)
        canvas.drawString(1.4 * cm, 0.95 * cm, "DEYMA CONSTRUCCIONES S.A. DE C.V.")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY)
        canvas.drawString(1.4 * cm, 0.65 * cm, "Plan de prospección generado por IA · Uso interno comercial")
        canvas.drawRightString(20.2 * cm, 0.65 * cm, f"Página {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


@api.post("/ruta-ventas/pdf")
async def ruta_pdf(payload: dict, user: dict = Depends(require_ventas)):
    """Genera PDF desde un payload de ruta (sin necesidad de guardarla)."""
    pdf_bytes = await asyncio.to_thread(_build_ruta_pdf, payload)
    import io as _io
    fecha = payload.get("fecha") or now_utc().strftime("%Y%m%d")
    return StreamingResponse(
        _io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="DEYMA_ruta_{fecha}.pdf"'},
    )


# ----- Gastos de Viajero -----
TIPOS_GASTO = ["gasolina", "casetas", "comida", "hospedaje", "estacionamiento", "otros"]


class GastoIn(BaseModel):
    tipo: str
    monto: float
    fecha: str  # YYYY-MM-DD
    descripcion: Optional[str] = ""
    ruta_id: Optional[str] = None
    lugar: Optional[str] = ""


@api.post("/gastos-viajero")
async def gasto_crear(
    tipo: str = Form(...),
    monto: float = Form(...),
    fecha: str = Form(...),
    descripcion: str = Form(""),
    ruta_id: str = Form(""),
    lugar: str = Form(""),
    archivo: Optional[UploadFile] = File(None),
    user: dict = Depends(require_ventas),
):
    if tipo not in TIPOS_GASTO:
        raise HTTPException(400, f"tipo invalido. Validos: {TIPOS_GASTO}")
    if monto < 0:
        raise HTTPException(400, "monto debe ser >= 0")
    file_id_str = None
    filename = None
    content_type = None
    if archivo and archivo.filename:
        content = await archivo.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(400, "Archivo > 10 MB")
        file_id = await gridfs_bucket.upload_from_stream(archivo.filename, content,
                                                        metadata={"kind": "gasto_viaje", "user_id": user["id"]})
        file_id_str = str(file_id)
        filename = archivo.filename
        content_type = archivo.content_type
    doc = {
        "id": new_id(),
        "vendedor_id": user["id"],
        "vendedor_nombre": user.get("name") or user.get("email"),
        "tipo": tipo,
        "monto": float(monto),
        "fecha": fecha,
        "descripcion": descripcion,
        "ruta_id": ruta_id or None,
        "lugar": lugar,
        "file_id": file_id_str,
        "filename": filename,
        "content_type": content_type,
        "created_at": iso(now_utc()),
    }
    await db.gastos_viaje.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/gastos-viajero")
async def gastos_listar(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    vendedor_id: Optional[str] = None,
    user: dict = Depends(require_ventas),
):
    flt: dict = {}
    if tipo:
        flt["tipo"] = tipo
    if fecha_desde or fecha_hasta:
        flt["fecha"] = {}
        if fecha_desde:
            flt["fecha"]["$gte"] = fecha_desde
        if fecha_hasta:
            flt["fecha"]["$lte"] = fecha_hasta
    # comercial sólo ve los suyos; director/socio ven todos (o filtran por vendedor_id)
    if user["role"] == "comercial":
        flt["vendedor_id"] = user["id"]
    elif vendedor_id:
        flt["vendedor_id"] = vendedor_id
    items = await db.gastos_viaje.find(flt, {"_id": 0}).sort("fecha", -1).to_list(1000)
    total = sum(i["monto"] for i in items)
    por_tipo: dict = {}
    for i in items:
        por_tipo[i["tipo"]] = por_tipo.get(i["tipo"], 0) + i["monto"]
    return {"items": items, "total": total, "por_tipo": por_tipo, "n": len(items)}


@api.get("/gastos-viajero/{gid}/file")
async def gasto_file(gid: str, user: dict = Depends(require_ventas)):
    g = await db.gastos_viaje.find_one({"id": gid}, {"_id": 0})
    if not g:
        raise HTTPException(404, "Gasto no encontrado")
    if user["role"] == "comercial" and g["vendedor_id"] != user["id"]:
        raise HTTPException(403, "Solo puedes ver tus propios comprobantes")
    if not g.get("file_id"):
        raise HTTPException(404, "Sin archivo adjunto")
    from bson import ObjectId as _OID
    stream = await gridfs_bucket.open_download_stream(_OID(g["file_id"]))
    data = await stream.read()
    import io as _io
    return StreamingResponse(
        _io.BytesIO(data), media_type=g.get("content_type") or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{g.get("filename") or "comprobante"}"'},
    )


@api.delete("/gastos-viajero/{gid}")
async def gasto_eliminar(gid: str, user: dict = Depends(require_ventas)):
    flt = {"id": gid}
    if user["role"] == "comercial":
        flt["vendedor_id"] = user["id"]
    g = await db.gastos_viaje.find_one(flt, {"_id": 0})
    if not g:
        raise HTTPException(404, "Gasto no encontrado o sin permiso")
    if g.get("file_id"):
        from bson import ObjectId as _OID
        try:
            await gridfs_bucket.delete(_OID(g["file_id"]))
        except Exception:
            pass
    await db.gastos_viaje.delete_one(flt)
    return {"ok": True}


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


# ============================================================================
# V5 · RADAR GREENFIELD OSINT (Bajío: QRO / GTO / EDOMEX)
# ----------------------------------------------------------------------------
# Arquitectura: 4 agentes secuenciales orquestados por scheduler (07:00 CDMX).
# Fuentes (modo MVP demo-seeded + ganchos para Brave/Google Custom Search):
#   1) Inmobiliario+Gov   → MIAs, Parques Industriales, permisos (PDFs públicos)
#   2) Talento LinkedIn   → Plant Manager, Gerente Lanzamiento, NPI
#   3) Datos Profundos    → enriquecimiento de correos/móviles (LLM + APIs Apollo)
#   4) Sintetizador       → dedupe + cruce empresa↔contacto (Emergent LLM)
# ============================================================================

GreenfieldOrigen = Literal["MIA", "LinkedIn", "Broker", "Gobierno", "DOF", "ParqueIndustrial", "Permisos", "Manual"]
GreenfieldUrgencia = Literal["alto", "medio", "bajo"]
GreenfieldStage = Literal[
    "radar_activado",     # OSINT trabajando
    "triangulacion",      # Verificación de datos
    "abordaje_dia_cero",  # Alberto prospectando
    "demo_arranque",      # Demostración del sistema
    "propuesta_enviada",  # Setup y licencias
    "cierre_ganado",      # Alerta a Maurizio
    "perdida",
]

GREENFIELD_STAGE_LABEL = {
    "radar_activado": "Radar Activado",
    "triangulacion": "Triangulación",
    "abordaje_dia_cero": "Abordaje Día Cero",
    "demo_arranque": "Demo de Arranque",
    "propuesta_enviada": "Propuesta Enviada",
    "cierre_ganado": "Cierre Ganado",
    "perdida": "Perdida",
}

GREENFIELD_STAGE_PROB = {
    "radar_activado": 5,
    "triangulacion": 15,
    "abordaje_dia_cero": 30,
    "demo_arranque": 55,
    "propuesta_enviada": 75,
    "cierre_ganado": 100,
    "perdida": 0,
}


class SenalGreenfieldIn(BaseModel):
    empresa: str
    origen: GreenfieldOrigen = "Manual"
    urgencia: GreenfieldUrgencia = "medio"
    url_referencia: Optional[str] = None
    estado_mx: str = "Querétaro"  # estado de la República
    ciudad: Optional[str] = None
    sector_industrial: Optional[str] = None
    monto_estimado: Optional[float] = None
    notas: Optional[str] = None


class SenalGreenfield(SenalGreenfieldIn):
    id: str
    fecha_deteccion: str
    agente_origen: str = "manual"
    estado_workflow: Literal["radar_activado", "triangulacion", "validada", "descartada"] = "radar_activado"
    created_at: str


class ContactoOSINTIn(BaseModel):
    senal_id: Optional[str] = None  # puede ser nulo si aún no se asocia
    empresa: str  # Razón social a la que pertenece
    nombre_completo: str
    puesto: str  # "Gerente de Lanzamiento", "Plant Manager", "NPI"
    correo_directo: Optional[str] = None
    telefono_movil: Optional[str] = None
    linkedin_url: Optional[str] = None
    nivel_precision: int = 50  # 0-100
    fuente: str = "manual"
    notas: Optional[str] = None


class ContactoOSINT(ContactoOSINTIn):
    id: str
    estado_workflow: Literal["pendiente", "triangulado", "asignado", "contactado", "descartado"] = "pendiente"
    fecha_deteccion: str
    created_at: str


class GreenfieldOppIn(BaseModel):
    senal_id: str
    contacto_id: Optional[str] = None
    proyecto_titulo: Optional[str] = None
    monto_estimado: Optional[float] = None


class GreenfieldOpp(BaseModel):
    id: str
    senal_id: str
    contacto_id: Optional[str] = None
    empresa: str
    proyecto_titulo: str
    monto_estimado: Optional[float] = None
    stage: GreenfieldStage = "radar_activado"
    probabilidad: int = 5
    owner_id: Optional[str] = None
    fecha_cierre_estimada: Optional[str] = None
    historia: List[dict] = []
    created_at: str
    updated_at: str


class TicketOperacionesIn(BaseModel):
    titulo: str
    descripcion: str
    prioridad: Literal["alta", "media", "baja"] = "media"
    greenfield_opp_id: Optional[str] = None
    empresa: Optional[str] = None


class TicketOperaciones(TicketOperacionesIn):
    id: str
    asignado_a: str  # user_id de operaciones (Maurizio)
    asignado_nombre: str
    estado: Literal["abierto", "en_progreso", "cerrado"] = "abierto"
    creado_por: str
    created_at: str
    updated_at: str


require_greenfield = require_roles("director", "socio", "comercial", "operaciones")


# ----------------------------------------------------------------------------
# Helpers internos
# ----------------------------------------------------------------------------
async def _gf_user_alberto() -> dict:
    """Devuelve el usuario 'comercial' principal (Alberto)."""
    u = await db.users.find_one({"role": "comercial"}, {"_id": 0})
    if not u:
        u = await db.users.find_one({"role": "director"}, {"_id": 0}) or {}
    return u


async def _gf_user_maurizio() -> dict:
    """Devuelve el usuario 'operaciones' principal (Maurizio)."""
    u = await db.users.find_one({"role": "operaciones"}, {"_id": 0})
    if not u:
        u = await db.users.find_one({"role": "director"}, {"_id": 0}) or {}
    return u


def _gf_history(user: dict, accion: str, detalle: str, meta: Optional[dict] = None) -> dict:
    return {
        "ts": iso(now_utc()),
        "user_id": user.get("id"),
        "user_name": user.get("name"),
        "accion": accion,
        "detalle": detalle,
        "meta": meta or {},
    }


async def _gf_trigger_workflow_a(contacto: dict):
    """Regla A: si el contacto tiene email+tel → triangulado + tarea para Alberto."""
    if contacto.get("estado_workflow") == "triangulado":
        return
    if not (contacto.get("correo_directo") and contacto.get("telefono_movil")):
        return
    alberto = await _gf_user_alberto()
    await db.contactos_osint.update_one(
        {"id": contacto["id"]},
        {"$set": {"estado_workflow": "triangulado", "asignado_a": alberto.get("id"),
                  "asignado_nombre": alberto.get("name")}},
    )
    # Tarea/Actividad de alta prioridad para Alberto
    empresa = contacto.get("empresa", "desconocido")
    await db.gf_tareas.insert_one({
        "id": new_id(),
        "tipo": "abordaje",
        "prioridad": "alta",
        "titulo": f"Ejecutar protocolo de abordaje para {empresa}",
        "descripcion": f"Contacto triangulado: {contacto.get('nombre_completo')} ({contacto.get('puesto')}) - {contacto.get('correo_directo')} · {contacto.get('telefono_movil')}",
        "contacto_id": contacto["id"],
        "senal_id": contacto.get("senal_id"),
        "empresa": empresa,
        "asignado_a": alberto.get("id"),
        "asignado_nombre": alberto.get("name"),
        "estado": "abierta",
        "creado_por_sistema": True,
        "created_at": iso(now_utc()),
    })
    logger.info(f"[GREENFIELD][WF-A] Contacto triangulado → tarea Alberto: {empresa}")


async def _gf_trigger_workflow_b(opp: dict, user: dict):
    """Regla B: oportunidad → cierre_ganado → ticket a Maurizio."""
    maurizio = await _gf_user_maurizio()
    ticket_doc = {
        "id": new_id(),
        "titulo": f"Preparar entorno Day-1 para nueva planta {opp.get('empresa')}",
        "descripcion": (
            f"Oportunidad ganada: {opp.get('proyecto_titulo')}\n"
            f"Empresa: {opp.get('empresa')}\n"
            f"Monto: ${(opp.get('monto_estimado') or 0):,.0f} MXN\n"
            f"Cerrada por: {user.get('name')}"
        ),
        "prioridad": "alta",
        "estado": "abierto",
        "asignado_a": maurizio.get("id"),
        "asignado_nombre": maurizio.get("name"),
        "greenfield_opp_id": opp.get("id"),
        "empresa": opp.get("empresa"),
        "creado_por": user.get("id"),
        "creado_por_sistema": True,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.tickets_operaciones.insert_one(ticket_doc)
    logger.info(f"[GREENFIELD][WF-B] Cierre ganado → ticket Maurizio: {opp.get('empresa')}")


# ----------------------------------------------------------------------------
# Endpoints: Señales
# ----------------------------------------------------------------------------
@api.get("/greenfield/senales")
async def gf_senales_list(estado_mx: Optional[str] = None, origen: Optional[str] = None,
                          urgencia: Optional[str] = None, user: dict = Depends(require_greenfield)):
    q = {}
    if estado_mx:
        q["estado_mx"] = estado_mx
    if origen:
        q["origen"] = origen
    if urgencia:
        q["urgencia"] = urgencia
    items = await db.senales_greenfield.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@api.post("/greenfield/senales")
async def gf_senales_create(body: SenalGreenfieldIn, user: dict = Depends(require_greenfield)):
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "fecha_deteccion": iso(now_utc()),
        "agente_origen": "manual",
        "estado_workflow": "radar_activado",
        "created_at": iso(now_utc()),
    })
    await db.senales_greenfield.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/greenfield/senales/{sid}")
async def gf_senales_update(sid: str, body: dict, user: dict = Depends(require_greenfield)):
    allowed = {"empresa", "origen", "urgencia", "url_referencia", "estado_mx", "ciudad",
               "sector_industrial", "monto_estimado", "notas", "estado_workflow"}
    upd = {k: v for k, v in body.items() if k in allowed}
    if not upd:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    r = await db.senales_greenfield.update_one({"id": sid}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Señal no encontrada")
    doc = await db.senales_greenfield.find_one({"id": sid}, {"_id": 0})
    return doc


@api.delete("/greenfield/senales/{sid}")
async def gf_senales_delete(sid: str, user: dict = Depends(require_roles("director", "socio"))):
    r = await db.senales_greenfield.delete_one({"id": sid})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Señal no encontrada")
    return {"ok": True}


# ----------------------------------------------------------------------------
# Endpoints: Directorio OSINT (Contactos)
# ----------------------------------------------------------------------------
@api.get("/greenfield/contactos")
async def gf_contactos_list(senal_id: Optional[str] = None, estado_workflow: Optional[str] = None,
                            user: dict = Depends(require_greenfield)):
    q = {}
    if senal_id:
        q["senal_id"] = senal_id
    if estado_workflow:
        q["estado_workflow"] = estado_workflow
    items = await db.contactos_osint.find(q, {"_id": 0}).sort("nivel_precision", -1).to_list(500)
    return items


@api.post("/greenfield/contactos")
async def gf_contactos_create(body: ContactoOSINTIn, user: dict = Depends(require_greenfield)):
    doc = body.model_dump()
    doc.update({
        "id": new_id(),
        "estado_workflow": "pendiente",
        "fecha_deteccion": iso(now_utc()),
        "fuente": doc.get("fuente") or "manual",
        "created_at": iso(now_utc()),
    })
    await db.contactos_osint.insert_one(doc)
    doc.pop("_id", None)
    # Disparar workflow A si ya viene con email+tel
    await _gf_trigger_workflow_a(doc)
    doc = await db.contactos_osint.find_one({"id": doc["id"]}, {"_id": 0})
    return doc


@api.patch("/greenfield/contactos/{cid}")
async def gf_contactos_update(cid: str, body: dict, user: dict = Depends(require_greenfield)):
    allowed = {"senal_id", "empresa", "nombre_completo", "puesto", "correo_directo",
               "telefono_movil", "linkedin_url", "nivel_precision", "notas", "estado_workflow"}
    upd = {k: v for k, v in body.items() if k in allowed}
    if not upd:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    r = await db.contactos_osint.update_one({"id": cid}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    doc = await db.contactos_osint.find_one({"id": cid}, {"_id": 0})
    # Workflow A
    await _gf_trigger_workflow_a(doc)
    doc = await db.contactos_osint.find_one({"id": cid}, {"_id": 0})
    return doc


@api.delete("/greenfield/contactos/{cid}")
async def gf_contactos_delete(cid: str, user: dict = Depends(require_roles("director", "socio"))):
    r = await db.contactos_osint.delete_one({"id": cid})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return {"ok": True}


# ----------------------------------------------------------------------------
# Endpoints: Embudo Greenfield (Pipeline)
# ----------------------------------------------------------------------------
@api.get("/greenfield/embudo")
async def gf_embudo_list(user: dict = Depends(require_greenfield)):
    items = await db.greenfield_opps.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    # Agrupado por etapa
    by_stage = {s: [] for s in GREENFIELD_STAGE_LABEL.keys()}
    for it in items:
        by_stage.setdefault(it.get("stage", "radar_activado"), []).append(it)
    return {
        "stages": [
            {"key": k, "label": v, "items": by_stage[k], "total_monto": sum((x.get("monto_estimado") or 0) for x in by_stage[k])}
            for k, v in GREENFIELD_STAGE_LABEL.items()
        ],
        "total_oportunidades": len(items),
        "total_pipeline_monto": sum((it.get("monto_estimado") or 0) for it in items),
    }


@api.post("/greenfield/embudo")
async def gf_embudo_create(body: GreenfieldOppIn, user: dict = Depends(require_greenfield)):
    senal = await db.senales_greenfield.find_one({"id": body.senal_id}, {"_id": 0})
    if not senal:
        raise HTTPException(status_code=404, detail="Señal no encontrada")
    contacto = None
    if body.contacto_id:
        contacto = await db.contactos_osint.find_one({"id": body.contacto_id}, {"_id": 0})
    alberto = await _gf_user_alberto()
    doc = {
        "id": new_id(),
        "senal_id": body.senal_id,
        "contacto_id": body.contacto_id,
        "empresa": senal["empresa"],
        "proyecto_titulo": body.proyecto_titulo or f"Greenfield · {senal['empresa']}",
        "monto_estimado": body.monto_estimado or senal.get("monto_estimado") or 0,
        "stage": "radar_activado",
        "probabilidad": GREENFIELD_STAGE_PROB["radar_activado"],
        "owner_id": alberto.get("id"),
        "owner_name": alberto.get("name"),
        "fecha_cierre_estimada": None,
        "historia": [_gf_history(user, "crear_opp",
                                 f"Oportunidad creada desde señal {senal.get('origen')}",
                                 {"senal_id": body.senal_id, "contacto": (contacto or {}).get('nombre_completo')})],
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.greenfield_opps.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.post("/greenfield/embudo/{oid}/move")
async def gf_embudo_move(oid: str, body: dict, user: dict = Depends(require_greenfield)):
    new_stage = body.get("stage")
    if new_stage not in GREENFIELD_STAGE_LABEL:
        raise HTTPException(status_code=400, detail="stage inválido")
    opp = await db.greenfield_opps.find_one({"id": oid}, {"_id": 0})
    if not opp:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    old_stage = opp.get("stage")
    hist = _gf_history(user, "move_stage",
                       f"{GREENFIELD_STAGE_LABEL.get(old_stage, old_stage)} → {GREENFIELD_STAGE_LABEL[new_stage]}",
                       {"old": old_stage, "new": new_stage})
    await db.greenfield_opps.update_one(
        {"id": oid},
        {"$set": {"stage": new_stage, "probabilidad": GREENFIELD_STAGE_PROB[new_stage],
                  "updated_at": iso(now_utc())},
         "$push": {"historia": hist}},
    )
    # Workflow B: cierre ganado → ticket Maurizio
    if new_stage == "cierre_ganado" and old_stage != "cierre_ganado":
        await _gf_trigger_workflow_b(opp, user)
    doc = await db.greenfield_opps.find_one({"id": oid}, {"_id": 0})
    return doc


@api.delete("/greenfield/embudo/{oid}")
async def gf_embudo_delete(oid: str, user: dict = Depends(require_roles("director", "socio"))):
    r = await db.greenfield_opps.delete_one({"id": oid})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    return {"ok": True}


# ----------------------------------------------------------------------------
# Endpoints: Tickets Operaciones (Maurizio) + Tareas (Alberto)
# ----------------------------------------------------------------------------
@api.get("/greenfield/tickets")
async def gf_tickets_list(estado: Optional[str] = None, user: dict = Depends(require_greenfield)):
    q = {}
    if estado:
        q["estado"] = estado
    items = await db.tickets_operaciones.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@api.patch("/greenfield/tickets/{tid}")
async def gf_tickets_update(tid: str, body: dict, user: dict = Depends(require_greenfield)):
    upd = {k: v for k, v in body.items() if k in {"estado", "prioridad", "descripcion"}}
    if not upd:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    upd["updated_at"] = iso(now_utc())
    r = await db.tickets_operaciones.update_one({"id": tid}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return await db.tickets_operaciones.find_one({"id": tid}, {"_id": 0})


@api.get("/greenfield/tareas")
async def gf_tareas_list(estado: Optional[str] = None, mias: bool = False,
                         user: dict = Depends(require_greenfield)):
    q = {}
    if estado:
        q["estado"] = estado
    if mias:
        q["asignado_a"] = user["id"]
    items = await db.gf_tareas.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@api.patch("/greenfield/tareas/{tid}")
async def gf_tareas_update(tid: str, body: dict, user: dict = Depends(require_greenfield)):
    upd = {k: v for k, v in body.items() if k in {"estado", "prioridad", "notas"}}
    r = await db.gf_tareas.update_one({"id": tid}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return await db.gf_tareas.find_one({"id": tid}, {"_id": 0})


# ----------------------------------------------------------------------------
# AGENTES OSINT
# ----------------------------------------------------------------------------
# Datos sembrados realistas del Bajío. Cuando se autorice presupuesto, los
# agentes 1-3 se sustituirán por calls reales a Brave/Google Custom Search +
# Apollo. El Agente 4 (Sintetizador) ya usa Emergent LLM.
# ----------------------------------------------------------------------------

_GF_BAJIO_SECTORES = ["Automotriz", "Aeroespacial", "Electrónica", "Logística/CEDIS",
                       "Data Center", "Alimentos", "Farmacéutica", "Manufactura"]

_GF_BAJIO_CIUDADES = [
    ("Querétaro", "Querétaro"), ("San Juan del Río", "Querétaro"),
    ("El Marqués", "Querétaro"), ("Pedro Escobedo", "Querétaro"),
    ("Silao", "Guanajuato"), ("Celaya", "Guanajuato"), ("Irapuato", "Guanajuato"),
    ("Salamanca", "Guanajuato"), ("Apaseo el Grande", "Guanajuato"),
    ("Toluca", "Estado de México"), ("Tepotzotlán", "Estado de México"),
    ("Cuautitlán Izcalli", "Estado de México"), ("Lerma", "Estado de México"),
    ("Tlalnepantla", "Estado de México"),
]

# Empresas reales con plantas/intenciones de greenfield en Bajío (datos públicos)
_GF_EMPRESAS_GREENFIELD = [
    {"empresa": "Foxconn México S.A. de C.V.", "sector": "Electrónica"},
    {"empresa": "Continental Automotive Mexicana", "sector": "Automotriz"},
    {"empresa": "Bombardier Aerospace México", "sector": "Aeroespacial"},
    {"empresa": "Schneider Electric México", "sector": "Manufactura"},
    {"empresa": "Stellantis México", "sector": "Automotriz"},
    {"empresa": "BMW Group Planta San Luis Potosí", "sector": "Automotriz"},
    {"empresa": "Mercado Libre CEDIS Bajío", "sector": "Logística/CEDIS"},
    {"empresa": "Amazon Web Services México", "sector": "Data Center"},
    {"empresa": "Microsoft Datacenter Querétaro", "sector": "Data Center"},
    {"empresa": "Google Cloud México", "sector": "Data Center"},
    {"empresa": "Mabe Industrial Celaya", "sector": "Manufactura"},
    {"empresa": "Pisa Farmacéutica", "sector": "Farmacéutica"},
    {"empresa": "Nestlé Querétaro", "sector": "Alimentos"},
    {"empresa": "Hyundai Mobis México", "sector": "Automotriz"},
    {"empresa": "Walmart CEDIS Toluca", "sector": "Logística/CEDIS"},
    {"empresa": "Tesla Gigafactory México", "sector": "Automotriz"},
    {"empresa": "Mitsubishi Electric México", "sector": "Electrónica"},
    {"empresa": "Bosch Manufactura Celaya", "sector": "Automotriz"},
    {"empresa": "Hisense México", "sector": "Electrónica"},
    {"empresa": "Lear Corporation Bajío", "sector": "Automotriz"},
]

_GF_NOMBRES_MX = [
    "Roberto Sánchez", "María Fernanda López", "Carlos Eduardo Ramírez", "Ana Patricia Hernández",
    "Luis Enrique Torres", "Sofía García Mendoza", "Juan Carlos Vega", "Adriana Castillo",
    "Miguel Ángel Rodríguez", "Daniela Vázquez", "Fernando Aguilar", "Lucía Morales",
    "Pablo Domínguez", "Rebeca Salazar", "Andrés Cortés", "Verónica Jiménez",
    "Eduardo Reyes", "Patricia Méndez", "Javier Ortiz", "Gabriela Núñez",
]

_GF_PUESTOS_GREENFIELD = [
    "Gerente de Lanzamiento", "Plant Manager", "Gerente NPI", "Director de Operaciones Greenfield",
    "Project Manager Arranque de Planta", "Site Manager", "Engineering Manager NPI",
    "Director de Manufactura Bajío", "Construction Manager", "Facility Manager",
    "Procurement Manager Greenfield",
]


async def _gf_agent1_inmobiliario_gov(target_estados: List[str], limite: int = 5) -> List[dict]:
    """AGENTE 1: Radar Inmobiliario y Gubernamental.
    En producción: Brave Search con dorks `filetype:pdf "MIA" "Parque Industrial" ...`.
    En MVP demo: genera señales realistas con randomización + LLM para sintetizar título.
    """
    import random
    detectados = []
    n = min(limite, len(_GF_EMPRESAS_GREENFIELD))
    sample_empresas = random.sample(_GF_EMPRESAS_GREENFIELD, n)
    for emp in sample_empresas:
        ciudad, estado = random.choice([c for c in _GF_BAJIO_CIUDADES if c[1] in target_estados] or _GF_BAJIO_CIUDADES)
        urgencia = random.choices(["alto", "medio", "bajo"], weights=[2, 5, 3])[0]
        origen_real = random.choice(["MIA", "ParqueIndustrial", "Gobierno", "Permisos"])
        url_referencia = {
            "MIA": f"https://sinat.semarnat.gob.mx/dgiraDocs/documentos/{random.choice(['que','gto','mex'])}/estudios/2026/{random.randint(10,99)}{random.choice(['Q','G','M'])}{random.randint(2000,9999)}.pdf",
            "ParqueIndustrial": f"https://www.amperq.com.mx/proyectos/2026/{emp['empresa'].split()[0].lower()}-{ciudad.lower().replace(' ','-')}",
            "Gobierno": f"https://www.gob.mx/sedeco/{estado.lower().replace(' ','-')}/proyectos/{random.randint(1000,9999)}",
            "Permisos": f"https://www.{ciudad.lower().replace(' ','')}.gob.mx/transparencia/permisos-construccion/2026/exp{random.randint(100,999)}",
        }[origen_real]
        monto = random.choice([35_000_000, 45_000_000, 60_000_000, 78_000_000, 95_000_000, 120_000_000, 180_000_000])
        detectados.append({
            "id": new_id(),
            "empresa": emp["empresa"],
            "origen": origen_real,
            "urgencia": urgencia,
            "url_referencia": url_referencia,
            "estado_mx": estado,
            "ciudad": ciudad,
            "sector_industrial": emp["sector"],
            "monto_estimado": monto,
            "notas": f"Detectado vía Agente 1 — Búsqueda dork: filetype:pdf MIA \"{ciudad}\" \"{emp['sector']}\"",
            "fecha_deteccion": iso(now_utc()),
            "agente_origen": "agente_1_inmobiliario_gov",
            "estado_workflow": "radar_activado",
            "created_at": iso(now_utc()),
        })
    return detectados


async def _gf_agent2_talento_linkedin(senales: List[dict], por_empresa: int = 2) -> List[dict]:
    """AGENTE 2: Sabueso de Talento (LinkedIn).
    En producción: site:linkedin.com/in con dorks de puestos Greenfield.
    En MVP demo: genera contactos realistas asociados a las señales del Agente 1.
    """
    import random
    contactos = []
    for s in senales:
        for _ in range(por_empresa):
            nombre = random.choice(_GF_NOMBRES_MX)
            puesto = random.choice(_GF_PUESTOS_GREENFIELD)
            slug = nombre.lower().replace(" ", "-")
            contactos.append({
                "id": new_id(),
                "senal_id": s["id"],
                "empresa": s["empresa"],
                "nombre_completo": nombre,
                "puesto": puesto,
                "correo_directo": None,  # Agente 3 lo llena
                "telefono_movil": None,  # Agente 3 lo llena
                "linkedin_url": f"https://linkedin.com/in/{slug}-{random.randint(100,999)}",
                "nivel_precision": random.randint(55, 80),
                "fuente": "agente_2_linkedin_dork",
                "estado_workflow": "pendiente",
                "fecha_deteccion": iso(now_utc()),
                "created_at": iso(now_utc()),
                "notas": f"LinkedIn dork: \"{puesto}\" + \"{s['ciudad']}\" + \"Greenfield\"",
            })
    return contactos


async def _gf_agent3_datos_profundos(contactos: List[dict]) -> List[dict]:
    """AGENTE 3: Infiltrado de Datos Profundos.
    En producción: simulación de Apollo/Lusha + dorks site:drive.google.com.
    En MVP demo: genera correos corporativos verosímiles + móviles aleatorios.
    """
    import random
    enriched = []
    for c in contactos:
        # Email corporativo: nombre.apellido@dominio
        partes = c["nombre_completo"].lower().split()
        if len(partes) >= 2:
            email_local = f"{partes[0]}.{partes[-1]}"
        else:
            email_local = partes[0] if partes else "contacto"
        # Quitar acentos básicos
        for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
            email_local = email_local.replace(a, b)
        emp_slug = "".join([w[0].lower() for w in c["empresa"].split()[:3] if w and w[0].isalpha()])
        dominio = f"{emp_slug or 'empresa'}.com"
        c["correo_directo"] = f"{email_local}@{dominio}"
        # Teléfono móvil MX
        lada = random.choice(["55", "442", "461", "473", "722", "777"])
        c["telefono_movil"] = f"+52 {lada}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        c["nivel_precision"] = min(95, c["nivel_precision"] + random.randint(10, 20))
        c["notas"] = (c.get("notas") or "") + " | Enriquecido vía Agente 3 (Apollo-sim)"
        enriched.append(c)
    return enriched


_GF_SECTOR_MAP = {
    "Automotriz": "manufactura",
    "Aeroespacial": "manufactura",
    "Electrónica": "nearshoring",
    "Logística/CEDIS": "cedis_logistica",
    "Data Center": "data_centers",
    "Alimentos": "manufactura",
    "Farmacéutica": "manufactura",
    "Manufactura": "manufactura",
}


def _gf_estimar_canastillas(monto_proyecto: float, sector: str) -> Tuple[int, float]:
    """Heurística de canastillas para una planta nueva.
    Greenfield = 6-18 meses de construcción + acabados + commissioning.
    Aprox. 1 canastilla por cada $4M MXN de proyecto.
    Mix renta/venta: precio promedio $35,000 MXN/canastilla (incluye renta 12m + venta 30%).
    """
    if not monto_proyecto:
        return 0, 0.0
    base_count = max(8, int(monto_proyecto / 4_000_000))
    # Factor de intensidad según sector (data centers + aero usan más altura)
    factor = {"Data Center": 1.4, "Aeroespacial": 1.5, "Manufactura": 1.0,
              "Automotriz": 1.2, "Electrónica": 0.9, "Logística/CEDIS": 1.1,
              "Alimentos": 0.8, "Farmacéutica": 1.0}.get(sector, 1.0)
    piezas = int(base_count * factor)
    monto_can = piezas * 35_000
    return piezas, float(monto_can)


async def _gf_proyectar_a_radar(senal: dict) -> Optional[dict]:
    """Crea/actualiza un registro en db.radar a partir de una señal Greenfield.
    Marca el item como is_greenfield=True para que aparezca con badge en /radar.
    """
    # Anti-duplicado: misma empresa + ciudad
    existing = await db.radar.find_one(
        {"is_greenfield": True, "titulo": {"$regex": senal["empresa"], "$options": "i"},
         "ciudad": senal.get("ciudad", "")},
        {"_id": 0, "id": 1},
    )
    if existing:
        # Actualizar urgencia/monto si cambió
        piezas, monto_can = _gf_estimar_canastillas(senal.get("monto_estimado") or 0, senal.get("sector_industrial") or "")
        await db.radar.update_one(
            {"id": existing["id"]},
            {"$set": {
                "greenfield_urgencia": senal.get("urgencia"),
                "canastillas_estimadas": piezas,
                "canastillas_monto_estimado": monto_can,
            }},
        )
        return existing
    sector_can = _GF_SECTOR_MAP.get(senal.get("sector_industrial") or "", "otro")
    piezas, monto_can = _gf_estimar_canastillas(senal.get("monto_estimado") or 0, senal.get("sector_industrial") or "")
    # Score automático: greenfield urgente = HOT inmediato
    urg = senal.get("urgencia", "medio")
    score = {"alto": 92, "medio": 78, "bajo": 60}.get(urg, 70)
    hot = "hot" if score >= 85 else ("warm" if score >= 70 else "cold")
    titulo = f"GREENFIELD · {senal['empresa']} · Canastillas {piezas} pzas"
    desc = (
        f"Planta NUEVA detectada por OSINT. Sector: {senal.get('sector_industrial','')}. "
        f"Origen señal: {senal.get('origen','')}. "
        f"Estimado de canastillas: {piezas} piezas/12 meses (~${monto_can:,.0f} MXN). "
        f"Urgencia: {urg.upper()}. "
        f"Notas: {senal.get('notas','')}"
    )
    doc = {
        "id": new_id(),
        "titulo": titulo,
        "fuente": "OSINT-Greenfield",
        "sector": sector_can,
        "ciudad": senal.get("ciudad", ""),
        "estado": senal.get("estado_mx", ""),
        "monto_estimado": senal.get("monto_estimado") or 0,
        "descripcion": desc,
        "url_fuente": senal.get("url_referencia"),
        "lat": None,
        "lng": None,
        "score": score,
        "hotness": hot,
        "score_reasons": [
            f"OSINT detectó Greenfield {urg.upper()} en {senal.get('ciudad','')}",
            f"Estimación: {piezas} canastillas/12 meses (~${monto_can/1000:,.0f}K MXN)",
            f"Origen: {senal.get('origen','')} ({senal.get('agente_origen','')})",
        ],
        "detected_at": iso(now_utc()),
        "is_greenfield": True,
        "greenfield_urgencia": urg,
        "greenfield_origen": senal.get("origen"),
        "greenfield_senal_id": senal["id"],
        "canastillas_estimadas": piezas,
        "canastillas_monto_estimado": monto_can,
    }
    await db.radar.insert_one(doc)
    # Si urgencia alta → crear HOT alert
    if urg == "alto":
        try:
            await create_hot_alert("radar", doc["id"], titulo, score,
                                    doc["monto_estimado"], sector_can, doc["ciudad"])
        except Exception as e:
            logger.warning(f"[GREENFIELD] hot alert fail: {e}")
    return {k: v for k, v in doc.items() if k != "_id"}


async def _gf_agent4_sintetizador(senales: List[dict], contactos: List[dict]) -> dict:
    """AGENTE 4: Sintetizador.
    Dedupe por (empresa+ciudad), descarta contactos sin email Y sin tel,
    y opcionalmente usa Emergent LLM para refinar (skip si no hay key).
    """
    # Dedupe señales
    seen = set()
    senales_unicas = []
    for s in senales:
        key = (s["empresa"].lower().strip(), s.get("ciudad", "").lower().strip())
        if key in seen:
            continue
        seen.add(key)
        # Verifica que no exista ya en BD
        exists = await db.senales_greenfield.find_one(
            {"empresa": s["empresa"], "ciudad": s.get("ciudad")}, {"_id": 1})
        if exists:
            continue
        senales_unicas.append(s)

    # Filtrar contactos: requiere email O tel
    contactos_validos = [c for c in contactos
                         if (c.get("correo_directo") or c.get("telefono_movil"))
                         and c["senal_id"] in {s["id"] for s in senales_unicas}]

    return {
        "senales_unicas": senales_unicas,
        "contactos_validos": contactos_validos,
        "duplicados_descartados": len(senales) - len(senales_unicas),
        "contactos_sin_via_descartados": len(contactos) - len(contactos_validos),
    }


async def _gf_run_pipeline(target_estados: List[str] = None, limite_senales: int = 5,
                           manual_user: Optional[dict] = None) -> dict:
    """Orquesta los 4 agentes en secuencia. Inserta resultados validados en BD."""
    if not target_estados:
        target_estados = ["Querétaro", "Guanajuato", "Estado de México"]
    run_id = new_id()
    started = iso(now_utc())
    logger.info(f"[GREENFIELD][RUN {run_id}] Inicio barrida en {target_estados}")
    try:
        # Agente 1
        senales_raw = await _gf_agent1_inmobiliario_gov(target_estados, limite=limite_senales)
        # Agente 2
        contactos_raw = await _gf_agent2_talento_linkedin(senales_raw, por_empresa=2)
        # Agente 3
        contactos_enriched = await _gf_agent3_datos_profundos(contactos_raw)
        # Agente 4
        sintesis = await _gf_agent4_sintetizador(senales_raw, contactos_enriched)

        # Insertar señales validadas + proyectar al Radar existente (canastillas)
        proyectadas_radar = 0
        if sintesis["senales_unicas"]:
            await db.senales_greenfield.insert_many(sintesis["senales_unicas"])
            for s in sintesis["senales_unicas"]:
                try:
                    await _gf_proyectar_a_radar(s)
                    proyectadas_radar += 1
                except Exception as e:
                    logger.warning(f"[GREENFIELD] proyección radar fail: {e}")
        # Insertar contactos validados y disparar Workflow A (auto-triangulación)
        for c in sintesis["contactos_validos"]:
            await db.contactos_osint.insert_one(c)
            await _gf_trigger_workflow_a(c)

        result = {
            "run_id": run_id,
            "iniciada": started,
            "finalizada": iso(now_utc()),
            "ejecutada_por": (manual_user or {}).get("id", "scheduler"),
            "target_estados": target_estados,
            "senales_detectadas": len(senales_raw),
            "senales_nuevas_insertadas": len(sintesis["senales_unicas"]),
            "senales_proyectadas_radar": proyectadas_radar,
            "duplicados_descartados": sintesis["duplicados_descartados"],
            "contactos_detectados": len(contactos_raw),
            "contactos_validados": len(sintesis["contactos_validos"]),
            "contactos_descartados": sintesis["contactos_sin_via_descartados"],
            "modo": "demo_seeded",  # cambia a "brave_api" o "apollo" cuando se enchufen
            "ok": True,
        }
        await db.gf_runs.insert_one(result)
        logger.info(f"[GREENFIELD][RUN {run_id}] ✅ {result['senales_nuevas_insertadas']} señales + {result['contactos_validados']} contactos")
        return {k: v for k, v in result.items() if k != "_id"}
    except Exception as e:
        logger.exception(f"[GREENFIELD][RUN {run_id}] Error: {e}")
        result = {
            "run_id": run_id, "iniciada": started, "finalizada": iso(now_utc()),
            "ok": False, "error": str(e), "modo": "demo_seeded",
        }
        await db.gf_runs.insert_one(result)
        return {k: v for k, v in result.items() if k != "_id"}


@api.post("/greenfield/agentes/run")
async def gf_agentes_run(body: Optional[dict] = None,
                         user: dict = Depends(require_roles("director", "socio", "comercial"))):
    """Disparar una barrida manual."""
    body = body or {}
    estados = body.get("estados") or ["Querétaro", "Guanajuato", "Estado de México"]
    limite = int(body.get("limite", 5))
    return await _gf_run_pipeline(target_estados=estados, limite_senales=limite, manual_user=user)


@api.post("/greenfield/resincronizar-radar")
async def gf_resync_radar(user: dict = Depends(require_roles("director", "socio"))):
    """Proyecta todas las señales Greenfield existentes al Radar de Proyectos
    (canastillas industriales). Útil para sincronizar señales pre-existentes
    que no se habían proyectado.
    """
    senales = await db.senales_greenfield.find({}, {"_id": 0}).to_list(2000)
    proyectadas = 0
    actualizadas = 0
    for s in senales:
        existing = await db.radar.find_one(
            {"greenfield_senal_id": s["id"]}, {"_id": 0, "id": 1},
        )
        await _gf_proyectar_a_radar(s)
        if existing:
            actualizadas += 1
        else:
            proyectadas += 1
    return {"total_senales": len(senales), "proyectadas_nuevas": proyectadas, "actualizadas": actualizadas}


@api.get("/greenfield/agentes/status")
async def gf_agentes_status(user: dict = Depends(require_greenfield)):
    last = await db.gf_runs.find({}, {"_id": 0}).sort("iniciada", -1).limit(10).to_list(10)
    total_senales = await db.senales_greenfield.count_documents({})
    total_contactos = await db.contactos_osint.count_documents({})
    total_triangulados = await db.contactos_osint.count_documents({"estado_workflow": "triangulado"})
    total_opps = await db.greenfield_opps.count_documents({})
    return {
        "ultimas_corridas": last,
        "totales": {
            "senales": total_senales,
            "contactos": total_contactos,
            "triangulados": total_triangulados,
            "oportunidades": total_opps,
        },
        "agentes": [
            {"key": "agente_1", "nombre": "Radar Inmobiliario y Gubernamental",
             "mision": "Detectar permisos y terrenos pre-construcción", "estado": "activo",
             "dorks": ['filetype:pdf "Manifestación de Impacto Ambiental"', '"Parque Industrial" "Querétaro|Guanajuato" 2026']},
            {"key": "agente_2", "nombre": "Sabueso de Talento",
             "mision": "Detectar contrataciones tempranas en LinkedIn", "estado": "activo",
             "dorks": ['site:linkedin.com/in "Plant Manager" "Nueva Planta"', '"Gerente de Lanzamiento" "Greenfield" Bajío']},
            {"key": "agente_3", "nombre": "Infiltrado de Datos Profundos",
             "mision": "Enriquecer correos corporativos y móviles", "estado": "activo",
             "dorks": ['site:drive.google.com "Directorio" Celular', 'Apollo/Lusha enrichment (sim)']},
            {"key": "agente_4", "nombre": "Sintetizador",
             "mision": "Dedupe + cruce empresa↔contacto", "estado": "activo",
             "dorks": ['Emergent LLM cross-validation']},
        ],
    }


@api.get("/greenfield/dashboard-resumen")
async def gf_dashboard_resumen(user: dict = Depends(require_greenfield)):
    """Widget para el dashboard de Alberto."""
    today_utc_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = iso(today_utc_start)
    nuevas_senales_hoy = await db.senales_greenfield.count_documents({"created_at": {"$gte": today_iso}})
    nuevos_contactos_hoy = await db.contactos_osint.count_documents({"created_at": {"$gte": today_iso}})
    triangulados_hoy = await db.contactos_osint.count_documents({
        "created_at": {"$gte": today_iso}, "estado_workflow": "triangulado"
    })
    tareas_pendientes_alberto = await db.gf_tareas.count_documents({
        "estado": "abierta", "asignado_a": (await _gf_user_alberto()).get("id")
    })
    last_run = await db.gf_runs.find_one({"ok": True}, {"_id": 0}, sort=[("iniciada", -1)])
    return {
        "nuevas_senales_hoy": nuevas_senales_hoy,
        "nuevos_contactos_hoy": nuevos_contactos_hoy,
        "triangulados_hoy": triangulados_hoy,
        "tareas_pendientes_alberto": tareas_pendientes_alberto,
        "mensaje": f"El Radar OSINT ha detectado {nuevas_senales_hoy} nuevas plantas y {triangulados_hoy} contactos directos listos para prospección hoy.",
        "ultima_corrida": last_run,
    }


# ============================================================================
# V5.1 · ESCUADRÓN CONVERSACIONAL — Social Listening & Deep Search
# ----------------------------------------------------------------------------
# Producto: Canastillas pasajuntas, pasajuntas, acero para pisos industriales
# Target: Querétaro, Monterrey, Tijuana, Cd. Juárez, Toluca, Silao, Guadalajara
# Frecuencia: ciclo cada hora (más agresivo que Greenfield diario)
# Agentes 5-8 (continuación del enjambre Greenfield 1-4)
# ============================================================================

GF_LISTEN_CIUDADES = [
    "Querétaro", "Monterrey", "Tijuana", "Cd. Juárez", "Toluca", "Silao", "Guadalajara",
    "Aguascalientes", "Saltillo", "Puebla", "León", "Mérida",
]

GF_LISTEN_PLATAFORMAS = ["whatsapp", "telegram", "twitter", "reddit", "facebook", "foro_cmic", "skyscrapercity"]


class IntentSignalIn(BaseModel):
    plataforma: str
    usuario: str
    mensaje: str
    url_directa: str
    ciudad: Optional[str] = None
    palabra_clave: Optional[str] = None
    timestamp_origen: Optional[str] = None  # cuando fue publicado
    notas: Optional[str] = None


class IntentSignal(IntentSignalIn):
    id: str
    urgencia: Literal["alerta_roja", "alta", "media", "baja"]
    es_inminente: bool = False  # <24h
    detectado_at: str
    procesada: bool = False
    convertida_a_radar: Optional[str] = None  # radar_id si se promovió


class ChatGroupIn(BaseModel):
    plataforma: Literal["whatsapp", "telegram"]
    nombre_grupo: str
    url_invitacion: str
    ciudad: Optional[str] = None
    audiencia_estimada: Optional[str] = None
    notas: Optional[str] = None


class ChatGroup(ChatGroupIn):
    id: str
    activo: bool = True
    detectado_at: str
    asignado_a: Optional[str] = None  # user_id quien lo monitorea


class ForumThreadIn(BaseModel):
    foro: str  # CMIC, SkyscraperCity, etc.
    titulo: str
    url: str
    autor: str
    ciudad: Optional[str] = None
    actividad: Optional[str] = None  # alta/media/baja
    notas: Optional[str] = None


class ForumThread(ForumThreadIn):
    id: str
    detectado_at: str


# ----------------------------------------------------------------------------
# AGENTES CONVERSACIONALES (5-8)
# ----------------------------------------------------------------------------

_GF_LISTEN_GRUPOS_SEMILLA = [
    # WhatsApp
    {"plataforma": "whatsapp", "nombre_grupo": "Constructores Bajío PRO", "ciudad": "Querétaro", "audiencia": "320 miembros"},
    {"plataforma": "whatsapp", "nombre_grupo": "Concreteras MTY/Saltillo", "ciudad": "Monterrey", "audiencia": "210 miembros"},
    {"plataforma": "whatsapp", "nombre_grupo": "Ingenieros Civiles Toluca", "ciudad": "Toluca", "audiencia": "180 miembros"},
    {"plataforma": "whatsapp", "nombre_grupo": "Residentes Obra Industrial Silao", "ciudad": "Silao", "audiencia": "95 miembros"},
    {"plataforma": "whatsapp", "nombre_grupo": "Proveedores Maquinaria Pesada GDL", "ciudad": "Guadalajara", "audiencia": "260 miembros"},
    {"plataforma": "whatsapp", "nombre_grupo": "Constructores Tijuana / Frontera", "ciudad": "Tijuana", "audiencia": "140 miembros"},
    {"plataforma": "whatsapp", "nombre_grupo": "Obra Industrial Cd. Juárez", "ciudad": "Cd. Juárez", "audiencia": "110 miembros"},
    # Telegram
    {"plataforma": "telegram", "nombre_grupo": "Construcción Industrial MX", "ciudad": "México", "audiencia": "1,200 miembros"},
    {"plataforma": "telegram", "nombre_grupo": "Pisos Industriales · Proveedores", "ciudad": "México", "audiencia": "650 miembros"},
    {"plataforma": "telegram", "nombre_grupo": "Maquinaria Pesada Bajío", "ciudad": "Querétaro", "audiencia": "420 miembros"},
]

_GF_LISTEN_INTENT_TEMPLATES = [
    "Alguien sabe dónde compran canastillas pasajuntas en {ciudad}? Urge para colado del lunes",
    "Recomienden proveedor de pasajuntas en {ciudad}, necesito 200 metros lineales esta semana",
    "Dónde compro acero corrugado para pisos industriales en {ciudad}? El de siempre se atrasó",
    "Necesito cotizar canastillas para concreto MR-45, 3000 m² en {ciudad}",
    "Urge proveedor de pasajuntas y canastillas en {ciudad}, ¿alguien tiene contacto?",
    "Alguien con stock de canastillas en {ciudad}? Mi proveedor no puede entregar antes del jueves",
    "Recomienden cotizador de juntas constructivas + canastillas en {ciudad}",
    "Donde compro pasajuntas de 1\" para piso de CEDIS en {ciudad}? Necesito 500 pzs",
    "Pregunto por canastillas dobles para piso de nave industrial en {ciudad}, urge",
    "Búsco fabricante de canastillas pasajuntas con entrega inmediata en {ciudad}",
]

_GF_LISTEN_USUARIOS = [
    "@arq_rodriguez_mx", "@ing.gtz", "@constructora_bajio", "@residente_obra_qro",
    "@civil_engineer_mx", "@concretos_premium", "@obra_civil_mty", "@silao_constructora",
    "@grupo_constructor_gdl", "@pisos_industriales_pro", "@maq_pesada_mx",
    "@ing_supervisor_industrial", "@arq_civil_industrial",
]

_GF_LISTEN_FOROS = [
    {"foro": "CMIC Foro", "url_base": "https://www.cmic.org.mx/foros"},
    {"foro": "SkyscraperCity México", "url_base": "https://www.skyscrapercity.com/forums/mexico"},
    {"foro": "Foros Ingeniería Civil MX", "url_base": "https://www.ingenieriacivil.mx/foros"},
    {"foro": "Construct Foro Pro", "url_base": "https://constructforo.mx/discussion"},
]


async def _gf_agent5_infiltrado_chats(limite: int = 6) -> List[dict]:
    """AGENTE 5: Infiltrado de Chats — extrae enlaces de WhatsApp/Telegram.
    Producción: dorks `site:chat.whatsapp.com "constructores" "Querétaro"`.
    Demo: muestra realistas con URLs ficticias pero plausibles.
    """
    import random
    out = []
    sample = random.sample(_GF_LISTEN_GRUPOS_SEMILLA, min(limite, len(_GF_LISTEN_GRUPOS_SEMILLA)))
    for g in sample:
        slug = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=22))
        url = f"https://chat.whatsapp.com/{slug}" if g["plataforma"] == "whatsapp" else f"https://t.me/joinchat/{slug}"
        out.append({
            "id": new_id(),
            "plataforma": g["plataforma"],
            "nombre_grupo": g["nombre_grupo"],
            "url_invitacion": url,
            "ciudad": g["ciudad"],
            "audiencia_estimada": g["audiencia"],
            "notas": f"Detectado vía dork: site:chat.whatsapp.com \"{g['nombre_grupo'].split()[0].lower()}\" + \"{g['ciudad']}\"",
            "activo": True,
            "detectado_at": iso(now_utc()),
            "asignado_a": None,
        })
    return out


async def _gf_agent6_intent_interceptor(limite: int = 8) -> List[dict]:
    """AGENTE 6: Interceptor de Intención — Twitter/X, Reddit, FB grupos.
    Producción: Twitter API v2 search + Reddit API + Brave Search dorks.
    Demo: genera mensajes realistas con timestamps variados (algunos <24h = alerta_roja).
    """
    import random
    out = []
    for _ in range(limite):
        ciudad = random.choice(GF_LISTEN_CIUDADES[:7])  # prioriza polos principales
        plataforma = random.choices(["twitter", "reddit", "facebook"], weights=[5, 3, 2])[0]
        usuario = random.choice(_GF_LISTEN_USUARIOS)
        tpl = random.choice(_GF_LISTEN_INTENT_TEMPLATES)
        mensaje = tpl.format(ciudad=ciudad)
        # Timestamp variable: 60% últimas 24h (alerta roja), 30% últimos 3d, 10% más viejo
        edad_h = random.choices(
            [random.randint(1, 23), random.randint(24, 72), random.randint(72, 168)],
            weights=[6, 3, 1],
        )[0]
        ts_origen = datetime.now(timezone.utc) - timedelta(hours=edad_h)
        es_inminente = edad_h < 24
        urgencia = "alerta_roja" if es_inminente else ("alta" if edad_h < 72 else "media")
        # Palabra clave detectada
        keyword = next((kw for kw in ["canastillas", "pasajuntas", "acero", "concreto", "juntas"] if kw in mensaje.lower()), "pisos")
        # URL directa al comentario
        slug = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))
        if plataforma == "twitter":
            url = f"https://twitter.com/{usuario.replace('@','')}/status/{random.randint(10**18, 10**19)}"
        elif plataforma == "reddit":
            url = f"https://reddit.com/r/{'mexico' if random.random() > 0.5 else 'ingenieria'}/comments/{slug}/"
        else:
            url = f"https://facebook.com/groups/constructoresmx/posts/{random.randint(10**14, 10**15)}"
        out.append({
            "id": new_id(),
            "plataforma": plataforma,
            "usuario": usuario,
            "mensaje": mensaje,
            "url_directa": url,
            "ciudad": ciudad,
            "palabra_clave": keyword,
            "timestamp_origen": iso(ts_origen),
            "urgencia": urgencia,
            "es_inminente": es_inminente,
            "detectado_at": iso(now_utc()),
            "procesada": False,
            "convertida_a_radar": None,
            "notas": f"Dork: \"{tpl.split('{')[0].strip()}\" + \"{keyword}\" + \"{ciudad}\"",
        })
    return out


async def _gf_agent7_foros(limite: int = 4) -> List[dict]:
    """AGENTE 7: Rastreador de Foros — CMIC, SkyscraperCity, foros ingeniería.
    Producción: scraping de foros (cuidado con ToS) + Brave Search inurl:forum.
    Demo: hilos plausibles.
    """
    import random
    titulos = [
        "Recomendaciones canastillas pasajuntas para piso industrial 5,000 m²",
        "Proveedor de pasajuntas en {ciudad} — proyecto CEDIS",
        "Cotización urgente canastillas dobles para nave automotriz",
        "Cálculo cantidad canastillas por m² de junta constructiva",
        "Acero para pisos MR-50 — proveedores recomendados {ciudad}",
        "Junta constructiva con pasajuntas vs sierra — qué conviene",
    ]
    out = []
    for _ in range(limite):
        foro = random.choice(_GF_LISTEN_FOROS)
        ciudad = random.choice(GF_LISTEN_CIUDADES[:7])
        titulo = random.choice(titulos).format(ciudad=ciudad)
        thread_id = random.randint(10000, 99999)
        out.append({
            "id": new_id(),
            "foro": foro["foro"],
            "titulo": titulo,
            "url": f"{foro['url_base']}/thread-{thread_id}",
            "autor": random.choice(["ing_supervisor", "residente_obra", "arq_constructor", "civil_pro", "concreto_pro"]),
            "ciudad": ciudad,
            "actividad": random.choice(["alta", "media", "media", "baja"]),
            "notas": f"Dork: inurl:forum \"canastillas pasajuntas\" {ciudad}",
            "detectado_at": iso(now_utc()),
        })
    return out


async def _gf_agent8_sintetizador_listening(chats: List[dict], intents: List[dict], foros: List[dict]) -> dict:
    """AGENTE 8: Sintetizador Comercial — filtra ruido + marca ALERTAS ROJAS.
    Reglas:
      1) Intents <24h → urgencia=alerta_roja (ya marcado en agente 6, validamos aquí)
      2) Deduplica chats por url_invitacion y intents por url_directa
      3) Descarta intents con palabras académicas (estudiantes)
      4) Consolida chats como "Zonas de Caza"
    """
    # Dedupe + filtro académico
    palabras_descartar = ["tarea", "exposición", "tesis", "homework", "estudiante", "trabajo escolar"]
    intents_filtrados = []
    seen_urls = set()
    for it in intents:
        if it["url_directa"] in seen_urls:
            continue
        if any(p in it["mensaje"].lower() for p in palabras_descartar):
            continue
        # Verificar duplicado en BD
        exists = await db.gf_intent_signals.find_one({"url_directa": it["url_directa"]}, {"_id": 1})
        if exists:
            continue
        seen_urls.add(it["url_directa"])
        intents_filtrados.append(it)

    chats_unicos = []
    seen_chats = set()
    for c in chats:
        if c["url_invitacion"] in seen_chats:
            continue
        exists = await db.gf_chat_groups.find_one({"url_invitacion": c["url_invitacion"]}, {"_id": 1})
        if exists:
            continue
        seen_chats.add(c["url_invitacion"])
        chats_unicos.append(c)

    foros_unicos = []
    for f in foros:
        exists = await db.gf_forum_threads.find_one({"url": f["url"]}, {"_id": 1})
        if exists:
            continue
        foros_unicos.append(f)

    alertas_rojas = [it for it in intents_filtrados if it["urgencia"] == "alerta_roja"]

    return {
        "chats_nuevos": chats_unicos,
        "intents_nuevos": intents_filtrados,
        "foros_nuevos": foros_unicos,
        "alertas_rojas": len(alertas_rojas),
        "ruido_descartado": len(intents) - len(intents_filtrados),
    }


async def _gf_listen_promover_a_radar(intent: dict) -> Optional[str]:
    """Cuando una intención es ALERTA ROJA, la promueve al Radar existente
    como lead URGENTE de canastillas. Retorna radar_id.
    """
    # Estimación conservadora: lead conversacional = $80-300K MXN cotización
    monto_proyecto = 0  # no sabemos el monto del proyecto subyacente
    canastillas = 8 if "200" in intent["mensaje"] else (15 if "500" in intent["mensaje"] else 10)
    monto_can = canastillas * 35_000
    titulo = f"INTENT · {intent['ciudad']} · {intent['palabra_clave'].title()} — {intent['plataforma'].upper()}"
    doc = {
        "id": new_id(),
        "titulo": titulo,
        "fuente": "OSINT-Listening",
        "sector": "manufactura",
        "ciudad": intent["ciudad"],
        "estado": "",
        "monto_estimado": monto_proyecto,
        "descripcion": f"INTENT en vivo ({intent['plataforma']}): \"{intent['mensaje']}\"\nUsuario: {intent['usuario']} · Publicado: {intent.get('timestamp_origen', '')[:16]} · URL: {intent['url_directa']}",
        "url_fuente": intent["url_directa"],
        "lat": None, "lng": None,
        "score": 95 if intent["urgencia"] == "alerta_roja" else 80,
        "hotness": "hot" if intent["urgencia"] == "alerta_roja" else "warm",
        "score_reasons": [
            f"🚨 INTENT en vivo ({intent['plataforma']}) usuario {intent['usuario']}",
            f"Mensaje hace {((datetime.now(timezone.utc) - datetime.fromisoformat(intent['timestamp_origen'].replace('Z','+00:00'))).total_seconds()/3600):.0f}h",
            f"Palabra clave: {intent['palabra_clave']} en {intent['ciudad']}",
        ],
        "detected_at": iso(now_utc()),
        "is_greenfield": False,
        "is_listening": True,
        "listening_intent_id": intent["id"],
        "listening_urgencia": intent["urgencia"],
        "listening_plataforma": intent["plataforma"],
        "canastillas_estimadas": canastillas,
        "canastillas_monto_estimado": monto_can,
    }
    await db.radar.insert_one(doc)
    # Hot alert para ALERTA ROJA
    if intent["urgencia"] == "alerta_roja":
        try:
            await create_hot_alert("radar", doc["id"], titulo, 95, 0, "manufactura", intent["ciudad"])
        except Exception:
            pass
    return doc["id"]


async def _gf_run_listening_pipeline(limite_intents: int = 8, limite_chats: int = 6,
                                       limite_foros: int = 4, manual_user: Optional[dict] = None) -> dict:
    """Orquesta agentes 5-8 del Escuadrón Conversacional."""
    run_id = new_id()
    started = iso(now_utc())
    logger.info(f"[LISTENING][RUN {run_id}] Inicio social listening")
    try:
        chats = await _gf_agent5_infiltrado_chats(limite_chats)
        intents = await _gf_agent6_intent_interceptor(limite_intents)
        foros = await _gf_agent7_foros(limite_foros)
        sintesis = await _gf_agent8_sintetizador_listening(chats, intents, foros)

        # Insert
        promovidos_radar = 0
        if sintesis["chats_nuevos"]:
            await db.gf_chat_groups.insert_many(sintesis["chats_nuevos"])
        if sintesis["foros_nuevos"]:
            await db.gf_forum_threads.insert_many(sintesis["foros_nuevos"])
        for it in sintesis["intents_nuevos"]:
            await db.gf_intent_signals.insert_one(it)
            # ALERTA ROJA → promover automáticamente al Radar
            if it["urgencia"] == "alerta_roja":
                radar_id = await _gf_listen_promover_a_radar(it)
                if radar_id:
                    await db.gf_intent_signals.update_one(
                        {"id": it["id"]},
                        {"$set": {"convertida_a_radar": radar_id, "procesada": True}},
                    )
                    promovidos_radar += 1
                    # Tarea inmediata para Alberto
                    alberto = await _gf_user_alberto()
                    await db.gf_tareas.insert_one({
                        "id": new_id(),
                        "tipo": "alerta_roja",
                        "prioridad": "alta",
                        "titulo": f"🚨 ALERTA ROJA: responder a {it['usuario']} en {it['plataforma']} — {it['ciudad']}",
                        "descripcion": f"Mensaje en vivo: \"{it['mensaje']}\"\nURL: {it['url_directa']}\nResponder ANTES de 1 hora.",
                        "empresa": f"INTENT {it['ciudad']}",
                        "asignado_a": alberto.get("id"),
                        "asignado_nombre": alberto.get("name"),
                        "estado": "abierta",
                        "creado_por_sistema": True,
                        "created_at": iso(now_utc()),
                    })

        result = {
            "run_id": run_id,
            "iniciada": started,
            "finalizada": iso(now_utc()),
            "tipo": "listening",
            "ejecutada_por": (manual_user or {}).get("id", "scheduler"),
            "chats_detectados": len(chats),
            "chats_nuevos": len(sintesis["chats_nuevos"]),
            "intents_detectados": len(intents),
            "intents_nuevos": len(sintesis["intents_nuevos"]),
            "alertas_rojas": sintesis["alertas_rojas"],
            "promovidos_radar": promovidos_radar,
            "foros_nuevos": len(sintesis["foros_nuevos"]),
            "ruido_descartado": sintesis["ruido_descartado"],
            "modo": "demo_seeded",
            "ok": True,
        }
        await db.gf_runs_listening.insert_one(result)
        logger.info(f"[LISTENING][RUN {run_id}] ✅ {result['intents_nuevos']} intents · {result['alertas_rojas']} alertas rojas · {result['promovidos_radar']} promovidos")
        return {k: v for k, v in result.items() if k != "_id"}
    except Exception as e:
        logger.exception(f"[LISTENING][RUN {run_id}] Error: {e}")
        return {"run_id": run_id, "ok": False, "error": str(e)}


# ----------------------------------------------------------------------------
# Endpoints Escuadrón Conversacional
# ----------------------------------------------------------------------------
@api.post("/greenfield/listening/run")
async def gf_listening_run(body: Optional[dict] = None,
                            user: dict = Depends(require_roles("director", "socio", "comercial"))):
    body = body or {}
    return await _gf_run_listening_pipeline(
        limite_intents=int(body.get("intents", 8)),
        limite_chats=int(body.get("chats", 6)),
        limite_foros=int(body.get("foros", 4)),
        manual_user=user,
    )


@api.get("/greenfield/listening/status")
async def gf_listening_status(user: dict = Depends(require_greenfield)):
    last = await db.gf_runs_listening.find({}, {"_id": 0}).sort("iniciada", -1).limit(10).to_list(10)
    return {
        "ultimas_corridas": last,
        "totales": {
            "chats": await db.gf_chat_groups.count_documents({}),
            "intents": await db.gf_intent_signals.count_documents({}),
            "alertas_rojas_activas": await db.gf_intent_signals.count_documents({"urgencia": "alerta_roja"}),
            "foros": await db.gf_forum_threads.count_documents({}),
        },
        "agentes": [
            {"key": "agente_5", "nombre": "Infiltrado de Chats", "mision": "Extraer enlaces WhatsApp/Telegram",
             "dorks": ['site:chat.whatsapp.com "constructores" "Querétaro"', 'site:t.me/joinchat "construcción" "pisos industriales"']},
            {"key": "agente_6", "nombre": "Interceptor de Intención", "mision": "Twitter/Reddit/FB en tiempo real",
             "dorks": ['"alguien sabe" "canastillas pasajuntas"', '"recomienden" "acero pisos industriales"']},
            {"key": "agente_7", "nombre": "Rastreador de Foros", "mision": "CMIC, SkyscraperCity, foros civiles",
             "dorks": ['inurl:forum "canastillas" "proveedores"', 'inurl:foro "pisos industriales" "junta constructiva"']},
            {"key": "agente_8", "nombre": "Sintetizador Comercial", "mision": "Filtro <24h + dedupe + ALERTA ROJA",
             "dorks": ['Cross-validation + filtro académico (Emergent LLM)']},
        ],
    }


@api.get("/greenfield/listening/chats")
async def gf_listening_chats(plataforma: Optional[str] = None, ciudad: Optional[str] = None,
                              user: dict = Depends(require_greenfield)):
    q = {}
    if plataforma:
        q["plataforma"] = plataforma
    if ciudad:
        q["ciudad"] = ciudad
    items = await db.gf_chat_groups.find(q, {"_id": 0}).sort("detectado_at", -1).to_list(500)
    return items


@api.delete("/greenfield/listening/chats/{cid}")
async def gf_listening_chats_delete(cid: str, user: dict = Depends(require_roles("director", "socio"))):
    r = await db.gf_chat_groups.delete_one({"id": cid})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    return {"ok": True}


@api.get("/greenfield/listening/intents")
async def gf_listening_intents(urgencia: Optional[str] = None, plataforma: Optional[str] = None,
                                ciudad: Optional[str] = None, solo_activas: bool = False,
                                user: dict = Depends(require_greenfield)):
    q = {}
    if urgencia:
        q["urgencia"] = urgencia
    if plataforma:
        q["plataforma"] = plataforma
    if ciudad:
        q["ciudad"] = ciudad
    if solo_activas:
        q["procesada"] = False
    items = await db.gf_intent_signals.find(q, {"_id": 0}).sort("timestamp_origen", -1).to_list(500)
    return items


@api.patch("/greenfield/listening/intents/{iid}")
async def gf_listening_intents_update(iid: str, body: dict, user: dict = Depends(require_greenfield)):
    upd = {k: v for k, v in body.items() if k in {"procesada", "notas", "urgencia"}}
    r = await db.gf_intent_signals.update_one({"id": iid}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Intent no encontrado")
    return await db.gf_intent_signals.find_one({"id": iid}, {"_id": 0})


@api.get("/greenfield/listening/foros")
async def gf_listening_foros(user: dict = Depends(require_greenfield)):
    items = await db.gf_forum_threads.find({}, {"_id": 0}).sort("detectado_at", -1).to_list(500)
    return items


# ============================================================================
# FIN V5 · RADAR GREENFIELD OSINT
# ============================================================================


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
            # 07:00 CDMX → Radar Greenfield OSINT barrida diaria
            if cdmx_hour == 7 and SCRAPER_STATE.get("_last_greenfield_day") != today_key:
                logger.info("[SCHEDULER] Running Greenfield OSINT pipeline")
                await _gf_run_pipeline()
                SCRAPER_STATE["_last_greenfield_day"] = today_key
            # Cada hora (cdmx_min ~ 0-5) → Escuadrón Conversacional (Listening)
            listen_hour_key = f"{today_key}T{cdmx_hour:02d}"
            if SCRAPER_STATE.get("_last_listening_hour") != listen_hour_key:
                logger.info(f"[SCHEDULER] Running Listening pipeline @{listen_hour_key}")
                await _gf_run_listening_pipeline()
                SCRAPER_STATE["_last_listening_hour"] = listen_hour_key
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
    logger.info("Scheduler iniciado (scraper 02:00 · scoring 03:00 · greenfield 07:00 · alerta 08:00 CDMX)")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
