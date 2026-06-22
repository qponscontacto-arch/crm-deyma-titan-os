import React, { useState, useEffect } from "react";
import { api, formatApiError } from "../lib/auth";
import {
  BellRing, MessageCircle, Mail, Loader2, Send, CheckCircle2, XCircle,
  Save, Plus, Trash2, RefreshCw,
} from "lucide-react";

export default function AdminNotificacionesPage() {
  const [cfg, setCfg] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [c, h] = await Promise.all([
        api.get("/notif-contactos/config"),
        api.get("/notif-contactos/historial"),
      ]);
      setCfg(c.data);
      setHistory(h.data);
    } catch (e) { /* silent */ }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!cfg || saving) return;
    setSaving(true);
    try {
      const body = {
        whatsapp_enabled: !!cfg.whatsapp_enabled,
        email_enabled: !!cfg.email_enabled,
        whatsapp_to: cfg.whatsapp_to || "",
        email_to: Array.isArray(cfg.email_to) ? cfg.email_to : [],
        min_batch_size: Number(cfg.min_batch_size || 1),
      };
      const { data } = await api.patch("/notif-contactos/config", body);
      setCfg(data);
      setTestResult({ ok: true, msg: "Configuración guardada" });
      setTimeout(() => setTestResult(null), 3000);
    } catch (e) { setTestResult({ ok: false, msg: formatApiError(e) }); }
    finally { setSaving(false); }
  };

  const sendTest = async () => {
    if (testing) return;
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post("/notif-contactos/test");
      setTestResult({
        ok: data.wa_sent || data.email_sent,
        wa: data.wa_sent, email: data.email_sent,
        errors: data.errors || [],
      });
      // refresh historial
      const h = await api.get("/notif-contactos/historial");
      setHistory(h.data);
    } catch (e) { setTestResult({ ok: false, msg: formatApiError(e) }); }
    finally { setTesting(false); }
  };

  const addEmail = () => {
    const e = prompt("Email destinatario adicional:");
    if (!e) return;
    setCfg({ ...cfg, email_to: [...(cfg.email_to || []), e.trim()] });
  };

  const removeEmail = (idx) => {
    setCfg({ ...cfg, email_to: cfg.email_to.filter((_, i) => i !== idx) });
  };

  if (loading || !cfg) {
    return (
      <div className="p-12 text-center text-zinc-500">
        <Loader2 size={20} className="inline animate-spin mr-2"/> Cargando…
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6" data-testid="notificaciones-page">
      <header>
        <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
          <BellRing size={11}/> V5.4 · Push automático
        </div>
        <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
          Notificaciones <span className="text-amber-400">·</span> Contactos Nuevos
        </h1>
        <div className="text-xs text-zinc-500 font-mono mt-1">
          WhatsApp + Email automáticos cada vez que se detecta un contacto con email o teléfono
          desde Greenfield OSINT · Francotirador DRO · Escuadrón · CRM manual
        </div>
      </header>

      {/* Test result banner */}
      {testResult && (
        <div className={`surface p-3 border-l-4 ${testResult.ok ? "border-emerald-500 bg-emerald-500/5" : "border-rose-500 bg-rose-500/5"}`}
             data-testid="test-result">
          {testResult.ok ? <CheckCircle2 size={14} className="inline mr-2 text-emerald-400"/>
                          : <XCircle size={14} className="inline mr-2 text-rose-400"/>}
          <span className="text-sm">
            {testResult.msg ||
              <>
                {testResult.wa && <span className="text-emerald-400 mr-3">✓ WhatsApp enviado</span>}
                {testResult.email && <span className="text-sky-400">✓ Email enviado</span>}
                {testResult.errors?.length > 0 && <span className="text-rose-400 ml-3">{testResult.errors.join(" · ")}</span>}
              </>
            }
          </span>
        </div>
      )}

      {/* Config canales */}
      <section className="surface p-5 space-y-4" data-testid="cfg-section">
        <h2 className="text-lg font-bold border-b border-white/10 pb-2">Canales activos</h2>

        {/* WhatsApp */}
        <div className="space-y-2">
          <label className="flex items-center justify-between cursor-pointer">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                <MessageCircle size={16}/>
              </div>
              <div>
                <div className="font-semibold text-sm">WhatsApp (Twilio)</div>
                <div className="text-[10px] text-zinc-500 font-mono">
                  Mensaje al instante cuando se detectan contactos nuevos con teléfono o email
                </div>
              </div>
            </div>
            <input
              type="checkbox"
              checked={!!cfg.whatsapp_enabled}
              onChange={(e) => setCfg({ ...cfg, whatsapp_enabled: e.target.checked })}
              className="w-5 h-5 accent-amber-500"
              data-testid="toggle-whatsapp"
            />
          </label>
          {cfg.whatsapp_enabled && (
            <input
              type="text"
              value={cfg.whatsapp_to || ""}
              onChange={(e) => setCfg({ ...cfg, whatsapp_to: e.target.value })}
              placeholder="whatsapp:+52442XXXXXXX"
              className="input-field font-mono text-xs"
              data-testid="input-whatsapp-to"
            />
          )}
        </div>

        {/* Email */}
        <div className="space-y-2">
          <label className="flex items-center justify-between cursor-pointer">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-sky-500/10 text-sky-400 border border-sky-500/30">
                <Mail size={16}/>
              </div>
              <div>
                <div className="font-semibold text-sm">Email (SendGrid)</div>
                <div className="text-[10px] text-zinc-500 font-mono">
                  Reporte HTML con tabla detallada de los contactos detectados
                </div>
              </div>
            </div>
            <input
              type="checkbox"
              checked={!!cfg.email_enabled}
              onChange={(e) => setCfg({ ...cfg, email_enabled: e.target.checked })}
              className="w-5 h-5 accent-amber-500"
              data-testid="toggle-email"
            />
          </label>
          {cfg.email_enabled && (
            <div className="space-y-1.5">
              {(cfg.email_to || []).map((em, i) => (
                <div key={i} className="flex items-center gap-2" data-testid={`email-row-${i}`}>
                  <input
                    type="email"
                    value={em}
                    onChange={(e) => {
                      const arr = [...cfg.email_to];
                      arr[i] = e.target.value;
                      setCfg({ ...cfg, email_to: arr });
                    }}
                    className="input-field font-mono text-xs flex-1"
                  />
                  <button onClick={() => removeEmail(i)} className="text-rose-400 hover:text-rose-300 p-1">
                    <Trash2 size={12}/>
                  </button>
                </div>
              ))}
              <button onClick={addEmail} className="btn-ghost text-xs" data-testid="add-email-btn">
                <Plus size={12} className="inline mr-1"/> Agregar email
              </button>
            </div>
          )}
        </div>

        {/* Umbral mínimo */}
        <div>
          <label className="label-overline">Mínimo de contactos por batch (1 = avisar siempre)</label>
          <input
            type="number"
            min={1}
            max={20}
            value={cfg.min_batch_size || 1}
            onChange={(e) => setCfg({ ...cfg, min_batch_size: Number(e.target.value) || 1 })}
            className="input-field font-mono w-32 text-xs"
            data-testid="input-batch-size"
          />
        </div>

        <div className="flex gap-2 pt-2">
          <button onClick={save} disabled={saving}
                  className="btn-primary bg-amber-500 hover:bg-amber-600 text-black border-amber-600 text-xs"
                  data-testid="save-cfg-btn">
            {saving ? <Loader2 size={12} className="animate-spin inline mr-1"/>
                    : <Save size={12} className="inline mr-1"/>}
            Guardar configuración
          </button>
          <button onClick={sendTest} disabled={testing} className="btn-ghost text-xs" data-testid="test-btn">
            {testing ? <Loader2 size={12} className="animate-spin inline mr-1"/>
                     : <Send size={12} className="inline mr-1"/>}
            Enviar prueba ahora
          </button>
        </div>
      </section>

      {/* Historial */}
      <section className="surface p-5" data-testid="history-section">
        <div className="flex items-center justify-between mb-3 border-b border-white/10 pb-2">
          <h2 className="text-lg font-bold">Historial reciente</h2>
          <button onClick={load} className="text-xs text-zinc-400 hover:text-amber-400">
            <RefreshCw size={12} className="inline mr-1"/> Refrescar
          </button>
        </div>
        {history.length === 0 ? (
          <div className="text-center text-zinc-500 text-sm py-6">— Sin notificaciones aún —</div>
        ) : (
          <table className="dtable">
            <thead><tr><th>Fecha</th><th>Fuente</th><th>Cant.</th><th>Muestra</th><th>WhatsApp</th><th>Email</th></tr></thead>
            <tbody>
              {history.map((r) => (
                <tr key={r.id} data-testid={`hist-row-${r.id}`}>
                  <td className="text-[10px] font-mono text-zinc-400">
                    {new Date(r.created_at).toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" })}
                  </td>
                  <td className="text-xs font-mono text-amber-400">{r.source_label}</td>
                  <td className="font-mono text-emerald-400 font-bold">{r.count}</td>
                  <td className="text-[11px] text-zinc-400 truncate max-w-[280px]">
                    {(r.sample_names || []).join(" · ")}
                  </td>
                  <td>
                    {r.wa_sent ? <CheckCircle2 size={12} className="text-emerald-400"/>
                              : <XCircle size={12} className="text-zinc-600"/>}
                  </td>
                  <td>
                    {r.email_sent ? <CheckCircle2 size={12} className="text-sky-400"/>
                                 : <XCircle size={12} className="text-zinc-600"/>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="text-[10px] text-zinc-600 font-mono text-center">
        Las notificaciones se disparan automáticamente al final de cada barrida OSINT (Greenfield, DRO, Escuadrón) y al crear contactos manualmente desde el CRM.
        Sólo se notifican contactos con email o teléfono válido para evitar ruido.
      </div>
    </div>
  );
}
