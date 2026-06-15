import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, formatApiError, downloadPdf } from "../lib/auth";
import { Modal } from "./ui-deyma";
import { Download, Send, MessageSquareReply, History as HistoryIcon, FileText, Plus, CheckCircle2, XCircle, AlertTriangle, Mail, Paperclip, ArrowDownToLine } from "lucide-react";

const ESTADO_LABEL = {
  borrador: { l: "BORRADOR", c: "text-zinc-400 border-zinc-400/40" },
  aprobada_direccion: { l: "APROBADA · ENVIADA", c: "text-sky-400 border-sky-400/40" },
  enviada: { l: "ENVIADA", c: "text-sky-400 border-sky-400/40" },
  aceptada: { l: "ACEPTADA", c: "text-emerald-400 border-emerald-400/40" },
  rechazada: { l: "RECHAZADA", c: "text-rose-400 border-rose-400/40" },
};

export default function SeguimientoCotizacionModal({ open, onClose, cotizacionId, onChanged }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("resumen");
  const [composer, setComposer] = useState(null);
  const [replyForm, setReplyForm] = useState(null);
  const [marcarOpen, setMarcarOpen] = useState(null);

  const load = async () => {
    if (!cotizacionId) return;
    const { data } = await api.get(`/cotizaciones/${cotizacionId}/seguimiento`);
    setData(data);
  };
  useEffect(() => { if (open) load(); /* eslint-disable-next-line */ }, [open, cotizacionId]);

  if (!open) return null;

  const cot = data?.cotizacion;
  const emp = data?.empresa || {};
  const cont = data?.contacto || {};
  const estado = cot?.estado || "borrador";
  const isFinal = ["aceptada", "rechazada"].includes(estado);

  return (
    <Modal open={open} onClose={onClose} title={cot ? `Seguimiento · ${cot.folio}` : "Cargando…"} size="xl" testId="seguimiento-modal">
      {!data ? <div className="p-8 text-center label-overline text-amber-400 animate-pulse">Cargando seguimiento…</div> : (
        <div className="space-y-4" data-testid="seguimiento-content">
          {/* Header */}
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className={`badge ${ESTADO_LABEL[estado]?.c}`} data-testid="cot-estado">{ESTADO_LABEL[estado]?.l}</span>
                <span className="label-overline text-zinc-500">{emp.nombre || "—"}</span>
                {!data.sendgrid_enabled && <span className="badge text-amber-400 border-amber-400/40">SENDGRID MOCK</span>}
              </div>
              <h3 className="text-lg font-bold">{cot.proyecto_titulo}</h3>
            </div>
            <div className="flex gap-2 flex-wrap">
              <button data-testid="download-pdf-btn" onClick={() => downloadPdf(`/cotizaciones/${cot.id}/pdf`, `cotizacion_${cot.folio}.pdf`)} className="btn-ghost flex items-center gap-2 text-xs">
                <Download size={12}/> PDF
              </button>
              {!isFinal && estado === "borrador" && (
                <button data-testid="open-composer-btn" onClick={async () => {
                  const { data: tpl } = await api.get(`/cotizaciones/${cot.id}/email-template`);
                  setComposer({ ...tpl, to: tpl.to || cont.email || "" });
                }} className="btn-primary flex items-center gap-2"><Send size={12}/> Aprobar y enviar al cliente</button>
              )}
              {!isFinal && (
                <>
                  <button data-testid="marcar-aceptada-btn" onClick={() => setMarcarOpen("aceptada")} className="text-[11px] px-3 py-1.5 border border-emerald-500/60 text-emerald-400 hover:bg-emerald-500/10 font-bold uppercase tracking-wider" style={{ fontFamily: "Chivo, sans-serif" }}>Marcar aceptada</button>
                  <button data-testid="marcar-rechazada-btn" onClick={() => setMarcarOpen("rechazada")} className="text-[11px] px-3 py-1.5 border border-rose-500/60 text-rose-400 hover:bg-rose-500/10 font-bold uppercase tracking-wider" style={{ fontFamily: "Chivo, sans-serif" }}>Rechazada</button>
                </>
              )}
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            <Stat label="Total" value={fmtMXN(cot.total)} color="text-amber-400"/>
            <Stat label="Correos enviados" value={data.outbound_emails.length} color="text-sky-400"/>
            <Stat label="Respuestas cliente" value={data.inbound_replies.length} color="text-emerald-400"/>
            <Stat label="Eventos historia" value={data.historia.length} color="text-zinc-300"/>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-white/10 flex-wrap">
            {[
              ["resumen", "Resumen", FileText],
              ["correos", `Correos (${data.outbound_emails.length})`, Mail],
              ["respuestas", `Respuestas (${data.inbound_replies.length})`, MessageSquareReply],
              ["historia", "Historia", HistoryIcon],
            ].map(([k, l, I]) => (
              <button key={k} onClick={() => setTab(k)} data-testid={`seg-tab-${k}`}
                className={`px-4 py-2 text-xs font-bold tracking-wider uppercase border-b-2 -mb-px flex items-center gap-2 ${
                  tab === k ? "border-amber-500 text-amber-400" : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`} style={{ fontFamily: "Chivo, sans-serif" }}>
                <I size={12}/> {l}
              </button>
            ))}
          </div>

          {tab === "resumen" && <Resumen cot={cot} emp={emp} cont={cont}/>}
          {tab === "correos" && <Correos outbound={data.outbound_emails} sendgridEnabled={data.sendgrid_enabled}/>}
          {tab === "respuestas" && (
            <Respuestas
              inbound={data.inbound_replies} estado={estado}
              onNew={() => setReplyForm({ de: cont.nombre || "", de_email: cont.email || "", asunto: "", contenido: "", sentimiento: "neutro" })}
            />
          )}
          {tab === "historia" && <Historia historia={data.historia}/>}
        </div>
      )}

      {/* Email composer */}
      {composer && (
        <ComposerModal data={composer} setData={setComposer} onClose={() => setComposer(null)} onSent={async () => { setComposer(null); await load(); onChanged?.(); }} cotizacionId={cotizacionId}/>
      )}

      {/* Reply form */}
      {replyForm && (
        <ReplyFormModal data={replyForm} setData={setReplyForm} onClose={() => setReplyForm(null)} onSaved={async () => { setReplyForm(null); await load(); onChanged?.(); }} cotizacionId={cotizacionId}/>
      )}

      {/* Marcar estado */}
      {marcarOpen && (
        <MarcarModal estado={marcarOpen} onClose={() => setMarcarOpen(null)} onSaved={async () => { setMarcarOpen(null); await load(); onChanged?.(); }} cotizacionId={cotizacionId}/>
      )}
    </Modal>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="surface p-3">
      <div className="label-overline">{label}</div>
      <div className={`font-mono text-xl mt-1 ${color}`}>{value}</div>
    </div>
  );
}

