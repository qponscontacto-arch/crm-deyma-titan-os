import React, { useEffect, useState } from "react";
import { api, fmtMXN, formatApiError } from "../lib/auth";
import { Bot, RefreshCw, Sparkles, Clock, Send, AlertTriangle, CheckCircle2 } from "lucide-react";

export default function ScraperPage() {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  const load = async () => {
    const { data } = await api.get("/scraper/status");
    setState(data);
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);

  const run = async (kind) => {
    setBusy(kind); setErr(""); setResult(null);
    try {
      const url = kind === "scrape" ? "/scraper/run"
        : kind === "score" ? "/scraper/score-batch"
        : "/scraper/morning-alert";
      const { data } = await api.post(url);
      setResult({ kind, data });
      await load();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(null); }
  };

  if (!state) return <div className="p-12 label-overline text-amber-400 animate-pulse">Cargando estado del scraper…</div>;

  return (
    <div className="p-6 space-y-5" data-testid="scraper-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Inteligencia Automatizada · GPT-5.2 · 24/7</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Scraper Nocturno</h1>
          <div className="text-xs text-zinc-500 mt-1">Detecta licitaciones de Compranet/Tenders MX y noticias industriales en toda la República Mexicana.</div>
        </div>
      </div>

      <div className="surface p-4 border-l-4 border-l-amber-500">
        <div className="flex items-start gap-3">
          <Clock size={20} className="text-amber-400 mt-0.5" strokeWidth={1.5}/>
          <div className="flex-1">
            <div className="font-bold mb-1">Calendario automático (zona CDMX)</div>
            <div className="text-xs text-zinc-400 leading-relaxed space-y-0.5">
              <div><span className="font-mono text-amber-400">02:00</span> · Scraper escanea Compranet + Tenders MX + noticias industriales → genera 5-8 nuevas oportunidades.</div>
              <div><span className="font-mono text-amber-400">03:00</span> · Batch scoring IA califica todas las oportunidades nuevas (0-100, hot/warm/cold).</div>
              <div><span className="font-mono text-amber-400">08:00</span> · Resumen matutino WhatsApp al Director con top 5 oportunidades HOT detectadas en las últimas 36h.</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ActionCard
          icon={Bot} color="amber" testId="card-scrape"
          title="Ejecutar scraper" subtitle="Detecta nuevas oportunidades ahora"
          lastRun={state.last_scrape} lastStat={`${state.last_scrape_added ?? 0} agregadas`}
          onRun={() => run("scrape")} busy={busy === "scrape"} action="Ejecutar"
        />
        <ActionCard
          icon={Sparkles} color="sky" testId="card-score"
          title="Calificar pendientes" subtitle="Batch scoring IA de items sin score"
          lastRun={state.last_scoring} lastStat={`${state.last_scoring_count ?? 0} calificadas`}
          onRun={() => run("score")} busy={busy === "score"} action="Calificar"
        />
        <ActionCard
          icon={Send} color="orange" testId="card-alert"
          title="Resumen matutino" subtitle="WhatsApp top 5 HOT al Director"
          lastRun={state.last_morning_alert} lastStat={`${(state.last_morning_alert_top || []).length} en top`}
          onRun={() => run("alert")} busy={busy === "alert"} action="Enviar"
        />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Total radar" value={state.radar_total} sub="proyectos" color="text-amber-400"/>
        <StatCard label="Detectados por IA" value={state.radar_auto_scraped} sub="vía scraper nocturno" color="text-sky-400"/>
        <StatCard label="Twilio WhatsApp" value={state.twilio_enabled ? "LIVE" : "MOCK"} sub={state.twilio_enabled ? "envío real" : "log only"} color={state.twilio_enabled ? "text-emerald-400" : "text-amber-400"}/>
        <StatCard label="Errores recientes" value={(state.errors || []).length} sub="ver detalles" color={(state.errors || []).length ? "text-rose-400" : "text-emerald-400"}/>
      </div>

      {result && (
        <div className="surface p-4 border-l-4 border-l-emerald-500" data-testid="scraper-result">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 size={16} className="text-emerald-400" strokeWidth={1.5}/>
            <span className="font-bold text-sm">{result.kind === "scrape" ? "Scraper ejecutado" : result.kind === "score" ? "Scoring completado" : "Resumen enviado"}</span>
          </div>
          {result.kind === "scrape" && (
            <div>
              <div className="text-xs text-zinc-400 mb-2">{result.data.added} nuevas oportunidades agregadas al radar:</div>
              <ul className="space-y-1 text-xs">
                {(result.data.items || []).map((it, i) => (
                  <li key={i} className="terminal-line text-zinc-300">{it.titulo} · <span className="text-amber-400">{it.estado}</span></li>
                ))}
              </ul>
            </div>
          )}
          {result.kind === "score" && <div className="text-xs text-zinc-400">{result.data.scored} oportunidades calificadas por GPT-5.2.</div>}
          {result.kind === "alert" && <div className="text-xs text-zinc-400">Resumen matutino con {result.data.sent} oportunidades enviado vía WhatsApp ({result.data.mock ? "MOCK" : "real"}). Revisa el Centro de Alertas.</div>}
        </div>
      )}

      {(state.last_morning_alert_top || []).length > 0 && (
        <div className="surface p-4">
          <div className="flex items-center gap-2 mb-3">
            <Send size={14} className="text-orange-400" strokeWidth={1.5}/>
            <h3 className="font-bold tracking-tight">Último resumen matutino · Top {state.last_morning_alert_top.length}</h3>
            <span className="font-mono text-[10px] text-zinc-500 ml-auto">{state.last_morning_alert ? new Date(state.last_morning_alert).toLocaleString("es-MX") : "—"}</span>
          </div>
          <div className="space-y-1">
            {state.last_morning_alert_top.map((p, i) => (
              <div key={i} className="surface-elev p-2 flex items-center gap-3">
                <div className="font-mono text-amber-400 font-bold w-8 text-center">#{i + 1}</div>
                <div className="font-mono text-xs px-2 border border-orange-400/40 text-orange-400">{p.score}/100</div>
                <div className="flex-1 min-w-0 text-xs truncate">{p.titulo}</div>
                <div className="text-[10px] text-zinc-500 font-mono">{p.estado}</div>
                <div className="font-mono text-xs text-amber-400">{fmtMXN(p.monto)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(state.errors || []).length > 0 && (
        <div className="surface p-4 border-l-4 border-l-rose-500">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-rose-400" strokeWidth={1.5}/>
            <h3 className="font-bold">Errores recientes del scraper</h3>
          </div>
          <ul className="space-y-1 text-xs font-mono text-rose-300">
            {state.errors.slice(0, 10).map((e, i) => (
              <li key={i}>▸ <span className="text-zinc-500">{e.ts}</span> {e.msg}</li>
            ))}
          </ul>
        </div>
      )}

      {err && <div className="text-rose-400 text-xs">{err}</div>}
    </div>
  );
}

function ActionCard({ icon: Icon, color, title, subtitle, lastRun, lastStat, onRun, busy, action, testId }) {
  const colorMap = { amber: "text-amber-400 border-amber-500/40", sky: "text-sky-400 border-sky-500/40", orange: "text-orange-400 border-orange-500/40" };
  return (
    <div className="surface p-4 flex flex-col gap-3" data-testid={testId}>
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 border ${colorMap[color]} flex items-center justify-center shrink-0`}>
          <Icon size={18} className={`${colorMap[color].split(" ")[0]}`} strokeWidth={1.5}/>
        </div>
        <div className="flex-1">
          <div className="font-bold text-sm">{title}</div>
          <div className="text-[11px] text-zinc-500">{subtitle}</div>
        </div>
      </div>
      <div className="text-[10px] font-mono text-zinc-500">
        <div>Última ejecución: <span className="text-zinc-300">{lastRun ? new Date(lastRun).toLocaleString("es-MX") : "nunca"}</span></div>
        <div>{lastStat}</div>
      </div>
      <button onClick={onRun} disabled={busy} data-testid={`${testId}-btn`} className="btn-primary flex items-center justify-center gap-2 mt-auto">
        {busy ? <><RefreshCw size={12} className="animate-spin"/>Procesando…</> : <>{action}</>}
      </button>
    </div>
  );
}

function StatCard({ label, value, sub, color }) {
  return (
    <div className="surface p-3">
      <div className="label-overline">{label}</div>
      <div className={`font-mono text-2xl mt-1 ${color}`}>{value}</div>
      <div className="text-[10px] text-zinc-500 mt-0.5">{sub}</div>
    </div>
  );
}
