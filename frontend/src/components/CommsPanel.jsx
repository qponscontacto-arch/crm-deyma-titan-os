import React, { useState, useEffect } from "react";
import {
  MessageCircle, Send, Link2, Linkedin, Twitter, Youtube,
  X as XIcon, ChevronLeft, ChevronRight, ExternalLink, Bookmark,
} from "lucide-react";

/**
 * Panel de Comunicaciones flotante (global, en todas las páginas).
 * Acceso a apps externas en ventanas popup tipo "ventana interna" del navegador.
 *
 * Limitación técnica: WhatsApp Web, Telegram, Reddit, LinkedIn, X bloquean iframes
 * (X-Frame-Options: DENY) por seguridad. Por eso usamos window.open() con
 * tamaño + posición fija para emular una "ventana lateral" del CRM.
 */

const APPS = [
  {
    id: "whatsapp", label: "WhatsApp Web",
    url: "https://web.whatsapp.com", icon: MessageCircle,
    color: "emerald", w: 460, h: 720,
  },
  {
    id: "telegram", label: "Telegram",
    url: "https://web.telegram.org", icon: Send,
    color: "sky", w: 460, h: 720,
  },
  {
    id: "reddit", label: "Reddit",
    url: "https://www.reddit.com", icon: Link2,
    color: "orange", w: 600, h: 720,
  },
  {
    id: "linkedin", label: "LinkedIn",
    url: "https://www.linkedin.com/feed/", icon: Linkedin,
    color: "indigo", w: 700, h: 800,
  },
  {
    id: "x", label: "X / Twitter",
    url: "https://x.com", icon: Twitter,
    color: "zinc", w: 600, h: 760,
  },
  {
    id: "youtube", label: "YouTube",
    url: "https://www.youtube.com", icon: Youtube,
    color: "rose", w: 700, h: 600,
  },
];

const STORAGE_KEY = "deyma_comms_open";

export default function CommsPanel() {
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch { return false; }
  });
  const [openWindows, setOpenWindows] = useState({}); // {id: WindowRef}

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, open ? "1" : "0"); } catch { /* ignore */ }
  }, [open]);

  // Calcular posiciones para que las ventanas no se solapen
  const getPosition = (idx) => {
    const screenW = window.screen.availWidth || 1920;
    const screenH = window.screen.availHeight || 1080;
    // Stack en cascada desde la esquina superior derecha
    const offset = idx * 40;
    const x = Math.max(0, screenW - 480 - offset);
    const y = Math.max(0, 80 + offset);
    return { x: Math.round(x), y: Math.round(y) };
  };

  const launch = (app) => {
    const existing = openWindows[app.id];
    if (existing && !existing.closed) {
      existing.focus(); return;
    }
    const idx = Object.keys(openWindows).filter((k) => openWindows[k] && !openWindows[k].closed).length;
    const { x, y } = getPosition(idx);
    const features = [
      `width=${app.w}`, `height=${app.h}`,
      `left=${x}`, `top=${y}`,
      "menubar=no", "toolbar=no", "location=yes",
      "resizable=yes", "scrollbars=yes", "status=no",
    ].join(",");
    const w = window.open(app.url, `deyma_${app.id}`, features);
    if (!w) {
      alert("Tu navegador bloqueó la ventana emergente. Por favor habilita popups para este sitio.");
      return;
    }
    setOpenWindows((prev) => ({ ...prev, [app.id]: w }));
  };

  const closeAll = () => {
    Object.values(openWindows).forEach((w) => {
      try { w && !w.closed && w.close(); } catch { /* ignore */ }
    });
    setOpenWindows({});
  };

  const activeCount = Object.values(openWindows).filter((w) => w && !w.closed).length;

  return (
    <>
      {/* Botón toggle flotante - oculto en print */}
      <button
        onClick={() => setOpen((v) => !v)}
        data-testid="comms-toggle"
        className={`fixed top-1/2 right-0 -translate-y-1/2 z-[60] flex items-center justify-center
                    w-7 h-16 bg-amber-500 hover:bg-amber-400 text-black font-bold shadow-lg
                    transition-all print:hidden ${open ? "translate-x-[260px]" : ""}`}
        title={open ? "Ocultar panel" : "Centro de Comunicaciones"}
        style={{ borderRadius: "8px 0 0 8px" }}
      >
        {open ? <ChevronRight size={16}/> : <ChevronLeft size={16}/>}
      </button>

      {/* Panel lateral */}
      <aside
        data-testid="comms-panel"
        className={`fixed top-0 right-0 h-screen w-[260px] z-50
                    bg-zinc-950 border-l border-amber-500/30
                    transform transition-transform duration-300 print:hidden
                    ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="p-4 border-b border-amber-500/20">
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Bookmark size={11}/> Centro de Comunicaciones
          </div>
          <h2 className="text-base font-bold mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Apps externas
          </h2>
          <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
            Ventanas popup persistentes
          </div>
        </div>

        <div className="p-3 space-y-2 overflow-y-auto" style={{ maxHeight: "calc(100vh - 200px)" }}>
          {APPS.map((app) => {
            const isOpen = openWindows[app.id] && !openWindows[app.id].closed;
            return (
              <button
                key={app.id}
                onClick={() => launch(app)}
                data-testid={`comms-launch-${app.id}`}
                className={`w-full flex items-center gap-3 p-2.5 transition-colors text-left
                            bg-zinc-900 hover:bg-${app.color}-500/10 border border-zinc-800
                            hover:border-${app.color}-500/40`}
              >
                <div className={`p-2 bg-${app.color}-500/10 text-${app.color}-400 border border-${app.color}-500/20`}>
                  <app.icon size={14}/>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold">{app.label}</div>
                  <div className="text-[9px] text-zinc-500 font-mono truncate">
                    {isOpen ? "● activa · click=enfocar" : "click para abrir"}
                  </div>
                </div>
                <ExternalLink size={10} className="text-zinc-500"/>
              </button>
            );
          })}
        </div>

        <div className="absolute bottom-0 left-0 right-0 p-3 border-t border-amber-500/20 bg-zinc-950">
          {activeCount > 0 ? (
            <button
              onClick={closeAll}
              data-testid="comms-close-all"
              className="w-full text-xs py-2 bg-rose-500/10 text-rose-400 border border-rose-500/30
                         hover:bg-rose-500/20 transition-colors flex items-center justify-center gap-1.5"
            >
              <XIcon size={12}/> Cerrar las {activeCount} ventana{activeCount > 1 ? "s" : ""}
            </button>
          ) : (
            <div className="text-[10px] text-zinc-500 font-mono text-center">
              Las ventanas mantienen su sesión<br/>mientras este panel esté abierto
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
