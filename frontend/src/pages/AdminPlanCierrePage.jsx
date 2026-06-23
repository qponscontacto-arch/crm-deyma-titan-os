import React, { useState, useEffect, useCallback } from "react";
import { api, formatApiError, API } from "../lib/auth";
import {
  Target, TrendingUp, Calendar, Download, Loader2, Copy, CheckCircle2,
  Flame, DollarSign, Package, Zap, MessageCircle, Mail, ExternalLink,
} from "lucide-react";
import { Link } from "react-router-dom";

export default function AdminPlanCierrePage() {
  const [data, setData] = useState(null);
  const [meta, setMeta] = useState(1200000);
  const [precio, setPrecio] = useState(1000);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const { data } = await api.get(
        `/plan-cierre/resumen?meta_mxn=${meta}&precio_canastilla=${precio}`
      );
      setData(data);
    } catch (e) { setErr(formatApiError(e)); }
    finally { setLoading(false); }
  }, [meta, precio]);

  useEffect(() => { load(); }, [load]);

  const downloadPDF = async () => {
    if (downloading) return;
    setDownloading(true);
    try {
      const token = localStorage.getItem("deyma_token");
      const res = await fetch(`${API}/plan-cierre/pdf?meta_mxn=${meta}&precio_canastilla=${precio}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `deyma_plan_cierre_${meta}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
    finally { setDownloading(false); }
  };

  if (loading || !data) {
    return (
      <div className="p-12 text-center text-zinc-500">
        <Loader2 size={20} className="inline animate-spin mr-2"/> Calculando estrategia…
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6" data-testid="plan-cierre-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Target size={11}/> V5.6 · Estrategia táctica
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Plan Cierre <span className="text-amber-400">·</span> ${(meta/1_000_000).toFixed(1)}M MXN
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Director + Socio · {data.meta.canastillas_target.toLocaleString("es-MX")} canastillas a ${precio.toLocaleString("es-MX")}/u
          </div>
        </div>
        <div className="flex items-end gap-2 flex-wrap">
          <div>
            <label className="label-overline text-[9px]">Meta MXN</label>
            <input type="number" value={meta} step={100000}
                   onChange={(e) => setMeta(Number(e.target.value) || 1200000)}
                   className="input-field font-mono w-32 text-xs" data-testid="meta-input"/>
          </div>
          <div>
            <label className="label-overline text-[9px]">Precio canastilla</label>
            <input type="number" value={precio} step={100}
                   onChange={(e) => setPrecio(Number(e.target.value) || 1000)}
                   className="input-field font-mono w-24 text-xs" data-testid="precio-input"/>
          </div>
          <button onClick={downloadPDF} disabled={downloading}
                  className="btn-primary bg-amber-500 hover:bg-amber-600 text-black border-amber-600 text-xs"
                  data-testid="download-plan-pdf">
            {downloading ? <Loader2 size={12} className="animate-spin inline mr-1"/>
                         : <Download size={12} className="inline mr-1"/>}
            Descargar PDF
          </button>
        </div>
      </header>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard icon={DollarSign} color="emerald" label="Pipeline Activo"
                 value={`$${(data.pipeline.monto_activo/1_000_000).toFixed(1)}M`} sub={`${data.pipeline.total_ops} oportunidades`}/>
        <KpiCard icon={TrendingUp} color="amber" label="Veces la meta"
                 value={`${data.pipeline.veces_meta}x`} sub="munición vs meta"/>
        <KpiCard icon={Package} color="sky" label="Canastillas meta"
                 value={data.meta.canastillas_target.toLocaleString("es-MX")} sub={`a $${precio}/u`}/>
        <KpiCard icon={Zap} color="rose" label="Combinaciones cierre"
                 value={data.combinaciones_meta.length} sub="cards que dan la meta solas"/>
      </div>

      {/* Combinaciones */}
      {data.combinaciones_meta.length > 0 && (
        <section className="surface p-4" data-testid="combinaciones-section">
          <div className="flex items-center gap-2 mb-3 pb-2 border-b border-amber-500/30">
            <Flame size={14} className="text-amber-400"/>
            <h2 className="text-base font-bold">Cards ganadoras (cualquiera resuelve solas la meta)</h2>
          </div>
          <div className="space-y-2">
            {data.combinaciones_meta.map((c, i) => (
              <div key={i} className="surface-elev p-3 bg-amber-500/5 border-amber-500/30" data-testid={`combo-${i}`}>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold">{c.label}</div>
                    <div className="text-[11px] font-mono text-zinc-400 mt-0.5">
                      Total oportunidad: ${c.monto_oportunidad.toLocaleString("es-MX")} MXN ·
                      <span className="text-amber-400 ml-1">solo {c.pct_requerido}% requerido</span> ·
                      {c.canastillas.toLocaleString("es-MX")} canastillas
                    </div>
                  </div>
                  <Link to="/admin/crm" className="text-xs text-amber-400 hover:underline">
                    Abrir en CRM <ExternalLink size={10} className="inline"/>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Top oportunidades */}
      <section className="surface overflow-x-auto" data-testid="top-ops-section">
        <div className="flex items-center justify-between p-4 pb-2">
          <h2 className="text-base font-bold flex items-center gap-2">
            <Target size={14} className="text-amber-400"/>
            TOP 10 oportunidades priorizadas (score × monto)
          </h2>
        </div>
        <table className="dtable">
          <thead><tr><th>#</th><th>Proyecto</th><th>Scope</th><th>Etapa</th><th>Score</th><th>Monto MXN</th><th>Canast.</th><th>% para meta</th><th></th></tr></thead>
          <tbody>
            {data.top_oportunidades.map((o, i) => (
              <tr key={o.id} data-testid={`top-op-${i}`}>
                <td className="font-mono text-amber-400 font-bold">{i + 1}</td>
                <td className="font-semibold">{o.titulo}</td>
                <td><span className="text-[9px] font-mono text-zinc-400 uppercase">{o.scope}</span></td>
                <td><span className="text-[10px] font-mono uppercase">{o.stage}</span></td>
                <td className="font-mono text-rose-400">{o.score || 0}</td>
                <td className="font-mono text-emerald-400">${(o.monto_estimado||0).toLocaleString("es-MX")}</td>
                <td className="font-mono text-sky-400">{o.canastillas_estimadas.toLocaleString("es-MX")}</td>
                <td className="font-mono text-amber-400 font-bold">{o.monto_para_meta_pct}%</td>
                <td>
                  <Link to="/admin/crm" className="text-[10px] text-amber-400 hover:underline">Ver</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Plan 7 días */}
      <section className="surface p-4" data-testid="plan-section">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-amber-500/30">
          <Calendar size={14} className="text-amber-400"/>
          <h2 className="text-base font-bold">Plan Táctico · 7 días</h2>
        </div>
        <div className="space-y-3">
          {data.plan_dias.map((d) => (
            <DiaCard key={d.dia} dia={d}/>
          ))}
        </div>
      </section>

      {/* Plantillas WhatsApp/Email */}
      <section className="surface p-4" data-testid="plantillas-section">
        <h2 className="text-base font-bold border-b border-amber-500/30 pb-2 mb-3 flex items-center gap-2">
          <MessageCircle size={14} className="text-emerald-400"/> Plantillas listas para pegar
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <PlantillaCard title="WhatsApp · CEDIS/Logística" icon={MessageCircle} color="emerald"
                         text={data.plantillas.whatsapp_cedis}/>
          <PlantillaCard title="WhatsApp · Industrial" icon={MessageCircle} color="sky"
                         text={data.plantillas.whatsapp_industrial}/>
          <PlantillaCard title="Email · Seguimiento" icon={Mail} color="amber"
                         text={data.plantillas.email_seguimiento}/>
        </div>
      </section>

      <div className="text-[10px] text-zinc-600 font-mono text-center pt-4">
        Plan generado en base a datos reales del CRM · Recalcula automáticamente al cambiar meta o precio
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, color, label, value, sub }) {
  return (
    <div className="surface p-3">
      <div className={`label-overline text-[9px] text-${color}-400 flex items-center gap-1.5`}>
        <Icon size={10}/> {label}
      </div>
      <div className="text-2xl font-black mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>{value}</div>
      <div className="text-[10px] text-zinc-500 font-mono mt-0.5">{sub}</div>
    </div>
  );
}

function DiaCard({ dia }) {
  const [done, setDone] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(`plan_done_${dia.dia}`) || "[]")); }
    catch { return new Set(); }
  });
  const toggle = (idx) => {
    const next = new Set(done);
    next.has(idx) ? next.delete(idx) : next.add(idx);
    setDone(next);
    try { localStorage.setItem(`plan_done_${dia.dia}`, JSON.stringify([...next])); } catch { /* ignore */ }
  };
  const pct = Math.round((done.size / dia.acciones.length) * 100);

  return (
    <div className="surface-elev p-3" data-testid={`dia-${dia.dia}`}>
      <div className="flex items-center justify-between gap-2 mb-2 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="bg-amber-500 text-black px-2 py-0.5 text-[10px] font-bold font-mono">DÍA {dia.dia}</div>
          <div className="text-[10px] font-mono text-zinc-400">{dia.fecha}</div>
          <div className="text-xs font-semibold">{dia.titulo}</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-[10px] font-mono text-zinc-500">{dia.responsable}</div>
          <div className={`text-[10px] font-mono px-1.5 py-0.5 ${pct === 100 ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}>
            {pct}% ({done.size}/{dia.acciones.length})
          </div>
        </div>
      </div>
      <div className="space-y-1.5">
        {dia.acciones.map((a, i) => (
          <label key={i} className="flex items-start gap-2 cursor-pointer text-xs"
                 data-testid={`accion-${dia.dia}-${i}`}>
            <input type="checkbox" checked={done.has(i)} onChange={() => toggle(i)}
                   className="mt-0.5 accent-amber-500"/>
            <span className={done.has(i) ? "line-through text-zinc-500" : "text-zinc-200"}>{a}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function PlantillaCard({ title, icon: Icon, color, text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { /* ignore */ }
  };
  return (
    <div className={`bg-zinc-900 border border-${color}-500/30 p-3`}>
      <div className={`flex items-center justify-between mb-2 text-${color}-400`}>
        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider">
          <Icon size={11}/> {title}
        </div>
        <button onClick={copy} className={`text-[10px] hover:text-${color}-300`}>
          {copied ? <CheckCircle2 size={11}/> : <Copy size={11}/>}
        </button>
      </div>
      <pre className="text-[11px] text-zinc-300 whitespace-pre-wrap font-sans leading-snug">{text}</pre>
    </div>
  );
}
