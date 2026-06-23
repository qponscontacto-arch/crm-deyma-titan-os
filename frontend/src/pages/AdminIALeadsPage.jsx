import React, { useState, useEffect } from "react";
import { api, formatApiError } from "../lib/auth";
import { Modal } from "../components/ui-deyma";
import {
  Bot, Send, MessageCircle, Loader2, ExternalLink, Trash2, Edit3,
  Copy, Webhook, Key, CheckCircle2, AlertOctagon, Settings,
} from "lucide-react";

const ESTADO_LABELS = {
  prospecto_detectado_ia: { label: "Detectado IA", color: "amber" },
  invitado_grupo: { label: "Invitado a Grupo", color: "emerald" },
  contactado: { label: "Contactado", color: "sky" },
  calificado: { label: "Calificado", color: "indigo" },
  descartado: { label: "Descartado", color: "rose" },
};

export default function AdminIALeadsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [estado, setEstado] = useState("");
  const [showWebhook, setShowWebhook] = useState(false);
  const [notice, setNotice] = useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const q = estado ? `?estado=${estado}` : "";
      const { data } = await api.get(`/ia-leads${q}`);
      setItems(data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [estado]);

  const invitar = async (lead) => {
    if (busy === lead.id) return;
    if (!lead.telefono) {
      setNotice({ kind: "err", msg: "Este lead no tiene teléfono — no se puede invitar automáticamente. Usa el botón WhatsApp Manual." });
      return;
    }
    if (!window.confirm(`¿Enviar invitación automática al grupo a ${lead.contacto_nombre || lead.empresa}?`)) return;
    setBusy(lead.id);
    try {
      const { data } = await api.post(`/ia-leads/${lead.id}/invitar`);
      if (data.ok) {
        setNotice({ kind: "ok", msg: `✓ Invitación enviada a ${lead.contacto_nombre || lead.empresa}` });
      } else if (data.mock) {
        setNotice({ kind: "warn", msg: `⚠️ Twilio en modo MOCK — el mensaje se logueó pero no se envió. Configura las env vars en producción.` });
      } else {
        setNotice({ kind: "err", msg: `Error: ${data.error || "no enviado"}` });
      }
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setBusy(null); }
  };

  const manualWA = (lead) => {
    const tel = (lead.telefono || "").replace(/[^\d+]/g, "").replace(/^\+/, "");
    if (!tel) { setNotice({ kind: "err", msg: "Sin teléfono" }); return; }
    const nombre = lead.contacto_nombre || lead.empresa;
    const ubic = lead.ubicacion || "su zona";
    const msg = `Hola ${nombre}, le saluda el equipo de DEYMA Desarrollo y Mantenimiento. Detectamos que están liderando proyectos de infraestructura en ${ubic}. Lo invitamos a sumarse a nuestra Red de Macroproyectos Industriales en WhatsApp.`;
    window.open(`https://wa.me/${tel}?text=${encodeURIComponent(msg)}`, "_blank");
  };

  const eliminar = async (lead) => {
    if (!window.confirm(`¿Eliminar permanentemente el lead "${lead.empresa}"?`)) return;
    try { await api.delete(`/ia-leads/${lead.id}`); load(); }
    catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-4" data-testid="ia-leads-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Bot size={11}/> V5.7 · Integración Opp-Detector
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Detecciones <span className="text-amber-400">·</span> IA Leads
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Webhook: <code>POST /api/v1/ia-leads</code> · dedupe automático por email/tel
          </div>
        </div>
        <button onClick={() => setShowWebhook(true)} className="btn-ghost text-xs" data-testid="btn-webhook-info">
          <Webhook size={12} className="inline mr-1"/> Webhook & API Key
        </button>
      </header>

      {notice && (
        <div className={`surface p-3 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5"
                                                  : notice.kind === "warn" ? "border-amber-500 bg-amber-500/5"
                                                  : "border-rose-500 bg-rose-500/5"}`}
             data-testid="ia-leads-notice">
          <div className="flex items-start justify-between gap-2">
            <div className={`text-sm ${notice.kind === "ok" ? "text-emerald-400" : notice.kind === "warn" ? "text-amber-400" : "text-rose-400"}`}>
              {notice.kind === "ok" ? <CheckCircle2 size={14} className="inline mr-2"/>
                                    : <AlertOctagon size={14} className="inline mr-2"/>}
              {notice.msg}
            </div>
            <button onClick={() => setNotice(null)} className="text-zinc-500 hover:text-zinc-300">✕</button>
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="flex items-center gap-2 flex-wrap">
        <select value={estado} onChange={(e) => setEstado(e.target.value)} className="input-field !w-auto text-xs" data-testid="filter-estado">
          <option value="">Todos los estados</option>
          {Object.entries(ESTADO_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
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
          Sin leads detectados aún. Cuando opp-detector envíe webhooks aparecerán aquí.
          <br/><br/>
          <button onClick={() => setShowWebhook(true)} className="btn-ghost text-xs">
            <Webhook size={12} className="inline mr-1"/> Ver instrucciones de configuración
          </button>
        </div>
      ) : (
        <div className="surface overflow-x-auto">
          <table className="dtable" data-testid="ia-leads-table">
            <thead><tr>
              <th>Empresa / Contacto</th><th>Ubicación</th><th>Notas detección</th>
              <th>Estado</th><th>Det.</th><th>Detectado</th><th>Acciones</th>
            </tr></thead>
            <tbody>
              {items.map((l) => {
                const meta = ESTADO_LABELS[l.estado] || { label: l.estado, color: "zinc" };
                return (
                  <tr key={l.id} data-testid={`ia-lead-${l.id}`}>
                    <td>
                      <div className="font-semibold">{l.empresa}</div>
                      {l.contacto_nombre && (
                        <div className="text-[11px] text-zinc-400 mt-0.5">
                          {l.contacto_nombre}{l.contacto_puesto ? ` · ${l.contacto_puesto}` : ""}
                        </div>
                      )}
                      <div className="text-[10px] font-mono mt-0.5">
                        {l.email && <span className="text-emerald-400 mr-2">📧 {l.email}</span>}
                        {l.telefono && <span className="text-sky-400">📞 {l.telefono}</span>}
                      </div>
                    </td>
                    <td className="text-xs">{l.ubicacion || "—"}</td>
                    <td className="text-[11px] text-zinc-400 max-w-[280px]">
                      <div className="line-clamp-3 whitespace-pre-wrap">{l.notas_contexto || "—"}</div>
                      {l.oportunidad_url && (
                        <a href={l.oportunidad_url} target="_blank" rel="noreferrer"
                           className="text-[10px] text-sky-400 hover:underline mt-1 inline-block">
                          fuente <ExternalLink size={8} className="inline"/>
                        </a>
                      )}
                    </td>
                    <td>
                      <span className={`text-[10px] font-mono uppercase bg-${meta.color}-500/10 text-${meta.color}-400 border border-${meta.color}-500/30 px-1.5 py-0.5`}>
                        {meta.label}
                      </span>
                      {l.invitacion_enviada && (
                        <div className="text-[9px] font-mono text-emerald-400 mt-0.5">
                          ✓ {l.invitacion_fecha?.slice(0, 10)}
                        </div>
                      )}
                    </td>
                    <td className="font-mono text-amber-400 font-bold text-center">{l.veces_detectado || 1}x</td>
                    <td className="text-[10px] font-mono text-zinc-500">{l.ultima_deteccion?.slice(0, 10)}</td>
                    <td className="text-right whitespace-nowrap">
                      <button
                        onClick={() => invitar(l)}
                        disabled={busy === l.id || !l.telefono}
                        title={l.telefono ? "Enviar invitación automática" : "Sin teléfono"}
                        className="text-emerald-400 hover:text-emerald-300 disabled:opacity-30 mr-2"
                        data-testid={`btn-invitar-${l.id}`}
                      >
                        {busy === l.id ? <Loader2 size={12} className="animate-spin"/> : <Send size={12}/>}
                      </button>
                      <button
                        onClick={() => manualWA(l)}
                        disabled={!l.telefono}
                        title="WhatsApp manual"
                        className="text-sky-400 hover:text-sky-300 disabled:opacity-30 mr-2"
                        data-testid={`btn-wa-manual-${l.id}`}
                      >
                        <MessageCircle size={12}/>
                      </button>
                      <button onClick={() => setEditTarget(l)} className="text-zinc-400 hover:text-amber-400 mr-2" title="Editar">
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

      <WebhookInfoModal open={showWebhook} onClose={() => setShowWebhook(false)}/>
      <EditModal lead={editTarget} onClose={() => setEditTarget(null)} onSaved={() => { setEditTarget(null); load(); }}/>
    </div>
  );
}

function WebhookInfoModal({ open, onClose }) {
  const [info, setInfo] = useState(null);
  const [copied, setCopied] = useState("");
  useEffect(() => {
    if (open) api.get("/ia-leads/webhook-info").then(r => setInfo(r.data)).catch(() => {});
  }, [open]);
  const copy = (val, key) => {
    navigator.clipboard.writeText(val); setCopied(key); setTimeout(() => setCopied(""), 2000);
  };
  if (!info) return open ? <Modal open={open} onClose={onClose} title="Cargando…"><Loader2 size={16} className="animate-spin"/></Modal> : null;
  return (
    <Modal open={open} onClose={onClose} title="Configuración del Webhook" testId="webhook-info-modal">
      <div className="space-y-3 text-xs">
        <div className="surface-elev p-3 border-l-4 border-amber-500 bg-amber-500/5">
          <Key size={12} className="inline mr-1 text-amber-400"/>
          <strong>Solo Director ve estas credenciales.</strong> Configúralas UNA SOLA VEZ en opp-detector.
        </div>

        <div>
          <label className="label-overline">URL del Webhook</label>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-zinc-900 p-2 font-mono text-[11px] break-all">{info.webhook_url}</code>
            <button onClick={() => copy(info.webhook_url, "url")} className="btn-ghost text-[10px]">
              {copied === "url" ? <CheckCircle2 size={11}/> : <Copy size={11}/>}
            </button>
          </div>
        </div>

        <div>
          <label className="label-overline">Header de Autenticación</label>
          <code className="block bg-zinc-900 p-2 font-mono text-[11px]">
            {info.header_name}: <span className="text-amber-400">{info.api_key}</span>
          </code>
          <button onClick={() => copy(info.api_key, "key")} className="text-[10px] text-amber-400 mt-1">
            {copied === "key" ? "✓ Copiada" : <><Copy size={9} className="inline mr-1"/>Copiar API Key</>}
          </button>
        </div>

        <div>
          <label className="label-overline">Ejemplo de Payload (JSON)</label>
          <pre className="bg-zinc-900 p-2 font-mono text-[10px] overflow-x-auto whitespace-pre-wrap">
{JSON.stringify(info.example_payload, null, 2)}
          </pre>
        </div>

        <div className="surface-elev p-2.5">
          <div className="label-overline text-[9px] text-emerald-400 mb-1">Enlace del grupo WhatsApp (mensaje de invitación)</div>
          <code className="block font-mono text-[11px] text-emerald-400 break-all">{info.whatsapp_group_link}</code>
        </div>

        <div className="surface-elev p-2.5 bg-sky-500/5 border-sky-500/30">
          <Settings size={11} className="inline mr-1 text-sky-400"/>
          <strong className="text-sky-400">Ejemplo cURL:</strong>
          <pre className="font-mono text-[10px] mt-1 whitespace-pre-wrap break-all">{`curl -X POST "${info.webhook_url}" \\
  -H "Content-Type: application/json" \\
  -H "${info.header_name}: ${info.api_key}" \\
  -d '${JSON.stringify(info.example_payload)}'`}</pre>
        </div>
      </div>
    </Modal>
  );
}

function EditModal({ lead, onClose, onSaved }) {
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (lead) setF({
      contacto_nombre: lead.contacto_nombre || "",
      contacto_puesto: lead.contacto_puesto || "",
      telefono: lead.telefono || "",
      email: lead.email || "",
      ubicacion: lead.ubicacion || "",
      notas_contexto: lead.notas_contexto || "",
      estado: lead.estado || "prospecto_detectado_ia",
    });
  }, [lead]);
  if (!lead) return null;
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await api.patch(`/ia-leads/${lead.id}`, f); onSaved(); }
    finally { setBusy(false); }
  };
  return (
    <Modal open={!!lead} onClose={onClose} title={`Editar — ${lead.empresa}`} testId="edit-lead-modal">
      <form onSubmit={submit} className="space-y-3 text-xs">
        <input className="input-field" placeholder="Nombre contacto"
               value={f.contacto_nombre} onChange={(e) => setF({ ...f, contacto_nombre: e.target.value })}/>
        <input className="input-field" placeholder="Puesto"
               value={f.contacto_puesto} onChange={(e) => setF({ ...f, contacto_puesto: e.target.value })}/>
        <div className="grid grid-cols-2 gap-2">
          <input className="input-field font-mono" placeholder="Teléfono"
                 value={f.telefono} onChange={(e) => setF({ ...f, telefono: e.target.value })}/>
          <input className="input-field font-mono" placeholder="Email" type="email"
                 value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })}/>
        </div>
        <input className="input-field" placeholder="Ubicación"
               value={f.ubicacion} onChange={(e) => setF({ ...f, ubicacion: e.target.value })}/>
        <select className="input-field" value={f.estado} onChange={(e) => setF({ ...f, estado: e.target.value })}>
          {Object.entries(ESTADO_LABELS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <textarea className="input-field" style={{ height: 100 }} placeholder="Notas contexto"
                  value={f.notas_contexto} onChange={(e) => setF({ ...f, notas_contexto: e.target.value })}/>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary">
            {busy ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
