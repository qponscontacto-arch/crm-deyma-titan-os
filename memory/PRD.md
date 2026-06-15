# PRD · DEYMA RADAR

> **Sistema de Inteligencia Comercial para Construcción Industrial**
> Versión 1.0 · Enero 2026
> Empresa: DEYMA Construcciones S.A. de C.V.
> Mercado objetivo: Querétaro · Bajío · Sector Industrial Mexicano

---

## 1. Problema original (verbatim)

> "El siguiente paso recomendable no es seguir agregando funciones, sino convertir DEYMA RADAR en un proyecto listo para desarrollo profesional con especificaciones completas." (PRD + MVP funcional con CRM + Radar + Cotizador + Mapa + IA + autenticación con roles, datos del sector industrial Bajío Querétaro).

Elecciones del usuario en esta iteración:
- **Alcance**: PRD + MVP funcional (opción c).
- **Módulos P0**: Login + Dashboard + CRM + Cotizador + Radar + **Mapa de Oportunidades**.
- **Autenticación**: JWT custom con roles (Director, Comercial, Operaciones).
- **IA**: Emergent LLM Key universal (GPT-5.2).
- **Datos semilla**: Sí, sector industrial Bajío.

---

## 2. Visión del proyecto

DEYMA RADAR convierte la prospección comercial reactiva ("dependemos de recomendaciones") en una **máquina de inteligencia de mercado** especializada en pisos industriales, concreto hidráulico, pavimentación, mantenimiento industrial y canastillas para el Bajío y México central.

**Norte estratégico**: capturar al menos un proyecto de $500K-$1M MXN al mes mediante detección temprana de oportunidades en parques industriales, CEDIS, manufactura nearshoring, data centers y expansiones de planta.

**Diferenciadores**:
- Foco en nicho industrial pesado (no SaaS genérico).
- Scoring IA contextual al sector y región Bajío.
- Cotizador adaptado a m² y partidas técnicas reales del giro.
- Mapa geográfico con corredores industriales (Querétaro–Silao–Aguascalientes–SLP–Monterrey).

---

## 3. Modelo de negocio

| Fase | Modelo | Ingresos esperados |
|------|--------|-------------------|
| V1 (uso interno DEYMA) | Productividad interna | +1 proyecto/mes = $6-24M MXN/año adicionales |
| V4 (SaaS) | $4,500-12,000 MXN/mes por constructora | 50 constructoras × $7K MXN ≈ $4.2M MXN ARR |

---

## 4. Personas y casos de uso

### Director General
- "Cada lunes 8am quiero ver el pipeline, forecast y top 10 oportunidades hot sin pedirle nada a nadie."
- "Quiero saber si llegamos al cierre del trimestre y qué proyectos lo definen."

### Comercial (Ana López)
- "Necesito mover oportunidades por etapas y pedirle al sistema que me redacte el correo de seguimiento."
- "Quiero filtrar el Radar por sector 'data centers' y ver solo los HOT de Querétaro."

### Operaciones (Carlos Ruiz)
- "Mi tablero es la lista de obras en ejecución con avance %."
- "Necesito saber qué cotizaciones aceptadas se convierten en obra."

---

## 5. Arquitectura técnica

```
┌─────────────────────────┐      ┌──────────────────────────┐
│  Frontend React 19      │ HTTP │  FastAPI (Python 3.11)   │
│  Tailwind · Lucide      │◀────▶│  Motor (MongoDB async)   │
│  Recharts (futuro)      │      │  PyJWT · bcrypt          │
│  SVG Map · localStorage │      │  emergentintegrations    │
└─────────────────────────┘      └─────────────┬────────────┘
                                                │
                                  ┌─────────────▼────────────┐
                                  │   MongoDB · deyma_radar  │
                                  │   users · empresas · …   │
                                  └──────────────────────────┘
                                                │
                                  ┌─────────────▼────────────┐
                                  │  Emergent LLM (GPT-5.2)  │
                                  │  scoring · summaries     │
                                  │  follow-up · forecast    │
                                  └──────────────────────────┘
```

