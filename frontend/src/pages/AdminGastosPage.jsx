import React, { useEffect, useState, useRef } from "react";
import { useAuth, api, fmtMXN, formatApiError } from "../lib/auth";
import { Wallet, Upload, Trash2, Download, Plus, AlertCircle, CheckCircle2, Filter, FileText, Receipt } from "lucide-react";

const TIPOS = [
  { key: "gasolina", label: "Gasolina", icon: "⛽" },
  { key: "casetas", label: "Casetas / Peajes", icon: "🛣️" },
  { key: "comida", label: "Comida", icon: "🍽️" },
  { key: "hospedaje", label: "Hospedaje", icon: "🏨" },
  { key: "estacionamiento", label: "Estacionamiento", icon: "🅿️" },
  { key: "otros", label: "Otros", icon: "📝" },
];

export default function AdminGastosPage() {
  const { user } = useAuth();
  const allowed = ["comercial", "director", "socio"].includes(user?.role);
  const [data, setData] = useState({ items: [], total: 0, por_tipo: {}, n: 0 });
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");
  const [showForm, setShowForm] = useState(false);

  const load = async () => {
    if (!allowed) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filtroTipo) params.set("tipo", filtroTipo);
      if (filtroDesde) params.set("fecha_desde", filtroDesde);
      if (filtroHasta) params.set("fecha_hasta", filtroHasta);
      const { data: d } = await api.get(`/gastos-viajero?${params.toString()}`);
      setData(d);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [filtroTipo, filtroDesde, filtroHasta, allowed]);

  if (!allowed) {
    return <div className="p-10 text-center text-rose-400 font-mono text-sm" data-testid="gastos-denied">Acceso denegado. Solo Comercial, Director y Socio.</div>;
  }

  const del = async (gid) => {
    if (!window.confirm("¿Eliminar este gasto?")) return;
    await api.delete(`/gastos-viajero/${gid}`); load();
  };

  const downloadComprobante = async (g) => {
    const res = await api.get(`/gastos-viajero/${g.id}/file`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a"); a.href = url; a.download = g.filename || "comprobante";
    document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="label-overline text-amber-400">Comprobaciones de viajero</div>
          <h1 className="text-3xl font-black flex items-center gap-3" style={{ fontFamily: "Chivo, sans-serif" }}>
            <Wallet size={26} className="text-amber-400" /> Gastos de Viajero
          </h1>
          <p className="text-xs text-zinc-500 mt-1 font-mono">{user.role === "comercial" ? "Tus gastos personales" : "Todos los vendedores"} · {data.n} registros</p>
        </div>
        <button onClick={() => setShowForm(true)} data-testid="gasto-add-btn" className="btn-primary flex items-center gap-2"><Plus size={14} /> Nuevo gasto</button>
      </header>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="gastos-stats">
        <BigStat k="Total filtrado" v={fmtMXN(data.total)} highlight />
        <BigStat k="Gasolina" v={fmtMXN(data.por_tipo?.gasolina || 0)} />
        <BigStat k="Casetas" v={fmtMXN(data.por_tipo?.casetas || 0)} />
        <BigStat k="Comida + Hosp." v={fmtMXN((data.por_tipo?.comida || 0) + (data.por_tipo?.hospedaje || 0))} />
      </div>

      {/* Filtros */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter size={14} className="text-zinc-500" />
        <select data-testid="gastos-filter-tipo" className="input-field max-w-[180px]" value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
          <option value="">Todos los tipos</option>
          {TIPOS.map((t) => <option key={t.key} value={t.key}>{t.icon} {t.label}</option>)}
        </select>
        <input data-testid="gastos-filter-desde" type="date" className="input-field max-w-[170px]" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} placeholder="Desde" />
        <input data-testid="gastos-filter-hasta" type="date" className="input-field max-w-[170px]" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} placeholder="Hasta" />
        {(filtroTipo || filtroDesde || filtroHasta) && (
          <button onClick={() => { setFiltroTipo(""); setFiltroDesde(""); setFiltroHasta(""); }} className="btn-ghost text-xs">Limpiar</button>
        )}
      </div>

      {/* Tabla */}
      <div className="border border-white/10 bg-zinc-950">
        {loading ? (
          <div className="p-10 text-center text-sm text-zinc-500 animate-pulse">Cargando…</div>
        ) : data.items.length === 0 ? (
          <div className="p-10 text-center text-sm text-zinc-500" data-testid="gastos-empty">Sin gastos registrados aún.</div>
        ) : (
          <table className="w-full text-xs" data-testid="gastos-table">
            <thead>
              <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
                <th className="p-3">Fecha</th>
                {user.role !== "comercial" && <th className="p-3">Vendedor</th>}
                <th className="p-3">Tipo</th>
                <th className="p-3 text-right">Monto</th>
                <th className="p-3">Lugar</th>
                <th className="p-3">Descripción</th>
                <th className="p-3 text-center">Comp.</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((g) => {
                const tipo = TIPOS.find((t) => t.key === g.tipo);
                return (
                  <tr key={g.id} className="border-b border-white/5 hover:bg-white/5" data-testid={`gasto-row-${g.id}`}>
                    <td className="p-3 font-mono">{g.fecha}</td>
                    {user.role !== "comercial" && <td className="p-3 text-zinc-300">{g.vendedor_nombre}</td>}
                    <td className="p-3">
                      <span className="px-2 py-0.5 text-[11px] border border-white/10 bg-zinc-900">{tipo?.icon} {tipo?.label || g.tipo}</span>
                    </td>
                    <td className="p-3 text-right font-mono font-bold text-amber-400">{fmtMXN(g.monto)}</td>
                    <td className="p-3 text-zinc-400">{g.lugar || "—"}</td>
                    <td className="p-3 text-zinc-300 truncate max-w-[260px]">{g.descripcion || "—"}</td>
                    <td className="p-3 text-center">
                      {g.file_id ? (
                        <button onClick={() => downloadComprobante(g)} data-testid={`gasto-file-${g.id}`} className="text-amber-400 hover:text-amber-300 inline-flex items-center gap-1">
                          <Receipt size={12} />
                        </button>
                      ) : <span className="text-zinc-600">—</span>}
                    </td>
                    <td className="p-3 text-right">
                      <button onClick={() => del(g.id)} data-testid={`gasto-del-${g.id}`} className="text-rose-400 hover:text-rose-300"><Trash2 size={12} /></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            {data.items.length > 0 && (
              <tfoot>
                <tr className="border-t-2 border-amber-500/40 bg-amber-500/5">
                  <td colSpan={user.role === "comercial" ? 2 : 3} className="p-3 font-bold text-zinc-300 label-overline">TOTAL FILTRADO</td>
                  <td className="p-3 text-right font-mono font-black text-amber-400 text-base" data-testid="gastos-total">{fmtMXN(data.total)}</td>
                  <td colSpan="4"></td>
                </tr>
              </tfoot>
            )}
          </table>
        )}
      </div>

      {showForm && <GastoForm onClose={() => setShowForm(false)} onSaved={() => { setShowForm(false); load(); }} />}
    </div>
  );
}

function BigStat({ k, v, highlight }) {
  return (
    <div className={`p-4 border ${highlight ? "border-amber-500/40 bg-amber-500/5" : "border-white/10 bg-zinc-950"}`}>
      <div className="label-overline text-[10px]">{k}</div>
      <div className={`text-2xl font-black mt-1 font-mono ${highlight ? "text-amber-400" : "text-zinc-100"}`} style={{ fontFamily: "Chivo, sans-serif" }}>{v}</div>
    </div>
  );
}

function GastoForm({ onClose, onSaved }) {
  const fileRef = useRef();
  const [form, setForm] = useState({
    tipo: "gasolina", monto: "", fecha: new Date().toISOString().slice(0, 10),
    descripcion: "", lugar: "", ruta_id: "",
  });
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    if (file) fd.append("archivo", file);
    try {
      await api.post("/gastos-viajero", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onSaved();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur flex items-start justify-center p-4 overflow-y-auto" onClick={onClose} data-testid="gasto-modal">
      <form onSubmit={submit} className="bg-zinc-950 border border-white/10 max-w-xl w-full my-8" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-white/10 p-5 flex items-center justify-between">
          <div>
            <div className="label-overline text-amber-400">Nuevo gasto de viaje</div>
            <h2 className="text-2xl font-black mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>Registrar gasto</h2>
          </div>
          <button type="button" onClick={onClose} data-testid="gasto-close" className="text-zinc-400 hover:text-rose-400 text-xl px-2">✕</button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="label-overline">Tipo de gasto</label>
            <div className="grid grid-cols-3 gap-2 mt-2">
              {TIPOS.map((t) => (
                <button key={t.key} type="button" onClick={() => set("tipo", t.key)} data-testid={`tipo-${t.key}`}
                  className={`p-2 border text-xs label-overline flex flex-col items-center gap-1 ${form.tipo === t.key ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}>
                  <span className="text-lg">{t.icon}</span> {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-overline">Monto MXN <span className="text-amber-400">*</span></label>
              <input data-testid="gasto-monto" required type="number" step="0.01" min="0" className="input-field mt-1" value={form.monto} onChange={(e) => set("monto", e.target.value)} placeholder="0.00" />
            </div>
            <div>
              <label className="label-overline">Fecha <span className="text-amber-400">*</span></label>
              <input data-testid="gasto-fecha" required type="date" className="input-field mt-1" value={form.fecha} onChange={(e) => set("fecha", e.target.value)} />
            </div>
          </div>

          <div>
            <label className="label-overline">Lugar</label>
            <input data-testid="gasto-lugar" className="input-field mt-1" value={form.lugar} onChange={(e) => set("lugar", e.target.value)} placeholder="Ej. PEMEX Salamanca km 32" />
          </div>

          <div>
            <label className="label-overline">Descripción</label>
            <textarea data-testid="gasto-desc" rows={2} className="input-field mt-1" value={form.descripcion} onChange={(e) => set("descripcion", e.target.value)} placeholder="Detalle del gasto (opcional)" />
          </div>

          <div>
            <label className="label-overline">Comprobante (foto o PDF) — máx 10 MB</label>
            <input ref={fileRef} data-testid="gasto-file" type="file" accept="image/*,.pdf"
              className="block mt-2 text-xs text-zinc-400 file:mr-3 file:py-2 file:px-3 file:border file:border-amber-500/40 file:bg-amber-500/10 file:text-amber-400 file:font-bold file:label-overline file:cursor-pointer"
              onChange={(e) => setFile(e.target.files?.[0] || null)} />
            {file && <div className="text-[10px] text-emerald-400 font-mono mt-1">✓ {file.name} · {(file.size / 1024).toFixed(1)} KB</div>}
          </div>

          {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono flex gap-1.5"><AlertCircle size={14} /> {err}</div>}

          <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
            <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
            <button disabled={busy} data-testid="gasto-submit" className="btn-primary flex items-center gap-2">
              {busy ? "Guardando…" : <><Upload size={14} /> Registrar</>}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
