import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth, formatApiError } from "../lib/auth";
import { Radar, Lock, Mail, Hash, UserPlus, Search } from "lucide-react";

export default function LoginPage() {
  const { login, loginCliente } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("staff");
  const [email, setEmail] = useState("director@deyma.mx");
  const [password, setPassword] = useState("Deyma2026!");
  const [dfnum, setDfnum] = useState("");
  const [clientPw, setClientPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submitStaff = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try { await login(email, password); nav("/"); }
    catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  const submitCliente = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try { await loginCliente(dfnum, clientPw); nav("/cliente"); }
    catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-5 bg-black text-zinc-100">
      <div className="hidden lg:block lg:col-span-3 relative overflow-hidden">
        <img
          src="https://images.pexels.com/photos/4170184/pexels-photo-4170184.jpeg"
          alt="Construction"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-black/80" />
        <div className="absolute inset-0 grid-backdrop opacity-50" />
        <div className="relative h-full flex flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-500 flex items-center justify-center"><Radar size={22} strokeWidth={2} className="text-black" /></div>
            <div>
              <div className="font-black tracking-tight text-2xl" style={{ fontFamily: "Chivo, sans-serif" }}>DEYMA · RADAR</div>
              <div className="label-overline text-amber-400/80">Sistema de Inteligencia Comercial</div>
            </div>
          </div>
          <div className="space-y-6 max-w-xl">
            <div className="label-overline text-amber-400">Bajío Industrial Intelligence</div>
            <h1 className="text-4xl md:text-5xl font-black leading-tight" style={{ fontFamily: "Chivo, sans-serif" }}>
              Detecta, califica y cierra<br/>cada oportunidad industrial<br/><span className="text-amber-400">antes que la competencia.</span>
            </h1>
            <p className="text-zinc-400 max-w-md">
              Pisos industriales · Concreto hidráulico · Pavimentación · Mantenimiento · Canastillas.
              Querétaro · Bajío · Nearshoring · Data Centers · CEDIS.
            </p>
            <div className="grid grid-cols-3 gap-4 pt-6">
              <Metric k="38" l="Pipeline activo" />
              <Metric k="$284M" l="MXN proyectados" />
              <Metric k="12" l="Obras en ejecución" />
            </div>
          </div>
          <div className="font-mono text-[10px] text-zinc-600 tracking-widest">
            ▸ V1.0 · ENERO 2026 · DEYMA CONSTRUCCIONES S.A. DE C.V.
          </div>
        </div>
      </div>

      <div className="lg:col-span-2 flex items-center justify-center p-8 industrial-noise">
        <div className="w-full max-w-sm space-y-6">
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-amber-500 flex items-center justify-center"><Radar size={18} className="text-black" /></div>
            <div className="font-black tracking-tight text-xl">DEYMA · RADAR</div>
          </div>

          <div className="grid grid-cols-2 border border-white/10" data-testid="login-tabs">
            <button
              onClick={() => { setTab("staff"); setErr(""); }}
              data-testid="tab-staff"
              className={`py-2.5 text-xs font-bold label-overline transition-colors ${tab === "staff" ? "bg-amber-500 text-black" : "text-zinc-400 hover:text-zinc-100"}`}
            >Staff DEYMA</button>
            <button
              onClick={() => { setTab("cliente"); setErr(""); }}
              data-testid="tab-cliente"
              className={`py-2.5 text-xs font-bold label-overline transition-colors ${tab === "cliente" ? "bg-amber-500 text-black" : "text-zinc-400 hover:text-zinc-100"}`}
            >Cliente DEYMA</button>
          </div>

          {tab === "staff" && (
            <form onSubmit={submitStaff} className="space-y-6" data-testid="login-form-staff">
              <div>
                <div className="label-overline mb-2 text-amber-400">Acceso autorizado</div>
                <h2 className="text-3xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>Iniciar sesión</h2>
                <p className="text-sm text-zinc-500 mt-1">Sistema interno DEYMA · Solo personal autorizado.</p>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="label-overline">Correo</label>
                  <div className="relative mt-1">
                    <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" strokeWidth={1.5} />
                    <input data-testid="login-email-input" className="input-field pl-9" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
                  </div>
                </div>
                <div>
                  <label className="label-overline">Contraseña</label>
                  <div className="relative mt-1">
                    <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" strokeWidth={1.5} />
                    <input data-testid="login-password-input" className="input-field pl-9" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
                  </div>
                </div>
              </div>
              {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-3 font-mono" data-testid="login-error">{err}</div>}
              <button type="submit" disabled={busy} data-testid="login-submit-btn" className="btn-primary w-full">{busy ? "Autenticando…" : "Acceder al radar"}</button>
              <div className="border-t border-white/10 pt-4 space-y-1 font-mono text-[10px] text-zinc-500">
                <div>▸ director@deyma.mx · Deyma2026!</div>
                <div>▸ socio@deyma.mx · Socio2026!</div>
                <div>▸ comercial@deyma.mx · Comercial2026!</div>
                <div>▸ operaciones@deyma.mx · Operaciones2026!</div>
              </div>
            </form>
          )}

          {tab === "cliente" && (
            <form onSubmit={submitCliente} className="space-y-6" data-testid="login-form-cliente">
              <div>
                <div className="label-overline mb-2 text-amber-400">Portal cliente</div>
                <h2 className="text-3xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>Acceso cliente</h2>
                <p className="text-sm text-zinc-500 mt-1">Ingresa con tu DFNUM y contraseña.</p>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="label-overline">DFNUM</label>
                  <div className="relative mt-1">
                    <Hash size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" strokeWidth={1.5} />
                    <input data-testid="cliente-dfnum-input" className="input-field pl-9 uppercase" type="text" value={dfnum} onChange={(e) => setDfnum(e.target.value.toUpperCase())} required placeholder="DFNUM-XXXXXX" />
                  </div>
                </div>
                <div>
                  <label className="label-overline">Contraseña</label>
                  <div className="relative mt-1">
                    <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" strokeWidth={1.5} />
                    <input data-testid="cliente-password-input" className="input-field pl-9" type="password" value={clientPw} onChange={(e) => setClientPw(e.target.value)} required />
                  </div>
                </div>
              </div>
              {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-3 font-mono" data-testid="cliente-login-error">{err}</div>}
              <button type="submit" disabled={busy} data-testid="cliente-login-submit-btn" className="btn-primary w-full">{busy ? "Validando…" : "Entrar al portal"}</button>
              <div className="border-t border-white/10 pt-4 space-y-2.5 text-xs">
                <Link to="/alta-cliente" data-testid="link-alta" className="flex items-center gap-2 text-amber-400 hover:underline">
                  <UserPlus size={14} /> ¿Aún no eres cliente? Regístrate aquí
                </Link>
                <Link to="/consulta-tramite" data-testid="link-consulta" className="flex items-center gap-2 text-zinc-400 hover:text-amber-400">
                  <Search size={14} /> Consultar estado de mi trámite
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

function Metric({ k, l }) {
  return (
    <div className="border-l-2 border-amber-500/70 pl-3">
      <div className="font-mono text-2xl font-bold text-amber-400">{k}</div>
      <div className="label-overline text-zinc-500">{l}</div>
    </div>
  );
}