**Stack**:
- Backend: FastAPI 0.110, Motor 3.3, PyJWT, bcrypt, emergentintegrations 0.2
- Frontend: React 19, React Router 7, Tailwind 3.4, Lucide-react, Axios
- Storage: MongoDB (idempotent seed en startup)
- IA: OpenAI GPT-5.2 vía `emergentintegrations` (universal key)
- Hosting: Kubernetes (Emergent preview · supervisor managed)

---

## 6. Arquitectura de datos

### Colecciones MongoDB (estructura tipo PostgreSQL/Supabase compatible)

```
users
├─ id (uuid)            password_hash (bcrypt)
├─ email (unique)       role: director|comercial|operaciones
├─ name                 created_at (ISO)

empresas
├─ id, nombre, rfc, sector, ciudad, estado, lat, lng
├─ sitio_web, notas, created_at

contactos
├─ id, empresa_id (FK→empresas), nombre, puesto, email, telefono

oportunidades
├─ id, empresa_id (FK), titulo, sector, descripcion
├─ monto_estimado, stage (prospección→ganada), probabilidad
├─ score (0-100), hotness, score_reasons[], owner_id (FK→users)
├─ fecha_cierre, created_at, updated_at

proyectos_radar (radar)
├─ id, titulo, fuente, sector, ciudad, estado, monto_estimado
├─ descripcion, url_fuente, lat, lng, score, hotness, score_reasons[]

cotizaciones
├─ id, folio (DEY-YYYY-####), empresa_id (FK), proyecto_titulo
├─ items[]: {descripcion, cantidad, unidad, precio_unitario}
├─ subtotal, iva_pct, iva_monto, total, estado, validez_dias
├─ owner_id (FK→users), notas, created_at

obras
├─ id, empresa_id (FK), cotizacion_id (FK opcional), nombre
├─ monto_contratado, fecha_inicio, fecha_fin_estimada
├─ estado (planeación|ejecución|pausada|completada), avance_pct
├─ ciudad, estado_geo

actividades (futuro V2)
├─ id, oportunidad_id, tipo, fecha, descripcion, owner_id

documentos (futuro V2)
├─ id, entidad_tipo, entidad_id, url, tipo, uploaded_by
```

### Relaciones

```
users ──1:N── oportunidades (owner_id)
empresas ──1:N── contactos
empresas ──1:N── oportunidades
empresas ──1:N── obras
empresas ──1:N── cotizaciones
cotizaciones ──1:1── obras (cuando aceptada→en ejecución)
```

---

## 7. Módulos del MVP (V1)

| Módulo | Endpoint principal | Estado |
|--------|--------------------|--------|
| Login | `POST /api/auth/login` | ✅ |
| Dashboard | `GET /api/dashboard/kpis` | ✅ |
| CRM Empresas | `GET/POST /api/empresas` | ✅ |
| CRM Contactos | `GET/POST /api/contactos` | ✅ |
| CRM Pipeline | `GET/POST/PATCH /api/oportunidades` | ✅ |
| Radar | `GET/POST /api/radar` | ✅ |
| Cotizador | `GET/POST /api/cotizaciones` | ✅ |
| Mapa Bajío | `GET /api/mapa/puntos` | ✅ |
| Obras | `GET/POST /api/obras` | ✅ |
| IA: Scoring | `POST /api/oportunidades/{id}/score` · `POST /api/radar/{id}/score` | ✅ |
| IA: Resumen ejecutivo | `GET /api/dashboard/executive-summary` | ✅ |
| IA: Correo seguimiento | `POST /api/oportunidades/{id}/followup-email` | ✅ |
| IA: Pronóstico | `GET /api/dashboard/forecast` | ✅ |

---

## 8. UX/UI · Sistema de diseño

