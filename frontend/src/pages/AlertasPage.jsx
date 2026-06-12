import React, { useEffect, useState } from "react";
import { api, fmtMXN } from "../lib/auth";
import { AlertTriangle, Send, CheckCircle2, MessageSquare } from "lucide-react";

export default function AlertasPage() {
  const [data, setData] = useState({ items: [], twilio_enabled: false, alert_phone: null });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const { data } = await api.get("/alertas");
    setData(data);
  };
  useEffect(() => { load(); }, []);

  const sendTest = async () => {
    setBusy(true);
    try { await api.post("/alertas/test"); await load(); }
    finally { setBusy(false); }
  };

  return (
    <div className="p-6 space-y-5" data-testid="alertas-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Alertas HOT · Notificaciones WhatsApp</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Centro de Alertas</h1>
        </div>
        <button data-testid="test-alert-btn" onClick={sendTest} disabled={busy} className="btn-primary flex items-center gap-2">
          <Send size={14} strokeWidth={2}/> {busy ? "Enviando…" : "Enviar alerta de prueba"}
        </button>
      </div>

      <div className={`surface p-4 border-l-4 ${data.twilio_enabled ? "border-l-emerald-500" : "border-l-amber-500"}`}>
        <div className="flex items-start gap-3">
          {data.twilio_enabled ? <CheckCircle2 size={20} className="text-emerald-400 mt-0.5" strokeWidth={1.5}/> : <AlertTriangle size={20} className="text-amber-400 mt-0.5" strokeWidth={1.5}/>}
          <div>
            <div className="font-bold mb-1">{data.twilio_enabled ? "Twilio WhatsApp ACTIVO" : "Modo MOCK · sin envío real"}</div>
            <div className="text-xs text-zinc-400 leading-relaxed">
              {data.twilio_enabled
                ? <>Las alertas se envían a <span className="font-mono text-amber-400">{data.alert_phone}</span> cuando una oportunidad o proyecto del radar alcanza score IA ≥ 85.</>
                : <>Las alertas se registran pero <span className="text-amber-400">no se envían</span> por WhatsApp. Para activarlas configura las variables <code className="font-mono text-amber-400">TWILIO_ACCOUNT_SID</code>, <code className="font-mono text-amber-400">TWILIO_AUTH_TOKEN</code>, <code className="font-mono text-amber-400">TWILIO_WHATSAPP_FROM</code> y <code className="font-mono text-amber-400">DEYMA_ALERT_PHONE</code> en <code className="font-mono">/app/backend/.env</code> y reinicia el backend.</>
              }
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="surface p-4">
          <div className="label-overline mb-1">Total alertas</div>
          <div className="font-mono text-3xl text-amber-400">{data.items.length}</div>
        </div>
        <div className="surface p-4">
          <div className="label-overline mb-1">Esta semana</div>
          <div className="font-mono text-3xl text-sky-400">{data.items.filter((a) => Date.now() - new Date(a.created_at).getTime() < 7 * 86400000).length}</div>
        </div>
        <div className="surface p-4">
          <div className="label-overline mb-1">Estado</div>
          <div className={`font-mono text-xl ${data.twilio_enabled ? "text-emerald-400" : "text-amber-400"}`}>
            {data.twilio_enabled ? "WHATSAPP LIVE" : "MOCK"}
          </div>
        </div>
      </div>

      {data.items.length === 0 ? (
        <div className="surface p-12 text-center">
          <MessageSquare size={48} strokeWidth={1} className="mx-auto text-zinc-700 mb-3"/>
          <div className="text-zinc-400 mb-1">Sin alertas todavía</div>
          <div className="text-xs text-zinc-500">Se generan automáticamente cuando una oportunidad o proyecto del radar alcanza score IA ≥ 85.</div>
        </div>
      ) : (
        <div className="space-y-2" data-testid="alertas-list">
          {data.items.map((a) => (
            <div key={a.id} className="surface p-4 flex items-start gap-4" data-testid={`alerta-${a.id}`}>
              <div className="w-10 h-10 bg-orange-500/20 border border-orange-500/40 flex items-center justify-center shrink-0">
                <AlertTriangle size={18} className="text-orange-400" strokeWidth={1.5}/>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="badge text-orange-400 border-orange-400/60">HOT {a.score}/100</span>
                  <span className="badge text-zinc-400 border-zinc-400/40">{a.entity_type.toUpperCase()}</span>
                  <span className="badge text-sky-400 border-sky-400/40">{a.channel.toUpperCase()}</span>
                  {a.mock && <span className="badge text-amber-400 border-amber-400/40">MOCK</span>}
                  {!a.mock && <span className="badge text-emerald-400 border-emerald-400/40">{(a.status || "").toUpperCase()}</span>}
                </div>
                <div className="font-bold mb-1">{a.titulo}</div>
                <div className="text-xs text-zinc-400 mb-2">{a.sector} · {a.ciudad} · <span className="font-mono text-amber-400">{fmtMXN(a.monto)}</span></div>
                <pre className="surface-elev p-2 text-[11px] whitespace-pre-wrap font-mono text-zinc-300">{a.body}</pre>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono text-[10px] text-zinc-500">{new Date(a.created_at).toLocaleString("es-MX")}</div>
                <div className="font-mono text-[10px] text-zinc-600 mt-1">→ {a.to}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
