import React, { useEffect, useState, useMemo } from "react";
import { api, fmtMXN, formatApiError } from "../lib/auth";
import { Modal } from "../components/ui-deyma";
import {
  Satellite, Building2, Users, Workflow, Bot, Play, Loader2,
  AlertTriangle, CheckCircle2, Phone, Mail, Linkedin, Target,
  MapPin, Calendar, TrendingUp, Plus, Trash2, X, Activity,
} from "lucide-react";

const STAGES = [
  { key: "radar_activado", label: "Radar Activado", color: "zinc", prob: 5 },
  { key: "triangulacion", label: "Triangulación", color: "sky", prob: 15 },
  { key: "abordaje_dia_cero", label: "Abordaje Día Cero", color: "indigo", prob: 30 },
  { key: "demo_arranque", label: "Demo de Arranque", color: "fuchsia", prob: 55 },
  { key: "propuesta_enviada", label: "Propuesta Enviada", color: "amber", prob: 75 },
  { key: "cierre_ganado", label: "Cierre Ganado", color: "emerald", prob: 100 },
  { key: "perdida", label: "Perdida", color: "rose", prob: 0 },
];

const URGENCIA_COLOR = { alto: "rose", medio: "amber", bajo: "zinc" };

export default function AdminRadarGreenfieldPage() {
  const [tab, setTab] = useState("embudo");
  const [resumen, setResumen] = useState(null);
  const [status, setStatus] = useState(null);

  const loadResumen = async () => {
    try {
      const { data: r } = await api.get("/greenfield/dashboard-resumen");
      setResumen(r);
      const { data: s } = await api.get("/greenfield/agentes/status");
      setStatus(s);
    } catch { /* silent */ }
  };

  useEffect(() => { loadResumen(); }, []);

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto" data-testid="radar-greenfield-page">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="label-overline text-[10px] text-emerald-400 flex items-center gap-2">
            <Satellite size={11} /> V5 · OSINT Multi-Agente
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Radar Greenfield <span className="text-emerald-400">OSINT</span>
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Bajío · Querétaro / Guanajuato / Estado de México · 4 agentes 24/7 (cron 07:00 CDMX)
          </div>
        </div>
        {resumen && (
          <div className="surface p-3 border-emerald-500/30 bg-emerald-500/5 min-w-[280px]">
            <div className="label-overline text-[9px] text-emerald-400 mb-1.5">Reporte hoy</div>
            <div className="text-xs leading-relaxed text-zinc-300">
              El Radar OSINT ha detectado{" "}
              <span className="text-emerald-400 font-bold font-mono">{resumen.nuevas_senales_hoy}</span>{" "}
              nuevas plantas y{" "}
              <span className="text-emerald-400 font-bold font-mono">{resumen.triangulados_hoy}</span>{" "}
              contactos directos listos para prospección hoy.
            </div>
          </div>
        )}
      </header>

      {/* Métricas */}
      {status?.totales && (
        <div className="grid grid-cols-4 gap-3" data-testid="gf-metrics">
          <Metric icon={Building2} label="Señales totales" v={status.totales.senales} color="amber" />
          <Metric icon={Users} label="Contactos OSINT" v={status.totales.contactos} color="sky" />
          <Metric icon={CheckCircle2} label="Triangulados" v={status.totales.triangulados} color="emerald" />
          <Metric icon={Workflow} label="En embudo" v={status.totales.oportunidades} color="fuchsia" />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-white/10" data-testid="gf-tabs">
        <Tab id="embudo" active={tab} onClick={setTab} icon={Workflow} label="Embudo Greenfield" />
        <Tab id="senales" active={tab} onClick={setTab} icon={Building2} label="Señales" />
        <Tab id="contactos" active={tab} onClick={setTab} icon={Users} label="Directorio OSINT" />
        <Tab id="agentes" active={tab} onClick={setTab} icon={Bot} label="Agentes & Cron" />
        <Tab id="tareas" active={tab} onClick={setTab} icon={Target} label="Tareas Alberto" />
        <Tab id="tickets" active={tab} onClick={setTab} icon={Activity} label="Tickets Maurizio" />
      </div>

      {tab === "embudo" && <EmbudoView reload={loadResumen} />}
      {tab === "senales" && <SenalesView reload={loadResumen} />}
      {tab === "contactos" && <ContactosView reload={loadResumen} />}
      {tab === "agentes" && <AgentesView status={status} reload={loadResumen} />}
      {tab === "tareas" && <TareasView />}
      {tab === "tickets" && <TicketsView />}
    </div>
  );
}

function Tab({ id, active, onClick, icon: Icon, label }) {
  const isActive = active === id;
  return (
    <button
      data-testid={`gf-tab-${id}`}
      onClick={() => onClick(id)}
      className={`px-4 py-2.5 text-xs flex items-center gap-2 border-b-2 transition-colors ${
        isActive
          ? "border-emerald-500 text-emerald-400 font-semibold"
          : "border-transparent text-zinc-400 hover:text-zinc-200"
      }`}
    >
      <Icon size={13} /> {label}
    </button>
  );
}

function Metric({ icon: Icon, label, v, color }) {
  return (
    <div className={`surface p-3 border-l-2 border-${color}-500/40`}>
      <div className="flex items-center gap-2">
        <Icon size={13} className={`text-${color}-400`} />
        <div className="label-overline text-[10px]">{label}</div>
      </div>
      <div className={`text-2xl font-black font-mono mt-1 text-${color}-400`}>{v}</div>
    </div>
  );
}

// ===========================================================================
// EMBUDO (Kanban) — 6 etapas + perdida
// ===========================================================================
function EmbudoView({ reload }) {
  const [data, setData] = useState(null);
  const [moving, setMoving] = useState(null);

  const load = async () => {
    const { data: r } = await api.get("/greenfield/embudo");
    setData(r);
  };
  useEffect(() => { load(); }, []);

  const move = async (oid, stage) => {
    if (moving) return;
    setMoving(oid);
    try {
      await api.post(`/greenfield/embudo/${oid}/move`, { stage });
      await load(); reload && reload();
    } catch (e) { alert(formatApiError(e)); }
    finally { setMoving(null); }
  };

  if (!data) return <Loading />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs text-zinc-400 font-mono">
          <span className="text-emerald-400 font-bold">{data.total_oportunidades}</span> oportunidades ·{" "}
          Pipeline total: <span className="text-amber-400 font-bold">{fmtMXN(data.total_pipeline_monto)}</span>
        </div>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2" data-testid="gf-kanban">
        {data.stages.map((s) => {
          const meta = STAGES.find((x) => x.key === s.key);
          const color = meta?.color || "zinc";
          return (
            <div key={s.key} className="min-w-[280px] w-[280px] surface p-3" data-testid={`gf-stage-${s.key}`}>
              <div className={`flex items-center justify-between mb-2 pb-2 border-b border-${color}-500/30`}>
                <div>
                  <div className={`label-overline text-[9px] text-${color}-400`}>{s.label}</div>
                  <div className="text-xs font-mono text-zinc-400">{s.items.length} · {fmtMXN(s.total_monto)}</div>
                </div>
                <span className={`text-[10px] font-mono text-${color}-400 bg-${color}-500/10 px-1.5 py-0.5`}>{meta?.prob}%</span>
              </div>
              <div className="space-y-2">
                {s.items.map((opp) => (
                  <OppCard key={opp.id} opp={opp} onMove={move} disabled={moving === opp.id} color={color} />
                ))}
                {s.items.length === 0 && (
                  <div className="text-[10px] text-zinc-600 font-mono text-center py-4">— Sin oportunidades —</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function OppCard({ opp, onMove, disabled, color }) {
  const [showMove, setShowMove] = useState(false);
  const validNext = STAGES.filter((s) => s.key !== opp.stage);

  return (
    <div
      className={`bg-zinc-950 border border-${color}-500/20 p-2.5 hover:border-${color}-500/50 transition-colors`}
      data-testid={`gf-opp-${opp.id}`}
    >
      <div className="text-xs font-semibold leading-snug">{opp.empresa}</div>
      <div className="text-[10px] text-zinc-400 mt-0.5 line-clamp-2">{opp.proyecto_titulo}</div>
      <div className="font-mono text-xs text-amber-400 mt-1.5">{fmtMXN(opp.monto_estimado || 0)}</div>
      {opp.owner_name && (
        <div className="text-[9px] text-zinc-500 font-mono mt-1">→ {opp.owner_name}</div>
      )}
      <div className="mt-2 pt-2 border-t border-white/5">
        <button
          onClick={() => setShowMove(!showMove)}
          disabled={disabled}
          className="text-[10px] text-zinc-400 hover:text-emerald-400 font-mono"
          data-testid={`gf-opp-${opp.id}-move-btn`}
        >
          {disabled ? "⟳ Moviendo…" : "→ Cambiar etapa"}
        </button>
        {showMove && (
          <div className="grid grid-cols-2 gap-1 mt-1.5">
            {validNext.map((s) => (
              <button
                key={s.key}
                onClick={() => { setShowMove(false); onMove(opp.id, s.key); }}
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

// ===========================================================================
// SEÑALES
// ===========================================================================
function SenalesView({ reload }) {
  const [items, setItems] = useState([]);
  const [filterEstado, setFilterEstado] = useState("");
  const [filterUrgencia, setFilterUrgencia] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [showCreateOpp, setShowCreateOpp] = useState(null);

  const load = async () => {
    const params = new URLSearchParams();
    if (filterEstado) params.set("estado_mx", filterEstado);
    if (filterUrgencia) params.set("urgencia", filterUrgencia);
    const { data } = await api.get(`/greenfield/senales?${params}`);
    setItems(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterEstado, filterUrgencia]);

  const eliminarSenal = async (sid) => {
    if (!window.confirm("¿Eliminar esta señal?")) return;
    try { await api.delete(`/greenfield/senales/${sid}`); load(); }
    catch (e) { alert(formatApiError(e)); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <select className="input-field !w-auto text-xs" value={filterEstado} onChange={(e) => setFilterEstado(e.target.value)}>
          <option value="">Todos los estados</option>
          <option value="Querétaro">Querétaro</option>
          <option value="Guanajuato">Guanajuato</option>
          <option value="Estado de México">Estado de México</option>
        </select>
        <select className="input-field !w-auto text-xs" value={filterUrgencia} onChange={(e) => setFilterUrgencia(e.target.value)}>
          <option value="">Todas urgencias</option>
          <option value="alto">Alta</option>
          <option value="medio">Media</option>
          <option value="bajo">Baja</option>
        </select>
        <div className="flex-1" />
        <button onClick={() => setShowNew(true)} data-testid="gf-new-senal-btn" className="btn-primary text-xs">
          <Plus size={12} className="inline" /> Captura manual
        </button>
      </div>

      {items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">
          Sin señales. Ejecuta una barrida de agentes en la pestaña “Agentes & Cron”.
        </div>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="dtable" data-testid="gf-senales-table">
            <thead>
              <tr>
                <th>Urgencia</th><th>Empresa</th><th>Origen</th><th>Ciudad / Estado</th>
                <th>Sector</th><th className="text-right">Monto</th><th>Detectado</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id} data-testid={`gf-senal-${s.id}`}>
                  <td><Badge color={URGENCIA_COLOR[s.urgencia]} text={s.urgencia.toUpperCase()} /></td>
                  <td className="font-semibold">{s.empresa}</td>
                  <td><span className="text-[10px] font-mono text-zinc-400 bg-white/5 px-1.5 py-0.5">{s.origen}</span></td>
                  <td className="text-xs text-zinc-400"><MapPin size={9} className="inline mr-1" />{s.ciudad}, {s.estado_mx}</td>
                  <td className="text-xs text-sky-400">{s.sector_industrial || "—"}</td>
                  <td className="text-right font-mono text-amber-400">{fmtMXN(s.monto_estimado || 0)}</td>
                  <td className="text-[10px] font-mono text-zinc-500">{(s.fecha_deteccion || "").slice(0, 10)}</td>
                  <td className="text-right">
                    <button
                      onClick={() => setShowCreateOpp(s)}
                      className="text-[10px] text-emerald-400 hover:text-emerald-300 font-mono mr-2"
                      data-testid={`gf-senal-${s.id}-to-embudo`}
                      title="Mover al embudo"
                    >→ Embudo</button>
                    {s.url_referencia && (
                      <a href={s.url_referencia} target="_blank" rel="noreferrer"
                         className="text-[10px] text-sky-400 hover:text-sky-300 mr-2">URL</a>
                    )}
                    <button onClick={() => eliminarSenal(s.id)} className="text-rose-400 hover:text-rose-300" title="Eliminar">
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NewSenalModal open={showNew} onClose={() => setShowNew(false)} onSaved={() => { setShowNew(false); load(); reload && reload(); }} />
      <CreateOppModal senal={showCreateOpp} onClose={() => setShowCreateOpp(null)}
                      onSaved={() => { setShowCreateOpp(null); reload && reload(); }} />
    </div>
  );
}

function NewSenalModal({ open, onClose, onSaved }) {
  const [f, setF] = useState({
    empresa: "", origen: "Manual", urgencia: "medio", estado_mx: "Querétaro",
    ciudad: "", sector_industrial: "", monto_estimado: 0, url_referencia: "", notas: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api.post("/greenfield/senales", { ...f, monto_estimado: Number(f.monto_estimado) || null });
      onSaved();
      setF({ empresa: "", origen: "Manual", urgencia: "medio", estado_mx: "Querétaro",
             ciudad: "", sector_industrial: "", monto_estimado: 0, url_referencia: "", notas: "" });
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Nueva señal Greenfield" testId="gf-new-senal-modal">
      <form onSubmit={submit} className="space-y-3">
        <input required className="input-field" placeholder="Razón social / Empresa"
               value={f.empresa} onChange={(e) => setF({ ...f, empresa: e.target.value })}
               data-testid="gf-senal-empresa" />
        <div className="grid grid-cols-2 gap-2">
          <select className="input-field" value={f.origen} onChange={(e) => setF({ ...f, origen: e.target.value })}>
            <option value="Manual">Manual</option>
            <option value="MIA">MIA (SEMARNAT)</option>
            <option value="LinkedIn">LinkedIn</option>
            <option value="Broker">Broker</option>
            <option value="Gobierno">Gobierno</option>
            <option value="DOF">DOF</option>
            <option value="ParqueIndustrial">Parque Industrial</option>
            <option value="Permisos">Permisos</option>
          </select>
          <select className="input-field" value={f.urgencia} onChange={(e) => setF({ ...f, urgencia: e.target.value })}>
            <option value="alto">Urgencia ALTA</option>
            <option value="medio">Urgencia Media</option>
            <option value="bajo">Urgencia Baja</option>
          </select>
          <select className="input-field" value={f.estado_mx} onChange={(e) => setF({ ...f, estado_mx: e.target.value })}>
            <option value="Querétaro">Querétaro</option>
            <option value="Guanajuato">Guanajuato</option>
            <option value="Estado de México">Estado de México</option>
            <option value="Aguascalientes">Aguascalientes</option>
            <option value="Jalisco">Jalisco</option>
            <option value="San Luis Potosí">San Luis Potosí</option>
            <option value="Nuevo León">Nuevo León</option>
          </select>
          <input className="input-field" placeholder="Ciudad" value={f.ciudad}
                 onChange={(e) => setF({ ...f, ciudad: e.target.value })} />
          <input className="input-field" placeholder="Sector industrial" value={f.sector_industrial}
                 onChange={(e) => setF({ ...f, sector_industrial: e.target.value })} />
          <input type="number" className="input-field font-mono" placeholder="Monto estimado MXN"
                 value={f.monto_estimado} onChange={(e) => setF({ ...f, monto_estimado: e.target.value })} />
        </div>
        <input className="input-field" placeholder="URL de referencia (MIA PDF, permiso, perfil…)"
               value={f.url_referencia} onChange={(e) => setF({ ...f, url_referencia: e.target.value })} />
        <textarea className="input-field" style={{ height: 60 }} placeholder="Notas"
                  value={f.notas} onChange={(e) => setF({ ...f, notas: e.target.value })} />
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary" data-testid="gf-senal-submit">
            {busy ? "Guardando…" : "Guardar señal"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function CreateOppModal({ senal, onClose, onSaved }) {
  const [contactos, setContactos] = useState([]);
  const [contactoId, setContactoId] = useState("");
  const [titulo, setTitulo] = useState("");
  const [monto, setMonto] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!senal) return;
    setTitulo(`Greenfield · ${senal.empresa}`);
    setMonto(senal.monto_estimado || 0);
    setContactoId("");
    setErr("");
    api.get(`/greenfield/contactos?senal_id=${senal.id}`).then(({ data }) => setContactos(data)).catch(() => setContactos([]));
  }, [senal]);

  if (!senal) return null;

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api.post("/greenfield/embudo", {
        senal_id: senal.id, contacto_id: contactoId || null,
        proyecto_titulo: titulo, monto_estimado: Number(monto) || 0,
      });
      onSaved();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={!!senal} onClose={onClose} title="Mover al Embudo Greenfield" testId="gf-create-opp-modal">
      <form onSubmit={submit} className="space-y-3">
        <div className="surface-elev p-3">
          <div className="label-overline text-emerald-400">Señal</div>
          <div className="text-sm font-semibold">{senal.empresa}</div>
          <div className="text-xs text-zinc-400">{senal.ciudad}, {senal.estado_mx} · {senal.sector_industrial}</div>
        </div>
        <div>
          <label className="label-overline">Título del proyecto</label>
          <input required className="input-field" value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </div>
        <div>
          <label className="label-overline">Monto estimado MXN</label>
          <input type="number" className="input-field font-mono" value={monto} onChange={(e) => setMonto(e.target.value)} />
        </div>
        <div>
          <label className="label-overline">Contacto OSINT (opcional)</label>
          <select className="input-field" value={contactoId} onChange={(e) => setContactoId(e.target.value)}>
            <option value="">Sin contacto asignado</option>
            {contactos.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre_completo} — {c.puesto} ({c.nivel_precision}%)</option>
            ))}
          </select>
        </div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary">{busy ? "Creando…" : "Crear oportunidad"}</button>
        </div>
      </form>
    </Modal>
  );
}

// ===========================================================================
// CONTACTOS (Directorio OSINT)
// ===========================================================================
function ContactosView({ reload }) {
  const [items, setItems] = useState([]);
  const [filterWf, setFilterWf] = useState("");

  const load = async () => {
    const { data } = await api.get(`/greenfield/contactos${filterWf ? `?estado_workflow=${filterWf}` : ""}`);
    setItems(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterWf]);

  const eliminar = async (cid) => {
    if (!window.confirm("¿Eliminar contacto?")) return;
    try { await api.delete(`/greenfield/contactos/${cid}`); load(); reload && reload(); }
    catch (e) { alert(formatApiError(e)); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <select className="input-field !w-auto text-xs" value={filterWf} onChange={(e) => setFilterWf(e.target.value)}>
          <option value="">Todos</option>
          <option value="pendiente">Pendientes</option>
          <option value="triangulado">Triangulados</option>
          <option value="asignado">Asignados</option>
          <option value="contactado">Contactados</option>
        </select>
        <div className="text-xs text-zinc-400 font-mono ml-auto">
          {items.length} contactos · {items.filter((c) => c.estado_workflow === "triangulado").length} triangulados
        </div>
      </div>

      {items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">Sin contactos OSINT.</div>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="dtable" data-testid="gf-contactos-table">
            <thead>
              <tr>
                <th>Estado</th><th>Nombre</th><th>Puesto</th><th>Empresa</th>
                <th>Contacto</th><th>LinkedIn</th><th className="text-right">Precisión</th><th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} data-testid={`gf-contacto-${c.id}`}>
                  <td>
                    {c.estado_workflow === "triangulado"
                      ? <Badge color="emerald" text="TRIANGULADO" />
                      : <Badge color="zinc" text={c.estado_workflow.toUpperCase()} />}
                  </td>
                  <td className="font-semibold">{c.nombre_completo}</td>
                  <td className="text-xs text-sky-400">{c.puesto}</td>
                  <td className="text-xs text-zinc-300">{c.empresa}</td>
                  <td className="text-[11px] font-mono">
                    {c.correo_directo && <div className="text-emerald-400 flex items-center gap-1"><Mail size={9} />{c.correo_directo}</div>}
                    {c.telefono_movil && <div className="text-sky-400 flex items-center gap-1"><Phone size={9} />{c.telefono_movil}</div>}
                    {!c.correo_directo && !c.telefono_movil && <span className="text-zinc-600">—</span>}
                  </td>
                  <td>
                    {c.linkedin_url
                      ? <a href={c.linkedin_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:text-sky-300"><Linkedin size={11} /></a>
                      : <span className="text-zinc-600">—</span>}
                  </td>
                  <td className="text-right font-mono">
                    <span className={c.nivel_precision >= 80 ? "text-emerald-400" : c.nivel_precision >= 50 ? "text-amber-400" : "text-zinc-500"}>
                      {c.nivel_precision}%
                    </span>
                  </td>
                  <td className="text-right">
                    <button onClick={() => eliminar(c.id)} className="text-rose-400 hover:text-rose-300"><Trash2 size={11} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ===========================================================================
// AGENTES & CRON
// ===========================================================================
function AgentesView({ status, reload }) {
  const [running, setRunning] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [estados, setEstados] = useState(["Querétaro", "Guanajuato", "Estado de México"]);
  const [limite, setLimite] = useState(5);

  const toggleEstado = (e) => setEstados((arr) => arr.includes(e) ? arr.filter((x) => x !== e) : [...arr, e]);

  const ejecutar = async () => {
    if (running) return;
    setRunning(true); setLastResult(null);
    try {
      const { data } = await api.post("/greenfield/agentes/run", { estados, limite });
      setLastResult(data);
      reload && reload();
    } catch (e) { alert(formatApiError(e)); }
    finally { setRunning(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Columna izquierda — control */}
      <div className="surface p-4 space-y-3">
        <div>
          <div className="label-overline text-emerald-400">Ejecutar barrida manual</div>
          <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
            CRON automático: <span className="text-emerald-400">07:00 CDMX diario</span>
          </div>
        </div>
        <div>
          <label className="label-overline">Estados objetivo</label>
          <div className="space-y-1 mt-1">
            {["Querétaro", "Guanajuato", "Estado de México", "Aguascalientes", "Jalisco", "San Luis Potosí"].map((e) => (
              <label key={e} className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" checked={estados.includes(e)} onChange={() => toggleEstado(e)} />
                <span>{e}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="label-overline">Señales por barrida</label>
          <input type="number" min={1} max={20} className="input-field font-mono" value={limite}
                 onChange={(e) => setLimite(Number(e.target.value) || 5)} />
        </div>
        <button onClick={ejecutar} disabled={running || estados.length === 0}
                className="btn-primary w-full" data-testid="gf-run-agentes-btn">
          {running ? (<><Loader2 size={13} className="inline animate-spin" /> Barriendo…</>)
                   : (<><Play size={13} className="inline" /> Ejecutar Agentes 1-4</>)}
        </button>
        {lastResult && (
          <div className={`surface-elev p-3 border-l-2 ${lastResult.ok ? "border-emerald-500" : "border-rose-500"}`}>
            <div className={`label-overline text-[9px] ${lastResult.ok ? "text-emerald-400" : "text-rose-400"}`}>
              {lastResult.ok ? "✓ Barrida completada" : "✗ Error"}
            </div>
            {lastResult.ok && (
              <div className="text-[10px] font-mono space-y-0.5 mt-1">
                <div>Señales detectadas: <span className="text-amber-400">{lastResult.senales_detectadas}</span></div>
                <div>Insertadas: <span className="text-emerald-400">{lastResult.senales_nuevas_insertadas}</span></div>
                <div>Contactos triangulados: <span className="text-emerald-400">{lastResult.contactos_validados}</span></div>
                <div>Duplicados descartados: <span className="text-zinc-500">{lastResult.duplicados_descartados}</span></div>
                <div className="text-amber-400/70 mt-1">Modo: {lastResult.modo}</div>
              </div>
            )}
            {!lastResult.ok && <div className="text-[10px] text-rose-300 mt-1">{lastResult.error}</div>}
          </div>
        )}
      </div>

      {/* Columna derecha — 4 agentes */}
      <div className="lg:col-span-2 space-y-3">
        {(status?.agentes || []).map((a, i) => (
          <div key={a.key} className="surface p-3 border-l-2 border-emerald-500/40">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-mono font-bold">
                {i + 1}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <div className="font-semibold text-sm">{a.nombre}</div>
                  <span className="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5">{a.estado}</span>
                </div>
                <div className="text-xs text-zinc-400 mt-0.5">{a.mision}</div>
                <div className="mt-2 space-y-0.5">
                  {(a.dorks || []).map((d, j) => (
                    <div key={j} className="text-[10px] font-mono text-zinc-500 bg-black/40 px-1.5 py-0.5 border border-white/5 truncate">
                      {d}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* Últimas corridas */}
        {status?.ultimas_corridas && status.ultimas_corridas.length > 0 && (
          <div className="surface p-3">
            <div className="label-overline mb-2">Últimas barridas</div>
            <div className="space-y-1">
              {status.ultimas_corridas.slice(0, 5).map((r) => (
                <div key={r.run_id} className="flex items-center justify-between text-[10px] font-mono py-1 border-b border-white/5 last:border-0">
                  <span className="text-zinc-500">{(r.iniciada || "").slice(0, 16).replace("T", " ")}</span>
                  <span className="text-emerald-400">
                    {r.senales_nuevas_insertadas || 0} señales · {r.contactos_validados || 0} contactos
                  </span>
                  <span className={r.ok ? "text-emerald-400" : "text-rose-400"}>{r.ok ? "✓" : "✗"}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ===========================================================================
// TAREAS Alberto / TICKETS Maurizio
// ===========================================================================
function TareasView() {
  const [items, setItems] = useState([]);
  const [estado, setEstado] = useState("abierta");

  const load = async () => {
    const { data } = await api.get(`/greenfield/tareas?estado=${estado}`);
    setItems(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [estado]);

  const cerrar = async (tid) => {
    try { await api.patch(`/greenfield/tareas/${tid}`, { estado: "cerrada" }); load(); }
    catch (e) { alert(formatApiError(e)); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <select className="input-field !w-auto text-xs" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="abierta">Abiertas</option>
          <option value="cerrada">Cerradas</option>
        </select>
        <div className="text-xs text-zinc-400 font-mono ml-auto">{items.length} tareas</div>
      </div>
      {items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">Sin tareas.</div>
      ) : (
        <div className="space-y-2">
          {items.map((t) => (
            <div key={t.id} className="surface p-3 border-l-2 border-amber-500/40" data-testid={`gf-tarea-${t.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge color={t.prioridad === "alta" ? "rose" : "amber"} text={t.prioridad.toUpperCase()} />
                    <div className="font-semibold text-sm">{t.titulo}</div>
                  </div>
                  <div className="text-xs text-zinc-400 mt-1">{t.descripcion}</div>
                  <div className="text-[10px] font-mono text-zinc-500 mt-1">
                    → {t.asignado_nombre} · {(t.created_at || "").slice(0, 16).replace("T", " ")}
                  </div>
                </div>
                {t.estado === "abierta" && (
                  <button onClick={() => cerrar(t.id)} className="btn-ghost text-xs">Cerrar</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TicketsView() {
  const [items, setItems] = useState([]);
  const [estado, setEstado] = useState("abierto");

  const load = async () => {
    const { data } = await api.get(`/greenfield/tickets?estado=${estado}`);
    setItems(data);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [estado]);

  const mover = async (tid, nuevoEstado) => {
    try { await api.patch(`/greenfield/tickets/${tid}`, { estado: nuevoEstado }); load(); }
    catch (e) { alert(formatApiError(e)); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <select className="input-field !w-auto text-xs" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="abierto">Abiertos</option>
          <option value="en_progreso">En progreso</option>
          <option value="cerrado">Cerrados</option>
        </select>
        <div className="text-xs text-zinc-400 font-mono ml-auto">{items.length} tickets</div>
      </div>
      {items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">Sin tickets.</div>
      ) : (
        <div className="space-y-2">
          {items.map((t) => (
            <div key={t.id} className="surface p-3 border-l-2 border-fuchsia-500/40" data-testid={`gf-ticket-${t.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge color={t.prioridad === "alta" ? "rose" : "amber"} text={t.prioridad.toUpperCase()} />
                    <Badge color={t.estado === "abierto" ? "fuchsia" : t.estado === "en_progreso" ? "amber" : "emerald"} text={t.estado.toUpperCase()} />
                    <div className="font-semibold text-sm">{t.titulo}</div>
                  </div>
                  <div className="text-xs text-zinc-400 mt-1 whitespace-pre-line">{t.descripcion}</div>
                  <div className="text-[10px] font-mono text-zinc-500 mt-1">
                    → {t.asignado_nombre} · {(t.created_at || "").slice(0, 16).replace("T", " ")}
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  {t.estado === "abierto" && (
                    <button onClick={() => mover(t.id, "en_progreso")} className="btn-ghost text-[10px]">→ En progreso</button>
                  )}
                  {t.estado !== "cerrado" && (
                    <button onClick={() => mover(t.id, "cerrado")} className="btn-ghost text-[10px]">→ Cerrado</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Atomos
function Badge({ color, text }) {
  return (
    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 bg-${color}-500/10 text-${color}-400 border border-${color}-500/30`}>
      {text}
    </span>
  );
}

function Loading() {
  return <div className="surface p-12 text-center text-zinc-500 text-sm"><Loader2 size={16} className="inline animate-spin mr-2" /> Cargando…</div>;
}
