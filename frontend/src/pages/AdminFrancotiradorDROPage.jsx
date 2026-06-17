import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../lib/auth";
import { Modal } from "../components/ui-deyma";
import {
  Crosshair, Play, Loader2, Phone, Mail, MapPin, Workflow, Users,
  ExternalLink, Trash2, MessageCircle, Send, Copy, Edit3, FileText,
  CheckCircle2, AlertOctagon, Target,
} from "lucide-react";

// Etapas del embudo Francotirador (alineadas con backend DRO_STAGE_LABEL)
const STAGES = [
  { key: "blanco_detectado",    label: "Blanco Detectado",   color: "zinc",     prob: 10 },
  { key: "kit_cad_enviado",     label: "Kit CAD Enviado",    color: "sky",      prob: 25 },
  { key: "interaccion_tecnica", label: "Interacción Técnica",color: "indigo",   prob: 45 },
  { key: "prescriptor_activo",  label: "Prescriptor Activo", label_short: "Prescriptor", color: "amber", prob: 70 },
  { key: "cierre_obra_ganada",  label: "Cierre Obra Ganada", color: "emerald",  prob: 100 },
  { key: "descartado",          label: "Descartado",         color: "rose",     prob: 0 },
];

export default function AdminFrancotiradorDROPage() {
  const [tab, setTab] = useState("padron");
  const [reloadKey, setReloadKey] = useState(0);
  const triggerReload = () => setReloadKey((x) => x + 1);

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto" data-testid="francotirador-dro-page">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Crosshair size={11} /> V5.2 · Operación Francotirador
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Padrón <span className="text-amber-400">DRO</span> · Prescriptores Técnicos
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Directores Responsables de Obra · Bajío · 2 agentes (gob.mx + colegios) · cron 06:00 CDMX
          </div>
        </div>
        <RunBarridaCard onDone={triggerReload} />
      </header>

      <div className="flex gap-1 border-b border-white/10 overflow-x-auto" data-testid="dro-tabs">
        <Tab id="padron"  active={tab} onClick={setTab} icon={Users}    label="Padrón DRO" />
        <Tab id="embudo"  active={tab} onClick={setTab} icon={Workflow} label="Embudo Francotirador" />
      </div>

      {tab === "padron" && <PadronView key={`p-${reloadKey}`} reload={triggerReload} />}
      {tab === "embudo" && <EmbudoView key={`e-${reloadKey}`} reload={triggerReload} />}
    </div>
  );
}

function Tab({ id, active, onClick, icon: Icon, label }) {
  const isActive = active === id;
  return (
    <button
      data-testid={`dro-tab-${id}`}
      onClick={() => onClick(id)}
      className={`px-4 py-2.5 text-xs flex items-center gap-2 border-b-2 transition-colors ${
        isActive ? "border-amber-500 text-amber-400 font-semibold"
                 : "border-transparent text-zinc-400 hover:text-zinc-200"
      }`}
    >
      <Icon size={13} /> {label}
    </button>
  );
}

