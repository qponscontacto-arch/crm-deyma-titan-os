import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, api, fmtMXN, downloadPdf, formatApiError } from "../lib/auth";
import { Radar, LogOut, Upload, FileText, Download, CheckCircle2, AlertCircle, ClipboardList, FileCheck2, Building2 } from "lucide-react";

export default function ClientePortalPage() {
  const { cliente, logout } = useAuth();
  const nav = useNavigate();
  const [tab, setTab] = useState("inicio");
  const [ocs, setOcs] = useState([]);
  const [cots, setCots] = useState([]);
  const [pdfDownloaded, setPdfDownloaded] = useState(false);

  useEffect(() => {
    if (!cliente) return;
    api.get("/clientes-oc").then((r) => setOcs(r.data)).catch(() => {});
    api.get("/clientes/me/cotizaciones").then((r) => setCots(r.data)).catch(() => {});
    // Auto-descargar PDF Bienvenida la primera vez
    const key = `welcome_pdf_${cliente.dfnum}`;
    if (cliente.dfnum && !localStorage.getItem(key)) {
      downloadPdf(`/clientes/${cliente.id}/pdf-bienvenida`, `DEYMA_bienvenida_${cliente.dfnum}.pdf`)
        .then(() => { localStorage.setItem(key, "1"); setPdfDownloaded(true); })
        .catch(() => {});
    }
  }, [cliente]);

  const reloadOcs = () => api.get("/clientes-oc").then((r) => setOcs(r.data));

  const onLogout = () => { logout(); nav("/login"); };

  if (!cliente) return null;

  return (
    <div className="min-h-screen bg-black text-zinc-100">
      <header className="border-b border-white/10 bg-zinc-950 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-500 flex items-center justify-center"><Radar size={20} className="text-black" strokeWidth={2} /></div>
            <div>
              <div className="font-black tracking-tight text-base" style={{ fontFamily: "Chivo, sans-serif" }}>DEYMA · PORTAL CLIENTE</div>
              <div className="label-overline text-amber-400/80 text-[10px]">{cliente.dfnum}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden md:block">
              <div className="text-xs font-semibold truncate max-w-[280px]">{cliente.razon_social}</div>
              <div className="label-overline text-zinc-500">{cliente.rfc}</div>
            </div>
            <button onClick={onLogout} data-testid="cliente-logout" className="text-zinc-400 hover:text-rose-400 p-1.5 border border-white/10"><LogOut size={14} /></button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 pt-6">
        <div className="flex items-center gap-1 border-b border-white/10" data-testid="cliente-tabs">
          <TabBtn id="inicio" cur={tab} set={setTab} icon={Building2} label="Inicio" />
          <TabBtn id="ocs" cur={tab} set={setTab} icon={ClipboardList} label={`Órdenes de Compra (${ocs.length})`} />
          <TabBtn id="cots" cur={tab} set={setTab} icon={FileCheck2} label={`Mis cotizaciones (${cots.length})`} />
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-6 py-6">
        {tab === "inicio" && <InicioTab cliente={cliente} pdfDownloaded={pdfDownloaded} />}
        {tab === "ocs" && <OCsTab ocs={ocs} reload={reloadOcs} />}
        {tab === "cots" && <CotsTab cots={cots} />}
      </main>
    </div>
  );
}

function TabBtn({ id, cur, set, icon: Icon, label }) {
  const active = cur === id;
  return (
    <button
      data-testid={`tab-${id}`}
      onClick={() => set(id)}
      className={`flex items-center gap-2 px-4 py-2.5 text-xs label-overline border-b-2 transition-colors ${active ? "border-amber-500 text-amber-400" : "border-transparent text-zinc-500 hover:text-zinc-200"}`}
    >
      <Icon size={14} /> {label}
    </button>
  );
}

