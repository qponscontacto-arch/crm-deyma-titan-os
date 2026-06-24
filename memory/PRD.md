# DEYMA RADAR — Product Requirements (PRD)

> CRM y sistema operativo para DEYMA Desarrollo y Mantenimiento (industria pesada en México, especialidad: canastillas industriales).

## Idioma de producto
Español MX. Toda la UI y notificaciones deben ser en español.

## Stack
- **Frontend:** React 19 + Tailwind + Shadcn (`/app/frontend/`)
- **Backend:** FastAPI + Motor (`/app/backend/server.py`)
- **DB:** MongoDB (env `MONGO_URL`, `DB_NAME`)
- **LLM:** GPT-5.2 vía Emergent LLM Key (`emergentintegrations`)
- **OSINT:** Apify (Google Search, Twitter, Facebook scrapers)
- **Notif:** Twilio WhatsApp (Sandbox 5 msg/día) + SendGrid Email

## Roles
- `director`, `socio`, `comercial`, `operaciones`
- Cliente externo (portal separado)

---

## Módulos implementados

### Core CRM
- Login JWT, Kanban CRM, Alta de Clientes, Cotizador dual-brand PDF, Mapa México
- Dashboard de KPIs, Mis Tareas, Alertas HOT, Obras
- RH · Personal, Ruta de Ventas IA, Gastos de Viajero
- Portal de Cliente (`/cliente`) con tracking de trámite

### Inteligencia & OSINT
- **Radar de Proyectos** — feed manual de oportunidades
- **Radar Greenfield OSINT** — scraping nocturno de obras nuevas
- **Francotirador DRO** — barrida diaria de DROs en CDMX 06:00
- **Scraper Nocturno** — pipeline 02:00 + scoring 03:00
- **Detecciones IA** (Webhook `/api/v1/ia-leads`) — recibe leads externos (opp-detector) con `X-API-KEY`, dedupe automático, invitación WhatsApp al grupo
- **📡 Radar de Condominios (V6.0 — IMPLEMENTADO 2026-02)** — 3 agentes IA:
  - 🐶 **El Sabueso** — Apify Google Search → administradores de condominios
  - ⚡ **El Analista** — Apify Twitter → quejas CFE/CEA → GPT-5.2 clasifica
  - 🕵️ **El Infiltrado** — Google Dorks → grupos WhatsApp/Telegram públicos
  - 5 páginas: Caza-Leads · Alertas Dolor · Mega-Condominios · Redes Vecinales · Config
  - Cron 04:00 CDMX + manual trigger por agente o pipeline completo
  - GPT-5.2 estima si >=200 casas (Mega)

### Gestión & Comunicación
- **Centralizado** (Cierre del día) — PDF generado
- **Plan Cierre $1.2M** — dashboard táctico de ventas
- **Notificaciones Push** — multi-destinatario Twilio + SendGrid LIVE
- **Accesos · Usuarios** — gestión de credenciales (solo director)
- **CommsPanel flotante** — comunicaciones internas

---

## Cron Schedule (CDMX = UTC-6)
| Hora | Tarea |
|---|---|
| 02:00 | Scraper nocturno |
| 03:00 | Scoring batch |
| **04:00** | **🆕 Radar de Condominios (3 agentes)** |
| 06:00 | Francotirador DRO |
| 07:00 | Greenfield OSINT |
| 08:00 | Morning digest |
| Cada hora | Listening pipeline |

---

## Endpoints clave nuevos (V6.0)
- `GET/PATCH /api/condo/config`
- `POST /api/condo/run` (pipeline completa)
- `POST /api/condo/run/{sabueso|analista|infiltrado}`
- `GET /api/condo/leads` (filtros: `estado`, `urgencia`, `mega=1`)
- `PATCH /api/condo/leads/{id}` (autoflag es_mega si casas>=200)
- `POST /api/condo/leads/{id}/promover-crm`
- `GET /api/condo/alertas` · `GET /api/condo/grupos`
- `GET /api/condo/stats`

---

## Backlog (Roadmap)

### P0 — Próximas
- Validar webhook `/api/v1/ia-leads` con primer lead real del agente externo opp-detector
- Que clientes suban Órdenes de Compra desde portal (P1 anterior)
- Refinar Apify queries del módulo Condominios (los actuales devuelven 0 — afinar dorks/actor IDs)

### P1
- Seed inicial: insertar 5-10 mega-condominios conocidos de Querétaro como base de comparación
- Vincular alertas de dolor a leads de admins (cruce automático por fraccionamiento)
- PWA / App móvil

### P2
- Sales Prediction con histórico
- Refactor `server.py` (>8,200 líneas) → routers modulares en `/app/backend/routers/`
- Multi-tenant SaaS para vender a otras constructoras

### P3
- Mover de Twilio Sandbox a tier pagado (eliminar límite 5 msg/día)
- Apollo upgrade para enrichment real (actualmente 403 free plan)

---

## Producción
- URL: `opp-detector.emergent.host`
- Variables de entorno: 10 configuradas en Emergent Secrets (Twilio, SendGrid, Apify, JWT, etc.)
- OSINT_MODE = `live`
- Conocido: cache de Chrome puede mostrar pantalla negra tras redeploy — solución: hard refresh (Ctrl+Shift+R) o incógnito.
