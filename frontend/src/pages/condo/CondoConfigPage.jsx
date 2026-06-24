import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/auth";
import {
  Settings, Save, Play, Loader2, CheckCircle2, AlertOctagon,
  Bot, Radar, Zap, Search, Crown,
} from "lucide-react";

function ArrayEditor({ label, items, onChange, placeholder, mono = false }) {
  return (
    <div>
      <label className="label-overline mb-2 block">{label}</label>
      <div className="space-y-2">
        {(items || []).map((it, i) => (
          <div key={i} className="flex gap-2">
            <input className={`input-field flex-1 ${mono ? "font-mono text-[11px]" : ""}`}
                   value={it} onChange={(e) => {
                     const arr = [...items]; arr[i] = e.target.value; onChange(arr);
                   }}/>
            <button onClick={() => onChange(items.filter((_, idx) => idx !== i))}
                    className="btn-ghost text-xs text-rose-400 hover:text-rose-300">✕</button>
          </div>
        ))}
        <button onClick={() => onChange([...(items || []), ""])}
                className="btn-ghost text-xs" data-testid={`add-${label.toLowerCase().replace(/\s/g, "-")}`}>
          + Agregar
        </button>
      </div>
      {placeholder && <div className="text-[10px] text-zinc-500 mt-1 font-mono">Ej: {placeholder}</div>}
    </div>
  );
}


