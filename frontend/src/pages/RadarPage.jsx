import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, formatApiError, SECTOR_LABEL } from "../lib/auth";
import { Hotness, ScoreBar, Modal } from "../components/ui-deyma";
import { Sparkles, ExternalLink, Filter, Radar as RadarIcon, ArrowRightCircle, Satellite, Package, Zap, RefreshCw } from "lucide-react";

const SOURCE_LABEL = { licitacion: "Licitación", noticia: "Noticia", referencia: "Referencia", prospeccion: "Prospección", "OSINT-Greenfield": "OSINT-Greenfield" };

const URGENCIA_BADGE = {
  alto: { color: "bg-rose-500 text-white", label: "URGENCIA ALTA" },
  medio: { color: "bg-amber-500 text-black", label: "URGENCIA MEDIA" },
  bajo: { color: "bg-zinc-500 text-white", label: "URGENCIA BAJA" },
};

export default function RadarPage() {
  const [items, setItems] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [sector, setSector] = useState("todos");
  const [filtroGF, setFiltroGF] = useState("todos"); // todos | solo_greenfield | sin_greenfield
  const [scoring, setScoring] = useState(null);
  const [importTarget, setImportTarget] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    const [{ data }, { data: emp }] = await Promise.all([api.get("/radar"), api.get("/empresas")]);
    setItems(data); setEmpresas(emp);
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    let list = sector === "todos" ? items : items.filter((p) => p.sector === sector);
    if (filtroGF === "solo_greenfield") list = list.filter((p) => p.is_greenfield);
    if (filtroGF === "sin_greenfield") list = list.filter((p) => !p.is_greenfield);
    return [...list].sort((a, b) => {
      // Greenfield URGENTE primero, luego score
      const ag = a.is_greenfield && a.greenfield_urgencia === "alto" ? 1000 : 0;
      const bg = b.is_greenfield && b.greenfield_urgencia === "alto" ? 1000 : 0;
      return (bg + (b.score || 0)) - (ag + (a.score || 0));
    });
  }, [items, sector, filtroGF]);

  // Métricas Greenfield → Pipeline canastillas
  const gfStats = useMemo(() => {
    const gf = items.filter((p) => p.is_greenfield);
    return {
      total: gf.length,
      altas: gf.filter((p) => p.greenfield_urgencia === "alto").length,
      piezas: gf.reduce((s, p) => s + (p.canastillas_estimadas || 0), 0),
      monto: gf.reduce((s, p) => s + (p.canastillas_monto_estimado || 0), 0),
    };
  }, [items]);

  const scoreOne = async (id) => {
    setScoring(id);
    try { await api.post(`/radar/${id}/score`); await load(); }
    finally { setScoring(null); }
  };

  const scoreAll = async () => {
    for (const p of items) { if (!p.score) await api.post(`/radar/${p.id}/score`); }
    await load();
  };

  const resyncGreenfield = async () => {
    if (syncing) return;
    setSyncing(true);
    try {
      const { data } = await api.post("/greenfield/resincronizar-radar");
      alert(`✓ Sincronizado: ${data.proyectadas_nuevas} nuevas, ${data.actualizadas} actualizadas`);
      await load();
    } catch (e) { alert(formatApiError(e)); }
    finally { setSyncing(false); }
  };

  return (
    <div className="p-6 space-y-5" data-testid="radar-page">
      <div className="divider pb-4 flex items-end justify-between flex-wrap gap-3">
        <div>
          <div className="label-overline text-amber-400">Inteligencia de Mercado · Bajío · Canastillas Industriales</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Radar de Proyectos</h1>
        </div>
        <div className="flex items-center gap-2">
          <button data-testid="radar-resync-greenfield" onClick={resyncGreenfield} disabled={syncing}
                  className="text-xs border border-emerald-500/60 text-emerald-400 hover:bg-emerald-500/10 px-3 py-2 flex items-center gap-2 font-bold uppercase tracking-wider"
                  style={{ fontFamily: "Chivo, sans-serif" }}>
            <RefreshCw size={12} strokeWidth={2} className={syncing ? "animate-spin" : ""}/>
            {syncing ? "Sincronizando…" : "Sincronizar Greenfield"}
          </button>
          <button data-testid="score-all-btn" onClick={scoreAll} className="btn-primary flex items-center gap-2"><Sparkles size={14} strokeWidth={2}/> Calificar pendientes</button>
        </div>
      </div>

      {/* Métricas Greenfield → Canastillas */}
      {gfStats.total > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="radar-gf-metrics">
          <div className="surface p-3 border-l-2 border-emerald-500">
            <div className="flex items-center gap-2"><Satellite size={12} className="text-emerald-400"/><div className="label-overline text-[10px]">Leads Greenfield</div></div>
            <div className="text-2xl font-black font-mono text-emerald-400 mt-1">{gfStats.total}</div>
          </div>
          <div className="surface p-3 border-l-2 border-rose-500">
            <div className="flex items-center gap-2"><Zap size={12} className="text-rose-400"/><div className="label-overline text-[10px]">Urgencia ALTA</div></div>
            <div className="text-2xl font-black font-mono text-rose-400 mt-1">{gfStats.altas}</div>
          </div>
          <div className="surface p-3 border-l-2 border-sky-500">
            <div className="flex items-center gap-2"><Package size={12} className="text-sky-400"/><div className="label-overline text-[10px]">Canastillas estimadas</div></div>
            <div className="text-2xl font-black font-mono text-sky-400 mt-1">{gfStats.piezas}</div>
          </div>
          <div className="surface p-3 border-l-2 border-amber-500">
            <div className="flex items-center gap-2"><div className="text-amber-400 text-sm">$</div><div className="label-overline text-[10px]">Ingreso 12m</div></div>
            <div className="text-2xl font-black font-mono text-amber-400 mt-1">{fmtMXN(gfStats.monto)}</div>
          </div>
        </div>
      )}

      <div className="surface p-3 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-zinc-500" strokeWidth={1.5}/>
        <span className="label-overline">Filtros</span>
        <select data-testid="radar-gf-filter" className="input-field !w-auto text-xs" value={filtroGF} onChange={(e) => setFiltroGF(e.target.value)}>
          <option value="todos">Todos los proyectos</option>
          <option value="solo_greenfield">🛰️ Solo Greenfield OSINT</option>
          <option value="sin_greenfield">Solo radar tradicional</option>
        </select>
        <select data-testid="radar-sector-filter" className="input-field max-w-xs" value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="todos">Todos los sectores</option>
          {Object.entries(SECTOR_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="ml-auto font-mono text-xs text-zinc-500">{filtered.length} proyectos detectados</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((p) => {
          const isGF = p.is_greenfield;
          const urg = isGF && p.greenfield_urgencia ? URGENCIA_BADGE[p.greenfield_urgencia] : null;
          return (
          <div key={p.id} className={`surface flex flex-col relative ${isGF ? "ring-1 ring-emerald-500/40" : ""}`} data-testid={`radar-card-${p.id}`}>
            {/* Banderín GREENFIELD */}
            {isGF && (
              <div className="absolute top-0 right-0 z-10 bg-emerald-500 text-black font-black text-[9px] tracking-widest px-2 py-1 flex items-center gap-1"
                   style={{ fontFamily: "Chivo, sans-serif" }} data-testid={`radar-gf-badge-${p.id}`}>
                <Satellite size={10} /> GREENFIELD OSINT
              </div>
            )}
            <div className="relative h-32 overflow-hidden border-b border-white/10">
              <img src={p.score >= 75 ? "https://images.unsplash.com/photo-1623428454599-0b106ed85f67" : "https://images.pexels.com/photos/25461690/pexels-photo-25461690.jpeg"}
                   alt={p.titulo} className="absolute inset-0 w-full h-full object-cover opacity-40" />
              <div className="absolute inset-0 bg-gradient-to-t from-black via-black/30 to-transparent" />
              <div className="absolute top-3 left-3 flex items-center gap-2 flex-wrap">
                <Hotness value={p.hotness} />
                <span className="badge text-zinc-300 border-zinc-400/40">{SOURCE_LABEL[p.fuente] || p.fuente}</span>
                {urg && (
                  <span className={`text-[8px] font-black tracking-widest px-1.5 py-0.5 ${urg.color}`}
                        data-testid={`radar-gf-urg-${p.id}`}>
                    {urg.label}
                  </span>
                )}
              </div>
              <div className="absolute bottom-2 right-3 font-mono text-xs text-amber-400">{p.ciudad}, {p.estado}</div>
            </div>
            <div className="p-4 flex-1 flex flex-col gap-3">
              <h3 className="text-sm font-bold leading-tight">{p.titulo}</h3>
              <div className="label-overline text-zinc-400">{SECTOR_LABEL[p.sector]}</div>
              {/* Banner CANASTILLAS para Greenfield */}
              {isGF && p.canastillas_estimadas > 0 && (
                <div className="bg-emerald-500/10 border border-emerald-500/30 p-2 flex items-center justify-between" data-testid={`radar-canastillas-${p.id}`}>
                  <div className="flex items-center gap-2">
                    <Package size={12} className="text-emerald-400" />
                    <span className="text-xs font-mono text-emerald-300">
                      <span className="text-emerald-400 font-bold">{p.canastillas_estimadas}</span> canastillas / 12m
                    </span>
                  </div>
                  <span className="text-xs font-mono text-emerald-400 font-bold">
                    {fmtMXN(p.canastillas_monto_estimado)}
                  </span>
                </div>
              )}
              <p className="text-xs text-zinc-400 line-clamp-3">{p.descripcion}</p>
              <div className="mt-auto space-y-2">
                <div className="flex items-baseline justify-between">
                  <span className="label-overline">Monto proyecto</span>
                  <span className="font-mono text-amber-400 text-base">{fmtMXN(p.monto_estimado)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="label-overline">AI Score</span>
                  <ScoreBar value={p.score || 0} />
                </div>
                {p.score_reasons?.length > 0 && (
                  <ul className="space-y-1 text-[11px] text-zinc-400 pt-1">
                    {p.score_reasons.slice(0, 3).map((r, i) => <li key={i} className="terminal-line">{r}</li>)}
                  </ul>
                )}
                <div className="flex items-center gap-2 pt-2 flex-wrap">
                  <button data-testid={`radar-score-btn-${p.id}`} onClick={() => scoreOne(p.id)} disabled={scoring === p.id} className="btn-ghost text-[10px] flex items-center gap-1">
                    <Sparkles size={11} strokeWidth={2}/> {scoring === p.id ? "Calificando…" : "Calificar IA"}
                  </button>
                  <button data-testid={`radar-import-btn-${p.id}`} onClick={() => setImportTarget(p)} className={`text-[10px] px-2 py-1 border flex items-center gap-1 font-bold uppercase tracking-wider ${isGF ? "border-emerald-500/60 text-emerald-400 hover:bg-emerald-500/10" : "border-amber-500/60 text-amber-400 hover:bg-amber-500/10"}`} style={{ fontFamily: "Chivo, sans-serif" }}>
                    <ArrowRightCircle size={11} strokeWidth={2}/> Importar al CRM
                  </button>
                  {isGF && (
                    <a href="/admin/radar-greenfield" className="text-[10px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1" title="Ver embudo Greenfield">
                      <Satellite size={10}/> Embudo OSINT
                    </a>
                  )}
                  {p.url_fuente && <a href={`https://${p.url_fuente.replace(/^https?:\/\//, "")}`} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 hover:text-sky-300 flex items-center gap-1 ml-auto"><ExternalLink size={10}/>fuente</a>}
                </div>
              </div>
            </div>
          </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="col-span-full surface p-12 text-center">
            <RadarIcon size={40} strokeWidth={1} className="mx-auto text-zinc-700 mb-3"/>
            <div className="text-zinc-400">Sin proyectos para este filtro</div>
          </div>
        )}
      </div>

      <ImportarModal target={importTarget} empresas={empresas} onClose={() => setImportTarget(null)} onDone={() => { setImportTarget(null); load(); }} />
    </div>
  );
}

function ImportarModal({ target, empresas, onClose, onDone }) {
  const [modo, setModo] = useState("crm"); // "crm" | "nueva"
  const [empresaId, setEmpresaId] = useState("");
  // Nueva empresa
  const [nNombre, setNNombre] = useState("");
  const [nRfc, setNRfc] = useState("");
  const [nSitio, setNSitio] = useState("");
  const [nNotas, setNNotas] = useState("");
  const [cNombre, setCNombre] = useState("");
  const [cPuesto, setCPuesto] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cTel, setCTel] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    setModo("crm"); setEmpresaId(""); setErr("");
    setNNombre(""); setNRfc(""); setNSitio(""); setNNotas("");
    setCNombre(""); setCPuesto(""); setCEmail(""); setCTel("");
  }, [target]);

  if (!target) return null;

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const payload = { probabilidad: 25, stage: "prospeccion" };
      if (modo === "crm") {
        if (!empresaId) throw new Error("Selecciona una empresa del CRM");
        payload.empresa_id = empresaId;
      } else {
        if (!nNombre.trim()) throw new Error("Captura el nombre de la empresa nueva");
        payload.nueva_empresa = {
          nombre: nNombre.trim(),
          rfc: nRfc.trim() || null,
          sitio_web: nSitio.trim() || null,
          notas: nNotas.trim() || null,
          contacto_nombre: cNombre.trim() || null,
          contacto_puesto: cPuesto.trim() || null,
          contacto_email: cEmail.trim() || null,
          contacto_telefono: cTel.trim() || null,
        };
      }
      await api.post(`/radar/${target.id}/importar`, payload);
      onDone();
      alert(`Proyecto "${target.titulo}" importado al CRM como oportunidad en prospección.`);
    } catch (e) { setErr(e?.message || formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={!!target} onClose={onClose} title="Importar al CRM" testId="importar-radar-modal" size="lg">
      <form onSubmit={submit} className="space-y-4">
        <div className="surface-elev p-3">
          <div className="label-overline">Proyecto</div>
          <div className="font-semibold text-sm">{target.titulo}</div>
          <div className="text-xs text-zinc-400 mt-1">{SECTOR_LABEL[target.sector]} · {target.ciudad}, {target.estado}</div>
          <div className="font-mono text-amber-400 mt-1">{fmtMXN(target.monto_estimado)}</div>
        </div>

        <div>
          <label className="label-overline">Empresa</label>
          <div className="grid grid-cols-2 gap-2 mt-1">
            <button
              type="button"
              data-testid="radar-modo-crm"
              onClick={() => setModo("crm")}
              className={`p-2.5 border text-xs label-overline ${modo === "crm" ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}
            >
              📇 Empresa del CRM
            </button>
            <button
              type="button"
              data-testid="radar-modo-nueva"
              onClick={() => setModo("nueva")}
              className={`p-2.5 border text-xs label-overline ${modo === "nueva" ? "border-sky-500 bg-sky-500/10 text-sky-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}
            >
              ➕ Crear empresa nueva
            </button>
          </div>
        </div>

        {modo === "crm" ? (
          <div>
            <label className="label-overline">Asignar a empresa</label>
            <select data-testid="importar-empresa-select" className="input-field" value={empresaId} onChange={(e) => setEmpresaId(e.target.value)}>
              <option value="">Selecciona una empresa…</option>
              {empresas.map((emp) => <option key={emp.id} value={emp.id}>{emp.nombre}</option>)}
            </select>
            <div className="text-[10px] text-zinc-500 mt-1 font-mono">Se creará una oportunidad en etapa "Prospección" con probabilidad 25%.</div>
          </div>
        ) : (
          <div className="border border-sky-500/30 bg-sky-500/5 p-3 space-y-3" data-testid="radar-nueva-block">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="label-overline">Razón social / Nombre <span className="text-rose-400">*</span></label>
                <input data-testid="radar-nueva-nombre" required className="input-field" value={nNombre} onChange={(e) => setNNombre(e.target.value)} placeholder="Ej. Constructora ABC S.A. de C.V." />
              </div>
              <div>
                <label className="label-overline">RFC (opcional)</label>
                <input data-testid="radar-nueva-rfc" className="input-field font-mono uppercase" value={nRfc} onChange={(e) => setNRfc(e.target.value.toUpperCase())} placeholder="XAXX010101000" maxLength={13} />
              </div>
              <div>
                <label className="label-overline">Sitio web (opcional)</label>
                <input data-testid="radar-nueva-sitio" className="input-field" value={nSitio} onChange={(e) => setNSitio(e.target.value)} placeholder="https://" />
              </div>
              <div className="col-span-2">
                <label className="label-overline">Notas internas (opcional)</label>
                <textarea data-testid="radar-nueva-notas" className="input-field" style={{ height: 50 }} value={nNotas} onChange={(e) => setNNotas(e.target.value)} placeholder="Cómo se identificó, recomendado por…" />
              </div>
            </div>
            <div className="border-t border-sky-500/20 pt-3">
              <div className="label-overline text-sky-400 mb-2">Contacto principal (opcional)</div>
              <div className="grid grid-cols-2 gap-3">
                <input data-testid="radar-nueva-cont-nombre" className="input-field" value={cNombre} onChange={(e) => setCNombre(e.target.value)} placeholder="Nombre completo" />
                <input data-testid="radar-nueva-cont-puesto" className="input-field" value={cPuesto} onChange={(e) => setCPuesto(e.target.value)} placeholder="Puesto / Cargo" />
                <input data-testid="radar-nueva-cont-email" type="email" className="input-field" value={cEmail} onChange={(e) => setCEmail(e.target.value)} placeholder="correo@empresa.com" />
                <input data-testid="radar-nueva-cont-tel" className="input-field font-mono" value={cTel} onChange={(e) => setCTel(e.target.value)} placeholder="442-123-4567" />
              </div>
            </div>
            <div className="text-[10px] font-mono text-zinc-500">
              💡 La empresa nueva quedará en el CRM con sector <span className="text-amber-400">{SECTOR_LABEL[target.sector]}</span> y ciudad <span className="text-amber-400">{target.ciudad}, {target.estado}</span>. Después podrás editarla en /admin/crm.
            </div>
          </div>
        )}

        {err && <div className="text-rose-400 text-xs" data-testid="radar-import-error">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="importar-submit-btn" disabled={busy} className="btn-primary">{busy ? "Importando…" : "Importar al CRM"}</button>
        </div>
      </form>
    </Modal>
  );
}
