import React, { useEffect, useState } from "react";
import { api, fmtMXN, fmtNum, SECTOR_LABEL, STAGE_LABEL, STAGE_ORDER } from "../lib/auth";
import { KpiCard } from "../components/ui-deyma";
import { Activity, TrendingUp, Flame, FileText, Hammer, Radar, Sparkles, Brain } from "lucide-react";

export default function DashboardPage() {
  const [k, setK] = useState(null);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [forecast, setForecast] = useState(null);
  const [forecastLoading, setForecastLoading] = useState(false);

  useEffect(() => { api.get("/dashboard/kpis").then((r) => setK(r.data)); }, []);

  const generateSummary = async () => {
    setSummaryLoading(true);
    try { const { data } = await api.get("/dashboard/executive-summary"); setSummary(data); }
    catch (e) { setSummary({ summary: "Error al generar resumen: " + (e?.response?.data?.detail || e.message) }); }
    finally { setSummaryLoading(false); }
  };

  const generateForecast = async () => {
    setForecastLoading(true);
    try { const { data } = await api.get("/dashboard/forecast"); setForecast(data); }
    catch (e) { setForecast({ narrative: "Error: " + (e?.response?.data?.detail || e.message) }); }
    finally { setForecastLoading(false); }
  };

  if (!k) return <Loading />;
  const maxStage = Math.max(1, ...Object.values(k.by_stage).map((s) => s.monto));

  return (
    <div className="p-6 space-y-6" data-testid="dashboard-page">
      <Header />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard testId="kpi-pipeline" label="Pipeline activo" value={fmtMXN(k.pipeline_total)} sub={`${k.total_oportunidades} oportunidades`} accent="amber" icon={Activity} />
        <KpiCard testId="kpi-forecast" label="Forecast ponderado" value={fmtMXN(k.forecast_ponderado)} sub="Probabilidad × monto" accent="blue" icon={TrendingUp} />
        <KpiCard testId="kpi-hot" label="Oportunidades HOT" value={fmtNum(k.hot_ops_count)} sub="Score ≥ 75" accent="red" icon={Flame} />
        <KpiCard testId="kpi-conversion" label="Conversión" value={`${k.conversion_rate}%`} sub={`Ingresos: ${fmtMXN(k.ingresos_ganados)}`} accent="green" icon={TrendingUp} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard testId="kpi-cot-mes" label="Cotizaciones del mes" value={fmtNum(k.cotizaciones_mes)} sub={fmtMXN(k.cotizaciones_mes_monto)} accent="gray" icon={FileText} />
        <KpiCard testId="kpi-obras" label="Obras activas" value={fmtNum(k.obras_activas)} sub={fmtMXN(k.obras_activas_monto)} accent="amber" icon={Hammer} />
        <KpiCard testId="kpi-radar" label="Proyectos en radar" value={fmtNum(k.radar_count)} sub={`${k.radar_hot} hot`} accent="blue" icon={Radar} />
        <KpiCard testId="kpi-ingresos" label="Ingresos ganados (YTD)" value={fmtMXN(k.ingresos_ganados)} sub="Oportunidades cerradas" accent="green" icon={TrendingUp} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="surface p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold tracking-tight">Pipeline por etapa</h3>
            <span className="label-overline">Monto MXN</span>
          </div>
          <div className="space-y-2">
            {STAGE_ORDER.map((s) => {
              const row = k.by_stage[s] || { count: 0, monto: 0 };
              const pct = (row.monto / maxStage) * 100;
              return (
                <div key={s} className="flex items-center gap-3" data-testid={`stage-row-${s}`}>
                  <div className="w-32 text-xs label-overline shrink-0">{STAGE_LABEL[s]}</div>
                  <div className="flex-1 h-6 bg-white/5 relative">
                    <div className={`h-full ${stageColor(s)}`} style={{ width: `${pct}%` }} />
                    <div className="absolute inset-0 flex items-center justify-between px-2 font-mono text-[11px]">
                      <span className="text-zinc-300">{row.count} ops</span>
                      <span className="text-zinc-200">{fmtMXN(row.monto)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="surface p-5">
          <h3 className="font-bold tracking-tight mb-4">Pipeline por sector</h3>
          <div className="space-y-3">
            {Object.entries(k.by_sector).sort((a, b) => b[1] - a[1]).map(([s, m]) => (
              <div key={s} data-testid={`sector-row-${s}`}>
                <div className="flex justify-between text-xs mb-1">
                  <span>{SECTOR_LABEL[s] || s}</span>
                  <span className="font-mono text-amber-400">{fmtMXN(m)}</span>
                </div>
                <div className="h-1 bg-white/10"><div className="h-full bg-amber-500" style={{ width: `${Math.min(100, m / k.pipeline_total * 100 || 0)}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="surface p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-amber-400" strokeWidth={1.5} />
              <h3 className="font-bold tracking-tight">Resumen ejecutivo IA</h3>
            </div>
            <button data-testid="generate-summary-btn" onClick={generateSummary} disabled={summaryLoading} className="btn-ghost">
              {summaryLoading ? "Generando…" : "Generar"}
            </button>
          </div>
          {summary ? (
            <div className="space-y-2">
              <p className="text-sm leading-relaxed text-zinc-300 whitespace-pre-wrap" data-testid="summary-text">{summary.summary}</p>
              {summary.generated_at && <div className="font-mono text-[10px] text-zinc-500">Generado: {new Date(summary.generated_at).toLocaleString("es-MX")}</div>}
            </div>
          ) : (
            <div className="text-xs text-zinc-500 font-mono terminal-line">Solicita un análisis del pipeline al modelo GPT-5.2 vía Emergent.</div>
          )}
        </div>

        <div className="surface p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain size={16} className="text-sky-400" strokeWidth={1.5} />
              <h3 className="font-bold tracking-tight">Pronóstico de cierre</h3>
            </div>
            <button data-testid="generate-forecast-btn" onClick={generateForecast} disabled={forecastLoading} className="btn-ghost">
              {forecastLoading ? "Calculando…" : "Calcular"}
            </button>
          </div>
          {forecast ? (
            <div className="space-y-3" data-testid="forecast-text">
              <div className="font-mono text-3xl text-sky-400">{fmtMXN(forecast.forecast_amount)}</div>
              <div className="label-overline">Confianza: <span className="text-zinc-200">{(forecast.confidence || "").toUpperCase()}</span></div>
              <p className="text-sm leading-relaxed text-zinc-300 whitespace-pre-wrap">{forecast.narrative}</p>
            </div>
          ) : (
            <div className="text-xs text-zinc-500 font-mono terminal-line">Predicción ponderada del cierre trimestral basada en pipeline activo.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function stageColor(s) {
  return ({
    prospeccion: "bg-zinc-500",
    calificada: "bg-sky-500",
    propuesta: "bg-blue-500",
    negociacion: "bg-amber-500",
    ganada: "bg-emerald-500",
    perdida: "bg-rose-500/70",
  })[s] || "bg-zinc-500";
}

function Header() {
  const now = new Date().toLocaleDateString("es-MX", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
  return (
    <div className="divider pb-4 flex items-end justify-between">
      <div>
        <div className="label-overline text-amber-400">Centro de Control · Director General</div>
        <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Dashboard</h1>
      </div>
      <div className="font-mono text-xs text-zinc-500 hidden md:block">▸ {now.toUpperCase()}</div>
    </div>
  );
}

function Loading() {
  return (
    <div className="p-12 text-center">
      <div className="label-overline text-amber-400 animate-pulse">Cargando datos del radar…</div>
    </div>
  );
}