- **Archetype**: Industrial Dark · Bloomberg Terminal × Construction Blueprint.
- **Tipografía**: Chivo (titulares) · IBM Plex Sans (body) · IBM Plex Mono (datos numéricos).
- **Paleta**: `#09090b` background · `#18181b` surface · `#f59e0b` ámbar industrial · `#38bdf8` blueprint blue · `#f97316` hot lead.
- **Patrones**: 1px borders en lugar de sombras · esquinas afiladas (radius 2px) · grids densos tipo "control room" · animaciones <150ms.
- **Sin emojis** · iconos Lucide (stroke 1.5).
- **Imágenes**: construcción aérea, blueprints, planos topográficos (Pexels/Unsplash).

Wireframes implementados en código (no Figma) en:
- `/app/frontend/src/pages/LoginPage.jsx` · split 60/40 con hero industrial
- `/app/frontend/src/pages/DashboardPage.jsx` · grid KPI 4×2 + pipeline bars + AI panels
- `/app/frontend/src/pages/CRMPage.jsx` · kanban horizontal 6 etapas
- `/app/frontend/src/pages/RadarPage.jsx` · grid 3 col con thumbnails y score
- `/app/frontend/src/pages/CotizadorPage.jsx` · tabla principal + modal multi-item con cálculo en vivo
- `/app/frontend/src/pages/MapaPage.jsx` · SVG custom con proyección lat/lng del Bajío
- `/app/frontend/src/pages/ObrasPage.jsx` · cards de obras con barra de avance

---

## 9. Seguridad y permisos

- **Auth**: JWT HS256, expiración 12h, secret 64-char hex en `.env`.
- **Passwords**: bcrypt con salt aleatorio.
- **Cookies**: actualmente Bearer token en localStorage (V1). V2: httpOnly cookies para mayor seguridad.
- **Roles**:
  - `director`: acceso total + eliminar.
  - `comercial`: CRUD CRM, cotizador, radar.
  - `operaciones`: CRUD obras + lectura general.
- **Guard FastAPI**: `Depends(get_current_user)` en todos los endpoints menos `/api/auth/*` y `/api/health`.
- **CORS**: configurable vía `CORS_ORIGINS`.
- **Próximos pasos**: rate-limiting, brute-force protection (5 intentos/15 min), refresh tokens, password reset.

---

## 10. Roadmap 12 meses

