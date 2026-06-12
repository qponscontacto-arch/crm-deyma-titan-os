import axios from "axios";
import React, { createContext, useContext, useEffect, useState } from "react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("deyma_token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("deyma_token");
    if (!t) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => { localStorage.removeItem("deyma_token"); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("deyma_token", data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("deyma_token");
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);

export function formatApiError(err) {
  const d = err?.response?.data?.detail;
  if (!d) return err?.message || "Error desconocido";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(" · ");
  return String(d);
}

export const fmtMXN = (n) =>
  new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 }).format(n || 0);
export const fmtNum = (n) =>
  new Intl.NumberFormat("es-MX", { maximumFractionDigits: 0 }).format(n || 0);

export const SECTOR_LABEL = {
  nearshoring: "Nearshoring",
  parques_industriales: "Parques Industriales",
  cedis_logistica: "CEDIS / Logística",
  manufactura: "Manufactura",
  data_centers: "Data Centers",
  expansion_planta: "Expansión de Planta",
  otro: "Otro",
};

export const STAGE_LABEL = {
  prospeccion: "Prospección",
  calificada: "Calificada",
  propuesta: "Propuesta",
  negociacion: "Negociación",
  ganada: "Ganada",
  perdida: "Perdida",
};

export const STAGE_ORDER = ["prospeccion", "calificada", "propuesta", "negociacion", "ganada", "perdida"];

export const ACTIVIDAD_LABEL = {
  llamada: "Llamada",
  correo: "Correo",
  reunion: "Reunión",
  visita: "Visita",
  nota: "Nota",
  tarea: "Tarea",
};

export async function downloadPdf(url, filename) {
  const res = await api.get(url, { responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = blobUrl; a.download = filename; document.body.appendChild(a); a.click();
  a.remove(); window.URL.revokeObjectURL(blobUrl);
}
