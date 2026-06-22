import React, { useEffect, useState, useCallback } from "react";
import { api, formatApiError, API } from "../lib/auth";
import {
  Printer, Download, Flame, Briefcase, Map, Crosshair, Satellite,
  MessageSquare, FileText, RefreshCw, Loader2, ExternalLink, Calendar,
  Lock,
} from "lucide-react";
import { Link } from "react-router-dom";

// Solo director/socio ven esta página (la ruta valida también en backend)

const STAGE_COLORS = {
  prospeccion: "zinc",
  calificada: "sky",
  propuesta: "indigo",
  negociacion: "amber",
};

export default function AdminCentralizadoPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [fecha, setFecha] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const { data } = await api.get(`/centralizado/resumen?fecha=${fecha}`);
      setData(data);
    } catch (e) { setErr(formatApiError(e)); }
    finally { setLoading(false); }
  }, [fecha]);

  useEffect(() => { load(); }, [load]);
  // auto-refresh cada 60s
  useEffect(() => {
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const handlePrint = () => window.print();

  const handleDownloadPDF = async () => {
    if (downloading) return;
    setDownloading(true);
    try {
      const token = localStorage.getItem("deyma_token");
      const res = await fetch(`${API}/centralizado/pdf?fecha=${fecha}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `deyma_centralizado_${fecha}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { alert("Error al descargar PDF: " + e.message); }
    finally { setDownloading(false); }
  };

  if (err === "Forbidden" || err.toLowerCase().includes("forbidden") || err.toLowerCase().includes("403")) {
    return (
      <div className="p-12 text-center text-zinc-400" data-testid="centralizado-forbidden">
        <Lock size={32} className="mx-auto mb-3 text-rose-400"/>
        <div className="text-lg font-semibold">Acceso restringido</div>
        <div className="text-sm mt-1">Solo Dirección General y Socios pueden ver este módulo.</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto print:p-0 print:max-w-none" data-testid="centralizado-page">
      {/* Estilos de impresión */}
      <style>{`
        @media print {
          nav, aside, header.app-header, [data-print-hide], .no-print { display: none !important; }
          body { background: white !important; color: black !important; }
          .surface, .surface-elev { background: white !important; color: black !important; border: 1px solid #ccc !important; }
          .print-only-show { display: block !important; }
          .text-zinc-400, .text-zinc-500, .text-zinc-300 { color: #444 !important; }
          .text-amber-400, .text-emerald-400, .text-sky-400, .text-rose-400, .text-indigo-400 { color: black !important; }
          a { color: black !important; text-decoration: none !important; }
          @page { size: letter; margin: 1.2cm; }
        }
      `}</style>

      <header className="flex items-start justify-between gap-4 flex-wrap" data-print-hide>
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Briefcase size={11}/> V5.3 · Centro de Mando
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Centralizado <span className="text-amber-400">·</span> Cierre del Día
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Vista única ejecutiva · solo dirección y socios · auto-refresh 60s
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 surface px-3 py-2">
            <Calendar size={13} className="text-zinc-400"/>
            <input
              type="date"
              value={fecha}
              max={today}
              onChange={(e) => setFecha(e.target.value)}
              className="bg-transparent text-xs font-mono outline-none"
              data-testid="centralizado-date"
            />
          </div>
          <button onClick={load} disabled={loading} className="btn-ghost text-xs" data-testid="centralizado-refresh">
            {loading ? <Loader2 size={13} className="animate-spin"/> : <RefreshCw size={13}/>}
          </button>
          <button onClick={handlePrint} className="btn-ghost text-xs" data-testid="centralizado-print">
            <Printer size={13} className="inline mr-1"/> Imprimir
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={downloading}
            className="btn-primary bg-amber-500 hover:bg-amber-600 text-black border-amber-600 text-xs"
            data-testid="centralizado-download-pdf"
          >
            {downloading ? <Loader2 size={13} className="animate-spin inline mr-1"/> : <Download size={13} className="inline mr-1"/>}
            Descargar PDF
          </button>
        </div>
      </header>

      {/* Print-only header */}
      <div className="hidden print:block" data-print-only>
        <div style={{ fontSize: 10, color: "#f59e0b", letterSpacing: 2, textTransform: "uppercase" }}>DEYMA · CENTRO DE MANDO</div>
        <h1 style={{ fontSize: 22, fontWeight: 800, marginTop: 4 }}>Cierre del día — {data?.fecha_label}</h1>
        <div style={{ fontSize: 9, color: "#52525b", marginTop: 2 }}>
          Generado por {data?.usuario?.name} ({data?.usuario?.role}) ·{" "}
          {data?.generado_en ? new Date(data.generado_en).toLocaleString("es-MX") : ""}
        </div>
        <hr style={{ borderColor: "#ddd", margin: "12px 0" }}/>
      </div>

      {loading && !data ? (
        <div className="surface p-12 text-center text-zinc-500">
          <Loader2 size={20} className="inline animate-spin mr-2"/> Cargando…
        </div>
      ) : err ? (
        <div className="surface p-6 text-rose-400">{err}</div>
      ) : data ? (
        <>
          <KPIRow data={data}/>
          <AlertasHotBlock items={data.alertas_hot}/>
          <PipelineBlock data={data}/>
          <VisitasBlock items={data.visitas_programadas} fecha={fecha}/>
          <FrancotiradorBlock items={data.francotirador_pendientes}/>
          <GreenfieldBlock items={data.greenfield_24h}/>
          <IntentsBlock items={data.intents_24h}/>
          <CotizacionesBlock items={data.cotizaciones_seguimiento}/>

          <div className="text-[10px] text-zinc-600 font-mono text-center pt-6 print:text-black print:pt-3">
            Documento confidencial · DEYMA RADAR · Distribución restringida a Dirección General y Socios
          </div>
        </>
      ) : null}
    </div>
  );
}

function KPIRow({ data }) {
  const t = data.totales || {};
  const kpis = [
    { label: "Alertas HOT", val: t.alertas_hot, icon: Flame, color: "rose" },
    { label: "Visitas hoy", val: t.visitas, icon: Map, color: "sky" },
    { label: "DROs pendientes", val: t.dro, icon: Crosshair, color: "amber" },
    { label: "Greenfield 24h", val: t.greenfield, icon: Satellite, color: "emerald" },
    { label: "Intents 24h", val: t.intents, icon: MessageSquare, color: "indigo" },
    { label: "Cotizaciones", val: t.cotizaciones, icon: FileText, color: "zinc" },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="centralizado-kpis">
      {kpis.map(k => (
        <div key={k.label} className="surface p-3 print:border print:border-zinc-300">
          <div className={`label-overline text-[9px] text-${k.color}-400 print:text-black flex items-center gap-1.5`}>
            <k.icon size={10}/> {k.label}
          </div>
          <div className="text-2xl font-black mt-1 print:text-black" style={{ fontFamily: "Chivo, sans-serif" }}>
            {k.val ?? 0}
          </div>
        </div>
      ))}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, color, count, link }) {
  return (
    <div className={`flex items-center justify-between mb-2 pb-2 border-b border-${color}-500/30 print:border-zinc-400`}>
      <div className="flex items-center gap-2">
        <Icon size={14} className={`text-${color}-400 print:text-black`}/>
        <h2 className="text-base font-bold print:text-black">{title}</h2>
        {count !== undefined && (
          <span className={`text-[10px] font-mono text-${color}-400 bg-${color}-500/10 px-1.5 py-0.5 print:bg-zinc-200 print:text-black`}>
            {count}
          </span>
        )}
      </div>
      {link && (
        <Link to={link} className={`text-[10px] font-mono text-${color}-400 hover:text-${color}-300 print:hidden`} data-print-hide>
          Ver módulo completo <ExternalLink size={9} className="inline"/>
        </Link>
      )}
    </div>
  );
}

function AlertasHotBlock({ items }) {
  return (
    <section className="surface p-4" data-testid="block-alertas-hot">
      <SectionHeader icon={Flame} title="Alertas HOT activas (score ≥ 85)" color="rose" count={items.length} link="/alertas"/>
      {items.length === 0 ? (
        <Empty msg="Sin alertas HOT activas"/>
      ) : (
        <table className="dtable">
          <thead><tr><th>Score</th><th>Empresa</th><th>Sector</th><th>Ciudad</th><th>Monto MXN</th><th></th></tr></thead>
          <tbody>
            {items.slice(0, 15).map((a) => (
              <tr key={a.id}>
                <td className="font-mono text-rose-400 print:text-black font-bold">{a.score}</td>
                <td className="font-semibold">{a.empresa_nombre || a.titulo || "—"}</td>
                <td className="text-xs">{a.sector || "—"}</td>
                <td className="text-xs">{a.ciudad || "—"}</td>
                <td className="font-mono text-emerald-400 print:text-black">${(a.monto_estimado || 0).toLocaleString("es-MX")}</td>
                <td className="text-right">
                  <Link to={`/admin/crm?op=${a.id}`} className="text-[10px] text-amber-400 hover:underline print:hidden" data-print-hide>
                    Abrir <ExternalLink size={9} className="inline"/>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function PipelineBlock({ data }) {
  return (
    <section className="surface p-4" data-testid="block-pipeline">
      <SectionHeader icon={Briefcase} title="Pipeline activo" color="sky" link="/admin/crm"/>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {data.pipeline.map(p => (
          <div key={p.key} className="surface-elev p-3 print:border print:border-zinc-300">
            <div className={`label-overline text-[9px] text-${STAGE_COLORS[p.key] || "zinc"}-400 print:text-black`}>{p.label}</div>
            <div className="text-xl font-black mt-0.5 print:text-black">{p.count} <span className="text-[10px] text-zinc-500 print:text-black">ops</span></div>
            <div className="text-xs font-mono text-emerald-400 print:text-black mt-0.5">${p.monto.toLocaleString("es-MX")}</div>
          </div>
        ))}
        <div className="surface-elev p-3 bg-amber-500/10 border-amber-500/40 print:bg-zinc-100">
          <div className="label-overline text-[9px] text-amber-400 print:text-black">TOTAL ACTIVO</div>
          <div className="text-xl font-black mt-0.5 text-amber-400 print:text-black">${data.pipeline_total_mxn.toLocaleString("es-MX")}</div>
        </div>
      </div>
    </section>
  );
}

function VisitasBlock({ items, fecha }) {
  return (
    <section className="surface p-4" data-testid="block-visitas">
      <SectionHeader icon={Map} title={`Visitas programadas ${fecha}`} color="sky" count={items.length} link="/admin/ruta-ventas"/>
      {items.length === 0 ? <Empty msg="Sin visitas pendientes para la fecha"/> : (
        <table className="dtable">
          <thead><tr><th>Empresa</th><th>Dirección/Ciudad</th><th>Vendedor</th><th>Briefing</th><th></th></tr></thead>
          <tbody>
            {items.slice(0, 15).map((v, i) => (
              <tr key={i}>
                <td className="font-semibold">{v.empresa}</td>
                <td className="text-xs text-zinc-400 print:text-black">{v.direccion || "—"}</td>
                <td className="text-xs">{v.vendedor || "—"}</td>
                <td className="text-[11px] text-zinc-400 print:text-black">{v.briefing || "—"}</td>
                <td className="text-right">
                  <Link to={`/admin/ruta-ventas?ruta=${v.ruta_id}`} className="text-[10px] text-sky-400 hover:underline print:hidden" data-print-hide>
                    Marcar visita <ExternalLink size={9} className="inline"/>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function FrancotiradorBlock({ items }) {
  return (
    <section className="surface p-4" data-testid="block-francotirador">
      <SectionHeader icon={Crosshair} title="Francotirador DRO · pendientes de contacto" color="amber" count={items.length} link="/admin/francotirador-dro"/>
      {items.length === 0 ? <Empty msg="Sin DROs pendientes"/> : (
        <table className="dtable">
          <thead><tr><th>DRO</th><th>Esp.</th><th>Ubicación</th><th>Contacto</th><th>Etapa</th><th></th></tr></thead>
          <tbody>
            {items.slice(0, 15).map((d) => (
              <tr key={d.id}>
                <td className="font-semibold">{d.nombre}</td>
                <td className="text-[11px] font-mono text-sky-400 print:text-black">{d.especialidad || "—"}</td>
                <td className="text-xs">{d.municipio || "—"}, {d.estado_mx}</td>
                <td className="text-[11px] font-mono">
                  {d.correo_electronico ? <span className="text-emerald-400 print:text-black">{d.correo_electronico}</span>
                   : d.telefono_movil ? <span className="text-sky-400 print:text-black">{d.telefono_movil}</span>
                   : <span className="text-zinc-500 print:text-black">— sin contacto —</span>}
                </td>
                <td className="text-[10px] font-mono text-amber-400 print:text-black">{(d.stage || "").replace(/_/g, " ")}</td>
                <td className="text-right">
                  <Link to="/admin/francotirador-dro" className="text-[10px] text-amber-400 hover:underline print:hidden" data-print-hide>
                    Contactar <ExternalLink size={9} className="inline"/>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function GreenfieldBlock({ items }) {
  return (
    <section className="surface p-4" data-testid="block-greenfield">
      <SectionHeader icon={Satellite} title="Greenfield OSINT · señales últimas 24h" color="emerald" count={items.length} link="/admin/radar-greenfield"/>
      {items.length === 0 ? <Empty msg="Sin señales nuevas"/> : (
        <table className="dtable">
          <thead><tr><th>Señal</th><th>Sector</th><th>Ciudad</th><th>Score</th><th>Monto MXN</th></tr></thead>
          <tbody>
            {items.slice(0, 12).map((g) => (
              <tr key={g.id}>
                <td className="font-semibold text-xs">{g.titulo}</td>
                <td className="text-xs">{g.sector || "—"}</td>
                <td className="text-xs">{g.ciudad || "—"}</td>
                <td className="font-mono text-emerald-400 print:text-black">{g.score}</td>
                <td className="font-mono text-xs">${(g.monto_estimado || 0).toLocaleString("es-MX")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function IntentsBlock({ items }) {
  return (
    <section className="surface p-4" data-testid="block-intents">
      <SectionHeader icon={MessageSquare} title="Escuadrón Conversacional · intents 24h" color="indigo" count={items.length} link="/admin/radar-greenfield"/>
      {items.length === 0 ? <Empty msg="Sin intents nuevos"/> : (
        <table className="dtable">
          <thead><tr><th>Plataforma</th><th>Urgencia</th><th>Mensaje</th><th></th></tr></thead>
          <tbody>
            {items.slice(0, 12).map((i) => (
              <tr key={i.id}>
                <td className="text-[10px] font-mono text-indigo-400 print:text-black uppercase">{i.plataforma}</td>
                <td className="text-[10px] font-mono text-amber-400 print:text-black">{i.urgencia || "—"}</td>
                <td className="text-xs">{(i.mensaje || "").slice(0, 140)}</td>
                <td className="text-right">
                  {i.url && (
                    <a href={i.url} target="_blank" rel="noreferrer" className="text-[10px] text-indigo-400 hover:underline print:hidden" data-print-hide>
                      Ver <ExternalLink size={9} className="inline"/>
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function CotizacionesBlock({ items }) {
  return (
    <section className="surface p-4" data-testid="block-cotizaciones">
      <SectionHeader icon={FileText} title="Cotizaciones esperando seguimiento (14 días)" color="zinc" count={items.length} link="/admin/cotizador"/>
      {items.length === 0 ? <Empty msg="Sin cotizaciones pendientes"/> : (
        <table className="dtable">
          <thead><tr><th>Folio</th><th>Cliente</th><th>Proyecto</th><th>Total</th><th>Estado</th><th></th></tr></thead>
          <tbody>
            {items.slice(0, 12).map((c) => (
              <tr key={c.id}>
                <td className="font-mono text-xs">{c.folio}</td>
                <td className="font-semibold">{c.cliente_nombre}</td>
                <td className="text-xs text-zinc-400 print:text-black">{(c.proyecto_titulo || "").slice(0, 40)}</td>
                <td className="font-mono text-emerald-400 print:text-black">${(c.total || 0).toLocaleString("es-MX")}</td>
                <td className="text-[10px] font-mono uppercase">{c.estado || "enviada"}</td>
                <td className="text-right">
                  <Link to={`/admin/cotizador?cot=${c.id}`} className="text-[10px] text-amber-400 hover:underline print:hidden" data-print-hide>
                    Ver <ExternalLink size={9} className="inline"/>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Empty({ msg }) {
  return <div className="text-center text-zinc-500 text-sm py-6 print:text-black">— {msg} —</div>;
}
