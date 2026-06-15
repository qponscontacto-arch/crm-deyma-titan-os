import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { AuthProvider, useAuth } from "@/lib/auth";
import LoginPage from "@/pages/LoginPage";
import AppLayout from "@/pages/AppLayout";
import DashboardPage from "@/pages/DashboardPage";
import CRMPage from "@/pages/CRMPage";
import RadarPage from "@/pages/RadarPage";
import CotizadorPage from "@/pages/CotizadorPage";
import MapaPage from "@/pages/MapaPage";
import AlertasPage from "@/pages/AlertasPage";
import MisTareasPage from "@/pages/MisTareasPage";
import ScraperPage from "@/pages/ScraperPage";
import ObrasPage from "@/pages/ObrasPage";
import AltaClientePage from "@/pages/AltaClientePage";
import ConsultaTramitePage from "@/pages/ConsultaTramitePage";
import ClientePortalPage from "@/pages/ClientePortalPage";
import AdminClientesPage from "@/pages/AdminClientesPage";
import AdminRHPage from "@/pages/AdminRHPage";
import AdminRutaVentasPage from "@/pages/AdminRutaVentasPage";
import AdminGastosPage from "@/pages/AdminGastosPage";

function ProtectedStaff({ children }) {
  const { user, cliente, loading } = useAuth();
  if (loading) return <Loader />;
  if (cliente && !user) return <Navigate to="/cliente" replace />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function ProtectedCliente({ children }) {
  const { cliente, user, loading } = useAuth();
  if (loading) return <Loader />;
  if (user && !cliente) return <Navigate to="/" replace />;
  if (!cliente) return <Navigate to="/login" replace />;
  return children;
}

const Loader = () => (
  <div className="min-h-screen flex items-center justify-center bg-black text-amber-400 font-mono text-xs label-overline animate-pulse">
    Verificando sesión…
  </div>
);

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/alta-cliente" element={<AltaClientePage />} />
            <Route path="/consulta-tramite" element={<ConsultaTramitePage />} />
            <Route path="/cliente" element={<ProtectedCliente><ClientePortalPage /></ProtectedCliente>} />
            <Route path="/" element={<ProtectedStaff><AppLayout /></ProtectedStaff>}>
              <Route index element={<DashboardPage />} />
              <Route path="radar" element={<RadarPage />} />
              <Route path="crm" element={<CRMPage />} />
              <Route path="cotizador" element={<CotizadorPage />} />
              <Route path="mapa" element={<MapaPage />} />
              <Route path="obras" element={<ObrasPage />} />
              <Route path="tareas" element={<MisTareasPage />} />
              <Route path="alertas" element={<AlertasPage />} />
              <Route path="scraper" element={<ScraperPage />} />
              <Route path="admin/clientes" element={<AdminClientesPage />} />
              <Route path="admin/rh" element={<AdminRHPage />} />
              <Route path="admin/ruta-ventas" element={<AdminRutaVentasPage />} />
              <Route path="admin/gastos" element={<AdminGastosPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
