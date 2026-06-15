import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { LayoutDashboard, Radar, Users, FileText, Map, Hammer, LogOut, ChevronRight, Bell, ListTodo, Bot, UserPlus, Users2 } from "lucide-react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/radar", label: "Radar de Proyectos", icon: Radar, testId: "nav-radar" },
  { to: "/scraper", label: "Scraper Nocturno", icon: Bot, testId: "nav-scraper" },
  { to: "/crm", label: "CRM Comercial", icon: Users, testId: "nav-crm" },
  { to: "/cotizador", label: "Cotizador", icon: FileText, testId: "nav-cotizador" },
  { to: "/mapa", label: "Mapa México", icon: Map, testId: "nav-mapa" },
  { to: "/obras", label: "Obras", icon: Hammer, testId: "nav-obras" },
  { to: "/tareas", label: "Mis Tareas", icon: ListTodo, testId: "nav-tareas" },
  { to: "/alertas", label: "Alertas HOT", icon: Bell, testId: "nav-alertas" },
  { to: "/admin/clientes", label: "Alta Clientes", icon: UserPlus, testId: "nav-admin-clientes", roles: ["director", "socio", "comercial"] },
  { to: "/admin/rh", label: "RH · Personal", icon: Users2, testId: "nav-admin-rh", roles: ["director", "socio"] },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const onLogout = () => { logout(); nav("/login"); };

  const roleLabel = { director: "Director General", comercial: "Comercial", operaciones: "Operaciones", socio: "Socio" }[user?.role] || user?.role;

  const visibleNav = NAV.filter((n) => !n.roles || n.roles.includes(user?.role));

  return (
    <div className="min-h-screen flex bg-black">
      <aside className="w-64 border-r border-white/10 flex flex-col" data-testid="sidebar">
        <div className="p-4 divider flex items-center gap-3">
          <div className="w-8 h-8 bg-amber-500 flex items-center justify-center shrink-0">
            <Radar size={18} className="text-black" strokeWidth={2} />
          </div>
          <div>
            <div className="font-black tracking-tight text-sm" style={{ fontFamily: "Chivo, sans-serif" }}>DEYMA · RADAR</div>
            <div className="label-overline text-[8px] text-amber-400/80">v1.0 · 2026</div>
          </div>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {visibleNav.map((n) => (
            <NavLink
              key={n.to} to={n.to} end={n.to === "/"} data-testid={n.testId}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "bg-amber-500/10 text-amber-400 border-l-2 border-amber-500"
                    : "text-zinc-400 hover:text-zinc-100 hover:bg-white/5 border-l-2 border-transparent"
                }`
              }
            >
              <n.icon size={16} strokeWidth={1.5} />
              <span className="flex-1">{n.label}</span>
              <ChevronRight size={12} className="opacity-40" strokeWidth={1.5} />
            </NavLink>
          ))}
        </nav>

        <div className="divider" />
        <div className="p-3">
          <div className="flex items-center gap-2 p-2 border border-white/10">
            <div className="w-8 h-8 bg-zinc-800 flex items-center justify-center text-amber-400 font-mono text-xs font-bold">
              {(user?.name || "?").charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs truncate font-semibold">{user?.name}</div>
              <div className="label-overline text-[8px] text-zinc-500">{roleLabel}</div>
            </div>
            <button data-testid="logout-btn" onClick={onLogout} className="text-zinc-500 hover:text-rose-400 p-1" title="Cerrar sesión">
              <LogOut size={14} strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}
