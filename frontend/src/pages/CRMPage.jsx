import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, formatApiError, SECTOR_LABEL, STAGE_LABEL, STAGE_ORDER } from "../lib/auth";
import { Modal, Hotness, ScoreBar, StageBadge, EmptyState } from "../components/ui-deyma";
import OpDetailModal from "../components/OpDetailModal";
import ContactQuickActions from "../components/ContactQuickActions";
import { Plus, Sparkles, Mail, Eye } from "lucide-react";

export default function CRMPage() {
  const [tab, setTab] = useState("pipeline");
  const [empresas, setEmpresas] = useState([]);
  const [contactos, setContactos] = useState([]);
  const [ops, setOps] = useState([]);
  const [openOp, setOpenOp] = useState(false);
  const [openEmp, setOpenEmp] = useState(false);
  const [emailModal, setEmailModal] = useState(null);
  const [detailOp, setDetailOp] = useState(null);

  const load = async () => {
    const [e, c, o] = await Promise.all([api.get("/empresas"), api.get("/contactos"), api.get("/oportunidades")]);
    setEmpresas(e.data); setContactos(c.data); setOps(o.data);
  };
  useEffect(() => { load(); }, []);

  const byStage = useMemo(() => {
    const g = Object.fromEntries(STAGE_ORDER.map((s) => [s, []]));
    ops.forEach((o) => { (g[o.stage] || g.prospeccion).push(o); });
    return g;
  }, [ops]);

  const empName = (id) => empresas.find((e) => e.id === id)?.nombre || "—";

  const moveStage = async (opId, stage) => {
    await api.patch(`/oportunidades/${opId}`, { stage });
    load();
  };

  const scoreOp = async (opId) => {
    await api.post(`/oportunidades/${opId}/score`);
    load();
  };

  const genEmail = async (op) => {
    setEmailModal({ loading: true, op });
    try {
      const { data } = await api.post(`/oportunidades/${op.id}/followup-email`);
      setEmailModal({ op, ...data });
    } catch (e) { setEmailModal({ op, subject: "Error", body: formatApiError(e) }); }
  };

  return (
    <div className="p-6 space-y-5" data-testid="crm-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Customer Relationship Management</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>CRM Comercial</h1>
        </div>
        <div className="flex gap-2">
          <button data-testid="new-empresa-btn" onClick={() => setOpenEmp(true)} className="btn-ghost flex items-center gap-2"><Plus size={14} strokeWidth={2} /> Empresa</button>
          <button data-testid="new-op-btn" onClick={() => setOpenOp(true)} className="btn-primary flex items-center gap-2"><Plus size={14} strokeWidth={2} /> Oportunidad</button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-white/10">
        {[
          ["pipeline", "Pipeline (Kanban)"],
          ["empresas", `Empresas (${empresas.length})`],
          ["contactos", `Contactos (${contactos.length})`],
        ].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`tab-${k}`}
            className={`px-4 py-2 text-xs font-bold tracking-wider uppercase border-b-2 -mb-px ${
              tab === k ? "border-amber-500 text-amber-400" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`} style={{ fontFamily: "Chivo, sans-serif" }}>{l}</button>
        ))}
      </div>

      {tab === "pipeline" && (
        <div className="overflow-x-auto pb-4">
          <div className="flex gap-3 min-w-max">
            {STAGE_ORDER.map((s) => (
              <div key={s} className="kanban-col w-64 flex-shrink-0" data-testid={`kanban-col-${s}`}>
                <div className="surface p-3 mb-2 flex items-center justify-between">
                  <StageBadge stage={s} />
                  <span className="font-mono text-xs text-zinc-400">{byStage[s].length}</span>
                </div>
                <div className="space-y-2">
                  {byStage[s].map((op) => (
                    <div key={op.id} className={`kanban-card ${kanbanBorder(s)}`} data-testid={`op-card-${op.id}`}>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="text-sm font-semibold leading-tight">{op.titulo}</div>
                        <Hotness value={op.hotness} />
                      </div>
                      <div className="text-[11px] text-zinc-400 mb-1">{empName(op.empresa_id)}</div>
                      <div className="text-[10px] text-zinc-500 mb-2">{SECTOR_LABEL[op.sector]}</div>
                      <div className="font-mono text-amber-400 text-sm mb-2">{fmtMXN(op.monto_estimado)}</div>
                      <ScoreBar value={op.score || 0} />
                      <div className="mt-3 flex items-center gap-1 flex-wrap">
                        <button data-testid={`score-btn-${op.id}`} onClick={() => scoreOp(op.id)} className="text-[10px] px-2 py-1 border border-amber-500/40 text-amber-400 hover:bg-amber-500/10 flex items-center gap-1" title="Calificar con IA">
                          <Sparkles size={10} /> IA
                        </button>
                        <button data-testid={`email-btn-${op.id}`} onClick={() => genEmail(op)} className="text-[10px] px-2 py-1 border border-sky-500/40 text-sky-400 hover:bg-sky-500/10 flex items-center gap-1" title="Generar correo">
                          <Mail size={10} /> Correo
                        </button>
                        <button data-testid={`detail-btn-${op.id}`} onClick={() => setDetailOp(op)} className="text-[10px] px-2 py-1 border border-white/15 text-zinc-300 hover:bg-white/5 flex items-center gap-1" title="Ver detalle, actividades y documentos">
                          <Eye size={10} /> Ver
                        </button>
                        <select
                          data-testid={`stage-select-${op.id}`}
                          value={s} onChange={(e) => moveStage(op.id, e.target.value)}
                          className="text-[10px] bg-zinc-900 border border-white/10 px-1 py-1 text-zinc-300 ml-auto"
                        >
                          {STAGE_ORDER.map((x) => <option key={x} value={x}>{STAGE_LABEL[x]}</option>)}
                        </select>
                      </div>
                    </div>
                  ))}
                  {byStage[s].length === 0 && <div className="text-[10px] text-zinc-600 font-mono p-2">// vacío</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "empresas" && (
        empresas.length === 0 ? <EmptyState title="Sin empresas" /> : (
          <div className="surface overflow-x-auto">
            <table className="dtable">
              <thead><tr><th>Empresa</th><th>Sector</th><th>Ciudad</th><th>Estado</th><th>Sitio</th><th>Notas</th></tr></thead>
              <tbody>
                {empresas.map((e) => (
                  <tr key={e.id} data-testid={`empresa-row-${e.id}`}>
                    <td className="font-semibold">{e.nombre}</td>
                    <td className="text-xs text-zinc-400">{SECTOR_LABEL[e.sector]}</td>
                    <td className="text-xs">{e.ciudad}</td>
                    <td className="text-xs">{e.estado}</td>
                    <td className="text-xs text-sky-400">{e.sitio_web || "—"}</td>
                    <td className="text-xs text-zinc-500 max-w-md truncate">{e.notas || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === "contactos" && (
        contactos.length === 0 ? <EmptyState title="Sin contactos" /> : (
          <div className="surface overflow-x-auto">
            <table className="dtable">
              <thead><tr><th>Nombre</th><th>Puesto</th><th>Empresa</th><th>Email</th><th>Tel</th><th>Acciones</th></tr></thead>
              <tbody>
                {contactos.map((c) => (
                  <tr key={c.id}>
                    <td className="font-semibold">{c.nombre}</td>
                    <td className="text-xs">{c.puesto}</td>
                    <td className="text-xs">{empName(c.empresa_id)}</td>
                    <td className="text-xs text-sky-400">{c.email}</td>
                    <td className="text-xs font-mono">{c.telefono}</td>
                    <td>
                      <ContactQuickActions
                        tel={c.telefono}
                        email={c.email}
                        linkedin={c.linkedin}
                        subject={`DEYMA · Seguimiento ${empName(c.empresa_id)}`}
                        mensaje={`Hola ${c.nombre}, le escribe el equipo comercial de DEYMA. Quería darle seguimiento a la propuesta de canastillas pasajuntas para sus proyectos.`}
                        size="sm"
                        testIdPrefix={`cqa-cont-${c.id}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      <NewOpModal open={openOp} onClose={() => setOpenOp(false)} empresas={empresas} onSaved={() => { setOpenOp(false); load(); }} />
      <NewEmpresaModal open={openEmp} onClose={() => setOpenEmp(false)} onSaved={() => { setOpenEmp(false); load(); }} />
      <OpDetailModal open={!!detailOp} onClose={() => setDetailOp(null)} op={detailOp} onChanged={load} />

      <Modal open={!!emailModal} onClose={() => setEmailModal(null)} title="Correo de seguimiento (IA)" size="lg" testId="email-modal">
        {emailModal?.loading ? (
          <div className="font-mono text-xs text-zinc-400 terminal-line py-8 text-center">Generando con GPT-5.2…</div>
        ) : (
          <div className="space-y-3">
            <div className="label-overline">Asunto</div>
            <div className="surface-elev p-3 text-sm font-semibold" data-testid="email-subject">{emailModal?.subject}</div>
            <div className="label-overline">Cuerpo</div>
            <pre className="surface-elev p-3 text-xs whitespace-pre-wrap leading-relaxed" data-testid="email-body">{emailModal?.body}</pre>
            <button onClick={() => { navigator.clipboard.writeText(`Asunto: ${emailModal.subject}\n\n${emailModal.body}`); }} className="btn-primary">Copiar al portapapeles</button>
          </div>
        )}
      </Modal>
    </div>
  );
}

function kanbanBorder(s) {
  return ({
    prospeccion: "border-l-zinc-500",
    calificada: "border-l-sky-500",
    propuesta: "border-l-blue-500",
    negociacion: "border-l-amber-500",
    ganada: "border-l-emerald-500",
    perdida: "border-l-rose-500",
  })[s];
}

function NewOpModal({ open, onClose, empresas, onSaved }) {
  const [form, setForm] = useState({ empresa_id: "", titulo: "", sector: "cedis_logistica", descripcion: "", monto_estimado: 1000000, probabilidad: 20, stage: "prospeccion" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      await api.post("/oportunidades", { ...form, monto_estimado: Number(form.monto_estimado), probabilidad: Number(form.probabilidad) });
      onSaved();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Nueva oportunidad" size="lg" testId="new-op-modal">
      <form onSubmit={submit} className="space-y-3" data-testid="new-op-form">
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="label-overline">Empresa</label>
            <select required data-testid="op-empresa-select" className="input-field" value={form.empresa_id} onChange={(e) => setForm({ ...form, empresa_id: e.target.value })}>
              <option value="">Selecciona…</option>
              {empresas.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="label-overline">Título</label>
            <input data-testid="op-titulo-input" className="input-field" required value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })} />
          </div>
          <div>
            <label className="label-overline">Sector</label>
            <select data-testid="op-sector-select" className="input-field" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })}>
              {Object.entries(SECTOR_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="label-overline">Etapa</label>
            <select data-testid="op-stage-select" className="input-field" value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}>
              {STAGE_ORDER.map((s) => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}
            </select>
          </div>
          <div>
            <label className="label-overline">Monto MXN</label>
            <input data-testid="op-monto-input" type="number" className="input-field" required value={form.monto_estimado} onChange={(e) => setForm({ ...form, monto_estimado: e.target.value })} />
          </div>
          <div>
            <label className="label-overline">Probabilidad %</label>
            <input data-testid="op-prob-input" type="number" min="0" max="100" className="input-field" value={form.probabilidad} onChange={(e) => setForm({ ...form, probabilidad: e.target.value })} />
          </div>
          <div className="col-span-2">
            <label className="label-overline">Descripción</label>
            <textarea data-testid="op-desc-input" className="input-field" style={{ height: 80 }} required value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
          </div>
        </div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="op-submit-btn" disabled={busy} className="btn-primary">{busy ? "Guardando…" : "Guardar oportunidad"}</button>
        </div>
      </form>
    </Modal>
  );
}

function NewEmpresaModal({ open, onClose, onSaved }) {
  const [form, setForm] = useState({ nombre: "", sector: "manufactura", ciudad: "Querétaro", estado: "Querétaro", sitio_web: "", notas: "" });
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try { await api.post("/empresas", form); onSaved(); }
    catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Nueva empresa" testId="new-empresa-modal">
      <form onSubmit={submit} className="space-y-3">
        <div><label className="label-overline">Nombre</label><input data-testid="emp-nombre-input" required className="input-field" value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></div>
        <div><label className="label-overline">Sector</label>
          <select data-testid="emp-sector-select" className="input-field" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })}>
            {Object.entries(SECTOR_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label-overline">Ciudad</label><input className="input-field" value={form.ciudad} onChange={(e) => setForm({ ...form, ciudad: e.target.value })} /></div>
          <div><label className="label-overline">Estado</label><input className="input-field" value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value })} /></div>
        </div>
        <div><label className="label-overline">Sitio web</label><input className="input-field" value={form.sitio_web} onChange={(e) => setForm({ ...form, sitio_web: e.target.value })} /></div>
        <div><label className="label-overline">Notas</label><textarea className="input-field" style={{ height: 70 }} value={form.notas} onChange={(e) => setForm({ ...form, notas: e.target.value })} /></div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="emp-submit-btn" disabled={busy} className="btn-primary">{busy ? "Guardando…" : "Guardar"}</button>
        </div>
      </form>
    </Modal>
  );
}
