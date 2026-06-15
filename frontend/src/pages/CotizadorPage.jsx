import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, formatApiError, downloadPdf } from "../lib/auth";
import { EmptyState } from "../components/ui-deyma";
import { Modal } from "../components/ui-deyma";
import SeguimientoCotizacionModal from "../components/SeguimientoCotizacionModal";
import { Plus, Trash2, Download, Eye } from "lucide-react";

const ESTADO_BADGE = {
  borrador: "text-zinc-400 border-zinc-400/40",
  aprobada_direccion: "text-sky-400 border-sky-400/40",
  enviada: "text-sky-400 border-sky-400/40",
  aceptada: "text-emerald-400 border-emerald-400/40",
  rechazada: "text-rose-400 border-rose-400/40",
};
const ESTADO_LABEL_SHORT = {
  borrador: "BORRADOR",
  aprobada_direccion: "APROBADA · ENVIADA",
  enviada: "ENVIADA",
  aceptada: "ACEPTADA",
  rechazada: "RECHAZADA",
};

export default function CotizadorPage() {
  const [cots, setCots] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  const [open, setOpen] = useState(false);
  const [seguimientoId, setSeguimientoId] = useState(null);
  const [pdfCot, setPdfCot] = useState(null); // cot seleccionado para descargar PDF

  const load = async () => {
    const [c, e] = await Promise.all([api.get("/cotizaciones"), api.get("/empresas")]);
    setCots(c.data); setEmpresas(e.data);
  };
  useEffect(() => { load(); }, []);

  const empName = (id) => empresas.find((e) => e.id === id)?.nombre || "—";

  return (
    <div className="p-6 space-y-5" data-testid="cotizador-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Generación de propuestas comerciales</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Cotizador</h1>
        </div>
        <button data-testid="new-cot-btn" onClick={() => setOpen(true)} className="btn-primary flex items-center gap-2"><Plus size={14} strokeWidth={2}/> Nueva cotización</button>
      </div>

      {cots.length === 0 ? <EmptyState title="Sin cotizaciones" /> : (
        <div className="surface overflow-x-auto">
          <table className="dtable">
            <thead><tr><th>Folio</th><th>Cliente</th><th>Proyecto</th><th className="text-right">Subtotal</th><th className="text-right">IVA</th><th className="text-right">Total</th><th>Estado</th><th>Fecha</th><th></th></tr></thead>
            <tbody>
              {cots.map((c) => (
                <tr key={c.id} data-testid={`cot-row-${c.id}`}>
                  <td className="font-mono text-amber-400 font-semibold">{c.folio}</td>
                  <td>
                    {c.empresa_id ? empName(c.empresa_id) : (
                      <span className="flex items-center gap-1.5">
                        <span>{c.cliente_nombre || "—"}</span>
                        <span className="text-[9px] font-mono text-sky-400 border border-sky-400/40 px-1 py-0.5">MANUAL</span>
                      </span>
                    )}
                  </td>
                  <td className="text-xs">{c.proyecto_titulo}</td>
                  <td className="font-mono text-right">{fmtMXN(c.subtotal)}</td>
                  <td className="font-mono text-right text-xs text-zinc-500">{fmtMXN(c.iva_monto)}</td>
                  <td className="font-mono text-right font-semibold text-amber-400">{fmtMXN(c.total)}</td>
                  <td><span className={`badge ${ESTADO_BADGE[c.estado]}`}>{ESTADO_LABEL_SHORT[c.estado] || c.estado.toUpperCase()}</span></td>
                  <td className="font-mono text-xs text-zinc-500">{new Date(c.created_at).toLocaleDateString("es-MX")}</td>
                  <td className="flex items-center gap-2">
                    <button data-testid={`seguimiento-cot-${c.id}`} onClick={() => setSeguimientoId(c.id)} className="text-amber-400 hover:text-amber-300" title="Panel de Seguimiento"><Eye size={14}/></button>
                    <button data-testid={`download-cot-${c.id}`} onClick={() => setPdfCot(c)} className="text-sky-400 hover:text-sky-300" title="Descargar PDF"><Download size={14}/></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NewCotModal open={open} onClose={() => setOpen(false)} empresas={empresas} onSaved={() => { setOpen(false); load(); }} />

      <DescargarMembreteModal cot={pdfCot} onClose={() => setPdfCot(null)} />

      <SeguimientoCotizacionModal
        open={!!seguimientoId}
        cotizacionId={seguimientoId}
        onClose={() => setSeguimientoId(null)}
        onChanged={load}
      />
    </div>
  );
}

function DescargarMembreteModal({ cot, onClose }) {
  const [busy, setBusy] = useState(false);
  if (!cot) return null;
  const descargar = async (marca) => {
    setBusy(true);
    try {
      const suffix = marca === "deyma" ? "DEYMA" : "FRECCIAMD";
      await downloadPdf(`/cotizaciones/${cot.id}/pdf?marca=${marca}`, `cotizacion_${suffix}_${cot.folio}.pdf`);
      onClose();
    } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur flex items-center justify-center p-4" onClick={onClose} data-testid="membrete-modal">
      <div className="bg-zinc-950 border border-white/10 max-w-lg w-full p-6 space-y-5" onClick={(e) => e.stopPropagation()}>
        <div>
          <div className="label-overline text-amber-400">Seleccionar membrete · {cot.folio}</div>
          <h2 className="text-2xl font-black mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>¿Con qué logo descargar?</h2>
          <p className="text-xs text-zinc-400 mt-2">El membrete cambia el logo, la razón social y el footer del PDF.</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button
            data-testid="membrete-deyma"
            disabled={busy}
            onClick={() => descargar("deyma")}
            className="border-2 border-white/10 hover:border-amber-500 bg-zinc-900 p-5 transition-all flex flex-col items-center gap-3 text-center group disabled:opacity-50"
          >
            <div className="w-14 h-14 bg-amber-500/20 border border-amber-500/40 flex items-center justify-center group-hover:bg-amber-500/30">
              <span className="text-2xl">🦺</span>
            </div>
            <div>
              <div className="font-bold text-amber-400 text-lg" style={{ fontFamily: "Chivo, sans-serif" }}>DEYMA</div>
              <div className="text-[10px] text-zinc-500 font-mono mt-1">DESARROLLO Y MANTENIMIENTO</div>
              <div className="text-[10px] text-zinc-500 font-mono">DEYMA CONSTRUCCIONES S.A. DE C.V.</div>
            </div>
          </button>

          <button
            data-testid="membrete-frecciamd"
            disabled={busy}
            onClick={() => descargar("frecciamd")}
            className="border-2 border-white/10 hover:border-sky-500 bg-zinc-900 p-5 transition-all flex flex-col items-center gap-3 text-center group disabled:opacity-50"
          >
            <div className="w-14 h-14 bg-sky-500/20 border border-sky-500/40 flex items-center justify-center group-hover:bg-sky-500/30">
              <span className="text-2xl">🧭</span>
            </div>
            <div>
              <div className="font-bold text-sky-400 text-lg" style={{ fontFamily: "Chivo, sans-serif" }}>FRECCIAMD</div>
              <div className="text-[10px] text-zinc-500 font-mono mt-1">FRECCIA · CONSTRUCCIÓN INDUSTRIAL</div>
              <div className="text-[10px] text-zinc-500 font-mono">FRECCIA MD S.A. DE C.V.</div>
            </div>
          </button>
        </div>

        <button onClick={onClose} disabled={busy} data-testid="membrete-cancel" className="btn-ghost w-full text-xs">Cancelar</button>
      </div>
    </div>
  );
}

function Row({ k, v, big }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className={`label-overline ${big ? "text-amber-400" : ""}`}>{k}</span>
      <span className={`font-mono ${big ? "text-amber-400 text-xl" : ""}`}>{v}</span>
    </div>
  );
}

const UNIDADES_COMUNES = [
  "m²", "m³", "ml", "m", "km", "cm", "mm",
  "kg", "ton", "g",
  "l", "ml(volumen)",
  "pza", "lote", "global",
  "hr", "día", "jornal", "turno", "viaje", "servicio",
  "saco", "tarima", "costal", "rollo", "bote", "tambo", "caja",
];

function NewCotModal({ open, onClose, empresas, onSaved }) {
  const blankItem = { descripcion: "", cantidad: 100, unidad: "m²", precio_unitario: 500 };
  const [modoCliente, setModoCliente] = useState("crm"); // "crm" | "manual"
  const [empresa_id, setEmpresaId] = useState("");
  // Manual
  const [clienteNombre, setClienteNombre] = useState("");
  const [clienteRfc, setClienteRfc] = useState("");
  const [clienteCiudad, setClienteCiudad] = useState("");
  const [clienteAtencion, setClienteAtencion] = useState("");
  const [clienteEmail, setClienteEmail] = useState("");
  const [clienteTelefono, setClienteTelefono] = useState("");
  const [proyecto, setProyecto] = useState("");
  const [iva, setIva] = useState(16);
  const [validez, setValidez] = useState(15);
  const [notas, setNotas] = useState("");
  const [items, setItems] = useState([{ ...blankItem }]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) {
      setItems([{ ...blankItem }]);
      setModoCliente("crm");
      setEmpresaId("");
      setClienteNombre(""); setClienteRfc(""); setClienteCiudad("");
      setClienteAtencion(""); setClienteEmail(""); setClienteTelefono("");
      setProyecto(""); setNotas(""); setErr("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const totals = useMemo(() => {
    const subtotal = items.reduce((s, it) => s + (Number(it.cantidad) || 0) * (Number(it.precio_unitario) || 0), 0);
    const ivaMonto = subtotal * (Number(iva) || 0) / 100;
    return { subtotal, ivaMonto, total: subtotal + ivaMonto };
  }, [items, iva]);

  const updateItem = (i, key, val) => {
    setItems(items.map((it, idx) => idx === i ? { ...it, [key]: val } : it));
  };

  const submit = async (e) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const payload = {
        proyecto_titulo: proyecto,
        iva_pct: Number(iva),
        validez_dias: Number(validez),
        notas,
        items: items.map((it) => ({
          descripcion: it.descripcion,
          cantidad: Number(it.cantidad),
          unidad: it.unidad,
          precio_unitario: Number(it.precio_unitario),
        })),
      };
      if (modoCliente === "crm") {
        if (!empresa_id) throw new Error("Selecciona una empresa del CRM");
        payload.empresa_id = empresa_id;
      } else {
        if (!clienteNombre.trim()) throw new Error("Captura el nombre del cliente manual");
        payload.cliente_nombre = clienteNombre.trim();
        payload.cliente_rfc = clienteRfc.trim() || null;
        payload.cliente_ciudad = clienteCiudad.trim() || null;
        payload.cliente_atencion = clienteAtencion.trim() || null;
        payload.cliente_email = clienteEmail.trim() || null;
        payload.cliente_telefono = clienteTelefono.trim() || null;
      }
      await api.post("/cotizaciones", payload);
      onSaved();
    } catch (e) { setErr(e?.message || formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Nueva cotización" size="xl" testId="new-cot-modal">
      <form onSubmit={submit} className="space-y-4" data-testid="new-cot-form">
        {/* Selector de modo Cliente */}
        <div>
          <label className="label-overline">Cliente</label>
          <div className="grid grid-cols-2 gap-2 mt-1" data-testid="cot-modo-cliente">
            <button
              type="button"
              data-testid="cot-modo-crm"
              onClick={() => setModoCliente("crm")}
              className={`p-2.5 border text-xs label-overline flex items-center justify-center gap-2 ${modoCliente === "crm" ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}
            >
              📇 Cliente del CRM
            </button>
            <button
              type="button"
              data-testid="cot-modo-manual"
              onClick={() => setModoCliente("manual")}
              className={`p-2.5 border text-xs label-overline flex items-center justify-center gap-2 ${modoCliente === "manual" ? "border-sky-500 bg-sky-500/10 text-sky-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}
            >
              ✍️ Cliente manual / nuevo
            </button>
          </div>
        </div>

        {modoCliente === "crm" ? (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-overline">Empresa (CRM)</label>
              <select data-testid="cot-empresa-select" className="input-field" value={empresa_id} onChange={(e) => setEmpresaId(e.target.value)}>
                <option value="">Selecciona…</option>
                {empresas.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="label-overline">Proyecto / Obra</label>
              <input data-testid="cot-proyecto-input" required className="input-field" value={proyecto} onChange={(e) => setProyecto(e.target.value)} />
            </div>
          </div>
        ) : (
          <div className="border border-sky-500/30 bg-sky-500/5 p-3 space-y-3" data-testid="cot-manual-block">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-overline">Razón social / Nombre <span className="text-rose-400">*</span></label>
                <input data-testid="cot-cliente-nombre" required className="input-field" value={clienteNombre} onChange={(e) => setClienteNombre(e.target.value)} placeholder="Ej. Industrias ACME S.A. de C.V." />
              </div>
              <div>
                <label className="label-overline">Proyecto / Obra <span className="text-rose-400">*</span></label>
                <input data-testid="cot-proyecto-input" required className="input-field" value={proyecto} onChange={(e) => setProyecto(e.target.value)} />
              </div>
              <div>
                <label className="label-overline">RFC (opcional)</label>
                <input data-testid="cot-cliente-rfc" className="input-field font-mono uppercase" value={clienteRfc} onChange={(e) => setClienteRfc(e.target.value.toUpperCase())} placeholder="XAXX010101000" maxLength={13} />
              </div>
              <div>
                <label className="label-overline">Ciudad, Estado (opcional)</label>
                <input data-testid="cot-cliente-ciudad" className="input-field" value={clienteCiudad} onChange={(e) => setClienteCiudad(e.target.value)} placeholder="Querétaro, Qro" />
              </div>
              <div>
                <label className="label-overline">Atención a (opcional)</label>
                <input data-testid="cot-cliente-atencion" className="input-field" value={clienteAtencion} onChange={(e) => setClienteAtencion(e.target.value)} placeholder="Ing. Juan Pérez" />
              </div>
              <div>
                <label className="label-overline">Teléfono (opcional)</label>
                <input data-testid="cot-cliente-tel" className="input-field font-mono" value={clienteTelefono} onChange={(e) => setClienteTelefono(e.target.value)} placeholder="442-123-4567" />
              </div>
              <div className="col-span-2">
                <label className="label-overline">Correo (opcional)</label>
                <input data-testid="cot-cliente-email" type="email" className="input-field" value={clienteEmail} onChange={(e) => setClienteEmail(e.target.value)} placeholder="compras@cliente.com" />
              </div>
            </div>
            <div className="text-[10px] font-mono text-zinc-500">
              💡 Este cliente NO se guarda en el CRM. Si quieres que aparezca en futuros cotizadores, regístralo en /admin/crm primero.
            </div>
          </div>
        )}

        <datalist id="unidades-comunes-list">
          {UNIDADES_COMUNES.map((u) => <option key={u} value={u} />)}
        </datalist>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="label-overline">Conceptos</span>
            <button type="button" data-testid="cot-add-item-btn" onClick={() => setItems([...items, { ...blankItem }])} className="btn-ghost text-[10px]"><Plus size={11} className="inline" /> Agregar</button>
          </div>
          <div className="surface p-2 space-y-2">
            <div className="grid grid-cols-12 gap-2 text-[9px] label-overline text-zinc-500 px-1">
              <div className="col-span-5">Descripción</div>
              <div className="col-span-2">Cantidad</div>
              <div className="col-span-1">Unidad</div>
              <div className="col-span-2">P. Unit MXN</div>
              <div className="col-span-1 text-right">Importe</div>
              <div className="col-span-1"></div>
            </div>
            {items.map((it, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center" data-testid={`cot-item-row-${i}`}>
                <input className="input-field col-span-5" placeholder="Descripción" required value={it.descripcion} onChange={(e) => updateItem(i, "descripcion", e.target.value)} />
                <input type="number" step="0.01" className="input-field col-span-2 font-mono" placeholder="Cant." value={it.cantidad} onChange={(e) => updateItem(i, "cantidad", e.target.value)} />
                <input
                  data-testid={`cot-item-unidad-${i}`}
                  list="unidades-comunes-list"
                  className="input-field col-span-1 font-mono"
                  placeholder="ud."
                  value={it.unidad}
                  onChange={(e) => updateItem(i, "unidad", e.target.value)}
                  title="Escribe libremente o elige de la lista (m², km, kg, pza, lote, etc.)"
                />
                <input type="number" step="0.01" className="input-field col-span-2 font-mono" placeholder="P. unit." value={it.precio_unitario} onChange={(e) => updateItem(i, "precio_unitario", e.target.value)} />
                <div className="col-span-1 font-mono text-xs text-amber-400 text-right">{fmtMXN((Number(it.cantidad)||0) * (Number(it.precio_unitario)||0))}</div>
                <button type="button" className="col-span-1 text-rose-400 hover:text-rose-300" onClick={() => setItems(items.filter((_, idx) => idx !== i))}><Trash2 size={13}/></button>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline">IVA %</label>
            <input type="number" className="input-field font-mono" value={iva} onChange={(e) => setIva(e.target.value)} />
          </div>
          <div>
            <label className="label-overline">Validez (días)</label>
            <input type="number" className="input-field font-mono" value={validez} onChange={(e) => setValidez(e.target.value)} />
          </div>
          <div className="col-span-2">
            <label className="label-overline">Notas</label>
            <textarea className="input-field" style={{ height: 60 }} value={notas} onChange={(e) => setNotas(e.target.value)} />
          </div>
        </div>

        <div className="surface-elev p-3 font-mono text-sm space-y-1">
          <div className="flex justify-between"><span className="text-zinc-400">Subtotal</span><span data-testid="cot-subtotal">{fmtMXN(totals.subtotal)}</span></div>
          <div className="flex justify-between"><span className="text-zinc-400">IVA</span><span>{fmtMXN(totals.ivaMonto)}</span></div>
          <div className="flex justify-between text-amber-400 text-base"><span>TOTAL</span><span data-testid="cot-total">{fmtMXN(totals.total)}</span></div>
        </div>

        {err && <div className="text-rose-400 text-xs" data-testid="cot-error">{err}</div>}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="cot-submit-btn" disabled={busy} className="btn-primary">{busy ? "Guardando…" : "Generar cotización"}</button>
        </div>
      </form>
    </Modal>
  );
}
