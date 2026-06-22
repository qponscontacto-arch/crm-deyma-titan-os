import React, { useState, useEffect } from "react";
import { api, formatApiError } from "../lib/auth";
import { Modal } from "../components/ui-deyma";
import {
  Shield, UserPlus, KeyRound, Trash2, Edit3, Loader2, Save,
  Eye, EyeOff, Copy, CheckCircle2, AlertOctagon, Lock,
} from "lucide-react";

const ROLES = [
  { value: "director", label: "Director General", color: "amber" },
  { value: "socio", label: "Socio", color: "indigo" },
  { value: "comercial", label: "Comercial", color: "emerald" },
  { value: "operaciones", label: "Operaciones", color: "sky" },
  { value: "marketing", label: "Marketing", color: "rose" },
  { value: "rh", label: "RH", color: "zinc" },
  { value: "finanzas", label: "Finanzas", color: "violet" },
];

export default function AdminAccesosPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [resetTarget, setResetTarget] = useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/accesos/usuarios");
      setUsers(data);
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const onCreated = (u, pw) => {
    setShowCreate(false);
    setNotice({
      kind: "ok",
      msg: `✓ Usuario creado: ${u.email}`,
      copyPw: pw,
      copyEmail: u.email,
    });
    load();
  };

  const onResetDone = (email, pw) => {
    setResetTarget(null);
    setNotice({
      kind: "ok",
      msg: `✓ Contraseña actualizada para ${email}`,
      copyPw: pw,
      copyEmail: email,
    });
  };

  const eliminarUsuario = async (u) => {
    if (!window.confirm(`¿Eliminar permanentemente a ${u.email}? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/accesos/usuarios/${u.id}`);
      setNotice({ kind: "ok", msg: `✓ ${u.email} eliminado` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6" data-testid="accesos-page">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
            <Shield size={11}/> Dirección · V5.5
          </div>
          <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
            Accesos <span className="text-amber-400">·</span> Gestión de Usuarios
          </h1>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Solo Director · contraseñas nunca visibles · auditoría completa
          </div>
        </div>
        <button onClick={() => setShowCreate(true)}
                className="btn-primary bg-amber-500 hover:bg-amber-600 text-black border-amber-600 text-xs"
                data-testid="btn-crear-usuario">
          <UserPlus size={13} className="inline mr-1"/> Crear usuario
        </button>
      </header>

      {notice && (
        <div className={`surface p-4 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5" : "border-rose-500 bg-rose-500/5"}`}
             data-testid="accesos-notice">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className={`text-sm ${notice.kind === "ok" ? "text-emerald-400" : "text-rose-400"}`}>
                {notice.kind === "ok" ? <CheckCircle2 size={14} className="inline mr-2"/>
                                     : <AlertOctagon size={14} className="inline mr-2"/>}
                {notice.msg}
              </div>
              {notice.copyPw && (
                <div className="mt-3 p-3 bg-zinc-900 border border-amber-500/30">
                  <div className="label-overline text-amber-400 text-[9px] mb-1">
                    🔐 Credenciales (cópialas y entrégalas al usuario · NO se mostrarán de nuevo)
                  </div>
                  <div className="font-mono text-xs space-y-1">
                    <div><span className="text-zinc-500">Email:</span> <span className="text-zinc-100">{notice.copyEmail}</span></div>
                    <div><span className="text-zinc-500">Pass:</span> <span className="text-amber-400 font-bold">{notice.copyPw}</span></div>
                  </div>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(`Email: ${notice.copyEmail}\nContraseña: ${notice.copyPw}`);
                      setNotice({ ...notice, copied: true });
                      setTimeout(() => setNotice((n) => n && { ...n, copied: false }), 2000);
                    }}
                    className="mt-2 text-[10px] text-amber-400 hover:text-amber-300 font-mono"
                    data-testid="copy-creds-btn"
                  >
                    <Copy size={10} className="inline mr-1"/>
                    {notice.copied ? "✓ Copiado" : "Copiar credenciales"}
                  </button>
                </div>
              )}
            </div>
            <button onClick={() => setNotice(null)} className="text-zinc-500 hover:text-zinc-300 text-xs">✕</button>
          </div>
        </div>
      )}

      <section className="surface overflow-x-auto" data-testid="usuarios-section">
        {loading ? (
          <div className="p-8 text-center text-zinc-500"><Loader2 size={16} className="inline animate-spin mr-2"/> Cargando…</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center text-zinc-500">— Sin usuarios —</div>
        ) : (
          <table className="dtable">
            <thead><tr><th>Nombre</th><th>Email</th><th>Rol</th><th>Estado</th><th>Creado</th><th>Acciones</th></tr></thead>
            <tbody>
              {users.map((u) => {
                const rmeta = ROLES.find((r) => r.value === u.role) || { color: "zinc" };
                return (
                  <tr key={u.id} data-testid={`user-row-${u.id}`}>
                    <td className="font-semibold">{u.name}</td>
                    <td className="text-xs font-mono">{u.email}</td>
                    <td>
                      <span className={`text-[10px] font-mono uppercase bg-${rmeta.color}-500/10 text-${rmeta.color}-400 border border-${rmeta.color}-500/30 px-1.5 py-0.5`}>
                        {u.role}
                      </span>
                    </td>
                    <td>
                      {u.activo === false ? (
                        <span className="text-[10px] font-mono text-rose-400">INACTIVO</span>
                      ) : (
                        <span className="text-[10px] font-mono text-emerald-400">ACTIVO</span>
                      )}
                    </td>
                    <td className="text-[10px] font-mono text-zinc-500">
                      {(u.created_at || "").slice(0, 10)}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button onClick={() => setEditTarget(u)}
                              className="text-zinc-400 hover:text-amber-400 mr-2"
                              data-testid={`btn-edit-${u.id}`} title="Editar">
                        <Edit3 size={12}/>
                      </button>
                      <button onClick={() => setResetTarget(u)}
                              className="text-amber-400 hover:text-amber-300 mr-2"
                              data-testid={`btn-reset-${u.id}`} title="Resetear contraseña">
                        <KeyRound size={12}/>
                      </button>
                      <button onClick={() => eliminarUsuario(u)}
                              className="text-rose-400 hover:text-rose-300"
                              data-testid={`btn-delete-${u.id}`} title="Eliminar">
                        <Trash2 size={12}/>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <div className="text-[10px] text-zinc-600 font-mono">
        🔒 Buenas prácticas: usa contraseñas largas (12+ caracteres mezclando letras, números y símbolos).
        Cambia las contraseñas cada 90 días. Desactiva en lugar de eliminar cuando un colaborador se va.
      </div>

      <CrearUsuarioModal open={showCreate} onClose={() => setShowCreate(false)} onCreated={onCreated}/>
      <ResetPasswordModal user={resetTarget} onClose={() => setResetTarget(null)} onDone={onResetDone}/>
      <EditUsuarioModal user={editTarget} onClose={() => setEditTarget(null)} onSaved={() => { setEditTarget(null); load(); }}/>
    </div>
  );
}

function generaPassword(len = 14) {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%&*";
  let out = "";
  for (let i = 0; i < len; i++) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}

function CrearUsuarioModal({ open, onClose, onCreated }) {
  const [f, setF] = useState({ name: "", email: "", role: "comercial", password: "" });
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (open) {
      setF({ name: "", email: "", role: "comercial", password: generaPassword() });
      setErr("");
    }
  }, [open]);

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const { data } = await api.post("/accesos/usuarios", f);
      onCreated(data, f.password);
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Crear nuevo usuario" testId="modal-crear-usuario">
      <form onSubmit={submit} className="space-y-3">
        <input required className="input-field" placeholder="Nombre completo"
               value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}
               data-testid="nuevo-nombre"/>
        <input required type="email" className="input-field" placeholder="email@deyma.mx"
               value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })}
               data-testid="nuevo-email"/>
        <select className="input-field" value={f.role}
                onChange={(e) => setF({ ...f, role: e.target.value })} data-testid="nuevo-role">
          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <div>
          <label className="label-overline">Contraseña (auto-generada · puedes editarla)</label>
          <div className="flex gap-2">
            <input
              type={showPw ? "text" : "password"}
              className="input-field font-mono flex-1"
              value={f.password}
              onChange={(e) => setF({ ...f, password: e.target.value })}
              minLength={6}
              data-testid="nuevo-password"
            />
            <button type="button" onClick={() => setShowPw((v) => !v)} className="btn-ghost text-xs">
              {showPw ? <EyeOff size={12}/> : <Eye size={12}/>}
            </button>
            <button type="button" onClick={() => setF({ ...f, password: generaPassword() })}
                    className="btn-ghost text-xs" data-testid="nuevo-regen-pw">
              ↻
            </button>
          </div>
          <div className="text-[10px] text-zinc-500 mt-1 font-mono">
            Mínimo 6 caracteres · Se mostrará una vez después de crear el usuario para que la copies.
          </div>
        </div>
        {err && <div className="text-rose-400 text-xs" data-testid="nuevo-error">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary" data-testid="nuevo-submit">
            {busy ? "Creando…" : "Crear usuario"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ResetPasswordModal({ user, onClose, onDone }) {
  const [pw, setPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (user) { setPw(generaPassword()); setErr(""); }
  }, [user]);

  if (!user) return null;

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api.post(`/accesos/usuarios/${user.id}/reset-password`, { new_password: pw });
      onDone(user.email, pw);
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={!!user} onClose={onClose} title={`Resetear contraseña — ${user.email}`} testId="modal-reset-pw">
      <form onSubmit={submit} className="space-y-3">
        <div className="surface-elev p-2.5 text-xs">
          <Lock size={12} className="inline mr-1 text-amber-400"/>
          Solo se mostrará esta vez. Cópiala y entrégala al usuario.
        </div>
        <div>
          <label className="label-overline">Nueva contraseña</label>
          <div className="flex gap-2">
            <input
              type={showPw ? "text" : "password"}
              className="input-field font-mono flex-1"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              minLength={6}
              data-testid="reset-pw-input"
            />
            <button type="button" onClick={() => setShowPw((v) => !v)} className="btn-ghost text-xs">
              {showPw ? <EyeOff size={12}/> : <Eye size={12}/>}
            </button>
            <button type="button" onClick={() => setPw(generaPassword())} className="btn-ghost text-xs" data-testid="reset-regen-pw">
              ↻
            </button>
          </div>
        </div>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy}
                  className="btn-primary bg-amber-500 hover:bg-amber-600 text-black border-amber-600"
                  data-testid="reset-pw-submit">
            {busy ? "Actualizando…" : "Resetear contraseña"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function EditUsuarioModal({ user, onClose, onSaved }) {
  const [f, setF] = useState({ name: "", role: "", activo: true });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (user) {
      setF({ name: user.name || "", role: user.role || "comercial", activo: user.activo !== false });
      setErr("");
    }
  }, [user]);

  if (!user) return null;

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      await api.patch(`/accesos/usuarios/${user.id}`, f);
      onSaved();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={!!user} onClose={onClose} title={`Editar — ${user.email}`} testId="modal-edit-user">
      <form onSubmit={submit} className="space-y-3">
        <input className="input-field" placeholder="Nombre"
               value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}/>
        <select className="input-field" value={f.role}
                onChange={(e) => setF({ ...f, role: e.target.value })}>
          {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={f.activo}
                 onChange={(e) => setF({ ...f, activo: e.target.checked })}
                 className="accent-amber-500"/>
          Usuario activo
        </label>
        {err && <div className="text-rose-400 text-xs">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" disabled={busy} className="btn-primary">
            <Save size={12} className="inline mr-1"/> {busy ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