### V1 — Día 1-30 (✅ ENTREGADO HOY)
- CRM completo (empresas, contactos, oportunidades, kanban)
- Radar de proyectos con scoring IA
- Cotizador funcional (m², IVA, folios DEY-YYYY-####)
- Mapa SVG del Bajío
- Dashboard Director con KPIs + IA resumen + forecast
- Auth JWT con 3 roles
- 10 empresas, 12 oportunidades, 12 proyectos radar, 3 cotizaciones, 4 obras seed

### V2 — Día 31-60
- Integración WhatsApp Business API (alertas de proyectos HOT)
- Generación automática de cotización PDF (jsPDF/WeasyPrint)
- Notificaciones por correo (SendGrid/Resend) al detectar proyectos
- Power BI / exportación CSV de pipeline
- Tareas y actividades por oportunidad
- Adjuntar documentos (S3/Cloudinary)

### V3 — Día 61-90
- App móvil (React Native / PWA)
- Portal Cliente (acceso a cotizaciones y avance de obra)
- Predicción de ventas con histórico (regresión + IA)
- Scraping automatizado de licitaciones Compranet, Compras MX

### V4 — Día 91-180
- Multi-tenant SaaS para vender a otras constructoras
- Onboarding self-service
- Billing Stripe (planes Mensual / Anual)
- Sistema de roles avanzado por organización

---

## 11. Costos de infraestructura estimados

| Componente | Mensual |
|-----------|---------|
| Hosting Emergent (preview/prod) | Incluido |
| MongoDB Atlas M10 (V2+) | $57 USD |
| Emergent LLM Key (~1000 ops/mes) | $20-40 USD |
| WhatsApp Business API (V2) | $50 USD |
| Dominio + SSL | $1 USD |
| **Total V1** | **<$50 USD/mes** |
| **Total V4 SaaS escalado** | **$300-500 USD/mes** |

---

## 12. Próximos pasos sugeridos

1. **Validación interna DEYMA**: que Director, Comercial y Operaciones usen el sistema 2 semanas y registren feedback.
2. **Conectar fuentes reales** al Radar (scraping Compranet + noticias industriales).
3. **PDF de cotización** con membrete DEYMA y firma digital del director.
4. **WhatsApp HOT alerts**: notificación inmediata cuando aparezca un proyecto con score ≥85.
5. **Convertir oportunidad ganada → obra** con un solo click.

---

## 13. Estado actual de implementación (12-Jun-2026 · V2 P1)

### V1 entregada (1ª iteración)
- ✅ Backend FastAPI 100% funcional con 24+ endpoints
- ✅ Frontend React con 7 páginas navegables + auth flow completo
- ✅ Diseño industrial dark según guidelines (Chivo + IBM Plex)
- ✅ Seed data realista del sector industrial Bajío
- ✅ IA GPT-5.2 integrada (scoring, resumen, correos, forecast) — probado funcional
- ✅ Mapa SVG custom del corredor Bajío con 22+ puntos georreferenciados
- ✅ test_credentials.md con 3 roles pre-cargados
- ✅ Testing: 22/22 backend (100%), 95% frontend

### V2 P1 entregada (2ª iteración · HOY)
- ✅ **PDF Cotización profesional** con membrete DEYMA generado server-side con ReportLab (logo, datos cliente, tabla de conceptos, totales, condiciones comerciales, firmas). Endpoint `GET /api/cotizaciones/{id}/pdf` + descarga con un click en la tabla y dentro del preview.
- ✅ **WhatsApp Alertas HOT** vía Twilio con **fallback MOCK** (cuando faltan keys). Auto-trigger cuando score IA ≥ 85. Página `/alertas` con banner de estado, stats, log de alertas y botón de prueba (solo director).
- ✅ **Convertir oportunidad ganada → obra** en un click desde el OpDetailModal. Hereda monto, empresa, ciudad; pre-llena fechas (hoy + 120 días). Crea actividad-nota automática. Bloquea duplicados.
- ✅ **Importar proyecto del Radar al CRM** con modal de selección de empresa. Hereda titulo/sector/descripcion/monto/score/hotness/reasons. Crea oportunidad en etapa Prospección con probabilidad 25%.
- ✅ **Sistema de Actividades** por oportunidad: tipos (llamada, correo, reunión, visita, nota, tarea) + fecha datetime-local + descripción + completada toggle + delete. Timeline en OpDetailModal.
- ✅ **Página "Mis Tareas"** muestra pendientes del usuario actual con filtros (Pendientes / Todas), badge VENCIDA para fechas pasadas, links a oportunidad.
- ✅ **Documentos por entidad** (MOCK metadata-only) en OpDetailModal: nombre, tipo (PDF/DWG/XLSX/JPG/PNG/DOC), tamaño, autor. Listo para integrar Cloudinary/S3 cuando se quiera.
- ✅ ESC key cierra modales (mejora UX)
- ✅ Testing: 15/15 backend V2 (100%), 100% frontend V2 nuevas features

**Activación Twilio real** (cuando estés listo):
1. Crear cuenta en https://www.twilio.com
2. Activar WhatsApp Sandbox o número aprobado
3. Llenar en `/app/backend/.env`:
   - `TWILIO_ACCOUNT_SID=AC...`
   - `TWILIO_AUTH_TOKEN=...`
   - `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` (o tu número)
   - `DEYMA_ALERT_PHONE=whatsapp:+521442XXXXXXX`
4. `sudo supervisorctl restart backend` y listo — las alertas se envían reales sin tocar código.

### V3.5 entregada (4ª iteración · HOY)
- ✅ **Panel de Seguimiento a Cotizaciones** completo: el preview modal del cotizador se convirtió en un panel con 4 pestañas (Resumen / Correos / Respuestas / Historia) y herramientas de acción contextual.
- ✅ **Flujo de estados extendido**: `borrador → aprobada_direccion (Director o Comercial aprueba + envía correo) → aceptada / rechazada`. Una vez en estado final se bloquea re-aprobación.
- ✅ **Envío de correo vía SendGrid** con **fallback MOCK transparente** (sin keys = se guarda el correo en `outbound_emails` con `status=queued_mock, mock=true`). Cuando llenes `SENDGRID_API_KEY` y `SENDGRID_FROM_EMAIL` en `.env` pasa a envío real automáticamente.
- ✅ **PDF de cotización adjuntado automáticamente** al correo enviado.
- ✅ **Plantilla HTML pre-rellenada y editable** antes de enviar (asunto, body HTML, body texto, CC opcional). Incluye membrete DEYMA, tabla de partidas, totales y firma del usuario que envía.
- ✅ **Registro manual de respuestas del cliente** con: remitente nombre/email opcional, asunto, contenido (pegar tal cual), fecha, **sentimiento** (positivo/neutro/negativo).
- ✅ **Marcar aceptada/rechazada** con nota de cierre obligatoria para historial auditable.
- ✅ **Historia completa de eventos**: aprobación+envío, respuestas, cambios de estado — con actor, rol y timestamp.
- ✅ **Role guards**: director y comercial pueden aprobar/enviar/registrar respuestas/marcar. Operaciones obtiene 403.
- ✅ **Bug fix HIGH**: validador `field_validator(mode='before')` en `RegistrarRespuestaIn.de_email` que coerce empty string → None + frontend strip antes de POST. Acepta respuestas de clientes sin email.

### Testing iter 4
- Backend: **10/10 V3.5** (100%) + 49/50 regresión completa (solo 1 502 transitorio en `/api/scraper/score-batch` por timeout de ingress en batch largos)
- Frontend: 85% inicialmente → **100% tras fix** del 422 con `de_email` vacío

### V3 P1 entregada (3ª iteración previa)
- ✅ **Mapa de toda la República Mexicana**: BBOX expandido de Bajío a 14.4°-32.8°N · -118.5° a -86.5°W. 30 ciudades industriales (Tijuana, Hermosillo, Cd. Juárez, Monterrey, Saltillo, Reynosa, Bajío completo, Guadalajara, CDMX, Puebla, Mérida, Cancún, Villahermosa, etc.). 3 sub-polígonos schemáticos: México continental + Baja California Sur + Yucatán + línea de frontera USA.
- ✅ **+16 empresas seed** distribuidas por toda la República: Tesla Gigafactory NL, Kia Pesquería, Volkswagen Puebla, Audi San José Chiapa, Ford Hermosillo, Cemex Mérida, Pemex Dos Bocas (Tabasco), Honda Jalisco, Tijuana Industrial Park, Hofusan, Toyota Apaseo, Mabe Saltillo, Bachoco Mérida, Equinix MX1, etc.
- ✅ **+13 proyectos radar seed** en estados nuevos: Coahuila, Nuevo León, Puebla, Tabasco, Baja California, Sonora, Yucatán, Jalisco.
- ✅ **Scraper IA nocturno** (`POST /api/scraper/run`, solo director): GPT-5.2 genera 5-8 oportunidades sintéticas-realistas basadas en tendencias de Compranet/Tenders MX/noticias industriales, dedupea por título y agrega al radar con `_source='ai_scraper'`.
- ✅ **Batch scoring nocturno** (`POST /api/scraper/score-batch`, solo director): califica todos los items con score=0, dispara auto-alerta para los HOT (≥85).
- ✅ **Resumen matutino WhatsApp** (`POST /api/scraper/morning-alert`, solo director): top 5 oportunidades detectadas en las últimas 36h, alerta tipo `morning_digest` con cuerpo "DEYMA RADAR · BUENOS DÍAS" formateado.
- ✅ **Scheduler asyncio background**: dispara scraper a 02:00, scoring a 03:00, alerta matutina a 08:00 hora CDMX (UTC-6). Anti-replay diario.
- ✅ **Frontend `/scraper`**: 3 action cards (Ejecutar / Calificar / Enviar) + 4 stats cards (Total radar / Detectados IA / Twilio status / Errores) + panel del último resumen matutino con top 5 + log de ejecuciones.
- ✅ Testing iter 3: 14/14 backend V3 (100%) + 100% frontend crítico. Bug NaN del mapa **resuelto**.

## 16. V4.5 RH · Personal Contratado (15-Feb-2026)
### Implementado y probado (iteration_6.json · 28/28 backend + 8/8 frontend)
- ✅ Nuevo módulo `/admin/rh` accesible SOLO para director y socio (RBAC backend + frontend con item de sidebar condicional). Comercial/operaciones reciben 403 / pantalla `rh-denied`.
- ✅ CRUD de empleados con campos: nombre, RFC, CURP, NSS, puesto, departamento (6 opciones fijas), fecha_ingreso, salario_diario+mensual+integrado, contacto emergencia, etc. Listado con filtros (status, depto, búsqueda libre).
- ✅ **Cálculo de prestaciones LFT 2023** (`_calcular_prestaciones`): tabla oficial de vacaciones por antigüedad (12/14/16/18/20 → 22 → 24 → 26 → 28 → 30 → 32), aguinaldo, prima vacacional, próximo aniversario.
- ✅ **6 categorías de documentos** subidos a GridFS: general, contrato, renuncia, amonestación, certificado médico, DC-3 STPS (con tema/instructor/vigencia). Bucket compartido `cliente_files`.
- ✅ **Registro de vacaciones tomadas** (programadas/gozadas/canceladas) con balance gozadas/pendientes calculado dinámico.
- ✅ **Expediente PDF descargable** (ReportLab) con 2 páginas: datos personales+laborales+prestaciones (página 1) y tabla de documentos + historial de vacaciones (página 2). Marca DEYMA + folio EXP-XXXX + footer "CONFIDENCIAL".
- ✅ Endpoint `/api/rh/alertas` para próximos aniversarios y documentos con vigencia próxima (preparado para integrar al dashboard en futuro).
- ✅ Tests: `/app/backend/tests/test_v45_rh.py` (28 casos parametrizados LFT).

### Endpoints nuevos
- `POST/GET /api/rh/empleados`, `GET/PATCH/DELETE /api/rh/empleados/{eid}`
- `POST/GET-via-detalle /api/rh/empleados/{eid}/documentos` · `GET/DELETE /api/rh/empleados/{eid}/documentos/{doc_id}`
- `POST/DELETE /api/rh/empleados/{eid}/vacaciones[/{vid}]`
- `GET /api/rh/empleados/{eid}/expediente` (PDF)
- `GET /api/rh/alertas`

### Edge cases conocidos (no bloqueantes — backlog V4.5 P2)
- Bisiesto: empleado con fecha_ingreso 29-feb siempre cae al 28-feb del año siguiente (corregible).
- 30 años exactos devuelve 30 días (la LFT dice 30+, podría ser 32).
- PATCH `/api/rh/empleados/{eid}` devuelve `{ok:true}` en lugar del doc actualizado (UX minor).


### Pendiente backlog (Next Action Items)
- **V4 P1 entregado HOY** ✅ Portal de Alta de Clientes completo (ver sección 15)
- **V3 P2**: Scraper REAL de Compranet (cuando el sitio esté accesible desde el container o pasando por proxy). Hoy es 100% sintético vía GPT-5.2.
- **V3 P2**: Refactor `server.py` (ahora 2,651 líneas) → routers/services modules — URGENTE antes de V5
- **V3 P2**: Exponer `_source` en `/api/radar` para que el frontend pueda filtrar items auto-scraped vs manuales
- **V3 P2**: Activar Twilio real (llenar las 4 env vars TWILIO_*)
- **V2 P2 pendiente**: Recordatorios por correo de tareas vencidas (SendGrid/Resend); Storage real de documentos (Cloudinary/S3); Logo SVG real DEYMA en PDF
- **V3**: App móvil PWA, Predicción ventas con histórico
- **V4 P2**: Endpoint cambio de password cliente; protección por token de los PDFs públicos por id; validación monto OC >= 0; unicidad DFNUM con retry; separar `aprobaciones` y `rechazos` para auditoría limpia
- **V5**: Multi-tenant SaaS con Stripe billing

## 15. Estado actual de implementación (15-Feb-2026 · V4 P1 — Portal de Alta de Clientes)

### V4 P1 entregada (5ª iteración · HOY)
- ✅ **Backend portal de alta completo** (15 endpoints `/api/clientes/*` y `/api/clientes-oc/*`): subida multipart con 5 PDFs a GridFS, generación de folio `ALT-YYYY-NNNN`, doble aprobación Director + Socio (cualquier orden), generación de DFNUM `DFNUM-XXXXXX` al completarse las dos firmas, rechazo final con nota auditable, descarga de documentos GridFS, upload/descarga de Órdenes de Compra del cliente, consulta pública de estado por folio o DFNUM.
- ✅ **Generación de 2 PDFs con ReportLab** (`_build_alta_pdf` modo 'alta' y 'bienvenida') con membrete DEYMA, datos del cliente, contactos, políticas aceptadas y bloque distintivo de DFNUM en el de bienvenida.
- ✅ **Nuevo rol `socio`** agregado al Literal y al seed idempotente (`socio@deyma.mx / Socio2026!`).
- ✅ **Frontend público** (sin login): `/alta-cliente` (formulario multi-step de 5 pasos con upload de los 5 PDFs y validación cliente-side), `/consulta-tramite` (consulta de estado por folio o DFNUM).
- ✅ **Login dual** (`/login`) con tabs **Staff DEYMA** (email+password) y **Cliente DEYMA** (DFNUM+password). `AuthProvider` ahora maneja dos contextos (`user` vs `cliente`) y `localStorage` distingue `deyma_kind=staff|cliente`.
- ✅ **Portal cliente** (`/cliente`): 3 tabs (Inicio con datos completos, Órdenes de Compra con form de upload + tabla con descarga, Mis cotizaciones por RFC con descarga del PDF). Auto-descarga el PDF de Bienvenida al primer login (controlado por `localStorage[welcome_pdf_${DFNUM}]`).
- ✅ **Panel admin de alta** (`/admin/clientes`, visible sólo para director/socio/comercial): tabla con filtros por estado, modal de detalle con descarga de los 5 documentos, ver políticas aceptadas, ver aprobaciones registradas, botones aprobar/rechazar con nota (sólo director y socio pueden decidir; comercial sólo lee).
- ✅ **Endpoint nuevo** `GET /api/clientes/me/cotizaciones` que liga cotizaciones existentes con el RFC del cliente autenticado.
- ✅ Testing iter 5: **35/35 backend** (100%) en `/app/backend/tests/test_v4_clientes.py` + frontend Playwright 100%. Sin issues bloqueantes ni regresiones.

### Notas técnicas
- Se evitó shadowing de rutas usando prefijo `/clientes-oc` para Órdenes de Compra (en lugar de `/clientes/ordenes-compra`) para no chocar con `/clientes/{cid}`.
- Documentación de PDFs públicos por UUID identificada como riesgo de seguridad — pendiente endurecer en V4 P2.

## 14. Estado actual de implementación (12-Jun-2026 · V3 P1)