function InicioTab({ cliente, pdfDownloaded }) {
  return (
    <div className="space-y-6">
      <div className="border border-emerald-500/40 bg-emerald-500/5 p-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 bg-emerald-500 flex items-center justify-center shrink-0"><CheckCircle2 size={22} className="text-black" /></div>
          <div className="flex-1">
            <div className="label-overline text-emerald-400">Cliente aprobado · DEYMA</div>
            <h1 className="text-2xl font-black mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>Bienvenido, {cliente.razon_social}</h1>
            <p className="text-sm text-zinc-300 mt-2">
              Tu alta fue completada con éxito tras la doble aprobación de DEYMA. Ya puedes operar normalmente: subir tus órdenes de compra, consultar cotizaciones ligadas a tu RFC y dar seguimiento a proyectos.
            </p>
            {pdfDownloaded && <div className="text-xs text-emerald-300 mt-2 font-mono">✓ PDF de Bienvenida descargado automáticamente</div>}
            <button
              onClick={() => downloadPdf(`/clientes/${cliente.id}/pdf-bienvenida`, `DEYMA_bienvenida_${cliente.dfnum}.pdf`)}
              data-testid="download-bienvenida"
              className="btn-ghost mt-3 flex items-center gap-1.5 text-xs"
            ><Download size={14} /> Re-descargar PDF de Bienvenida</button>
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <DataCard title="Datos fiscales" rows={[
          ["Razón social", cliente.razon_social],
          ["RFC", cliente.rfc],
          ["Folio de registro", cliente.folio_registro],
          ["DFNUM", cliente.dfnum],
          ["Domicilio fiscal", cliente.domicilio_fiscal],
          ["Domicilio planta", cliente.domicilio_planta || "—"],
        ]} />
        <DataCard title="Contactos registrados" rows={[
          ["Técnico", `${cliente.contactos?.tecnico?.nombre} · ${cliente.contactos?.tecnico?.correo}`],
          ["Compras", `${cliente.contactos?.compras?.nombre} · ${cliente.contactos?.compras?.correo}`],
          ["Cuentas por pagar", `${cliente.contactos?.cuentas_por_pagar?.nombre} · ${cliente.contactos?.cuentas_por_pagar?.correo}`],
          ["Firma representante", cliente.firmas?.representante?.nombre],
          ["Firma técnica", cliente.firmas?.tecnico?.nombre],
        ]} />
      </div>
    </div>
  );
}

