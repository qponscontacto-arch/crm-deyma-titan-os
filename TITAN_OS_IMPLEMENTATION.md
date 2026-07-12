# TITÁN OS — Implementación inicial dentro de CRM DEYMA

## Acceso
Ruta interna: `/titan`

## Alcance integrado
- CEO Command Center
- Activos y QR/RFID
- Órdenes de trabajo
- IA predictiva
- Gemelo digital
- Producción y OEE
- Calidad QMS
- Seguridad industrial EHS
- Energía
- Almacén inteligente
- Compras IA
- Personal y capacitación autónoma
- Portal del cliente
- Integraciones SAP/SCADA/OPC UA/PLC/IoT
- Administración SaaS multiempresa

## Diseño
Workspace independiente con fondo blanco, navegación industrial, panel ejecutivo, indicadores, gráficas, alertas, estado de activos y experiencia responsiva.

## Archivos principales
- `frontend/src/pages/TitanOSPage.jsx`
- `frontend/src/App.js`
- `frontend/src/pages/AppLayout.jsx`
- `frontend/src/App.css`

## Próxima capa de desarrollo
La versión actual establece la experiencia y arquitectura visual funcional. La persistencia definitiva de cada módulo debe conectarse a modelos y endpoints FastAPI/MongoDB por dominio, conservando segregación multiempresa, auditoría y permisos por rol.