function Resumen({ cot, emp, cont }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="surface-elev p-3"><div className="label-overline mb-1">Cliente</div><div className="font-semibold">{emp.nombre}</div><div className="text-zinc-400">{emp.ciudad}, {emp.estado}</div></div>
        <div className="surface-elev p-3"><div className="label-overline mb-1">Contacto</div><div className="font-semibold">{cont.nombre || "—"}</div><div className="text-zinc-400">{cont.email || "sin correo"} · {cont.telefono || "—"}</div></div>
      </div>
      <table className="dtable">
        <thead><tr><th>Concepto</th><th className="text-right">Cant.</th><th>Unidad</th><th className="text-right">P. Unit.</th><th className="text-right">Subtotal</th></tr></thead>
        <tbody>{cot.items.map((it, i) => (
          <tr key={i}><td>{it.descripcion}</td><td className="font-mono text-right">{it.cantidad.toLocaleString("es-MX")}</td><td className="text-xs">{it.unidad}</td><td className="font-mono text-right">{fmtMXN(it.precio_unitario)}</td><td className="font-mono text-right">{fmtMXN(it.cantidad * it.precio_unitario)}</td></tr>
        ))}</tbody>
      </table>
      <div className="flex justify-end">
        <div className="surface-elev p-3 w-72 space-y-1 text-xs">
          <Row k="Subtotal" v={fmtMXN(cot.subtotal)}/>
          <Row k={`IVA (${cot.iva_pct}%)`} v={fmtMXN(cot.iva_monto)}/>
          <div className="divider"/>
          <Row k="TOTAL MXN" v={fmtMXN(cot.total)} big/>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v, big }) {
  return <div className="flex justify-between"><span className={`label-overline ${big ? "text-amber-400" : ""}`}>{k}</span><span className={`font-mono ${big ? "text-amber-400 text-lg" : ""}`}>{v}</span></div>;
}

