import React, { useEffect, useState } from "react";
import { api, ACTIVIDAD_LABEL, fmtMXN, formatApiError } from "../lib/auth";
import { Modal } from "./ui-deyma";
import { Plus, CheckCircle2, Circle, Trash2, Paperclip, FileText, Phone, Mail, Users, MapPin, ListTodo } from "lucide-react";

const TIPO_ICON = {
  llamada: Phone, correo: Mail, reunion: Users, visita: MapPin, nota: FileText, tarea: ListTodo,
};

export default function OpDetailModal({ open, onClose, op, onChanged }) {
  const [tab, setTab] = useState("actividades");
  const [acts, setActs] = useState([]);
  const [docs, setDocs] = useState([]);
  const [formAct, setFormAct] = useState({ tipo: "llamada", fecha: new Date().toISOString().slice(0, 16), descripcion: "" });
  const [formDoc, setFormDoc] = useState({ nombre: "", tipo: "pdf", tamano_bytes: 0 });
  const [err, setErr] = useState("");

  const load = async () => {
    if (!op) return;
    const [{ data: a }, { data: d }] = await Promise.all([
      api.get(`/actividades`, { params: { oportunidad_id: op.id } }),
      api.get(`/documentos`, { params: { entidad_tipo: "oportunidad", entidad_id: op.id } }),
    ]);
    setActs(a); setDocs(d);
  };
  useEffect(() => { if (open && op) load(); /* eslint-disable-next-line */ }, [open, op]);

  const addAct = async (e) => {
    e.preventDefault(); setErr("");
    try {
      await api.post("/actividades", {
        oportunidad_id: op.id,
        tipo: formAct.tipo,
        fecha: new Date(formAct.fecha).toISOString(),
        descripcion: formAct.descripcion,
      });
      setFormAct({ tipo: "llamada", fecha: new Date().toISOString().slice(0, 16), descripcion: "" });
      load();
    } catch (e) { setErr(formatApiError(e)); }
  };

  const toggleAct = async (a) => {
    await api.patch(`/actividades/${a.id}`, { completada: !a.completada });
    load();
  };
  const delAct = async (a) => {
    await api.delete(`/actividades/${a.id}`);
    load();
  };

  const addDoc = async (e) => {
    e.preventDefault(); setErr("");
    try {
      await api.post("/documentos", {
        entidad_tipo: "oportunidad",
        entidad_id: op.id,
        nombre: formDoc.nombre,
        tipo: formDoc.tipo,
        tamano_bytes: Number(formDoc.tamano_bytes) || 0,
      });
      setFormDoc({ nombre: "", tipo: "pdf", tamano_bytes: 0 });
      load();
    } catch (e) { setErr(formatApiError(e)); }
  };

  const delDoc = async (d) => { await api.delete(`/documentos/${d.id}`); load(); };

  const convertirObra = async () => {
    setErr("");
    try {
      await api.post(`/oportunidades/${op.id}/convertir-obra`, {});
      onClose();
      if (onChanged) onChanged();
      alert("Obra creada exitosamente. Revisa el módulo de Obras.");
    } catch (e) { setErr(formatApiError(e)); }
  };

  return (
    <Modal open={open} onClose={onClose} title={op?.titulo || "Oportunidad"} size="xl" testId="op-detail-modal">
      {op && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3 text-xs">
            <div><div className="label-overline">Monto</div><div className="font-mono text-amber-400 text-base">{fmtMXN(op.monto_estimado)}</div></div>
            <div><div className="label-overline">Etapa</div><div className="font-semibold uppercase">{op.stage}</div></div>
            <div><div className="label-overline">Score IA</div><div className="font-mono text-amber-400">{op.score || 0}/100</div></div>
          </div>

          {op.stage === "ganada" && (
            <div className="surface p-3 border-l-4 border-l-emerald-500 flex items-center justify-between">
              <div>
                <div className="font-bold text-emerald-400">Oportunidad ganada</div>
                <div className="text-xs text-zinc-400">Conviértela a obra para iniciar la ejecución.</div>
              </div>
              <button data-testid="convertir-obra-btn" onClick={convertirObra} className="btn-primary">Crear obra</button>
            </div>
          )}

          <div className="flex gap-1 border-b border-white/10">
            {[
              ["actividades", `Actividades (${acts.length})`],
              ["documentos", `Documentos (${docs.length})`],
            ].map(([k, l]) => (
              <button key={k} onClick={() => setTab(k)} data-testid={`op-tab-${k}`}
                className={`px-4 py-2 text-xs font-bold tracking-wider uppercase border-b-2 -mb-px ${
                  tab === k ? "border-amber-500 text-amber-400" : "border-transparent text-zinc-500"
                }`} style={{ fontFamily: "Chivo, sans-serif" }}>{l}</button>
            ))}
          </div>

          {tab === "actividades" && (
            <div className="space-y-3">
              <form onSubmit={addAct} className="grid grid-cols-12 gap-2" data-testid="new-actividad-form">
                <select className="input-field col-span-3" value={formAct.tipo} onChange={(e) => setFormAct({ ...formAct, tipo: e.target.value })}>
                  {Object.entries(ACTIVIDAD_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <input type="datetime-local" className="input-field col-span-3 font-mono" value={formAct.fecha} onChange={(e) => setFormAct({ ...formAct, fecha: e.target.value })} required />
                <input className="input-field col-span-5" placeholder="Descripción…" value={formAct.descripcion} onChange={(e) => setFormAct({ ...formAct, descripcion: e.target.value })} required />
                <button type="submit" data-testid="add-actividad-btn" className="btn-primary col-span-1 text-xs"><Plus size={11} className="inline"/></button>
              </form>

              {acts.length === 0 ? (
                <div className="text-xs text-zinc-500 font-mono terminal-line py-4">Sin actividades registradas.</div>
              ) : (
                <div className="space-y-1">
                  {acts.map((a) => {
                    const Icon = TIPO_ICON[a.tipo] || FileText;
                    return (
                      <div key={a.id} className="surface-elev p-2 flex items-center gap-2" data-testid={`act-${a.id}`}>
                        <button onClick={() => toggleAct(a)}>
                          {a.completada ? <CheckCircle2 size={16} className="text-emerald-400"/> : <Circle size={16} className="text-zinc-500"/>}
                        </button>
                        <Icon size={13} className="text-zinc-400"/>
                        <div className="flex-1 min-w-0">
                          <div className={`text-xs ${a.completada ? "line-through text-zinc-500" : ""}`}>{a.descripcion}</div>
                          <div className="text-[10px] text-zinc-500 font-mono">{new Date(a.fecha).toLocaleString("es-MX", { day:"2-digit", month:"short", hour:"2-digit", minute:"2-digit" })}</div>
                        </div>
                        <button onClick={() => delAct(a)} className="text-rose-400 hover:text-rose-300"><Trash2 size={12}/></button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {tab === "documentos" && (
            <div className="space-y-3">
              <div className="surface-elev p-3 text-[11px] text-zinc-400 border-l-2 border-l-amber-500">
                <span className="badge text-amber-400 border-amber-400/40 mr-2">MOCK</span>
                Sistema de archivos en modo metadatos (sin storage binario). Para activar uploads reales, integrar Cloudinary/S3 en una próxima iteración.
              </div>
              <form onSubmit={addDoc} className="grid grid-cols-12 gap-2" data-testid="new-doc-form">
                <input className="input-field col-span-6" placeholder="Nombre del archivo (ej. plano_planta_a.pdf)" value={formDoc.nombre} onChange={(e) => setFormDoc({ ...formDoc, nombre: e.target.value })} required />
                <select className="input-field col-span-2" value={formDoc.tipo} onChange={(e) => setFormDoc({ ...formDoc, tipo: e.target.value })}>
                  <option value="pdf">PDF</option><option value="dwg">DWG</option><option value="xlsx">XLSX</option>
                  <option value="jpg">JPG</option><option value="png">PNG</option><option value="doc">DOC</option>
                </select>
                <input type="number" className="input-field col-span-3 font-mono" placeholder="Tamaño (bytes)" value={formDoc.tamano_bytes} onChange={(e) => setFormDoc({ ...formDoc, tamano_bytes: e.target.value })} />
                <button type="submit" data-testid="add-doc-btn" className="btn-primary col-span-1 text-xs"><Plus size={11} className="inline"/></button>
              </form>

              {docs.length === 0 ? (
                <div className="text-xs text-zinc-500 font-mono terminal-line py-4">Sin documentos adjuntos.</div>
              ) : (
                <div className="space-y-1">
                  {docs.map((d) => (
                    <div key={d.id} className="surface-elev p-2 flex items-center gap-2" data-testid={`doc-${d.id}`}>
                      <Paperclip size={13} className="text-amber-400"/>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold truncate">{d.nombre}</div>
                        <div className="text-[10px] text-zinc-500 font-mono">{d.tipo.toUpperCase()} · {(d.tamano_bytes/1024).toFixed(1)} KB · {d.uploaded_by_name || "—"}</div>
                      </div>
                      <button onClick={() => delDoc(d)} className="text-rose-400 hover:text-rose-300"><Trash2 size={12}/></button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {err && <div className="text-rose-400 text-xs">{err}</div>}
        </div>
      )}
    </Modal>
  );
}
