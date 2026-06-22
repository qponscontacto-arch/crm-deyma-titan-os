import React, { useState, useEffect, useRef } from "react";
import {
  MessageCircle, Send, Link2, Linkedin, Twitter, Youtube,
  X as XIcon, ChevronLeft, ChevronRight, ExternalLink, Bookmark,
  EyeOff, Eye, Maximize2,
} from "lucide-react";

/**
 * Centro de Comunicaciones flotante (global).
 * Apps externas en ventanas popup persistentes.
 *
 * Limitación técnica: WhatsApp Web, Telegram, Reddit, LinkedIn, X bloquean
 * iframes (X-Frame-Options: DENY). Por eso usamos window.open() y permitimos
 * ESCONDER las ventanas (sin cerrarlas, manteniendo la sesión activa).
 */

const APPS = [
  { id: "whatsapp", label: "WhatsApp Web", url: "https://web.whatsapp.com", icon: MessageCircle, color: "emerald", w: 460, h: 720 },
  { id: "telegram", label: "Telegram", url: "https://web.telegram.org", icon: Send, color: "sky", w: 460, h: 720 },
  { id: "reddit", label: "Reddit", url: "https://www.reddit.com", icon: Link2, color: "orange", w: 600, h: 720 },
  { id: "linkedin", label: "LinkedIn", url: "https://www.linkedin.com/feed/", icon: Linkedin, color: "indigo", w: 700, h: 800 },
  { id: "x", label: "X / Twitter", url: "https://x.com", icon: Twitter, color: "zinc", w: 600, h: 760 },
  { id: "youtube", label: "YouTube", url: "https://www.youtube.com", icon: Youtube, color: "rose", w: 700, h: 600 },
];

const STORAGE_KEY = "deyma_comms_open";
const HIDDEN_POS = { x: -32000, y: -32000 };