export default function CondoConfigPage() {
  const [cfg, setCfg] = useState(null);
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    try {
      const [c, s] = await Promise.all([api.get("/condo/config"), api.get("/condo/stats")]);
      setCfg(c.data);
      setStats(s.data);
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setBusy(true);
    try {
      const body = {
        ciudades: cfg.ciudades,
        keywords_contactos: cfg.keywords_contactos,
        keywords_quejas: cfg.keywords_quejas,
        keywords_grupos: cfg.keywords_grupos,
        min_casas_mega: parseInt(cfg.min_casas_mega, 10) || 200,
        activo: cfg.activo,
      };
      await api.patch("/condo/config", body);
      setNotice({ kind: "ok", msg: "✓ Configuración guardada" });
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setBusy(false); }
  };

  const runAll = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/condo/run");
      const total = (data.sabueso?.inserted || 0) + (data.analista?.inserted || 0) + (data.infiltrado?.inserted || 0);
      setNotice({ kind: "ok", msg: `✓ Pipeline completa: ${total} nuevos registros entre los 3 agentes` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setRunning(false); }
  };

  const seedQro = async () => {
    if (!window.confirm("¿Cargar los 12 mega-condominios curados de Querétaro como base inicial?")) return;
    setRunning(true);
    try {
      const { data } = await api.post("/condo/seed-mega");
      setNotice({ kind: "ok", msg: `✓ Seed Querétaro: ${data.inserted} nuevos · ${data.updated} actualizados` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setRunning(false); }
  };

  if (!cfg) return (
    <div className="p-8 text-center text-zinc-500"><Loader2 size={16} className="inline animate-spin mr-2"/>Cargando configuración…</div>
  );

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6" data-testid="condo-config-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Settings size={11}/> V6.0 · Radar de Condominios · Configuración
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Configuración de Agentes
          </h1>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={seedQro} disabled={running} className="btn-ghost text-xs disabled:opacity-50" data-testid="btn-seed-qro">
            <Crown size={12} className="inline mr-1"/>Seed Mega QRO
          </button>
          <button onClick={runAll} disabled={running} className="btn-ghost text-xs disabled:opacity-50" data-testid="btn-run-all">
            {running ? <Loader2 size={12} className="inline mr-1 animate-spin"/> : <Play size={12} className="inline mr-1"/>}
            Ejecutar TODO
          </button>
          <button onClick={save} disabled={busy} className="btn-primary text-xs disabled:opacity-50" data-testid="btn-save-config">
            {busy ? <Loader2 size={12} className="inline mr-1 animate-spin"/> : <Save size={12} className="inline mr-1"/>}
            Guardar
          </button>
        </div>
      </header>

      {notice && (
        <div className={`surface p-3 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5"
                                                   : "border-rose-500 bg-rose-500/5"}`} data-testid="config-notice">
          <div className="flex items-start justify-between gap-2">
            <div className={`text-sm ${notice.kind === "ok" ? "text-emerald-400" : "text-rose-400"}`}>
              {notice.kind === "ok" ? <CheckCircle2 size={14} className="inline mr-2"/> : <AlertOctagon size={14} className="inline mr-2"/>}
              {notice.msg}
            </div>
            <button onClick={() => setNotice(null)} className="text-zinc-500 hover:text-zinc-300">✕</button>
          </div>
        </div>
      )}

      {/* Stats Dashboard */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="condo-stats">
          <div className="surface p-3">
            <div className="label-overline text-[9px] text-amber-400 flex items-center gap-1"><Bot size={9}/>Sabueso</div>
            <div className="text-2xl font-black mt-1">{stats.leads_total}</div>
            <div className="text-[10px] text-zinc-500">leads detectados</div>
          </div>
          <div className="surface p-3">
            <div className="label-overline text-[9px] text-rose-400 flex items-center gap-1"><Zap size={9}/>Analista</div>
            <div className="text-2xl font-black mt-1">{stats.alertas_total}</div>
            <div className="text-[10px] text-rose-400">{stats.alertas_alto} urgencia alta</div>
          </div>
          <div className="surface p-3">
            <div className="label-overline text-[9px] text-sky-400 flex items-center gap-1"><Search size={9}/>Infiltrado</div>
            <div className="text-2xl font-black mt-1">{stats.grupos_total}</div>
            <div className="text-[10px] text-emerald-400">{stats.grupos_whatsapp} WhatsApp</div>
          </div>
          <div className="surface p-3">
            <div className="label-overline text-[9px] text-amber-400 flex items-center gap-1"><Radar size={9}/>Mega</div>
            <div className="text-2xl font-black mt-1">{stats.leads_mega}</div>
            <div className="text-[10px] text-zinc-500">+200 casas</div>
          </div>
        </div>
      )}

      {stats && (
        <div className={`surface p-3 text-xs flex items-center justify-between flex-wrap gap-2 ${stats.osint_live ? "border-l-4 border-emerald-500" : "border-l-4 border-amber-500"}`}>
          <div>
            <strong className={stats.osint_live ? "text-emerald-400" : "text-amber-400"}>
              {stats.osint_live ? "🟢 OSINT LIVE" : "🟡 OSINT MOCK"}
            </strong>
            <span className="text-zinc-400 ml-2">
              {stats.osint_live ? "Apify activo. Agentes consumen API real." : "Configura APIFY_TOKEN y OSINT_MODE=live."}
            </span>
          </div>
          {stats.ultima_corrida && (
            <div className="text-zinc-500 font-mono">
              Última corrida: {stats.ultima_corrida.slice(0, 16).replace("T", " ")}
            </div>
          )}
        </div>
      )}

      <div className="surface p-5 space-y-4">
        <div className="flex items-center gap-3">
          <input type="checkbox" id="activo" checked={!!cfg.activo}
                 onChange={(e) => setCfg({ ...cfg, activo: e.target.checked })}
                 className="w-4 h-4" data-testid="cfg-activo"/>
          <label htmlFor="activo" className="text-sm">
            <strong>Cron automático activo</strong>
            <span className="text-zinc-500 ml-2 text-xs">— corre los 3 agentes diario a las 04:00 CDMX</span>
          </label>
        </div>

        <div>
          <label className="label-overline">Umbral Mega-Condominio (mínimo de casas)</label>
          <input type="number" className="input-field w-32 font-mono mt-2"
                 value={cfg.min_casas_mega}
                 onChange={(e) => setCfg({ ...cfg, min_casas_mega: e.target.value })}
                 data-testid="cfg-mega"/>
        </div>
      </div>

      <div className="surface p-5">
        <h2 className="text-sm font-bold mb-3 text-amber-400">📍 Ciudades / Geo target</h2>
        <ArrayEditor label="Ciudades" items={cfg.ciudades}
                     onChange={(v) => setCfg({ ...cfg, ciudades: v })}
                     placeholder="Querétaro"/>
      </div>

      <div className="surface p-5">
        <h2 className="text-sm font-bold mb-3 text-amber-400 flex items-center gap-2">
          <Bot size={14}/> Agente Sabueso — Keywords de contactos
        </h2>
        <ArrayEditor label="Keywords para encontrar administradores" items={cfg.keywords_contactos}
                     onChange={(v) => setCfg({ ...cfg, keywords_contactos: v })}
                     placeholder="administrador de condominio"/>
      </div>

      <div className="surface p-5">
        <h2 className="text-sm font-bold mb-3 text-rose-400 flex items-center gap-2">
          <Zap size={14}/> Agente Analista — Keywords de dolor
        </h2>
        <ArrayEditor label="Keywords para detectar quejas (CFE/CEA/mantenimiento)" items={cfg.keywords_quejas}
                     onChange={(v) => setCfg({ ...cfg, keywords_quejas: v })}
                     placeholder="sin luz, CFE, fuga de agua"/>
      </div>

      <div className="surface p-5">
        <h2 className="text-sm font-bold mb-3 text-sky-400 flex items-center gap-2">
          <Search size={14}/> Agente Infiltrado — Google Dorks
        </h2>
        <ArrayEditor label="Dorks para grupos WhatsApp/Telegram" items={cfg.keywords_grupos}
                     onChange={(v) => setCfg({ ...cfg, keywords_grupos: v })}
                     placeholder='site:facebook.com "chat.whatsapp.com" "vecinos"' mono/>
      </div>
    </div>
  );
}
