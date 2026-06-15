import React, { useEffect, useState } from "react";
import { useAuth, api, formatApiError, downloadPdf } from "../lib/auth";
import { Users2, CheckCircle2, XCircle, Clock, FileText, Download, AlertCircle, Eye } from "lucide-react";

const ESTADO_META = {
  pendiente: { label: "Pendiente", color: "amber", icon: Clock },
  aprobado_director: { label: "Director ✓ · Falta Socio", color: "amber", icon: Clock },
  aprobado_socio: { label: "Socio ✓ · Falta Director", color: "amber", icon: Clock },
  aprobado_completo: { label: "Aprobado", color: "emerald", icon: CheckCircle2 },
  rechazado: { label: "Rechazado", color: "rose", icon: XCircle },
};

const DOC_LABELS = {
  csf: "Constancia Situación Fiscal",
  acta: "Acta Constitutiva",
  poder: "Poder Representante",
  ine: "INE Representante",
  comprobante: "Comprobante de Domicilio",
};

export default function AdminClientesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const url = filter ? `/clientes?estado=${filter}` : "/clientes";
      const { data } = await api.get(url);
      setItems(data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter]);

  const canDecide = user?.role === "director" || user?.role === "socio";

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Portal de Alta · Doble aprobación Director + Socio</div>
          <h1 className="text-3xl font-black flex items-center gap-3" style={{ fontFamily: "Chivo, sans-serif" }}>
            <Users2 size={26} className="text-amber-400" /> Solicitudes de alta
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <FilterBtn cur={filter} val="" set={setFilter} label="Todas" />
          <FilterBtn cur={filter} val="pendiente" set={setFilter} label="Pendientes" />
          <FilterBtn cur={filter} val="aprobado_director" set={setFilter} label="Falta Socio" />
          <FilterBtn cur={filter} val="aprobado_socio" set={setFilter} label="Falta Director" />
          <FilterBtn cur={filter} val="aprobado_completo" set={setFilter} label="Aprobados" />
          <FilterBtn cur={filter} val="rechazado" set={setFilter} label="Rechazados" />
        </div>
      </header>

      <div className="border border-white/10 bg-zinc-950">
        {loading ? (
          <div className="p-10 text-center text-sm text-zinc-500 animate-pulse">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="p-10 text-center text-sm text-zinc-500" data-testid="admin-clientes-empty">Sin solicitudes en este filtro.</div>
        ) : (
          <table className="w-full text-xs" data-testid="admin-clientes-table">
            <thead>
              <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
                <th className="p-3">Folio</th>
                <th className="p-3">Razón social</th>
                <th className="p-3">RFC</th>
                <th className="p-3">Estado</th>
                <th className="p-3">DFNUM</th>
                <th className="p-3">Fecha</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => {
                const meta = ESTADO_META[c.estado] || ESTADO_META.pendiente;
                const Icon = meta.icon;
                return (
                  <tr key={c.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="p-3 font-mono">{c.folio_registro}</td>
                    <td className="p-3 text-zinc-200">{c.razon_social}</td>
                    <td className="p-3 font-mono text-zinc-400">{c.rfc}</td>
                    <td className="p-3"><span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase border bg-${meta.color}-500/10 text-${meta.color}-400 border-${meta.color}-500/40`}><Icon size={10} /> {meta.label}</span></td>
                    <td className="p-3 font-mono text-zinc-300">{c.dfnum || "—"}</td>
                    <td className="p-3 font-mono text-zinc-500">{new Date(c.created_at).toLocaleDateString("es-MX")}</td>
                    <td className="p-3 text-right">
                      <button onClick={() => setOpen(c.id)} data-testid={`admin-open-${c.id}`} className="inline-flex items-center gap-1 text-amber-400 hover:text-amber-300"><Eye size={12} /> Detalle</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {open && <DetailModal cid={open} onClose={() => { setOpen(null); load(); }} canDecide={canDecide} user={user} />}
    </div>
  );
}

function FilterBtn({ cur, val, set, label }) {
  const active = cur === val;
  return (
    <button
      onClick={() => set(val)}
      data-testid={`filter-${val || "all"}`}
      className={`px-3 py-1.5 text-[11px] label-overline border transition-colors ${active ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-white/10 text-zinc-400 hover:text-zinc-100"}`}
    >{label}</button>
  );
}

function DetailModal({ cid, onClose, canDecide, user }) {
  const [cli, setCli] = useState(null);
  const [nota, setNota] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = () => api.get(`/clientes/${cid}`).then((r) => setCli(r.data));
  useEffect(() => { load(); }, [cid]);

  useEffect(() => {
    const onEsc = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onEsc);
    return () => document.removeEventListener("keydown", onEsc);
  }, [onClose]);

  if (!cli) return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center"><div className="text-amber-400 font-mono text-xs animate-pulse">Cargando…</div></div>
  );

  const yaAprobeRol = cli.aprobaciones?.some((a) => a.rol === user?.role && a.decision !== "rechazado");
  const final = ["aprobado_completo", "rechazado"].includes(cli.estado);

  const doAction = async (action) => {
    setBusy(true); setErr("");
    try {
      await api.post(`/clientes/${cid}/${action}`, { nota });
      await load();
      setNota("");
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  const fileUrl = (key) => `${api.defaults.baseURL}/clientes/${cli.id}/file/${key}`;

  const downloadFile = async (key) => {
    const res = await api.get(`/clientes/${cli.id}/file/${key}`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a");
    a.href = url; a.download = cli.documentos?.[key]?.filename || `${key}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur z-50 flex items-start justify-center p-6 overflow-y-auto" onClick={onClose} data-testid="admin-detail-modal">
      <div className="bg-zinc-950 border border-white/10 max-w-4xl w-full my-8" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-white/10 p-5 flex items-start justify-between">
          <div>
            <div className="label-overline text-amber-400">Solicitud {cli.folio_registro}</div>
            <h2 className="text-2xl font-black mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>{cli.razon_social}</h2>
            <div className="text-xs text-zinc-500 font-mono mt-1">{cli.rfc} · {cli.email}</div>
          </div>
          <button onClick={onClose} data-testid="admin-detail-close" className="text-zinc-400 hover:text-rose-400 text-xl px-2">✕</button>
        </div>

        <div className="p-5 space-y-5">
          <div className="grid grid-cols-2 gap-3">
            <Mini k="Estado" v={cli.estado} />
            <Mini k="DFNUM" v={cli.dfnum || "Pendiente"} />
            <Mini k="Domicilio fiscal" v={cli.domicilio_fiscal} />
            <Mini k="Domicilio planta" v={cli.domicilio_planta || "—"} />
          </div>

          <Section title="Contactos">
            <ContactoRow t="Técnico" c={cli.contactos?.tecnico} />
            <ContactoRow t="Compras" c={cli.contactos?.compras} />
            <ContactoRow t="Cuentas por pagar" c={cli.contactos?.cuentas_por_pagar} />
          </Section>

          <Section title="Políticas aceptadas">
            <ul className="text-xs text-zinc-300 space-y-1">
              {Object.entries(cli.politicas || {}).map(([k, v]) => (
                <li key={k} className="flex items-center gap-2 font-mono">
                  <span className={v ? "text-emerald-400" : "text-rose-400"}>{v ? "✓" : "✗"}</span> {k}
                </li>
              ))}
              {Object.entries(cli.financieras || {}).map(([k, v]) => (
                <li key={k} className="flex items-center gap-2 font-mono">
                  <span className={v ? "text-emerald-400" : "text-rose-400"}>{v ? "✓" : "✗"}</span> {k}
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Documentos">
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(cli.documentos || {}).map(([k, d]) => (
                <div key={k} className="flex items-center gap-2 p-2 border border-white/10 hover:bg-white/5">
                  <FileText size={14} className="text-amber-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-bold">{DOC_LABELS[k] || k}</div>
                    <div className="text-[10px] text-zinc-500 truncate font-mono">{d.filename || "—"}</div>
                  </div>
                  <button onClick={() => downloadFile(k)} data-testid={`doc-${k}`} className="text-xs text-amber-400 hover:text-amber-300 px-2"><Download size={12} /></button>
                </div>
              ))}
            </div>
          </Section>

          <Section title={`Aprobaciones (${cli.aprobaciones?.length || 0})`}>
            {cli.aprobaciones?.length > 0 ? (
              <ul className="space-y-1.5">
                {cli.aprobaciones.map((a, i) => (
                  <li key={i} className="text-xs font-mono flex gap-2 items-start">
                    <span className={a.decision === "rechazado" ? "text-rose-400" : "text-emerald-400"}>{a.decision === "rechazado" ? "✗" : "✓"}</span>
                    <div>
                      <div className="text-zinc-200">{a.user_name} <span className="text-zinc-500">({a.rol})</span></div>
                      <div className="text-zinc-500 text-[10px]">{new Date(a.ts).toLocaleString("es-MX")}</div>
                      {a.nota && <div className="text-zinc-400 italic mt-0.5">"{a.nota}"</div>}
                    </div>
                  </li>
                ))}
              </ul>
            ) : <div className="text-xs text-zinc-500">Aún no hay aprobaciones registradas.</div>}
          </Section>

          {cli.estado === "aprobado_completo" && (
            <button onClick={() => downloadPdf(`/clientes/${cli.id}/pdf-bienvenida`, `DEYMA_bienvenida_${cli.dfnum}.pdf`)} data-testid="admin-download-bienvenida" className="btn-ghost flex items-center gap-1.5 text-xs"><Download size={12} /> Descargar PDF Bienvenida</button>
          )}

          {canDecide && !final && !yaAprobeRol && (
            <div className="border border-amber-500/30 bg-amber-500/5 p-4 space-y-3">
              <div className="label-overline text-amber-400">Tu decisión ({user.role})</div>
              <textarea
                data-testid="admin-nota"
                value={nota} onChange={(e) => setNota(e.target.value)}
                rows={2} placeholder="Nota (opcional)" className="input-field"
              />
              {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono flex gap-1.5"><AlertCircle size={14} /> {err}</div>}
              <div className="flex items-center gap-2">
                <button onClick={() => doAction("aprobar")} disabled={busy} data-testid="admin-aprobar" className="btn-primary flex items-center gap-1.5 text-xs"><CheckCircle2 size={14} /> Aprobar</button>
                <button onClick={() => doAction("rechazar")} disabled={busy} data-testid="admin-rechazar" className="btn-ghost flex items-center gap-1.5 text-xs border-rose-500/40 text-rose-300 hover:bg-rose-500/10"><XCircle size={14} /> Rechazar</button>
              </div>
            </div>
          )}

          {canDecide && yaAprobeRol && !final && (
            <div className="border border-emerald-500/40 bg-emerald-500/5 p-3 text-xs text-emerald-300 font-mono">
              ✓ Ya registraste tu aprobación como {user.role}. Esperando al otro firmante.
            </div>
          )}

          {final && (
            <div className="border border-white/10 bg-zinc-900 p-3 text-xs text-zinc-400 font-mono">
              Solicitud en estado final: <b>{cli.estado.toUpperCase()}</b>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Mini({ k, v }) {
  return (
    <div className="border border-white/10 p-2.5">
      <div className="label-overline text-[10px]">{k}</div>
      <div className="text-xs text-zinc-200 mt-0.5 truncate">{v}</div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="space-y-2">
      <div className="label-overline text-amber-400">{title}</div>
      {children}
    </div>
  );
}

function ContactoRow({ t, c }) {
  if (!c) return null;
  return (
    <div className="text-xs flex gap-2 items-baseline">
      <span className="text-zinc-500 w-24 shrink-0">{t}</span>
      <span className="text-zinc-200">{c.nombre}</span>
      <span className="text-zinc-500 font-mono ml-2">{c.correo}</span>
      <span className="text-zinc-500 font-mono">{c.tel}</span>
    </div>
  );
}
