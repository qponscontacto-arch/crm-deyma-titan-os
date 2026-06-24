import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/auth";
import {
  AlertTriangle, Trash2, ExternalLink, Loader2, CheckCircle2, AlertOctagon,
  Twitter, Zap, Radar,
} from "lucide-react";

const URG_COLOR = { alto: "rose", medio: "amber", bajo: "emerald" };
const TIPO_ICON = { luz: "⚡", agua: "💧", seguridad: "🚨", mantenimiento: "🔧", otro: "❓" };

export default function CondoAlertasPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [urgencia, setUrgencia] = useState("");
  const [tipo, setTipo] = useState("");
  const [notice, setNotice] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = [];
      if (urgencia) params.push(`urgencia=${urgencia}`);
      if (tipo) params.push(`tipo=${tipo}`);
      const q = params.length ? `?${params.join("&")}` : "";
      const { data } = await api.get(`/condo/alertas${q}`);
      setItems(data);
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [urgencia, tipo]);

  const runAnalista = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/condo/run/analista");
      if (data.mock) setNotice({ kind: "warn", msg: "⚠️ OSINT en modo MOCK. Configura APIFY_TOKEN y OSINT_MODE=live." });
      else setNotice({ kind: "ok", msg: `🚨 Analista terminó: ${data.inserted || 0} alertas nuevas` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setRunning(false); }
  };

  const eliminar = async (a) => {
    if (!window.confirm("¿Eliminar esta alerta?")) return;
    try { await api.delete(`/condo/alertas/${a.id}`); load(); }
    catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-4" data-testid="condo-alertas-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-rose-400 flex items-center gap-2">
            <Radar size={11}/> V6.0 · Radar de Condominios · Agente Analista
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Alertas de Dolor <span className="text-rose-400">·</span> Quejas CFE/CEA
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Extracción Inversa de Dolor · Twitter/X · GPT-5.2 clasifica urgencia
          </div>
        </div>
        <button onClick={runAnalista} disabled={running} className="btn-primary text-xs disabled:opacity-50" data-testid="btn-run-analista">
          {running ? <Loader2 size={12} className="inline mr-1 animate-spin"/> : <Zap size={12} className="inline mr-1"/>}
          {running ? "Analizando..." : "Ejecutar Analista"}
        </button>
      </header>

      {notice && (
        <div className={`surface p-3 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5"
                                                   : notice.kind === "warn" ? "border-amber-500 bg-amber-500/5"
                                                   : "border-rose-500 bg-rose-500/5"}`} data-testid="alertas-notice">
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
        <select value={urgencia} onChange={(e) => setUrgencia(e.target.value)} className="input-field !w-auto text-xs" data-testid="filter-urgencia">
          <option value="">Toda urgencia</option>
          <option value="alto">Alto</option><option value="medio">Medio</option><option value="bajo">Bajo</option>
        </select>
        <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="input-field !w-auto text-xs" data-testid="filter-tipo">
          <option value="">Todo tipo</option>
          <option value="luz">⚡ Luz</option>
          <option value="agua">💧 Agua</option>
          <option value="seguridad">🚨 Seguridad</option>
          <option value="mantenimiento">🔧 Mantenimiento</option>
        </select>
        <div className="text-xs text-zinc-400 font-mono ml-auto">
          <span className="text-amber-400 font-bold">{items.length}</span> alertas
        </div>
      </div>

      {loading ? (
        <div className="surface p-8 text-center text-zinc-500">
          <Loader2 size={16} className="inline animate-spin mr-2"/> Cargando…
        </div>
      ) : items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">
          Sin alertas detectadas aún. Dale click a <strong>Ejecutar Analista</strong> para barrer Twitter o espera al cron (04:00 CDMX).
        </div>
      ) : (
        <div className="grid gap-3" data-testid="alertas-feed">
          {items.map((a) => {
            const ucol = URG_COLOR[a.urgencia] || "zinc";
            return (
              <div key={a.id} className={`surface p-4 border-l-4 border-${ucol}-500`} data-testid={`alerta-${a.id}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 text-xs flex-wrap">
                      <span className={`font-mono uppercase bg-${ucol}-500/10 text-${ucol}-400 border border-${ucol}-500/30 px-2 py-0.5`}>
                        <AlertTriangle size={10} className="inline mr-1"/>
                        {a.urgencia}
                      </span>
                      <span className="text-zinc-400 font-mono">
                        {TIPO_ICON[a.tipo] || "❓"} {a.tipo}
                      </span>
                      <span className="text-zinc-500 font-mono">
                        <Twitter size={10} className="inline mr-1"/>@{a.autor_handle || "?"}
                      </span>
                      {a.fraccionamiento_detectado && (
                        <span className="text-amber-400 font-bold font-mono">📍 {a.fraccionamiento_detectado}</span>
                      )}
                    </div>
                    <p className="text-sm mt-2 text-zinc-200">{a.texto}</p>
                    <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-zinc-500">
                      <span>{a.ubicacion || "Querétaro"}</span>
                      <span>·</span>
                      <span>{(a.fecha_deteccion || "").slice(0, 10)}</span>
                      {a.url && (
                        <a href={a.url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
                          ver tweet <ExternalLink size={8} className="inline"/>
                        </a>
                      )}
                    </div>
                  </div>
                  <button onClick={() => eliminar(a)} className="text-rose-400 hover:text-rose-300" title="Eliminar">
                    <Trash2 size={12}/>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
