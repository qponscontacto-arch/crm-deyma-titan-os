import axios from "axios";
import React, { createContext, useContext, useEffect, useState } from "react";

// Resolver BACKEND_URL con fallback defensivo:
// 1) Si la env var apunta a un dominio claramente roto (legado o inválido), ignorarla.
// 2) Si no está definida o está rota, usar el mismo dominio del navegador
//    (en Emergent, el ingress redirige /api → backend automáticamente).
// 3) Solo usar la env var si parece válida.
const _envUrl = process.env.REACT_APP_BACKEND_URL;
const _KNOWN_BAD_HOSTS = ["deyma.tech"]; // dominios legados que rompen producción
const _isBroken = _envUrl && _KNOWN_BAD_HOSTS.some((h) => _envUrl.includes(h));
const BACKEND_URL = (_envUrl && !_isBroken)
  ? _envUrl
  : (typeof window !== "undefined" ? window.location.origin : "");
export const API = `${BACKEND_URL}/api`;

const TOKEN_KEY = "deyma_token";
const KIND_KEY = "deyma_kind"; // "staff" | "cliente"

export const api = axios.create({ baseURL: API });
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [cliente, setCliente] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem(TOKEN_KEY);
    const kind = localStorage.getItem(KIND_KEY);
    if (!t) { setLoading(false); return; }
    const url = kind === "cliente" ? "/clientes/me" : "/auth/me";
    api.get(url)
      .then((r) => { if (kind === "cliente") setCliente(r.data); else setUser(r.data); })
      .catch(() => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(KIND_KEY); setUser(null); setCliente(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(KIND_KEY, "staff");
    setUser(data.user);
    setCliente(null);
    return data.user;
  };

  const loginCliente = async (dfnum, password) => {
    const { data } = await api.post("/clientes/login", { dfnum, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(KIND_KEY, "cliente");
    setCliente(data.cliente);
    setUser(null);
    return data.cliente;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(KIND_KEY);
    setUser(null);
    setCliente(null);
  };

  return (
    <AuthCtx.Provider value={{ user, cliente, loading, login, loginCliente, logout }}>
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
