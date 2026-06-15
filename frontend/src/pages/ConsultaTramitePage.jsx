import React, { useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { API, formatApiError } from "../lib/auth";
import { Radar, ArrowLeft, Search, CheckCircle2, Clock, XCircle, AlertCircle } from "lucide-react";

const ESTADO_INFO = {
  pendiente: { label: "Pendiente · En revisión", color: "amber", icon: Clock, msg: "Tu solicitud fue recibida. Validación documental en curso." },
  aprobado_director: { label: "Aprobado por Director · Falta Socio", color: "amber", icon: Clock, msg: "El Director General ya aprobó. Esperando firma del Socio." },
  aprobado_socio: { label: "Aprobado por Socio · Falta Director", color: "amber", icon: Clock, msg: "Un Socio ya aprobó. Esperando firma del Director General." },
  aprobado_completo: { label: "Aprobado · DFNUM asignado", color: "emerald", icon: CheckCircle2, msg: "¡Listo! Ya puedes ingresar al portal cliente con tu DFNUM." },
  rechazado: { label: "Rechazado", color: "rose", icon: XCircle, msg: "Tu solicitud fue rechazada. Contacta a DEYMA para más detalles." },
};

export default function ConsultaTramitePage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const buscar = async (e) => {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true); setErr(""); setRes(null);
    try {
      const { data } = await axios.get(`${API}/clientes/status/${encodeURIComponent(q.trim())}`);
      setRes(data);
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  const info = res ? ESTADO_INFO[res.estado] || ESTADO_INFO.pendiente : null;
  const Icon = info?.icon;

  return (
    <div className="min-h-screen bg-black text-zinc-100">
      <header className="border-b border-white/10 bg-zinc-950">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-500 flex items-center justify-center"><Radar size={20} className="text-black" strokeWidth={2} /></div>
            <div>
              <div className="font-black tracking-tight text-base" style={{ fontFamily: "Chivo, sans-serif" }}>DEYMA · CONSULTA DE TRÁMITE</div>
              <div className="label-overline text-amber-400/80 text-[10px]">Estado de tu alta de cliente</div>
            </div>
          </div>
          <Link to="/login" data-testid="back-to-login" className="text-xs text-zinc-400 hover:text-amber-400 flex items-center gap-1.5"><ArrowLeft size={14} /> Volver</Link>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="text-3xl font-black mb-3" style={{ fontFamily: "Chivo, sans-serif" }}>¿Cuál es el estado de mi solicitud?</h1>
        <p className="text-sm text-zinc-400 mb-8">Ingresa tu <b>folio de registro</b> (ej. <span className="font-mono text-amber-400">ALT-2026-0001</span>) o tu <b>DFNUM</b> si ya fue aprobada.</p>

        <form onSubmit={buscar} className="flex gap-3" data-testid="consulta-form">
          <input
            data-testid="consulta-input"
            className="input-field flex-1 uppercase"
            value={q} onChange={(e) => setQ(e.target.value.toUpperCase())}
            placeholder="ALT-2026-XXXX  o  DFNUM-XXXXXX"
            required
          />
          <button data-testid="consulta-btn" disabled={busy} className="btn-primary flex items-center gap-1.5">
            <Search size={14} /> {busy ? "Buscando…" : "Consultar"}
          </button>
        </form>

        {err && (
          <div className="mt-6 border border-rose-500/60 bg-rose-500/10 text-rose-300 text-sm p-4 font-mono flex gap-2" data-testid="consulta-error">
            <AlertCircle size={16} className="shrink-0 mt-0.5" /> {err}
          </div>
        )}

        {res && info && (
          <div className="mt-8 border border-white/10 bg-zinc-950 p-6 space-y-5" data-testid="consulta-result">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 flex items-center justify-center bg-${info.color}-500/10 border border-${info.color}-500/40 text-${info.color}-400`}>
                <Icon size={22} />
              </div>
              <div>
                <div className="label-overline text-amber-400">{res.razon_social}</div>
                <div className="text-xl font-bold mt-0.5" style={{ fontFamily: "Chivo, sans-serif" }}>{info.label}</div>
              </div>
            </div>
            <p className="text-sm text-zinc-300">{info.msg}</p>

            <div className="grid grid-cols-2 gap-3">
              <div className="border border-white/10 p-3">
                <div className="label-overline">Folio</div>
                <div className="font-mono text-sm mt-1" data-testid="result-folio-text">{res.folio_registro}</div>
              </div>
              <div className="border border-white/10 p-3">
                <div className="label-overline">DFNUM</div>
                <div className="font-mono text-sm mt-1" data-testid="result-dfnum-text">{res.dfnum || "Aún no asignado"}</div>
              </div>
            </div>

            {res.aprobaciones?.length > 0 && (
              <div>
                <div className="label-overline text-amber-400 mb-2">Aprobaciones</div>
                <ul className="space-y-1.5">
                  {res.aprobaciones.map((a, i) => (
                    <li key={i} className="text-xs text-zinc-400 font-mono flex gap-2">
                      <span className="text-emerald-400">●</span>
                      {a.user_name} <span className="text-zinc-600">({a.rol})</span> · {new Date(a.ts).toLocaleString("es-MX")}
                      {a.decision === "rechazado" && <span className="text-rose-400">[RECHAZADO]</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {res.estado === "aprobado_completo" && (
              <div className="border border-emerald-500/40 bg-emerald-500/5 p-4 text-xs text-emerald-200">
                Ya puedes ingresar al portal cliente con tu DFNUM y la contraseña que registraste.
                <Link to="/login" className="block mt-2 text-emerald-400 font-bold hover:underline">→ Ir al login</Link>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
