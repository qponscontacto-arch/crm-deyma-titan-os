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
import ObrasPage from "@/pages/ObrasPage";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center bg-black text-amber-400 font-mono text-xs label-overline animate-pulse">Verificando sesión…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<Protected><AppLayout /></Protected>}>
              <Route index element={<DashboardPage />} />
              <Route path="radar" element={<RadarPage />} />
              <Route path="crm" element={<CRMPage />} />
              <Route path="cotizador" element={<CotizadorPage />} />
              <Route path="mapa" element={<MapaPage />} />
              <Route path="obras" element={<ObrasPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