export default function CommsPanel() {
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch { return false; }
  });
  const [openWindows, setOpenWindows] = useState({}); // {id: WindowRef}
  const [hiddenIds, setHiddenIds] = useState(new Set()); // ids escondidos
  const positionsRef = useRef({}); // {id: {x, y, w, h}}
  const [, forceRender] = useState(0);

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, open ? "1" : "0"); } catch { /* ignore */ }
  }, [open]);

  // Poll para detectar ventanas cerradas manualmente por el usuario
  useEffect(() => {
    const t = setInterval(() => {
      let changed = false;
      Object.entries(openWindows).forEach(([id, w]) => {
        if (w && w.closed) {
          delete openWindows[id];
          hiddenIds.delete(id);
          changed = true;
        }
      });
      if (changed) {
        setOpenWindows({ ...openWindows });
        setHiddenIds(new Set(hiddenIds));
      }
    }, 1500);
    return () => clearInterval(t);
  }, [openWindows, hiddenIds]);

  const computePosition = (idx) => {
    const sw = window.screen.availWidth || 1920;
    const offset = idx * 40;
    const x = Math.max(0, sw - 480 - offset);
    const y = Math.max(0, 80 + offset);
    return { x: Math.round(x), y: Math.round(y) };
  };

  const launch = (app) => {
    const existing = openWindows[app.id];
    if (existing && !existing.closed) {
      // Si estaba escondido, restaurarlo
      if (hiddenIds.has(app.id)) {
        const pos = positionsRef.current[app.id];
        if (pos) {
          try { existing.moveTo(pos.x, pos.y); existing.resizeTo(pos.w, pos.h); }
          catch { /* ignore — algunos browsers restringen moveTo */ }
        }
        hiddenIds.delete(app.id);
        setHiddenIds(new Set(hiddenIds));
      }
      existing.focus();
      return;
    }
    const idx = Object.keys(openWindows).filter((k) => openWindows[k] && !openWindows[k].closed).length;
    const { x, y } = computePosition(idx);
    const features = [
      `width=${app.w}`, `height=${app.h}`,
      `left=${x}`, `top=${y}`,
      "menubar=no", "toolbar=no", "location=yes",
      "resizable=yes", "scrollbars=yes", "status=no",
    ].join(",");
    const w = window.open(app.url, `deyma_${app.id}`, features);
    if (!w) {
      alert("Tu navegador bloqueó la ventana emergente. Habilita popups para este sitio.");
      return;
    }
    positionsRef.current[app.id] = { x, y, w: app.w, h: app.h };
    setOpenWindows((prev) => ({ ...prev, [app.id]: w }));
  };

  const hideOne = (id) => {
    const w = openWindows[id];
    if (!w || w.closed) return;
    try { w.moveTo(HIDDEN_POS.x, HIDDEN_POS.y); }
    catch { /* ignore */ }
    hiddenIds.add(id);
    setHiddenIds(new Set(hiddenIds));
  };

  const restoreOne = (id) => {
    const w = openWindows[id];
    if (!w || w.closed) return;
    const pos = positionsRef.current[id];
    if (pos) {
      try { w.moveTo(pos.x, pos.y); w.resizeTo(pos.w, pos.h); }
      catch { /* ignore */ }
    }
    w.focus();
    hiddenIds.delete(id);
    setHiddenIds(new Set(hiddenIds));
  };

  const hideAll = () => {
    Object.entries(openWindows).forEach(([id, w]) => {
      if (w && !w.closed) {
        try { w.moveTo(HIDDEN_POS.x, HIDDEN_POS.y); } catch { /* ignore */ }
        hiddenIds.add(id);
      }
    });
    setHiddenIds(new Set(hiddenIds));
    // Foco al CRM
    try { window.focus(); } catch { /* ignore */ }
  };

  const restoreAll = () => {
    Object.entries(openWindows).forEach(([id, w]) => {
      if (w && !w.closed) {
        const pos = positionsRef.current[id];
        if (pos) {
          try { w.moveTo(pos.x, pos.y); w.resizeTo(pos.w, pos.h); }
          catch { /* ignore */ }
        }
        hiddenIds.delete(id);
      }
    });
    setHiddenIds(new Set(hiddenIds));
    forceRender((x) => x + 1);
  };

  const closeAll = () => {
    Object.values(openWindows).forEach((w) => {
      try { w && !w.closed && w.close(); } catch { /* ignore */ }
    });
    setOpenWindows({});
    setHiddenIds(new Set());
  };

  const activeWindows = Object.entries(openWindows).filter(([, w]) => w && !w.closed);
  const hiddenCount = activeWindows.filter(([id]) => hiddenIds.has(id)).length;

  return (
    <>
      {/* Botón toggle flotante */}
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

      {/* Mini-dock flotante cuando hay ventanas escondidas y el panel está cerrado */}
      {!open && hiddenCount > 0 && (
        <div
          className="fixed bottom-4 right-12 z-[55] flex items-center gap-1.5 bg-zinc-950 border border-amber-500/40 rounded shadow-xl px-2 py-1.5 print:hidden"
          data-testid="comms-mini-dock"
        >
          <span className="text-[10px] text-amber-400 font-mono mr-1">
            {hiddenCount} oculta{hiddenCount > 1 ? "s" : ""}
          </span>
          {activeWindows.filter(([id]) => hiddenIds.has(id)).map(([id]) => {
            const app = APPS.find((a) => a.id === id);
            if (!app) return null;
            return (
              <button
                key={id}
                onClick={() => restoreOne(id)}
                title={`Mostrar ${app.label}`}
                data-testid={`comms-mini-restore-${id}`}
                className={`p-1.5 bg-${app.color}-500/10 text-${app.color}-400 hover:bg-${app.color}-500/30 border border-${app.color}-500/30 transition-colors`}
              >
                <app.icon size={12}/>
              </button>
            );
          })}
          <button
            onClick={restoreAll}
            title="Mostrar todas"
            data-testid="comms-mini-restore-all"
            className="p-1.5 text-amber-400 hover:bg-amber-500/10 border border-amber-500/30 ml-1"
          >
            <Maximize2 size={12}/>
          </button>
        </div>
      )}

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

        <div className="p-3 space-y-1.5 overflow-y-auto" style={{ maxHeight: "calc(100vh - 240px)" }}>
          {APPS.map((app) => {
            const w = openWindows[app.id];
            const isOpen = w && !w.closed;
            const isHidden = isOpen && hiddenIds.has(app.id);
            return (
              <div
                key={app.id}
                className={`bg-zinc-900 border border-zinc-800 hover:border-${app.color}-500/40 transition-colors`}
                data-testid={`comms-row-${app.id}`}
              >
                <button
                  onClick={() => launch(app)}
                  data-testid={`comms-launch-${app.id}`}
                  className="w-full flex items-center gap-2.5 p-2.5 text-left"
                >
                  <div className={`p-1.5 bg-${app.color}-500/10 text-${app.color}-400 border border-${app.color}-500/20`}>
                    <app.icon size={12}/>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold">{app.label}</div>
                    <div className="text-[9px] text-zinc-500 font-mono truncate">
                      {!isOpen ? "click para abrir"
                       : isHidden ? `● oculta · click=mostrar`
                       : "● activa · click=enfocar"}
                    </div>
                  </div>
                  {!isOpen && <ExternalLink size={10} className="text-zinc-500"/>}
                </button>
                {isOpen && (
                  <div className="flex border-t border-zinc-800">
                    {isHidden ? (
                      <button
                        onClick={(e) => { e.stopPropagation(); restoreOne(app.id); }}
                        data-testid={`comms-restore-${app.id}`}
                        className={`flex-1 py-1.5 text-[10px] text-${app.color}-400 hover:bg-${app.color}-500/10 transition-colors flex items-center justify-center gap-1`}
                      >
                        <Eye size={10}/> Mostrar
                      </button>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); hideOne(app.id); }}
                        data-testid={`comms-hide-${app.id}`}
                        className="flex-1 py-1.5 text-[10px] text-zinc-400 hover:text-amber-400 hover:bg-amber-500/5 transition-colors flex items-center justify-center gap-1"
                      >
                        <EyeOff size={10}/> Ocultar
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        try { w.close(); } catch { /* ignore */ }
                        delete openWindows[app.id];
                        hiddenIds.delete(app.id);
                        setOpenWindows({ ...openWindows });
                        setHiddenIds(new Set(hiddenIds));
                      }}
                      data-testid={`comms-close-${app.id}`}
                      className="px-2 py-1.5 text-[10px] text-rose-400 hover:bg-rose-500/10 transition-colors border-l border-zinc-800"
                    >
                      <XIcon size={10}/>
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer con acciones globales */}
        <div className="absolute bottom-0 left-0 right-0 p-3 border-t border-amber-500/20 bg-zinc-950 space-y-1.5">
          {activeWindows.length > 0 ? (
            <>
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  onClick={hideAll}
                  disabled={hiddenCount === activeWindows.length}
                  data-testid="comms-hide-all"
                  className="text-[10px] py-1.5 bg-zinc-800 text-amber-400 border border-amber-500/30 hover:bg-amber-500/10 disabled:opacity-40 transition-colors flex items-center justify-center gap-1"
                >
                  <EyeOff size={10}/> Ocultar todas
                </button>
                <button
                  onClick={restoreAll}
                  disabled={hiddenCount === 0}
                  data-testid="comms-restore-all"
                  className="text-[10px] py-1.5 bg-zinc-800 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/10 disabled:opacity-40 transition-colors flex items-center justify-center gap-1"
                >
                  <Eye size={10}/> Mostrar todas
                </button>
              </div>
              <button
                onClick={closeAll}
                data-testid="comms-close-all"
                className="w-full text-xs py-1.5 bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 transition-colors flex items-center justify-center gap-1.5"
              >
                <XIcon size={11}/> Cerrar las {activeWindows.length} ventana{activeWindows.length > 1 ? "s" : ""}
              </button>
            </>
          ) : (
            <div className="text-[10px] text-zinc-500 font-mono text-center py-1">
              Las ventanas mantienen su sesión<br/>mientras este panel esté abierto
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