function DataCard({ title, rows }) {
  return (
    <div className="border border-white/10 bg-zinc-950 p-5">
      <div className="label-overline text-amber-400 mb-3">{title}</div>
      <dl className="space-y-2">
        {rows.map(([k, v], i) => (
          <div key={i} className="grid grid-cols-[140px_1fr] text-xs">
            <dt className="text-zinc-500">{k}</dt>
            <dd className="text-zinc-200">{v || "—"}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function OCsTab({ ocs, reload }) {
  const fileRef = useRef();
  const [referencia, setReferencia] = useState("");
  const [monto, setMonto] = useState("");
  const [notas, setNotas] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!file) { setErr("Selecciona el PDF de la OC"); return; }
    setBusy(true); setErr(""); setOk("");
    const fd = new FormData();
    fd.append("referencia", referencia);
    fd.append("monto", String(monto || 0));
    fd.append("notas", notas);
    fd.append("archivo", file);
    try {
      await api.post("/clientes-oc", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setOk("OC cargada correctamente");
      setReferencia(""); setMonto(""); setNotas(""); setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      await reload();
    } catch (e2) { setErr(formatApiError(e2)); }
    finally { setBusy(false); }
  };

  const download = async (oc) => {
    const res = await api.get(`/clientes-oc/${oc.id}/file`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url; a.download = oc.filename || "OC.pdf"; document.body.appendChild(a); a.click();
    a.remove(); window.URL.revokeObjectURL(url);
  };

  return (
    <div className="grid md:grid-cols-[400px_1fr] gap-6">
      <form onSubmit={submit} className="border border-white/10 bg-zinc-950 p-5 space-y-4" data-testid="oc-form">
        <div className="label-overline text-amber-400">Subir nueva Orden de Compra</div>
        <div>
          <label className="label-overline">Referencia / Número OC</label>
          <input data-testid="oc-referencia" required className="input-field mt-1" value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="OC-2026-001" />
        </div>
        <div>
          <label className="label-overline">Monto (MXN)</label>
          <input data-testid="oc-monto" type="number" min="0" step="any" className="input-field mt-1" value={monto} onChange={(e) => setMonto(e.target.value)} />
        </div>
        <div>
          <label className="label-overline">Notas</label>
          <textarea data-testid="oc-notas" rows={3} className="input-field mt-1" value={notas} onChange={(e) => setNotas(e.target.value)} />
        </div>
        <div>
          <label className="label-overline">Archivo PDF (máx 15 MB)</label>
          <input ref={fileRef} data-testid="oc-file" type="file" accept=".pdf" className="block mt-2 text-xs text-zinc-400 file:mr-3 file:py-2 file:px-3 file:border file:border-amber-500/40 file:bg-amber-500/10 file:text-amber-400 file:font-bold file:label-overline file:cursor-pointer" onChange={(e) => setFile(e.target.files?.[0] || null)} required />
        </div>
        {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono flex gap-1.5"><AlertCircle size={14} /> {err}</div>}
        {ok && <div className="border border-emerald-500/60 bg-emerald-500/10 text-emerald-300 text-xs p-2 font-mono flex gap-1.5"><CheckCircle2 size={14} /> {ok}</div>}
        <button disabled={busy} data-testid="oc-submit" className="btn-primary w-full flex items-center justify-center gap-1.5">
          <Upload size={14} /> {busy ? "Subiendo…" : "Subir OC"}
        </button>
      </form>

      <div className="border border-white/10 bg-zinc-950">
        <div className="p-4 border-b border-white/10 label-overline text-amber-400">Historial de Órdenes de Compra</div>
        {ocs.length === 0 ? (
          <div className="p-10 text-center text-sm text-zinc-500" data-testid="oc-empty">Aún no has subido ninguna OC.</div>
        ) : (
          <table className="w-full text-xs" data-testid="oc-table">
            <thead>
              <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
                <th className="p-3">Ref.</th><th className="p-3">Archivo</th><th className="p-3 text-right">Monto</th><th className="p-3">Fecha</th><th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {ocs.map((oc) => (
                <tr key={oc.id} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-3 font-mono">{oc.referencia}</td>
                  <td className="p-3 text-zinc-300 truncate max-w-[200px]"><FileText size={12} className="inline mr-1.5 opacity-60" />{oc.filename}</td>
                  <td className="p-3 text-right font-mono">{fmtMXN(oc.monto)}</td>
                  <td className="p-3 text-zinc-500 font-mono">{new Date(oc.uploaded_at).toLocaleDateString("es-MX")}</td>
                  <td className="p-3 text-right">
                    <button onClick={() => download(oc)} data-testid={`oc-download-${oc.id}`} className="text-amber-400 hover:text-amber-300 inline-flex items-center gap-1"><Download size={12} /> PDF</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function CotsTab({ cots }) {
  const [openId, setOpenId] = useState(null);
  const open = cots.find((c) => c.id === openId);

  return (
    <div className="border border-white/10 bg-zinc-950">
      <div className="p-4 border-b border-white/10 label-overline text-amber-400">Cotizaciones ligadas a tu RFC</div>
      {cots.length === 0 ? (
        <div className="p-10 text-center text-sm text-zinc-500" data-testid="cots-empty">Aún no hay cotizaciones asociadas a tu empresa.</div>
      ) : (
        <table className="w-full text-xs" data-testid="cots-table">
          <thead>
            <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
              <th className="p-3">Folio</th><th className="p-3">Proyecto</th><th className="p-3">Estado</th><th className="p-3 text-right">Total</th><th className="p-3">Fecha</th><th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {cots.map((c) => (
              <tr key={c.id} className="border-b border-white/5 hover:bg-white/5">
                <td className="p-3 font-mono">{c.folio}</td>
                <td className="p-3 text-zinc-200">{c.proyecto_titulo}</td>
                <td className="p-3"><StateBadge estado={c.estado} /></td>
                <td className="p-3 text-right font-mono">{fmtMXN(c.total)}</td>
                <td className="p-3 text-zinc-500 font-mono">{new Date(c.created_at).toLocaleDateString("es-MX")}</td>
                <td className="p-3 text-right">
                  <button onClick={() => downloadPdf(`/cotizaciones/${c.id}/pdf`, `${c.folio}.pdf`)} data-testid={`cot-pdf-${c.id}`} className="text-amber-400 hover:text-amber-300 inline-flex items-center gap-1"><Download size={12} /> PDF</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function StateBadge({ estado }) {
  const map = {
    borrador: "bg-zinc-700/30 text-zinc-300 border-zinc-600",
    aprobada_direccion: "bg-amber-500/10 text-amber-400 border-amber-500/40",
    aceptada: "bg-emerald-500/10 text-emerald-400 border-emerald-500/40",
    rechazada: "bg-rose-500/10 text-rose-400 border-rose-500/40",
  };
  return <span className={`inline-block px-2 py-0.5 text-[10px] font-mono uppercase border ${map[estado] || "border-white/10 text-zinc-400"}`}>{estado}</span>;
}
