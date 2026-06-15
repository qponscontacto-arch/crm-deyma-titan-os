import React, { useEffect, useState, useRef } from "react";
import { useAuth, api, fmtMXN, formatApiError } from "../lib/auth";
import { Users2, UserPlus, Search, Eye, Download, Upload, FileText, CheckCircle2, XCircle, AlertCircle, Trash2, Calendar, Plus, Building2, Briefcase, Heart, Award, Wallet } from "lucide-react";

const DEPARTAMENTOS = ["Obra", "Administración", "Comercial", "Operaciones", "Diseño", "RH"];
const TIPOS_DOC = [
  { key: "general", label: "Documentación general (INE/CURP/NSS)", icon: FileText },
  { key: "contrato", label: "Contrato de contratación", icon: Briefcase },
  { key: "renuncia", label: "Carta de renuncia", icon: XCircle },
  { key: "amonestacion", label: "Carta de amonestación", icon: AlertCircle },
  { key: "cert_medico", label: "Certificado médico", icon: Heart },
  { key: "dc3", label: "Constancia DC-3 STPS", icon: Award },
];

export default function AdminRHPage() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [filterStatus, setFilterStatus] = useState("activo");
  const [filterDept, setFilterDept] = useState("");
  const [openId, setOpenId] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  const allowed = ["director", "socio"].includes(user?.role);

  const load = async () => {
    if (!allowed) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (filterStatus) params.set("status", filterStatus);
      if (filterDept) params.set("departamento", filterDept);
      const { data } = await api.get(`/rh/empleados?${params.toString()}`);
      setItems(data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filterStatus, filterDept, allowed]);

  if (!allowed) {
    return <div className="p-10 text-center text-rose-400 font-mono text-sm" data-testid="rh-denied">Acceso denegado. Solo Director y Socio.</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="label-overline text-amber-400">Recursos Humanos · Acceso restringido</div>
          <h1 className="text-3xl font-black flex items-center gap-3" style={{ fontFamily: "Chivo, sans-serif" }}>
            <Users2 size={26} className="text-amber-400" /> Personal Contratado
          </h1>
          <p className="text-xs text-zinc-500 mt-1 font-mono">Director General y Socio · {items.length} empleados visibles</p>
        </div>
        <button onClick={() => setShowCreate(true)} data-testid="rh-create-btn" className="btn-primary flex items-center gap-2">
          <UserPlus size={14} /> Nuevo empleado
        </button>
      </header>

      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[260px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input data-testid="rh-search" className="input-field pl-9" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} placeholder="Buscar por nombre, RFC, CURP o puesto…" />
        </div>
        <select data-testid="rh-filter-status" className="input-field max-w-[160px]" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="">Todos los estatus</option>
          <option value="activo">Activos</option>
          <option value="baja">Bajas</option>
        </select>
        <select data-testid="rh-filter-dept" className="input-field max-w-[200px]" value={filterDept} onChange={(e) => setFilterDept(e.target.value)}>
          <option value="">Todos los depto.</option>
          {DEPARTAMENTOS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      </div>

      <div className="border border-white/10 bg-zinc-950">
        {loading ? (
          <div className="p-10 text-center text-sm text-zinc-500 animate-pulse">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="p-10 text-center text-sm text-zinc-500" data-testid="rh-empty">
            Sin empleados {filterStatus ? `con estatus '${filterStatus}'` : ""} {filterDept ? `en ${filterDept}` : ""}.
          </div>
        ) : (
          <table className="w-full text-xs" data-testid="rh-table">
            <thead>
              <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
                <th className="p-3">Nombre</th>
                <th className="p-3">Puesto</th>
                <th className="p-3">Depto.</th>
                <th className="p-3">Antigüedad</th>
                <th className="p-3 text-right">Vac. periodo</th>
                <th className="p-3">Estatus</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-3">
                    <div className="text-zinc-100 font-semibold">{e.nombre}</div>
                    <div className="text-zinc-500 font-mono text-[10px]">{e.rfc || "—"}</div>
                  </td>
                  <td className="p-3 text-zinc-300">{e.puesto}</td>
                  <td className="p-3"><span className="px-1.5 py-0.5 text-[10px] font-mono uppercase border border-white/10 text-zinc-300">{e.departamento}</span></td>
                  <td className="p-3 font-mono text-zinc-400">{e.prestaciones?.antiguedad_anios}a · {e.prestaciones?.antiguedad_meses}m</td>
                  <td className="p-3 text-right font-mono text-amber-400 font-bold">{e.prestaciones?.vacaciones_anuales_periodo_actual} días</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 text-[10px] font-mono uppercase border ${e.status === "activo" ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400" : "border-rose-500/40 bg-rose-500/10 text-rose-400"}`}>
                      {e.status}
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <button onClick={() => setOpenId(e.id)} data-testid={`rh-open-${e.id}`} className="text-amber-400 hover:text-amber-300 inline-flex items-center gap-1"><Eye size={12} /> Detalle</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showCreate && <CreateEmpleadoModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />}
      {openId && <EmpleadoModal eid={openId} onClose={() => { setOpenId(null); load(); }} />}
    </div>
  );
}

function CreateEmpleadoModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    nombre: "", rfc: "", curp: "", nss: "", puesto: "", departamento: "Obra",
    fecha_ingreso: new Date().toISOString().slice(0, 10),
    salario_diario: 0, salario_mensual: 0, sueldo_integrado: 0,
    tel: "", correo: "", domicilio: "",
    contacto_emergencia_nombre: "", contacto_emergencia_tel: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await api.post("/rh/empleados", { ...form, salario_diario: +form.salario_diario, salario_mensual: +form.salario_mensual, sueldo_integrado: +form.sueldo_integrado });
      onCreated();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur z-50 flex items-start justify-center p-6 overflow-y-auto" onClick={onClose} data-testid="rh-create-modal">
      <form onSubmit={submit} className="bg-zinc-950 border border-white/10 max-w-3xl w-full my-8" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-white/10 p-5 flex items-center justify-between">
          <div>
            <div className="label-overline text-amber-400">Alta de empleado</div>
            <h2 className="text-2xl font-black mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>Nuevo empleado</h2>
          </div>
          <button type="button" onClick={onClose} data-testid="rh-create-close" className="text-zinc-400 hover:text-rose-400 text-xl px-2">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <Section title="Datos personales">
            <div className="grid md:grid-cols-2 gap-3">
              <Field label="Nombre completo" required><input data-testid="emp-nombre" required className="input-field" value={form.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
              <Field label="Puesto" required><input data-testid="emp-puesto" required className="input-field" value={form.puesto} onChange={(e) => set("puesto", e.target.value)} /></Field>
              <Field label="RFC"><input data-testid="emp-rfc" className="input-field uppercase" value={form.rfc} onChange={(e) => set("rfc", e.target.value.toUpperCase())} maxLength={13} /></Field>
              <Field label="CURP"><input data-testid="emp-curp" className="input-field uppercase" value={form.curp} onChange={(e) => set("curp", e.target.value.toUpperCase())} maxLength={18} /></Field>
              <Field label="NSS (IMSS)"><input data-testid="emp-nss" className="input-field" value={form.nss} onChange={(e) => set("nss", e.target.value)} maxLength={11} /></Field>
              <Field label="Departamento" required>
                <select data-testid="emp-dept" className="input-field" value={form.departamento} onChange={(e) => set("departamento", e.target.value)}>
                  {DEPARTAMENTOS.map((d) => <option key={d}>{d}</option>)}
                </select>
              </Field>
              <Field label="Teléfono"><input data-testid="emp-tel" className="input-field" value={form.tel} onChange={(e) => set("tel", e.target.value)} /></Field>
              <Field label="Correo"><input data-testid="emp-correo" type="email" className="input-field" value={form.correo} onChange={(e) => set("correo", e.target.value)} /></Field>
              <Field label="Domicilio" span={2}><input data-testid="emp-domicilio" className="input-field" value={form.domicilio} onChange={(e) => set("domicilio", e.target.value)} /></Field>
            </div>
          </Section>

          <Section title="Datos laborales y salariales">
            <div className="grid md:grid-cols-2 gap-3">
              <Field label="Fecha de ingreso" required><input data-testid="emp-fecha" required type="date" className="input-field" value={form.fecha_ingreso} onChange={(e) => set("fecha_ingreso", e.target.value)} /></Field>
              <Field label="Salario diario (MXN)"><input data-testid="emp-sal-diario" type="number" step="0.01" className="input-field" value={form.salario_diario} onChange={(e) => set("salario_diario", e.target.value)} /></Field>
              <Field label="Salario mensual (MXN)"><input data-testid="emp-sal-mensual" type="number" step="0.01" className="input-field" value={form.salario_mensual} onChange={(e) => set("salario_mensual", e.target.value)} /></Field>
              <Field label="Sueldo integrado (MXN)"><input data-testid="emp-sal-integrado" type="number" step="0.01" className="input-field" value={form.sueldo_integrado} onChange={(e) => set("sueldo_integrado", e.target.value)} /></Field>
            </div>
          </Section>

          <Section title="Contacto de emergencia">
            <div className="grid md:grid-cols-2 gap-3">
              <Field label="Nombre"><input data-testid="emp-em-nombre" className="input-field" value={form.contacto_emergencia_nombre} onChange={(e) => set("contacto_emergencia_nombre", e.target.value)} /></Field>
              <Field label="Teléfono"><input data-testid="emp-em-tel" className="input-field" value={form.contacto_emergencia_tel} onChange={(e) => set("contacto_emergencia_tel", e.target.value)} /></Field>
            </div>
          </Section>

          {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono flex gap-1.5"><AlertCircle size={14} /> {err}</div>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
            <button disabled={busy} data-testid="emp-submit" className="btn-primary">{busy ? "Guardando…" : "Crear empleado"}</button>
          </div>
        </div>
      </form>
    </div>
  );
}

function EmpleadoModal({ eid, onClose }) {
  const [emp, setEmp] = useState(null);
  const [tab, setTab] = useState("datos");
  const [err, setErr] = useState("");

  const load = async () => {
    try { const { data } = await api.get(`/rh/empleados/${eid}`); setEmp(data); }
    catch (e) { setErr(formatApiError(e)); }
  };
  useEffect(() => { load(); }, [eid]);

  const downloadExpediente = async () => {
    const res = await api.get(`/rh/empleados/${eid}/expediente`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a"); a.href = url; a.download = `DEYMA_expediente_${emp.nombre.replace(/\s/g, "_")}.pdf`;
    document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
  };

  if (!emp) {
    return <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center"><div className="text-amber-400 font-mono text-xs animate-pulse">Cargando…</div></div>;
  }
  const p = emp.prestaciones || {};

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur z-50 flex items-start justify-center p-4 overflow-y-auto" onClick={onClose} data-testid="rh-detail-modal">
      <div className="bg-zinc-950 border border-white/10 max-w-5xl w-full my-6" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-white/10 p-5 flex items-start justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <div className="label-overline text-amber-400">EXP-{emp.id.slice(0, 8).toUpperCase()}</div>
            <h2 className="text-2xl font-black mt-1 truncate" style={{ fontFamily: "Chivo, sans-serif" }}>{emp.nombre}</h2>
            <div className="text-xs text-zinc-500 font-mono mt-1">{emp.puesto} · {emp.departamento} · {emp.status?.toUpperCase()} · Ingreso {emp.fecha_ingreso}</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={downloadExpediente} data-testid="rh-download-expediente" className="btn-primary flex items-center gap-1.5 text-xs"><Download size={14} /> Expediente PDF</button>
            <button onClick={onClose} data-testid="rh-detail-close" className="text-zinc-400 hover:text-rose-400 text-xl px-2">✕</button>
          </div>
        </div>

        <div className="flex border-b border-white/10 overflow-x-auto" data-testid="rh-tabs">
          <DTab id="datos" cur={tab} set={setTab} icon={Building2} label="Datos" />
          <DTab id="prestaciones" cur={tab} set={setTab} icon={Wallet} label={`Prestaciones · ${p.vacaciones_anuales_periodo_actual || 0} vac`} />
          <DTab id="vacaciones" cur={tab} set={setTab} icon={Calendar} label={`Vacaciones (${emp.vacaciones?.length || 0})`} />
          {TIPOS_DOC.map((t) => (
            <DTab key={t.key} id={`doc-${t.key}`} cur={tab} set={setTab} icon={t.icon} label={`${t.label.split("(")[0].trim()} (${emp.documentos?.filter((d) => d.tipo === t.key).length || 0})`} />
          ))}
        </div>

        <div className="p-5">
          {tab === "datos" && <DatosTab emp={emp} onChange={load} />}
          {tab === "prestaciones" && <PrestacionesTab emp={emp} />}
          {tab === "vacaciones" && <VacacionesTab eid={eid} vacaciones={emp.vacaciones || []} onChange={load} />}
          {tab.startsWith("doc-") && <DocsTab eid={eid} tipo={tab.slice(4)} docs={(emp.documentos || []).filter((d) => d.tipo === tab.slice(4))} onChange={load} />}
        </div>
      </div>
    </div>
  );
}

function DTab({ id, cur, set, icon: Icon, label }) {
  const active = cur === id;
  return (
    <button data-testid={`rh-tab-${id}`} onClick={() => set(id)} className={`flex items-center gap-1.5 px-3 py-2.5 text-[11px] label-overline border-b-2 whitespace-nowrap transition-colors ${active ? "border-amber-500 text-amber-400" : "border-transparent text-zinc-500 hover:text-zinc-100"}`}>
      <Icon size={12} /> {label}
    </button>
  );
}

function DatosTab({ emp, onChange }) {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState(emp);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setBusy(true); setErr("");
    try {
      const payload = { ...form };
      ["prestaciones", "documentos", "vacaciones", "created_at", "created_by", "id", "documentos_count"].forEach((k) => delete payload[k]);
      await api.patch(`/rh/empleados/${emp.id}`, payload);
      setEdit(false); onChange();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  const darBaja = async () => {
    if (!window.confirm(`¿Dar de baja a ${emp.nombre}?`)) return;
    const motivo = prompt("Motivo de la baja:") || "";
    await api.patch(`/rh/empleados/${emp.id}`, { status: "baja", motivo_baja: motivo });
    onChange();
  };

  if (!edit) {
    return (
      <div className="space-y-5">
        <div className="grid md:grid-cols-2 gap-3">
          <Mini k="RFC" v={emp.rfc} />
          <Mini k="CURP" v={emp.curp} />
          <Mini k="NSS" v={emp.nss} />
          <Mini k="Teléfono" v={emp.tel} />
          <Mini k="Correo" v={emp.correo} />
          <Mini k="Domicilio" v={emp.domicilio} />
          <Mini k="Salario diario" v={fmtMXN(emp.salario_diario)} />
          <Mini k="Salario mensual" v={fmtMXN(emp.salario_mensual)} />
          <Mini k="Sueldo integrado" v={fmtMXN(emp.sueldo_integrado)} />
          <Mini k="Contacto emergencia" v={`${emp.contacto_emergencia_nombre || "—"} · ${emp.contacto_emergencia_tel || ""}`} />
          {emp.motivo_baja && <Mini k="Motivo de baja" v={emp.motivo_baja} />}
        </div>
        <div className="flex gap-2 justify-end">
          {emp.status === "activo" && <button onClick={darBaja} data-testid="emp-baja-btn" className="btn-ghost text-xs border-rose-500/40 text-rose-300 hover:bg-rose-500/10 flex items-center gap-1.5"><XCircle size={14} /> Dar de baja</button>}
          <button onClick={() => setEdit(true)} data-testid="emp-edit-btn" className="btn-primary text-xs">Editar</button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-3">
        <Field label="Nombre"><input className="input-field" value={form.nombre || ""} onChange={(e) => set("nombre", e.target.value)} /></Field>
        <Field label="Puesto"><input className="input-field" value={form.puesto || ""} onChange={(e) => set("puesto", e.target.value)} /></Field>
        <Field label="RFC"><input className="input-field uppercase" value={form.rfc || ""} onChange={(e) => set("rfc", e.target.value.toUpperCase())} /></Field>
        <Field label="CURP"><input className="input-field uppercase" value={form.curp || ""} onChange={(e) => set("curp", e.target.value.toUpperCase())} /></Field>
        <Field label="NSS"><input className="input-field" value={form.nss || ""} onChange={(e) => set("nss", e.target.value)} /></Field>
        <Field label="Departamento"><select className="input-field" value={form.departamento || "Obra"} onChange={(e) => set("departamento", e.target.value)}>{DEPARTAMENTOS.map((d) => <option key={d}>{d}</option>)}</select></Field>
        <Field label="Tel"><input className="input-field" value={form.tel || ""} onChange={(e) => set("tel", e.target.value)} /></Field>
        <Field label="Correo"><input className="input-field" value={form.correo || ""} onChange={(e) => set("correo", e.target.value)} /></Field>
        <Field label="Domicilio" span={2}><input className="input-field" value={form.domicilio || ""} onChange={(e) => set("domicilio", e.target.value)} /></Field>
        <Field label="Salario diario"><input type="number" step="0.01" className="input-field" value={form.salario_diario || 0} onChange={(e) => set("salario_diario", +e.target.value)} /></Field>
        <Field label="Salario mensual"><input type="number" step="0.01" className="input-field" value={form.salario_mensual || 0} onChange={(e) => set("salario_mensual", +e.target.value)} /></Field>
        <Field label="Sueldo integrado"><input type="number" step="0.01" className="input-field" value={form.sueldo_integrado || 0} onChange={(e) => set("sueldo_integrado", +e.target.value)} /></Field>
      </div>
      {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono">{err}</div>}
      <div className="flex gap-2 justify-end">
        <button onClick={() => { setEdit(false); setForm(emp); }} className="btn-ghost text-xs">Cancelar</button>
        <button onClick={save} disabled={busy} data-testid="emp-save-btn" className="btn-primary text-xs">{busy ? "Guardando…" : "Guardar"}</button>
      </div>
    </div>
  );
}

function PrestacionesTab({ emp }) {
  const p = emp.prestaciones || {};
  return (
    <div className="space-y-5">
      <div className="grid md:grid-cols-3 gap-3">
        <Big k="Antigüedad" v={`${p.antiguedad_anios || 0} años`} sub={`${p.antiguedad_meses || 0} meses totales`} />
        <Big k="Vacaciones · periodo actual" v={`${p.vacaciones_anuales_periodo_actual || 0} días`} sub="Según LFT vigente (2023)" highlight />
        <Big k="Vacaciones · próximo periodo" v={`${p.vacaciones_proximo_periodo || 0} días`} sub={`A partir de ${p.proximo_aniversario || "—"}`} />
        <Big k="Vacaciones gozadas (acum.)" v={`${p.vacaciones_gozadas || 0} días`} sub="Registradas en este periodo" />
        <Big k="Vacaciones pendientes" v={`${p.vacaciones_pendientes || 0} días`} sub="Periodo actual" highlight />
        <Big k="Próximo aniversario" v={p.proximo_aniversario || "—"} sub={p.dias_para_aniversario != null ? `En ${p.dias_para_aniversario} días` : ""} />
        <Big k="Aguinaldo" v={`${p.aguinaldo_dias || 15} días`} sub="Mínimo LFT" />
        <Big k="Prima vacacional" v={`${p.prima_vacacional_pct || 25} %`} sub="Mínimo LFT" />
      </div>
      <div className="border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-amber-200">
        <b>Tabla LFT 2023 — días de vacaciones por antigüedad:</b>
        <div className="font-mono mt-2 grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1 text-[11px] text-zinc-300">
          <span>Año 1: 12 días</span><span>Año 2: 14 días</span><span>Año 3: 16 días</span><span>Año 4: 18 días</span>
          <span>Año 5: 20 días</span><span>Años 6-10: 22</span><span>Años 11-15: 24</span><span>Años 16-20: 26</span>
          <span>Años 21-25: 28</span><span>Años 26-30: 30</span><span>Año 31+: 32</span>
        </div>
      </div>
    </div>
  );
}

function VacacionesTab({ eid, vacaciones, onChange }) {
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ fecha_inicio: "", fecha_fin: "", dias: 0, estatus: "programadas", nota: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await api.post(`/rh/empleados/${eid}/vacaciones`, { ...form, dias: +form.dias });
      setShow(false); setForm({ fecha_inicio: "", fecha_fin: "", dias: 0, estatus: "programadas", nota: "" });
      onChange();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  const del = async (vid) => {
    if (!window.confirm("¿Eliminar este periodo vacacional?")) return;
    await api.delete(`/rh/empleados/${eid}/vacaciones/${vid}`);
    onChange();
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-xs text-zinc-400">Periodos vacacionales registrados</div>
        <button onClick={() => setShow(true)} data-testid="vac-add-btn" className="btn-ghost flex items-center gap-1.5 text-xs"><Plus size={14} /> Registrar periodo</button>
      </div>
      {vacaciones.length === 0 ? (
        <div className="border border-white/10 p-10 text-center text-sm text-zinc-500" data-testid="vac-empty">Sin periodos registrados.</div>
      ) : (
        <table className="w-full text-xs border border-white/10" data-testid="vac-table">
          <thead>
            <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
              <th className="p-3">Inicio</th><th className="p-3">Fin</th><th className="p-3 text-right">Días</th><th className="p-3">Estatus</th><th className="p-3">Nota</th><th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {vacaciones.map((v) => (
              <tr key={v.id} className="border-b border-white/5">
                <td className="p-3 font-mono">{v.fecha_inicio}</td>
                <td className="p-3 font-mono">{v.fecha_fin}</td>
                <td className="p-3 text-right font-mono font-bold text-amber-400">{v.dias}</td>
                <td className="p-3"><span className={`px-1.5 py-0.5 text-[10px] font-mono uppercase border ${v.estatus === "gozadas" ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10" : v.estatus === "canceladas" ? "border-rose-500/40 text-rose-400 bg-rose-500/10" : "border-amber-500/40 text-amber-400 bg-amber-500/10"}`}>{v.estatus}</span></td>
                <td className="p-3 text-zinc-300">{v.nota || "—"}</td>
                <td className="p-3 text-right"><button onClick={() => del(v.id)} className="text-rose-400 hover:text-rose-300"><Trash2 size={12} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {show && (
        <form onSubmit={submit} className="border border-amber-500/40 bg-amber-500/5 p-4 space-y-3" data-testid="vac-form">
          <div className="label-overline text-amber-400">Nuevo periodo vacacional</div>
          <div className="grid md:grid-cols-4 gap-3">
            <Field label="Fecha inicio" required><input data-testid="vac-inicio" required type="date" className="input-field" value={form.fecha_inicio} onChange={(e) => set("fecha_inicio", e.target.value)} /></Field>
            <Field label="Fecha fin" required><input data-testid="vac-fin" required type="date" className="input-field" value={form.fecha_fin} onChange={(e) => set("fecha_fin", e.target.value)} /></Field>
            <Field label="Días" required><input data-testid="vac-dias" required type="number" min="1" className="input-field" value={form.dias} onChange={(e) => set("dias", e.target.value)} /></Field>
            <Field label="Estatus">
              <select data-testid="vac-estatus" className="input-field" value={form.estatus} onChange={(e) => set("estatus", e.target.value)}>
                <option value="programadas">Programadas</option>
                <option value="gozadas">Gozadas</option>
                <option value="canceladas">Canceladas</option>
              </select>
            </Field>
          </div>
          <Field label="Nota"><input data-testid="vac-nota" className="input-field" value={form.nota} onChange={(e) => set("nota", e.target.value)} /></Field>
          {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono">{err}</div>}
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShow(false)} className="btn-ghost text-xs">Cancelar</button>
            <button disabled={busy} data-testid="vac-submit" className="btn-primary text-xs">{busy ? "Guardando…" : "Registrar"}</button>
          </div>
        </form>
      )}
    </div>
  );
}

function DocsTab({ eid, tipo, docs, onChange }) {
  const fileRef = useRef();
  const [file, setFile] = useState(null);
  const [descripcion, setDescripcion] = useState("");
  const [vigencia, setVigencia] = useState("");
  const [tema, setTema] = useState("");
  const [instructor, setInstructor] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const tipoMeta = TIPOS_DOC.find((t) => t.key === tipo);

  const submit = async (e) => {
    e.preventDefault();
    if (!file) return setErr("Selecciona un archivo");
    setBusy(true); setErr("");
    const fd = new FormData();
    fd.append("tipo", tipo);
    fd.append("descripcion", descripcion);
    if (vigencia) fd.append("vigencia", vigencia);
    if (tipo === "dc3") { fd.append("tema", tema); fd.append("instructor", instructor); }
    fd.append("archivo", file);
    try {
      await api.post(`/rh/empleados/${eid}/documentos`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setFile(null); setDescripcion(""); setVigencia(""); setTema(""); setInstructor("");
      if (fileRef.current) fileRef.current.value = "";
      onChange();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  const download = async (d) => {
    const res = await api.get(`/rh/empleados/${eid}/documentos/${d.id}`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a"); a.href = url; a.download = d.filename || "doc.pdf";
    document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
  };
  const del = async (d) => {
    if (!window.confirm(`¿Eliminar "${d.filename}"?`)) return;
    await api.delete(`/rh/empleados/${eid}/documentos/${d.id}`); onChange();
  };

  return (
    <div className="grid md:grid-cols-[360px_1fr] gap-5">
      <form onSubmit={submit} className="border border-white/10 bg-zinc-900 p-4 space-y-3" data-testid={`doc-form-${tipo}`}>
        <div className="label-overline text-amber-400">Subir nuevo · {tipoMeta?.label}</div>
        <Field label="Descripción"><input data-testid={`doc-desc-${tipo}`} className="input-field" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Ej. Contrato inicial 2024" /></Field>
        {(tipo === "cert_medico" || tipo === "dc3") && (
          <Field label="Vigencia (hasta)"><input data-testid={`doc-vig-${tipo}`} type="date" className="input-field" value={vigencia} onChange={(e) => setVigencia(e.target.value)} /></Field>
        )}
        {tipo === "dc3" && (
          <>
            <Field label="Tema del curso"><input data-testid="dc3-tema" className="input-field" value={tema} onChange={(e) => setTema(e.target.value)} placeholder="Ej. Trabajo en alturas" /></Field>
            <Field label="Instructor / Agente capacitador"><input data-testid="dc3-instructor" className="input-field" value={instructor} onChange={(e) => setInstructor(e.target.value)} /></Field>
          </>
        )}
        <Field label="Archivo PDF (máx 15 MB)">
          <input ref={fileRef} data-testid={`doc-file-${tipo}`} required type="file" accept=".pdf,image/*" className="block mt-1 text-xs text-zinc-400 file:mr-2 file:py-2 file:px-3 file:border file:border-amber-500/40 file:bg-amber-500/10 file:text-amber-400 file:font-bold file:label-overline file:cursor-pointer" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </Field>
        {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono">{err}</div>}
        <button disabled={busy} data-testid={`doc-submit-${tipo}`} className="btn-primary w-full flex items-center justify-center gap-1.5 text-xs"><Upload size={14} /> {busy ? "Subiendo…" : "Subir"}</button>
      </form>

      <div className="border border-white/10 bg-zinc-900">
        <div className="p-3 border-b border-white/10 label-overline text-amber-400">Archivos cargados ({docs.length})</div>
        {docs.length === 0 ? (
          <div className="p-10 text-center text-sm text-zinc-500" data-testid={`doc-empty-${tipo}`}>Sin documentos.</div>
        ) : (
          <ul className="divide-y divide-white/5">
            {docs.map((d) => (
              <li key={d.id} className="p-3 flex items-center gap-3 hover:bg-white/5" data-testid={`doc-row-${d.id}`}>
                <FileText size={14} className="text-amber-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold truncate">{d.filename}</div>
                  <div className="text-[10px] text-zinc-500 font-mono">
                    {d.descripcion && <>{d.descripcion} · </>}
                    {(d.size / 1024).toFixed(1)} KB · {new Date(d.uploaded_at).toLocaleDateString("es-MX")}
                    {d.vigencia && <> · vence {d.vigencia}</>}
                  </div>
                  {(d.tema || d.instructor) && (
                    <div className="text-[10px] text-amber-300/80 font-mono mt-0.5">
                      {d.tema && <>📘 {d.tema} </>}
                      {d.instructor && <> · 👨‍🏫 {d.instructor}</>}
                    </div>
                  )}
                </div>
                <button onClick={() => download(d)} data-testid={`doc-download-${d.id}`} className="text-amber-400 hover:text-amber-300 p-1.5"><Download size={12} /></button>
                <button onClick={() => del(d)} data-testid={`doc-delete-${d.id}`} className="text-rose-400 hover:text-rose-300 p-1.5"><Trash2 size={12} /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ---------- helpers ----------
const Field = ({ label, children, required, span }) => (
  <div className={span === 2 ? "md:col-span-2" : ""}>
    <label className="label-overline mb-1 block">{label}{required && <span className="text-amber-400"> *</span>}</label>
    {children}
  </div>
);
const Mini = ({ k, v }) => (
  <div className="border border-white/10 p-2.5"><div className="label-overline text-[10px]">{k}</div><div className="text-xs text-zinc-200 mt-0.5">{v || "—"}</div></div>
);
const Big = ({ k, v, sub, highlight }) => (
  <div className={`p-4 border ${highlight ? "border-amber-500/40 bg-amber-500/5" : "border-white/10 bg-zinc-900"}`}>
    <div className="label-overline text-[10px] text-zinc-400">{k}</div>
    <div className={`text-2xl font-black mt-1 font-mono ${highlight ? "text-amber-400" : "text-zinc-100"}`} style={{ fontFamily: "Chivo, sans-serif" }}>{v}</div>
    {sub && <div className="text-[10px] text-zinc-500 mt-1">{sub}</div>}
  </div>
);
const Section = ({ title, children }) => (
  <div className="space-y-2"><div className="label-overline text-amber-400">{title}</div>{children}</div>
);
