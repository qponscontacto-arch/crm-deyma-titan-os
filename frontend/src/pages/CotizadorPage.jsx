import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, formatApiError, downloadPdf } from "../lib/auth";
import { Modal, EmptyState } from "../components/ui-deyma";
import SeguimientoCotizacionModal from "../components/SeguimientoCotizacionModal";
import { Plus, Trash2, FileText, Download, Eye } from "lucide-react";

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
            <thead><tr><th>Folio</th><th>Empresa</th><th>Proyecto</th><th className="text-right">Subtotal</th><th className="text-right">IVA</th><th className="text-right">Total</th><th>Estado</th><th>Fecha</th><th></th></tr></thead>
            <tbody>
              {cots.map((c) => (
                <tr key={c.id} data-testid={`cot-row-${c.id}`}>
                  <td className="font-mono text-amber-400 font-semibold">{c.folio}</td>
                  <td>{empName(c.empresa_id)}</td>
                  <td className="text-xs">{c.proyecto_titulo}</td>
                  <td className="font-mono text-right">{fmtMXN(c.subtotal)}</td>
                  <td className="font-mono text-right text-xs text-zinc-500">{fmtMXN(c.iva_monto)}</td>
                  <td className="font-mono text-right font-semibold text-amber-400">{fmtMXN(c.total)}</td>
                  <td><span className={`badge ${ESTADO_BADGE[c.estado]}`}>{ESTADO_LABEL_SHORT[c.estado] || c.estado.toUpperCase()}</span></td>
                  <td className="font-mono text-xs text-zinc-500">{new Date(c.created_at).toLocaleDateString("es-MX")}</td>
                  <td className="flex items-center gap-2">
                    <button data-testid={`seguimiento-cot-${c.id}`} onClick={() => setSeguimientoId(c.id)} className="text-amber-400 hover:text-amber-300" title="Panel de Seguimiento"><Eye size={14}/></button>
                    <button data-testid={`download-cot-${c.id}`} onClick={() => downloadPdf(`/cotizaciones/${c.id}/pdf`, `cotizacion_${c.folio}.pdf`)} className="text-sky-400 hover:text-sky-300" title="Descargar PDF"><Download size={14}/></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NewCotModal open={open} onClose={() => setOpen(false)} empresas={empresas} onSaved={() => { setOpen(false); load(); }} />

      <SeguimientoCotizacionModal
        open={!!seguimientoId}
        cotizacionId={seguimientoId}
        onClose={() => setSeguimientoId(null)}
        onChanged={load}
      />
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

function NewCotModal({ open, onClose, empresas, onSaved }) {
  const blankItem = { descripcion: "", cantidad: 100, unidad: "m2", precio_unitario: 500 };
  const [empresa_id, setEmpresaId] = useState("");
  const [proyecto, setProyecto] = useState("");
  const [iva, setIva] = useState(16);
  const [validez, setValidez] = useState(15);
  const [notas, setNotas] = useState("");
  const [items, setItems] = useState([{ ...blankItem }]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) { setItems([{ ...blankItem }]); setEmpresaId(""); setProyecto(""); setNotas(""); setErr(""); }
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
      await api.post("/cotizaciones", {
        empresa_id, proyecto_titulo: proyecto, iva_pct: Number(iva), validez_dias: Number(validez), notas,
        items: items.map((it) => ({ ...it, cantidad: Number(it.cantidad), precio_unitario: Number(it.precio_unitario) })),
      });
      onSaved();
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  return (
    <Modal open={open} onClose={onClose} title="Nueva cotización" size="xl" testId="new-cot-modal">
      <form onSubmit={submit} className="space-y-4" data-testid="new-cot-form">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label-overline">Empresa</label>
            <select required data-testid="cot-empresa-select" className="input-field" value={empresa_id} onChange={(e) => setEmpresaId(e.target.value)}>
              <option value="">Selecciona…</option>
              {empresas.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="label-overline">Proyecto / Obra</label>
            <input data-testid="cot-proyecto-input" required className="input-field" value={proyecto} onChange={(e) => setProyecto(e.target.value)} />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="label-overline">Conceptos</span>
            <button type="button" data-testid="cot-add-item-btn" onClick={() => setItems([...items, { ...blankItem }])} className="btn-ghost text-[10px]"><Plus size={11} className="inline" /> Agregar</button>
          </div>
          <div className="surface p-2 space-y-2">
            {items.map((it, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center" data-testid={`cot-item-row-${i}`}>
                <input className="input-field col-span-5" placeholder="Descripción" required value={it.descripcion} onChange={(e) => updateItem(i, "descripcion", e.target.value)} />
                <input type="number" step="0.01" className="input-field col-span-2 font-mono" placeholder="Cant." value={it.cantidad} onChange={(e) => updateItem(i, "cantidad", e.target.value)} />
                <select className="input-field col-span-1" value={it.unidad} onChange={(e) => updateItem(i, "unidad", e.target.value)}>
                  <option value="m2">m²</option><option value="m3">m³</option><option value="ml">ml</option><option value="pza">pza</option>
                </select>
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

        {err && <div className="text-rose-400 text-xs">{err}</div>}

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancelar</button>
          <button type="submit" data-testid="cot-submit-btn" disabled={busy} className="btn-primary">{busy ? "Guardando…" : "Generar cotización"}</button>
        </div>
      </form>
    </Modal>
  );
}