// ===========================================================================
// EJECUTAR BARRIDA
// ===========================================================================
function RunBarridaCard({ onDone }) {
  const [running, setRunning] = useState(false);
  const [last, setLast] = useState(null);
  const [estados, setEstados] = useState(["Querétaro", "Guanajuato", "Estado de México"]);
  const [limite, setLimite] = useState(6);
  const [showCfg, setShowCfg] = useState(false);

  const toggle = (e) =>
    setEstados((arr) => (arr.includes(e) ? arr.filter((x) => x !== e) : [...arr, e]));

  const run = async () => {
    if (running) return;
    setRunning(true); setLast(null);
    try {
      const { data } = await api.post("/francotirador/run", { estados, limite });
      setLast(data);
      onDone && onDone();
    } catch (e) { alert(formatApiError(e)); }
    finally { setRunning(false); }
  };

  return (
    <div className="surface p-3 border-amber-500/30 bg-amber-500/5 min-w-[320px]">
      <div className="flex items-center justify-between mb-2">
        <div className="label-overline text-[9px] text-amber-400 flex items-center gap-1.5">
          <Target size={10}/> Barrida manual
        </div>
        <button onClick={() => setShowCfg((v) => !v)}
                className="text-[10px] font-mono text-zinc-400 hover:text-amber-400"
                data-testid="dro-cfg-toggle">
          {showCfg ? "Ocultar" : "Configurar"}
        </button>
      </div>
      {showCfg && (
        <div className="space-y-2 mb-2 pb-2 border-b border-amber-500/20">
          <div>
            <div className="label-overline text-[9px]">Estados objetivo</div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-1">
              {["Querétaro", "Guanajuato", "Estado de México", "Aguascalientes", "Jalisco", "San Luis Potosí"].map((e) => (
                <label key={e} className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                  <input type="checkbox" checked={estados.includes(e)} onChange={() => toggle(e)} />
                  <span>{e}</span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <div className="label-overline text-[9px]">DROs por barrida</div>
            <input type="number" min={1} max={20} value={limite}
                   onChange={(e) => setLimite(Number(e.target.value) || 6)}
                   className="input-field font-mono w-full" />
          </div>
        </div>
      )}
      <button
        onClick={run}
        disabled={running || estados.length === 0}
        data-testid="dro-run-btn"
        className="btn-primary w-full bg-amber-500 hover:bg-amber-600 text-black border-amber-600"
      >
        {running ? (<><Loader2 size={13} className="inline animate-spin"/> Barriendo padrones…</>)
                 : (<><Play size={13} className="inline"/> Ejecutar Operación Francotirador</>)}
      </button>
      {last && (
        <div className={`mt-2 p-2 border-l-2 ${last.ok ? "border-emerald-500 bg-emerald-500/5" : "border-rose-500 bg-rose-500/5"}`}>
          <div className={`text-[10px] font-mono ${last.ok ? "text-emerald-400" : "text-rose-400"}`}>
            {last.ok
              ? `✓ ${last.unicos_insertados} DROs nuevos · ${last.tareas_creadas_alberto} tareas Alberto · modo ${last.modo}`
              : `✗ ${last.error || "Error"}`}
          </div>
          {last.ok && (
            <div className="text-[9px] text-zinc-500 mt-0.5 font-mono">
              Gov: {last.gov_detectados} · Colegios: {last.colegios_detectados}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ===========================================================================
// PADRÓN DRO — Tabla
// ===========================================================================
function PadronView({ reload }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [estado, setEstado] = useState("");
  const [stage, setStage]   = useState("");
  const [muni, setMuni]     = useState("");
  const [showPlantilla, setShowPlantilla] = useState(null);
  const [showEdit, setShowEdit]           = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (estado) params.set("estado_mx", estado);
      if (stage)  params.set("stage", stage);
      if (muni)   params.set("municipio", muni);
      const { data } = await api.get(`/francotirador/padron?${params}`);
      setItems(data);
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [estado, stage, muni]);

  const eliminar = async (did) => {
    if (!window.confirm("¿Eliminar este DRO del padrón?")) return;
    try { await api.delete(`/francotirador/${did}`); load(); reload && reload(); }
    catch (e) { alert(formatApiError(e)); }
  };

  const moveStage = async (did, newStage) => {
    try { await api.post(`/francotirador/${did}/move`, { stage: newStage }); load(); reload && reload(); }
    catch (e) { alert(formatApiError(e)); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <select className="input-field !w-auto text-xs" value={estado} onChange={(e) => setEstado(e.target.value)}
                data-testid="dro-filter-estado">
          <option value="">Todos los estados</option>
          {["Querétaro", "Guanajuato", "Estado de México", "Aguascalientes", "Jalisco", "San Luis Potosí"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select className="input-field !w-auto text-xs" value={stage} onChange={(e) => setStage(e.target.value)}
                data-testid="dro-filter-stage">
          <option value="">Todas las etapas</option>
          {STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <input className="input-field !w-auto text-xs" placeholder="Municipio…" value={muni}
               onChange={(e) => setMuni(e.target.value)} data-testid="dro-filter-muni" />
        <div className="text-xs text-zinc-400 font-mono ml-auto">
          <span className="text-amber-400 font-bold">{items.length}</span> DROs
        </div>
      </div>

      {loading ? <Loading />
       : items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">
          Sin DROs. Ejecuta la <b>Operación Francotirador</b> arriba para empezar.
        </div>
       ) : (
        <div className="surface overflow-x-auto">
          <table className="dtable" data-testid="dro-padron-table">
            <thead>
              <tr>
                <th>Etapa</th><th>Nombre</th><th>Esp.</th><th>Municipio · Estado</th>
                <th>Contacto</th><th>Fuente</th><th>Detectado</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => {
                const meta = STAGES.find((s) => s.key === d.stage) || STAGES[0];
                return (
                  <tr key={d.id} data-testid={`dro-row-${d.id}`}>
                    <td>
                      <select value={d.stage} onChange={(e) => moveStage(d.id, e.target.value)}
                              className={`text-[10px] bg-${meta.color}-500/10 text-${meta.color}-400 border border-${meta.color}-500/30 px-1.5 py-0.5 font-mono`}
                              data-testid={`dro-stage-select-${d.id}`}>
                        {STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                      </select>
                    </td>
                    <td className="font-semibold">
                      {d.nombre}
                      {d.numero_registro && (
                        <div className="text-[10px] font-mono text-zinc-500">{d.numero_registro}</div>
                      )}
                    </td>
                    <td><span className="text-[10px] font-mono text-sky-400">{d.especialidad || "—"}</span></td>
                    <td className="text-xs text-zinc-400">
                      <MapPin size={9} className="inline mr-1"/>{d.municipio || "—"}, {d.estado_mx}
                    </td>
                    <td className="text-[11px] font-mono">
                      {d.correo_electronico && (
                        <div className="text-emerald-400 flex items-center gap-1">
                          <Mail size={9}/>{d.correo_electronico}
                        </div>
                      )}
                      {(d.telefono_movil || d.telefono_oficina) && (
                        <div className="text-sky-400 flex items-center gap-1">
                          <Phone size={9}/>{d.telefono_movil || d.telefono_oficina}
                        </div>
                      )}
                      {!d.correo_electronico && !d.telefono_movil && !d.telefono_oficina && (
                        <span className="text-zinc-600">— sin contacto —</span>
                      )}
                    </td>
                    <td>
                      <span className="text-[10px] font-mono text-zinc-400 bg-white/5 px-1.5 py-0.5">
                        {d.fuente_agente?.includes("gov") ? "Gov.mx" : "Colegio"}
                      </span>
                    </td>
                    <td className="text-[10px] font-mono text-zinc-500">
                      {(d.fecha_deteccion || "").slice(0, 10)}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button onClick={() => setShowPlantilla(d)}
                              className="text-[10px] text-amber-400 hover:text-amber-300 font-mono mr-2"
                              data-testid={`dro-plantilla-${d.id}`}
                              title="Ver plantilla 1-clic">
                        <Send size={11} className="inline"/> Plantilla
                      </button>
                      {d.url_documento_fuente && (
                        <a href={d.url_documento_fuente} target="_blank" rel="noreferrer"
                           className="text-[10px] text-sky-400 hover:text-sky-300 mr-2" title="Doc fuente">
                          <FileText size={11} className="inline"/>
                        </a>
                      )}
                      <button onClick={() => setShowEdit(d)} className="text-zinc-400 hover:text-amber-400 mr-2" title="Editar">
                        <Edit3 size={11}/>
                      </button>
                      <button onClick={() => eliminar(d.id)} className="text-rose-400 hover:text-rose-300" title="Eliminar">
                        <Trash2 size={11}/>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
       )}

      <PlantillaModal dro={showPlantilla} onClose={() => setShowPlantilla(null)} />
      <EditDROModal dro={showEdit} onClose={() => setShowEdit(null)}
                    onSaved={() => { setShowEdit(null); load(); reload && reload(); }} />
    </div>
  );
}

// ===========================================================================
// PLANTILLA 1-CLIC — WhatsApp / Email
// ===========================================================================
function PlantillaModal({ dro, onClose }) {
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (dro) setMsg(dro.plantilla_mensaje || "");
  }, [dro]);

  if (!dro) return null;

  const tel = (dro.telefono_movil || dro.telefono_oficina || "").replace(/[^\d+]/g, "");
  const waLink = tel ? `https://wa.me/${tel.replace(/^\+/, "")}?text=${encodeURIComponent(msg)}` : null;
  const mailLink = dro.correo_electronico
    ? `mailto:${dro.correo_electronico}?subject=${encodeURIComponent("DEYMA · Canastillas pasajuntas para sus obras")}&body=${encodeURIComponent(msg)}`
    : null;

  const copy = async () => {
    try { await navigator.clipboard.writeText(msg); alert("Mensaje copiado al portapapeles"); }
    catch { /* ignore */ }
  };

  return (
    <Modal open={!!dro} onClose={onClose} title={`Plantilla Francotirador — ${dro.nombre}`} testId="dro-plantilla-modal">
      <div className="space-y-3">
        <div className="surface-elev p-3 text-xs">
          <div className="label-overline text-amber-400 mb-1">Destinatario</div>
          <div className="font-semibold">{dro.nombre}</div>
          <div className="text-zinc-400 mt-1">
            {dro.especialidad || "DRO"} · {dro.municipio || dro.estado_mx}
            {dro.numero_registro && <> · Reg. {dro.numero_registro}</>}
          </div>
          <div className="mt-1.5 font-mono text-[11px]">
            {dro.correo_electronico
              ? <span className="text-emerald-400">📧 {dro.correo_electronico}</span>
              : <span className="text-zinc-500">— sin email —</span>}
            <span className="mx-2 text-zinc-700">·</span>
            {(dro.telefono_movil || dro.telefono_oficina)
              ? <span className="text-sky-400">📞 {dro.telefono_movil || dro.telefono_oficina}</span>
              : <span className="text-zinc-500">— sin teléfono —</span>}
          </div>
        </div>

        <div>
          <label className="label-overline">Mensaje (editable)</label>
          <textarea
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            data-testid="dro-plantilla-text"
            className="input-field font-mono text-xs"
            style={{ height: 180 }}
          />
        </div>

        <div className="grid grid-cols-3 gap-2">
          {waLink ? (
            <a href={waLink} target="_blank" rel="noreferrer"
               className="btn-primary bg-emerald-500 hover:bg-emerald-600 text-black border-emerald-600 text-xs text-center"
               data-testid="dro-send-whatsapp">
              <MessageCircle size={12} className="inline"/> WhatsApp
            </a>
          ) : (
            <button disabled className="btn-ghost opacity-40 cursor-not-allowed text-xs">Sin teléfono</button>
          )}
          {mailLink ? (
            <a href={mailLink}
               className="btn-primary bg-sky-500 hover:bg-sky-600 text-white border-sky-600 text-xs text-center"
               data-testid="dro-send-email">
              <Mail size={12} className="inline"/> Email
            </a>
          ) : (
            <button disabled className="btn-ghost opacity-40 cursor-not-allowed text-xs">Sin email</button>
          )}
          <button onClick={copy} className="btn-ghost text-xs" data-testid="dro-copy-msg">
            <Copy size={12} className="inline"/> Copiar
          </button>
        </div>

        <div className="text-[10px] text-zinc-500 font-mono">
          💡 Tras enviar el mensaje, mueve el DRO a &ldquo;Kit CAD Enviado&rdquo; desde el selector de etapa.
        </div>
      </div>
    </Modal>
  );
}

// ===========================================================================
// EDITAR DRO
// ===========================================================================
function EditDROModal({ dro, onClose, onSaved }) {
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!dro) return;
    setF({
      nombre: dro.nombre || "",
      numero_registro: dro.numero_registro || "",
      especialidad: dro.especialidad || "",
      municipio: dro.municipio || "",
      estado_mx: dro.estado_mx || "Querétaro",
      telefono_movil: dro.telefono_movil || "",
      telefono_oficina: dro.telefono_oficina || "",
      correo_electronico: dro.correo_electronico || "",
      colegio_agremiado: dro.colegio_agremiado || "",
      notas: dro.notas || "",
    });
    setErr("");
  }, [dro]);

  if (!dro) return null;

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await api.patch(`/francotirador/${dro.id}`, f); onSaved(); }
    catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={!!dro} onClose={onClose} title="Editar DRO" testId="dro-edit-modal">
      <form onSubmit={submit} className="space-y-3">
        <input required className="input-field" placeholder="Nombre completo"
               value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} />
        <div className="grid grid-cols-2 gap-2">
          <input className="input-field" placeholder="Número de registro (DRO-…)"
                 value={f.numero_registro} onChange={(e) => setF({ ...f, numero_registro: e.target.value })} />
          <select className="input-field" value={f.especialidad}
                  onChange={(e) => setF({ ...f, especialidad: e.target.value })}>
            <option value="">Especialidad…</option>
            <option value="Civil">Ing. Civil</option>
            <option value="Estructural">Estructural</option>
            <option value="Arquitecto">Arquitecto</option>
          </select>
          <input className="input-field" placeholder="Municipio"
                 value={f.municipio} onChange={(e) => setF({ ...f, municipio: e.target.value })} />
          <select className="input-field" value={f.estado_mx}
                  onChange={(e) => setF({ ...f, estado_mx: e.target.value })}>
            {["Querétaro", "Guanajuato", "Estado de México", "Aguascalientes", "Jalisco", "San Luis Potosí", "Nuevo León"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input className="input-field" placeholder="Tel. móvil"
                 value={f.telefono_movil} onChange={(e) => setF({ ...f, telefono_movil: e.target.value })} />
          <input className="input-field" placeholder="Tel. oficina"
                 value={f.telefono_oficina} onChange={(e) => setF({ ...f, telefono_oficina: e.target.value })} />
        </div>
        <input className="input-field" placeholder="Correo electrónico" type="email"
               value={f.correo_electronico} onChange={(e) => setF({ ...f, correo_electronico: e.target.value })} />
        <input className="input-field" placeholder="Colegio agremiado"
               value={f.colegio_agremiado} onChange={(e) => setF({ ...f, colegio_agremiado: e.target.value })} />
        <textarea className="input-field" style={{ height: 60 }} placeholder="Notas"
                  value={f.notas} onChange={(e) => setF({ ...f, notas: e.target.value })} />
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary" data-testid="dro-edit-submit">
            {busy ? "Guardando…" : "Guardar cambios"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ===========================================================================
// EMBUDO (Kanban)
// ===========================================================================
function EmbudoView({ reload }) {
  const [data, setData] = useState(null);
  const [moving, setMoving] = useState(null);

  const load = async () => {
    try {
      const { data: r } = await api.get("/francotirador/embudo");
      setData(r);
    } catch { setData({ stages: [], total: 0 }); }
  };
  useEffect(() => { load(); }, []);

  const move = async (did, stage) => {
    if (moving) return;
    setMoving(did);
    try {
      await api.post(`/francotirador/${did}/move`, { stage });
      await load(); reload && reload();
    } catch (e) { alert(formatApiError(e)); }
    finally { setMoving(null); }
  };

  if (!data) return <Loading />;

  return (
    <div className="space-y-3">
      <div className="text-xs text-zinc-400 font-mono">
        <span className="text-amber-400 font-bold">{data.total}</span> DROs en pipeline
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2" data-testid="dro-kanban">
        {data.stages.map((s) => {
          const meta = STAGES.find((x) => x.key === s.key) || STAGES[0];
          const color = meta.color;
          return (
            <div key={s.key} className="min-w-[280px] w-[280px] surface p-3" data-testid={`dro-stage-${s.key}`}>
              <div className={`flex items-center justify-between mb-2 pb-2 border-b border-${color}-500/30`}>
                <div>
                  <div className={`label-overline text-[9px] text-${color}-400`}>{s.label}</div>
                  <div className="text-xs font-mono text-zinc-400">{s.items.length} DROs</div>
                </div>
                <span className={`text-[10px] font-mono text-${color}-400 bg-${color}-500/10 px-1.5 py-0.5`}>
                  {meta.prob}%
                </span>
              </div>
              <div className="space-y-2">
                {s.items.map((d) => (
                  <DROCard key={d.id} dro={d} onMove={move} disabled={moving === d.id} color={color} />
                ))}
                {s.items.length === 0 && (
                  <div className="text-[10px] text-zinc-600 font-mono text-center py-4">— vacío —</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DROCard({ dro, onMove, disabled, color }) {
  const [showMove, setShowMove] = useState(false);
  const next = STAGES.filter((s) => s.key !== dro.stage);

  return (
    <div className={`bg-zinc-950 border border-${color}-500/20 p-2.5 hover:border-${color}-500/50 transition-colors`}
         data-testid={`dro-card-${dro.id}`}>
      <div className="text-xs font-semibold leading-snug">{dro.nombre}</div>
      <div className="text-[10px] text-zinc-400 mt-0.5">
        {dro.especialidad || "DRO"} · {dro.municipio || dro.estado_mx}
      </div>
      <div className="mt-1.5 text-[10px] font-mono">
        {dro.correo_electronico && (
          <div className="text-emerald-400 truncate" title={dro.correo_electronico}>
            <Mail size={9} className="inline mr-1"/>{dro.correo_electronico}
          </div>
        )}
        {(dro.telefono_movil || dro.telefono_oficina) && (
          <div className="text-sky-400">
            <Phone size={9} className="inline mr-1"/>{dro.telefono_movil || dro.telefono_oficina}
          </div>
        )}
      </div>
      <div className="mt-2 pt-2 border-t border-white/5">
        <button
          onClick={() => setShowMove((v) => !v)}
          disabled={disabled}
          className="text-[10px] text-zinc-400 hover:text-amber-400 font-mono"
          data-testid={`dro-card-${dro.id}-move-btn`}
        >
          {disabled ? "⟳ Moviendo…" : "→ Cambiar etapa"}
        </button>
        {showMove && (
          <div className="grid grid-cols-2 gap-1 mt-1.5">
            {next.map((s) => (
              <button
                key={s.key}
                onClick={() => { setShowMove(false); onMove(dro.id, s.key); }}
                className={`text-[9px] py-1 px-1.5 bg-${s.color}-500/10 text-${s.color}-400 hover:bg-${s.color}-500/20 transition-colors text-left`}
              >
                {s.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="surface p-12 text-center text-zinc-500 text-sm">
      <Loader2 size={16} className="inline animate-spin mr-2"/> Cargando…
    </div>
  );
}