function Correos({ outbound, sendgridEnabled }) {
  if (outbound.length === 0) {
    return (
      <div className="surface p-8 text-center text-zinc-400">
        <Mail size={36} strokeWidth={1} className="mx-auto mb-2 text-zinc-700"/>
        <div className="text-sm">Aún no se ha enviado ningún correo al cliente.</div>
        <div className="text-xs text-zinc-500 mt-1">Aprueba la cotización para activar el envío.</div>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {!sendgridEnabled && (
        <div className="surface-elev p-3 border-l-2 border-l-amber-500 text-[11px] text-zinc-400">
          <AlertTriangle size={12} className="inline mr-1 text-amber-400"/>
          Los correos están en modo MOCK. Para activar el envío real configura <code className="font-mono text-amber-400">SENDGRID_API_KEY</code> y <code className="font-mono text-amber-400">SENDGRID_FROM_EMAIL</code>.
        </div>
      )}
      {outbound.map((o) => (
        <div key={o.id} className="surface p-3" data-testid={`outbound-${o.id}`}>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="badge text-sky-400 border-sky-400/40">ENVIADO</span>
            {o.mock && <span className="badge text-amber-400 border-amber-400/40">MOCK</span>}
            {!o.mock && <span className="badge text-emerald-400 border-emerald-400/40">{o.status?.toUpperCase()}</span>}
            <span className="font-mono text-[10px] text-zinc-500 ml-auto">{new Date(o.sent_at).toLocaleString("es-MX")}</span>
          </div>
          <div className="text-xs space-y-1">
            <div><span className="label-overline mr-2">Para</span><span className="font-mono text-amber-400">{o.to}</span></div>
            {(o.cc || []).length > 0 && <div><span className="label-overline mr-2">CC</span>{o.cc.join(", ")}</div>}
            <div><span className="label-overline mr-2">Asunto</span><span className="font-semibold">{o.subject}</span></div>
            <div><span className="label-overline mr-2">Enviado por</span>{o.sent_by_name} ({o.sent_by_role})</div>
            {(o.attachments || []).length > 0 && (
              <div className="flex items-center gap-2 text-zinc-400">
                <Paperclip size={11}/>
                {o.attachments.map((a, i) => <span key={i} className="font-mono text-[11px]">{a.filename}</span>)}
              </div>
            )}
          </div>
          <details className="mt-2">
            <summary className="text-[10px] text-zinc-500 cursor-pointer hover:text-zinc-300 label-overline">Ver cuerpo HTML del correo ▾</summary>
            <div className="surface-elev p-3 mt-2 text-xs max-h-96 overflow-auto" dangerouslySetInnerHTML={{ __html: o.body_html }}/>
          </details>
        </div>
      ))}
    </div>
  );
}

function Respuestas({ inbound, estado, onNew }) {
  const sentColor = { positivo: "text-emerald-400 border-emerald-400/40", neutro: "text-zinc-400 border-zinc-400/40", negativo: "text-rose-400 border-rose-400/40" };
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="label-overline">Respuestas registradas del cliente</div>
        <button data-testid="new-reply-btn" onClick={onNew} className="btn-primary flex items-center gap-2 text-xs"><Plus size={12}/> Registrar respuesta del cliente</button>
      </div>
      {inbound.length === 0 ? (
        <div className="surface p-8 text-center text-zinc-400">
          <MessageSquareReply size={36} strokeWidth={1} className="mx-auto mb-2 text-zinc-700"/>
          <div className="text-sm">Aún no hay respuestas del cliente registradas.</div>
          <div className="text-xs text-zinc-500 mt-1">Cuando el cliente responda al correo, pega el contenido aquí para mantener el seguimiento.</div>
        </div>
      ) : inbound.map((r) => (
        <div key={r.id} className="surface p-3 border-l-4 border-l-emerald-500/60" data-testid={`inbound-${r.id}`}>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <ArrowDownToLine size={13} className="text-emerald-400"/>
            <span className="font-semibold text-sm">{r.de}</span>
            {r.de_email && <span className="font-mono text-[11px] text-zinc-500">&lt;{r.de_email}&gt;</span>}
            <span className={`badge ${sentColor[r.sentimiento] || sentColor.neutro}`}>{(r.sentimiento || "neutro").toUpperCase()}</span>
            <span className="font-mono text-[10px] text-zinc-500 ml-auto">{new Date(r.fecha).toLocaleString("es-MX")}</span>
          </div>
          <div className="text-sm font-bold mb-1">{r.asunto}</div>
          <pre className="surface-elev p-3 text-xs whitespace-pre-wrap leading-relaxed font-mono text-zinc-300">{r.contenido}</pre>
          {(r.adjuntos || []).length > 0 && (
            <div className="flex items-center gap-2 mt-2 text-[10px] text-zinc-500">
              <Paperclip size={11}/> {r.adjuntos.map((a, i) => <span key={i} className="font-mono">{a.nombre || a.filename}</span>)}
            </div>
          )}
          {r.registrado_por_name && <div className="text-[10px] text-zinc-600 mt-1 font-mono">▸ Registrado por {r.registrado_por_name} · {new Date(r.registrado_at).toLocaleString("es-MX")}</div>}
        </div>
      ))}
    </div>
  );
}

