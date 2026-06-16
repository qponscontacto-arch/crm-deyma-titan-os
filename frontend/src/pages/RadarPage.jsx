import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, formatApiError, SECTOR_LABEL } from "../lib/auth";
import { Hotness, ScoreBar, Modal } from "../components/ui-deyma";
import { Sparkles, ExternalLink, Filter, Radar as RadarIcon, ArrowRightCircle } from "lucide-react";

const SOURCE_LABEL = { licitacion: "Licitación", noticia: "Noticia", referencia: "Referencia", prospeccion: "Prospección" };

export default function RadarPage() {
  const [items, setItems] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [sector, setSector] = useState("todos");
  const [scoring, setScoring] = useState(null);
  const [importTarget, setImportTarget] = useState(null);

  const load = async () => {
    const [{ data }, { data: emp }] = await Promise.all([api.get("/radar"), api.get("/empresas")]);
    setItems(data); setEmpresas(emp);
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const list = sector === "todos" ? items : items.filter((p) => p.sector === sector);
    return [...list].sort((a, b) => (b.score || 0) - (a.score || 0));
  }, [items, sector]);

  const scoreOne = async (id) => {
    setScoring(id);
    try { await api.post(`/radar/${id}/score`); await load(); }
    finally { setScoring(null); }
  };

  const scoreAll = async () => {
    for (const p of items) { if (!p.score) await api.post(`/radar/${p.id}/score`); }
    await load();
  };

  return (
    <div className="p-6 space-y-5" data-testid="radar-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Inteligencia de Mercado · Bajío</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Radar de Proyectos</h1>
        </div>
        <button data-testid="score-all-btn" onClick={scoreAll} className="btn-primary flex items-center gap-2"><Sparkles size={14} strokeWidth={2}/> Calificar pendientes</button>
      </div>

      <div className="surface p-3 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-zinc-500" strokeWidth={1.5}/>
        <span className="label-overline">Filtros</span>
        <select data-testid="radar-sector-filter" className="input-field max-w-xs" value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="todos">Todos los sectores</option>
          {Object.entries(SECTOR_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="ml-auto font-mono text-xs text-zinc-500">{filtered.length} proyectos detectados</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((p) => (
          <div key={p.id} className="surface flex flex-col" data-testid={`radar-card-${p.id}`}>
            <div className="relative h-32 overflow-hidden border-b border-white/10">
              <img src={p.score >= 75 ? "https://images.unsplash.com/photo-1623428454599-0b106ed85f67" : "https://images.pexels.com/photos/25461690/pexels-photo-25461690.jpeg"}
                   alt={p.titulo} className="absolute inset-0 w-full h-full object-cover opacity-40" />
              <div className="absolute inset-0 bg-gradient-to-t from-black via-black/30 to-transparent" />
              <div className="absolute top-3 left-3 flex items-center gap-2">
                <Hotness value={p.hotness} />
                <span className="badge text-zinc-300 border-zinc-400/40">{SOURCE_LABEL[p.fuente] || p.fuente}</span>
              </div>
              <div className="absolute bottom-2 right-3 font-mono text-xs text-amber-400">{p.ciudad}, {p.estado}</div>
            </div>
            <div className="p-4 flex-1 flex flex-col gap-3">
              <h3 className="text-sm font-bold leading-tight">{p.titulo}</h3>
              <div className="label-overline text-zinc-400">{SECTOR_LABEL[p.sector]}</div>
              <p className="text-xs text-zinc-400 line-clamp-3">{p.descripcion}</p>
              <div className="mt-auto space-y-2">
                <div className="flex items-baseline justify-between">
                  <span className="label-overline">Monto estimado</span>
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
                <div className="flex items-center gap-2 pt-2">
                  <button data-testid={`radar-score-btn-${p.id}`} onClick={() => scoreOne(p.id)} disabled={scoring === p.id} className="btn-ghost text-[10px] flex items-center gap-1">
                    <Sparkles size={11} strokeWidth={2}/> {scoring === p.id ? "Calificando…" : "Calificar IA"}
                  </button>
                  <button data-testid={`radar-import-btn-${p.id}`} onClick={() => setImportTarget(p)} className="text-[10px] px-2 py-1 border border-amber-500/60 text-amber-400 hover:bg-amber-500/10 flex items-center gap-1 font-bold uppercase tracking-wider" style={{ fontFamily: "Chivo, sans-serif" }}>
                    <ArrowRightCircle size={11} strokeWidth={2}/> Importar al CRM
                  </button>
                  {p.url_fuente && <a href={`https://${p.url_fuente.replace(/^https?:\/\//, "")}`} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 hover:text-sky-300 flex items-center gap-1 ml-auto"><ExternalLink size={10}/>{p.url_fuente}</a>}
                </div>
              </div>
            </div>
          </div>
        ))}
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
