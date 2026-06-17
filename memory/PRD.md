# DEYMA RADAR — PRD

## Original Problem Statement
CRM y sistema operativo profesional para proyectos de construcción industrial en México (DEYMA RADAR). Usuario habla **español únicamente**.

Stack:
- Backend: FastAPI + Motor/MongoDB
- Frontend: React + Tailwind + shadcn/ui
- AI: Emergent LLM Key (GPT-5.2) para scoring, briefings y limpieza de datos
- OSINT: Apify API en modo LIVE (token configurado)

## Módulos completados (CHANGELOG resumido)

### V1-V4 (sesiones previas)
- Auth JWT staff + DFNUM cliente
- CRM Kanban (oportunidades, empresas, actividades)
- Cotizador PDF dual-brand (DEYMA / RT) con cliente custom + unidades libres
- Ruta de Ventas IA con autocomplete origen/destino (Nominatim/Photon)
- Portal cliente con OC + cotizaciones por RFC
- Onboarding cliente con doble firma (Director + Socio)
- RH / Personal contratado (vacaciones LFT 2023 + expediente PDF)
- Gastos de Viajero
- Scraper nocturno (02:00 CDMX) + scoring (03:00) + digest matutino (08:00)

### V5 — Radar Greenfield OSINT (sesión previa)
- 4 agentes 24/7 (cron 07:00 CDMX): SEMARNAT MIA, LinkedIn intent, parques industriales, permisos municipales
- Apify LIVE para SERP real (gob.mx, edu.mx, org.mx)
- Embudo Greenfield 6 etapas
- Triangulación de contactos OSINT (LinkedIn → email/tel)
- Escuadrón Conversacional (Agentes 5-8 · hourly): WhatsApp groups, Telegram, Twitter, Reddit
- Alertas Rojas con CTA Responder (sub-24h)
- Tareas Alberto + Tickets Maurizio

### V5.2 — Operación Francotirador DRO (ESTA SESIÓN · Feb 2026)
- 2 nuevos agentes OSINT (cron 06:00 CDMX):
  - **Agente DRO-1 (Infiltrado Gubernamental)**: dorks Apify SERP sobre `gob.mx` y `edu.mx` para padrones municipales de Directores Responsables de Obra
  - **Agente DRO-2 (Rastreador Colegiado)**: dorks sobre `org.mx`/`edu.mx` para directorios de Colegios de Ingenieros y Arquitectos
- Colección `db.padron_dro` con 6 etapas de embudo: `blanco_detectado → kit_cad_enviado → interaccion_tecnica → prescriptor_activo → cierre_obra_ganada / descartado`
- Auto-asignación a **Alberto** (comercial) + plantilla pre-llenada de WhatsApp/Email
- Auto-creación de tareas para DROs con contacto válido
- Frontend nuevo: `/admin/francotirador-dro` con tabs Padrón (tabla + filtros + plantilla 1-clic) y Embudo (Kanban 6 columnas)
- Botón "Ejecutar Operación Francotirador" para barrida manual on-demand
- Plantilla editable + botones nativos WhatsApp (wa.me), Email (mailto:) y Copiar

### Carry-over verificado
- ✅ Marcar Visita en Ruta de Ventas IA inserta actividad automática en CRM (oportunidad creada si no existe)

## Endpoints clave V5.2
| Método | Endpoint | Notas |
|--------|----------|-------|
| POST | `/api/francotirador/run` | Ejecuta barrida manual (director/socio/comercial) |
| GET  | `/api/francotirador/padron` | Lista DROs con filtros estado_mx/stage/municipio |
| GET  | `/api/francotirador/embudo` | Kanban 6 etapas con conteos |
| POST | `/api/francotirador/{id}/move` | Cambia etapa + historia |
| PATCH| `/api/francotirador/{id}` | Edición campos whitelisted |
| DELETE| `/api/francotirador/{id}` | Solo director/socio |

## Modelos DB nuevos
```
padron_dro: {id, nombre, numero_registro, especialidad, municipio, estado_mx,
             telefono_movil, telefono_oficina, correo_electronico,
             url_documento_fuente, colegio_agremiado, notas,
             stage, probabilidad, asignado_a, asignado_nombre,
             plantilla_mensaje, fuente_agente, fecha_deteccion,
             historia[], created_at, updated_at}

dro_runs: {run_id, iniciada, finalizada, ejecutada_por, target_estados,
           gov_detectados, colegios_detectados, unicos_insertados,
           tareas_creadas_alberto, modo, ok}
```

## Tests
- `/app/test_reports/iteration_9.json` — V5.2 + carry-over: **backend 22/22 PASS, frontend Playwright 100%**
- 0 bugs críticos · 0 regresiones detectadas

## ROADMAP (backlog priorizado)

### P1 (próximas)
- Refactor crítico: dividir `server.py` (6,432 líneas) en `routes/auth.py`, `routes/crm.py`, `routes/osint.py`, `routes/francotirador.py`, `routes/clientes.py`. Bloquea velocidad de desarrollo futuro.
- Pydantic BaseModels para DROMoveIn / DROPatchIn (mejora OpenAPI docs)
- LLM PDF parser para DROs detectados en gob.mx (hoy quedan como placeholder "DRO en padrón — {título PDF}")
- Cargas de Órdenes de Compra natively en portal cliente (P1 previa)

### P2 (V3 roadmap)
- Integración REAL Twilio (WhatsApp transaccional) — hoy mockeada
- Integración REAL SendGrid (transaccionales) — hoy mockeada
- Mobile PWA
- Sales Prediction con histórico
- Apollo enrichment de pago (hoy bypass con Apify; 403 en free plan)
- Split AdminFrancotiradorDROPage.jsx (593 líneas) → componentes PlantillaModal / EditDROModal

### P3 (V4 roadmap)
- Multi-tenant SaaS architecture (revender a otras constructoras del Bajío)

## Integraciones 3rd party
- ✅ Emergent LLM Key (GPT-5.2) — text generation
- ✅ Apify (`APIFY_TOKEN`) — LIVE web scraping
- ✅ Nominatim / Photon Komoot — geocoding gratuito
- ⚠️ Apollo — configurado pero 403 (free plan, bypass funcional vía Apify)
- 🔶 Twilio — MOCKEADO
- 🔶 SendGrid — MOCKEADO

## Notas operativas
- App está deployada a producción. Cambios aplican primero al PREVIEW. Usuario debe pulsar "Deploy" en la UI para promover a prod.
- `OSINT_MODE=live` en `/app/backend/.env`. **NO sobrescribir** esa variable ni `APIFY_TOKEN`.
- Schedulers diarios (CDMX): scraper 02:00 · scoring 03:00 · DRO 06:00 · Greenfield 07:00 · digest 08:00 · Listening cada hora.