function Historia({ historia }) {
  const icons = { aprobacion_envio: Send, respuesta_cliente: MessageSquareReply, cambio_estado: HistoryIcon };
  return (
    <div className="space-y-1">
      {historia.length === 0 ? (
        <div className="text-xs text-zinc-500 font-mono terminal-line py-4">Sin eventos registrados.</div>
      ) : historia.slice().reverse().map((h) => {
        const I = icons[h.tipo] || HistoryIcon;
        return (
          <div key={h.id} className="surface-elev p-2 flex items-start gap-3 text-xs">
            <I size={14} className="text-amber-400 mt-0.5 shrink-0"/>
            <div className="flex-1 min-w-0">
              <div>{h.detalle}</div>
              <div className="text-[10px] text-zinc-500 font-mono">{h.actor_name} ({h.actor_role}) · {new Date(h.ts).toLocaleString("es-MX")}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ComposerModal({ data, setData, onClose, onSent, cotizacionId }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api.post(`/cotizaciones/${cotizacionId}/aprobar-enviar`, {
        to: data.to, cc: data.cc || [],
        subject: data.subject, body_html: data.body_html, body_text: data.body_text,
        adjuntar_pdf: true,
      });
      onSent();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };
  return (
    <Modal open={true} onClose={onClose} title="Aprobar cotización y enviar al cliente" size="xl" testId="composer-modal">
      <form onSubmit={submit} className="space-y-3" data-testid="composer-form">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline">Para</label>
            <input data-testid="composer-to" required type="email" className="input-field" value={data.to} onChange={(e) => setData({ ...data, to: e.target.value })}/>
          </div>
          <div>
            <label className="label-overline">CC (separados por coma)</label>
            <input className="input-field" value={(data.cc || []).join(", ")} onChange={(e) => setData({ ...data, cc: e.target.value.split(",").map(s => s.trim()).filter(Boolean) })}/>
          </div>
        </div>
        <div>
          <label className="label-overline">Asunto</label>
          <input data-testid="composer-subject" required className="input-field" value={data.subject} onChange={(e) => setData({ ...data, subject: e.target.value })}/>
        </div>
        <div>
          <label className="label-overline">Cuerpo HTML (editable)</label>
          <textarea data-testid="composer-body-html" className="input-field font-mono text-[11px]" style={{ height: 180 }} value={data.body_html} onChange={(e) => setData({ ...data, body_html: e.target.value })}/>
        </div>
        <div>
          <label className="label-overline">Versión texto plano (fallback)</label>
          <textarea className="input-field font-mono text-[11px]" style={{ height: 80 }} value={data.body_text || ""} onChange={(e) => setData({ ...data, body_text: e.target.value })}/>
        </div>
        <div className="surface-elev p-3 text-[11px] text-zinc-400 flex items-center gap-2">
          <Paperclip size={12} className="text-amber-400"/>
          <span>Se adjuntará automáticamente el PDF de la cotización.</span>
        </div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="composer-send-btn" disabled={busy} className="btn-primary flex items-center gap-2">
            <Send size={12}/> {busy ? "Enviando…" : "Aprobar y enviar al cliente"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ReplyFormModal({ data, setData, onClose, onSaved, cotizacionId }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const payload = { ...data };
      if (!payload.de_email || !payload.de_email.trim()) delete payload.de_email;
      if (!payload.fecha) delete payload.fecha;
      await api.post(`/cotizaciones/${cotizacionId}/respuesta`, payload);
      onSaved();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };
  return (
    <Modal open={true} onClose={onClose} title="Registrar respuesta del cliente" size="lg" testId="reply-form-modal">
      <form onSubmit={submit} className="space-y-3" data-testid="reply-form">
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label-overline">De (nombre)</label><input data-testid="reply-de" required className="input-field" value={data.de} onChange={(e) => setData({ ...data, de: e.target.value })}/></div>
          <div><label className="label-overline">Email del remitente</label><input className="input-field" type="email" value={data.de_email || ""} onChange={(e) => setData({ ...data, de_email: e.target.value })}/></div>
        </div>
        <div><label className="label-overline">Asunto</label><input data-testid="reply-asunto" required className="input-field" value={data.asunto} onChange={(e) => setData({ ...data, asunto: e.target.value })}/></div>
        <div><label className="label-overline">Contenido del correo (pegar tal cual)</label><textarea data-testid="reply-contenido" required className="input-field" style={{ height: 200 }} value={data.contenido} onChange={(e) => setData({ ...data, contenido: e.target.value })}/></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label-overline">Fecha de recepción</label><input type="datetime-local" className="input-field font-mono" value={data.fecha || ""} onChange={(e) => setData({ ...data, fecha: e.target.value })}/></div>
          <div><label className="label-overline">Sentimiento</label>
            <select data-testid="reply-sentimiento" className="input-field" value={data.sentimiento} onChange={(e) => setData({ ...data, sentimiento: e.target.value })}>
              <option value="positivo">Positivo (avanza)</option>
              <option value="neutro">Neutro (preguntas)</option>
              <option value="negativo">Negativo (objeciones)</option>
            </select>
          </div>
        </div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="reply-save-btn" disabled={busy} className="btn-primary">{busy ? "Guardando…" : "Registrar respuesta"}</button>
        </div>
      </form>
    </Modal>
  );
}

function MarcarModal({ estado, onClose, onSaved, cotizacionId }) {
  const [nota, setNota] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const isAcept = estado === "aceptada";
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api.post(`/cotizaciones/${cotizacionId}/marcar`, { estado, nota: nota || null });
      onSaved();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };
  return (
    <Modal open={true} onClose={onClose} title={`Marcar como ${estado.toUpperCase()}`} testId="marcar-modal">
      <form onSubmit={submit} className="space-y-3">
        <div className={`surface-elev p-3 border-l-4 ${isAcept ? "border-l-emerald-500" : "border-l-rose-500"}`}>
          {isAcept ? <CheckCircle2 size={16} className="inline text-emerald-400 mr-2"/> : <XCircle size={16} className="inline text-rose-400 mr-2"/>}
          <span className="text-sm">{isAcept ? "La cotización se marcará como aceptada (cierre exitoso). Considera crear la obra desde el módulo de Obras." : "La cotización se marcará como rechazada. Se recomienda dejar nota con el motivo."}</span>
        </div>
        <div><label className="label-overline">Nota (opcional)</label><textarea data-testid="marcar-nota" className="input-field" style={{ height: 100 }} value={nota} onChange={(e) => setNota(e.target.value)}/></div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="marcar-confirm-btn" disabled={busy} className={isAcept ? "btn-primary" : "text-[11px] px-4 py-2 border border-rose-500/60 text-rose-400 hover:bg-rose-500/10 font-bold uppercase tracking-wider"} style={{ fontFamily: "Chivo, sans-serif" }}>
            {busy ? "Guardando…" : `Confirmar ${estado}`}
          </button>
        </div>
      </form>
    </Modal>
  );
}
