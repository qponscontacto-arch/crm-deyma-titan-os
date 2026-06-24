import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/auth";
import {
  Users, ExternalLink, Trash2, Loader2, CheckCircle2, AlertOctagon,
  Search, Copy, MessageCircle, Send,
} from "lucide-react";

const PLAT_COLOR = { whatsapp: "emerald", telegram: "sky" };
const PLAT_LABEL = { whatsapp: "WhatsApp", telegram: "Telegram" };

export default function CondoRedesPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [plataforma, setPlataforma] = useState("");
  const [notice, setNotice] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const q = plataforma ? `?plataforma=${plataforma}` : "";
      const { data } = await api.get(`/condo/grupos${q}`);
      setItems(data);
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [plataforma]);

  const runInfiltrado = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/condo/run/infiltrado");
      if (data.mock) setNotice({ kind: "warn", msg: "⚠️ OSINT en modo MOCK. Configura APIFY_TOKEN y OSINT_MODE=live." });
      else setNotice({ kind: "ok", msg: `🕵️ Infiltrado terminó: ${data.inserted || 0} grupos detectados` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setRunning(false); }
  };

  const copiarLink = async (link) => {
    try {
      await navigator.clipboard.writeText(link);
      setNotice({ kind: "ok", msg: "✓ Link copiado" });
    } catch { setNotice({ kind: "err", msg: "No se pudo copiar" }); }
  };

  const eliminar = async (g) => {
    if (!window.confirm("¿Eliminar este grupo?")) return;
    try { await api.delete(`/condo/grupos/${g.id}`); load(); }
    catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-4" data-testid="condo-redes-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-sky-400 flex items-center gap-2">
            <Search size={11}/> V6.0 · Radar de Condominios · Agente Infiltrado
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Redes Vecinales <span className="text-sky-400">·</span> Grupos WA/Telegram
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Google Dorking · site:facebook.com &quot;chat.whatsapp.com&quot; &quot;vecinos&quot;
          </div>
        </div>
        <button onClick={runInfiltrado} disabled={running} className="btn-primary text-xs disabled:opacity-50" data-testid="btn-run-infiltrado">
          {running ? <Loader2 size={12} className="inline mr-1 animate-spin"/> : <Search size={12} className="inline mr-1"/>}
          {running ? "Buscando..." : "Ejecutar Infiltrado"}
        </button>
      </header>

      {notice && (
        <div className={`surface p-3 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5"
                                                   : notice.kind === "warn" ? "border-amber-500 bg-amber-500/5"
                                                   : "border-rose-500 bg-rose-500/5"}`} data-testid="redes-notice">
          <div className="flex items-start justify-between gap-2">
            <div className={`text-sm ${notice.kind === "ok" ? "text-emerald-400" : notice.kind === "warn" ? "text-amber-400" : "text-rose-400"}`}>
              {notice.kind === "ok" ? <CheckCircle2 size={14} className="inline mr-2"/> : <AlertOctagon size={14} className="inline mr-2"/>}
              {notice.msg}
            </div>
            <button onClick={() => setNotice(null)} className="text-zinc-500 hover:text-zinc-300">✕</button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        <select value={plataforma} onChange={(e) => setPlataforma(e.target.value)} className="input-field !w-auto text-xs" data-testid="filter-plataforma">
          <option value="">Todas las plataformas</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="telegram">Telegram</option>
        </select>
        <div className="text-xs text-zinc-400 font-mono ml-auto">
          <span className="text-amber-400 font-bold">{items.length}</span> grupos
        </div>
      </div>

      {loading ? (
        <div className="surface p-8 text-center text-zinc-500">
          <Loader2 size={16} className="inline animate-spin mr-2"/> Cargando…
        </div>
      ) : items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">
          Sin grupos detectados aún. Dale click a <strong>Ejecutar Infiltrado</strong> para buscar dorks o espera al cron (04:00 CDMX).
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="redes-grid">
          {items.map((g) => {
            const pcol = PLAT_COLOR[g.plataforma] || "zinc";
            const icon = g.plataforma === "telegram" ? <Send size={14}/> : <MessageCircle size={14}/>;
            return (
              <div key={g.id} className={`surface p-4 border-l-4 border-${pcol}-500`} data-testid={`grupo-${g.id}`}>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 flex-1">
                    <span className={`text-${pcol}-400`}>{icon}</span>
                    <span className={`text-[10px] font-mono uppercase bg-${pcol}-500/10 text-${pcol}-400 border border-${pcol}-500/30 px-1.5 py-0.5`}>
                      {PLAT_LABEL[g.plataforma] || g.plataforma}
                    </span>
                  </div>
                  <button onClick={() => eliminar(g)} className="text-rose-400 hover:text-rose-300" title="Eliminar">
                    <Trash2 size={11}/>
                  </button>
                </div>

                <div className="text-sm font-semibold mb-1 line-clamp-2">{g.nombre_grupo || "(sin título)"}</div>
                {g.fraccionamiento && (
                  <div className="text-xs text-amber-400 font-mono mb-2">📍 {g.fraccionamiento}</div>
                )}

                <div className="flex items-center gap-2 mb-2">
                  <code className={`flex-1 bg-zinc-900 p-2 font-mono text-[10px] text-${pcol}-400 break-all`}>
                    {g.url}
                  </code>
                  <button onClick={() => copiarLink(g.url)} className="btn-ghost text-[10px]" title="Copiar">
                    <Copy size={11}/>
                  </button>
                </div>

                <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500">
                  <a href={g.url} target="_blank" rel="noreferrer" className={`text-${pcol}-400 hover:underline font-bold`}>
                    Entrar al grupo <ExternalLink size={9} className="inline"/>
                  </a>
                  <span className="mx-1">·</span>
                  {g.source_url && (
                    <a href={g.source_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
                      fuente
                    </a>
                  )}
                  <span className="ml-auto">{(g.fecha_deteccion || "").slice(0, 10)}</span>
                </div>

                {g.notas && (
                  <div className="text-[10px] text-zinc-500 mt-2 line-clamp-2 italic">{g.notas}</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
