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

## 13. Estado actual de implementación (12-Jun-2026)

- ✅ Backend FastAPI 100% funcional con 24+ endpoints
- ✅ Frontend React con 7 páginas navegables + auth flow completo
- ✅ Diseño industrial dark según guidelines (Chivo + IBM Plex)
- ✅ Seed data realista del sector industrial Bajío
- ✅ IA GPT-5.2 integrada (scoring, resumen, correos, forecast) — probado funcional
- ✅ Mapa SVG custom del corredor Bajío con 22+ puntos georreferenciados
- ✅ test_credentials.md con 3 roles pre-cargados

**Pendiente backlog (Next Action Items)**:
- WhatsApp/Email automation (V2)
- PDF cotización (V2)
- Importar oportunidad desde radar con un click (mejora UX)
- Sistema de actividades por oportunidad (V2)
- App móvil (V3)
