import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/auth";
import {
  Search, MessageCircle, Trash2, Edit3, Send, Phone, Mail,
  ExternalLink, Loader2, CheckCircle2, AlertOctagon, ArrowUpRight, Bot,
} from "lucide-react";
import { Modal } from "../../components/ui-deyma";

const URG_COLOR = { alto: "rose", medio: "amber", bajo: "emerald" };
const EST_LABEL = {
  nuevo: "Nuevo", contactado: "Contactado", calificado: "Calificado",
  ganado: "Ganado", descartado: "Descartado",
};

export default function CondoCazaLeadsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [estado, setEstado] = useState("");
  const [urgencia, setUrgencia] = useState("");
  const [notice, setNotice] = useState(null);
  const [edit, setEdit] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = [];
      if (estado) params.push(`estado=${estado}`);
      if (urgencia) params.push(`urgencia=${urgencia}`);
      const q = params.length ? `?${params.join("&")}` : "";
      const { data } = await api.get(`/condo/leads${q}`);
      setItems(data);
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [estado, urgencia]);

  const runSabueso = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/condo/run/sabueso");
      if (data.mock) setNotice({ kind: "warn", msg: "⚠️ OSINT en modo MOCK. Configura APIFY_TOKEN y OSINT_MODE=live." });
      else setNotice({ kind: "ok", msg: `🐶 Sabueso terminó: ${data.inserted || 0} nuevos · ${data.updated || 0} actualizados` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setRunning(false); }
  };

  const promover = async (l) => {
    if (!window.confirm(`Promover "${l.condominio_nombre}" al CRM Comercial?`)) return;
    try {
      await api.post(`/condo/leads/${l.id}/promover-crm`);
      setNotice({ kind: "ok", msg: `✓ ${l.condominio_nombre} promovido al CRM` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  const eliminar = async (l) => {
    if (!window.confirm(`¿Eliminar "${l.condominio_nombre}"?`)) return;
    try { await api.delete(`/condo/leads/${l.id}`); load(); }
    catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  const waManual = (l) => {
    const tel = (l.telefono || "").replace(/\D/g, "");
    if (!tel) { setNotice({ kind: "err", msg: "Sin teléfono" }); return; }
    const msg = `Hola, le saluda DEYMA Desarrollo y Mantenimiento. Detectamos que administra ${l.condominio_nombre || "su fraccionamiento"} y nos gustaría apoyarle con soluciones de mantenimiento industrial y servicios. ¿Tiene 5 min?`;
    window.open(`https://wa.me/52${tel}?text=${encodeURIComponent(msg)}`, "_blank");
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-4" data-testid="condo-cazaleads-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Bot size={11}/> V6.0 · Radar de Condominios · Agente Sabueso
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Caza-Leads <span className="text-amber-400">·</span> Administradores
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Apify Google Search · &quot;administrador de condominio&quot; · Querétaro
          </div>
        </div>
        <button onClick={runSabueso} disabled={running} className="btn-primary text-xs disabled:opacity-50" data-testid="btn-run-sabueso">
          {running ? <Loader2 size={12} className="inline mr-1 animate-spin"/> : <Search size={12} className="inline mr-1"/>}
          {running ? "Cazando..." : "Ejecutar Sabueso"}
        </button>
      </header>

      {notice && (
        <div className={`surface p-3 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5"
                                                   : notice.kind === "warn" ? "border-amber-500 bg-amber-500/5"
                                                   : "border-rose-500 bg-rose-500/5"}`} data-testid="condo-notice">
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
        <select value={estado} onChange={(e) => setEstado(e.target.value)} className="input-field !w-auto text-xs" data-testid="filter-estado">
          <option value="">Todos los estados</option>
          {Object.entries(EST_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={urgencia} onChange={(e) => setUrgencia(e.target.value)} className="input-field !w-auto text-xs" data-testid="filter-urgencia">
          <option value="">Toda urgencia</option>
          <option value="alto">Alto</option>
          <option value="medio">Medio</option>
          <option value="bajo">Bajo</option>
        </select>
        <div className="text-xs text-zinc-400 font-mono ml-auto">
          <span className="text-amber-400 font-bold">{items.length}</span> leads
        </div>
      </div>

      {loading ? (
        <div className="surface p-8 text-center text-zinc-500">
          <Loader2 size={16} className="inline animate-spin mr-2"/> Cargando…
        </div>
      ) : items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">
          Sin administradores cazados aún. Dale click a <strong>Ejecutar Sabueso</strong> para lanzar la primera barrida o espera al cron (04:00 CDMX).
        </div>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="dtable" data-testid="condo-leads-table">
            <thead><tr>
              <th>Condominio</th><th>Contacto</th><th>Tel / Email</th><th>Urgencia</th>
              <th>Casas</th><th>Estado</th><th>Detectado</th><th>Acciones</th>
            </tr></thead>
            <tbody>
              {items.map((l) => {
                const ucol = URG_COLOR[l.urgencia] || "zinc";
                return (
                  <tr key={l.id} data-testid={`condo-lead-${l.id}`}>
                    <td>
                      <div className="font-semibold">{l.condominio_nombre}</div>
                      <div className="text-[11px] text-zinc-400">{l.ubicacion || "—"}</div>
                      {l.source_url && (
                        <a href={l.source_url} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 hover:underline">
                          fuente <ExternalLink size={8} className="inline"/>
                        </a>
                      )}
                    </td>
                    <td className="text-xs">
                      <div>{l.contacto_nombre || "—"}</div>
                      <div className="text-[10px] text-zinc-500">{l.contacto_puesto}</div>
                    </td>
                    <td className="text-[10px] font-mono">
                      {l.telefono && <div className="text-sky-400"><Phone size={9} className="inline mr-1"/>{l.telefono}</div>}
                      {l.email && <div className="text-emerald-400"><Mail size={9} className="inline mr-1"/>{l.email}</div>}
                      {!l.telefono && !l.email && <span className="text-zinc-600">—</span>}
                    </td>
                    <td>
                      <span className={`text-[10px] font-mono uppercase bg-${ucol}-500/10 text-${ucol}-400 border border-${ucol}-500/30 px-1.5 py-0.5`}>
                        {l.urgencia || "—"}
                      </span>
                    </td>
                    <td className="font-mono text-amber-400 text-center text-xs">
                      {l.num_casas_estimado ? `~${l.num_casas_estimado}` : "—"}
                      {l.es_mega && <div className="text-[9px] text-rose-400 font-bold">MEGA</div>}
                    </td>
                    <td className="text-[10px] font-mono text-zinc-400">{EST_LABEL[l.estado] || l.estado}</td>
                    <td className="text-[10px] font-mono text-zinc-500">{(l.ultima_deteccion || "").slice(0, 10)}</td>
                    <td className="text-right whitespace-nowrap">
                      <button onClick={() => waManual(l)} disabled={!l.telefono}
                              className="text-emerald-400 hover:text-emerald-300 disabled:opacity-30 mr-2"
                              title="WhatsApp manual" data-testid={`btn-wa-${l.id}`}>
                        <MessageCircle size={12}/>
                      </button>
                      <button onClick={() => promover(l)} className="text-amber-400 hover:text-amber-300 mr-2"
                              title="Promover a CRM" data-testid={`btn-promover-${l.id}`}>
                        <ArrowUpRight size={12}/>
                      </button>
                      <button onClick={() => setEdit(l)} className="text-zinc-400 hover:text-amber-400 mr-2" title="Editar">
                        <Edit3 size={12}/>
                      </button>
                      <button onClick={() => eliminar(l)} className="text-rose-400 hover:text-rose-300" title="Eliminar">
                        <Trash2 size={12}/>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <EditCondoLead lead={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }}/>
    </div>
  );
}

function EditCondoLead({ lead, onClose, onSaved }) {
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (lead) setF({
      condominio_nombre: lead.condominio_nombre || "",
      contacto_nombre: lead.contacto_nombre || "",
      contacto_puesto: lead.contacto_puesto || "",
      telefono: lead.telefono || "",
      email: lead.email || "",
      ubicacion: lead.ubicacion || "",
      urgencia: lead.urgencia || "medio",
      problema_principal: lead.problema_principal || "",
      num_casas_estimado: lead.num_casas_estimado || "",
      estado: lead.estado || "nuevo",
      notas: lead.notas || "",
    });
  }, [lead]);
  if (!lead) return null;
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    const body = { ...f };
    if (body.num_casas_estimado === "") body.num_casas_estimado = null;
    else body.num_casas_estimado = parseInt(body.num_casas_estimado, 10) || null;
    try { await api.patch(`/condo/leads/${lead.id}`, body); onSaved(); }
    finally { setBusy(false); }
  };
  return (
    <Modal open={!!lead} onClose={onClose} title={`Editar — ${lead.condominio_nombre}`} testId="edit-condo-lead-modal">
      <form onSubmit={submit} className="space-y-3 text-xs">
        <input className="input-field" placeholder="Nombre condominio" value={f.condominio_nombre}
               onChange={(e) => setF({ ...f, condominio_nombre: e.target.value })}/>
        <div className="grid grid-cols-2 gap-2">
          <input className="input-field" placeholder="Contacto" value={f.contacto_nombre}
                 onChange={(e) => setF({ ...f, contacto_nombre: e.target.value })}/>
          <input className="input-field" placeholder="Puesto" value={f.contacto_puesto}
                 onChange={(e) => setF({ ...f, contacto_puesto: e.target.value })}/>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <input className="input-field font-mono" placeholder="Teléfono" value={f.telefono}
                 onChange={(e) => setF({ ...f, telefono: e.target.value })}/>
          <input className="input-field font-mono" placeholder="Email" type="email" value={f.email}
                 onChange={(e) => setF({ ...f, email: e.target.value })}/>
        </div>
        <input className="input-field" placeholder="Ubicación" value={f.ubicacion}
               onChange={(e) => setF({ ...f, ubicacion: e.target.value })}/>
        <div className="grid grid-cols-3 gap-2">
          <select className="input-field" value={f.urgencia} onChange={(e) => setF({ ...f, urgencia: e.target.value })}>
            <option value="alto">Alto</option><option value="medio">Medio</option><option value="bajo">Bajo</option>
          </select>
          <input className="input-field font-mono" placeholder="Casas (est.)" type="number" value={f.num_casas_estimado}
                 onChange={(e) => setF({ ...f, num_casas_estimado: e.target.value })}/>
          <select className="input-field" value={f.estado} onChange={(e) => setF({ ...f, estado: e.target.value })}>
            {Object.entries(EST_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <input className="input-field" placeholder="Problema principal" value={f.problema_principal}
               onChange={(e) => setF({ ...f, problema_principal: e.target.value })}/>
        <textarea className="input-field" style={{ height: 100 }} placeholder="Notas" value={f.notas}
                  onChange={(e) => setF({ ...f, notas: e.target.value })}/>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary">{busy ? "Guardando…" : "Guardar"}</button>
        </div>
      </form>
    </Modal>
  );
}
