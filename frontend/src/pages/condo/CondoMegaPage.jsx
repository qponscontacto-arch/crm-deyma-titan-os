import React, { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/auth";
import {
  Building2, MessageCircle, Trash2, Phone, Mail, ExternalLink,
  Loader2, CheckCircle2, AlertOctagon, ArrowUpRight, Crown,
} from "lucide-react";

const URG_COLOR = { alto: "rose", medio: "amber", bajo: "emerald" };

export default function CondoMegaPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/condo/leads?mega=1");
      setItems(data);
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const promover = async (l) => {
    if (!window.confirm(`Promover "${l.condominio_nombre}" al CRM?`)) return;
    try {
      await api.post(`/condo/leads/${l.id}/promover-crm`);
      setNotice({ kind: "ok", msg: `✓ ${l.condominio_nombre} promovido al CRM` });
      load();
    } catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  const eliminar = async (l) => {
    if (!window.confirm(`¿Eliminar "${l.condominio_nombre}"?`)) return;
    try { await api.delete(`/condo/leads/${l.id}`); load(); }
    catch (e) { setNotice({ kind: "err", msg: formatApiError(e) }); }
  };

  const waManual = (l) => {
    const tel = (l.telefono || "").replace(/\D/g, "");
    if (!tel) { setNotice({ kind: "err", msg: "Sin teléfono" }); return; }
    const msg = `Hola, le saluda DEYMA. Detectamos que administra ${l.condominio_nombre} (uno de los mega-condominios del Bajío). Tenemos paquetes empresariales de mantenimiento ideales para 200+ casas. ¿Le mando propuesta?`;
    window.open(`https://wa.me/52${tel}?text=${encodeURIComponent(msg)}`, "_blank");
  };

  return (
    <div className="p-6 max-w-[1500px] mx-auto space-y-4" data-testid="condo-mega-page">
      <header>
        <div className="label-overline text-[10px] text-amber-400 flex items-center gap-2">
          <Crown size={11}/> V6.0 · Radar de Condominios · Tier Premium
        </div>
        <h1 className="text-3xl font-black tracking-tight mt-1" style={{ fontFamily: "Chivo, sans-serif" }}>
          Mega-Condominios <span className="text-amber-400">·</span> +200 casas
        </h1>
        <div className="text-xs text-zinc-500 font-mono mt-1">
          GPT-5.2 estima tamaño automáticamente · Filtro alto valor
        </div>
      </header>

      {notice && (
        <div className={`surface p-3 border-l-4 ${notice.kind === "ok" ? "border-emerald-500 bg-emerald-500/5"
                                                   : "border-rose-500 bg-rose-500/5"}`} data-testid="mega-notice">
          <div className="flex items-start justify-between gap-2">
            <div className={`text-sm ${notice.kind === "ok" ? "text-emerald-400" : "text-rose-400"}`}>
              {notice.kind === "ok" ? <CheckCircle2 size={14} className="inline mr-2"/> : <AlertOctagon size={14} className="inline mr-2"/>}
              {notice.msg}
            </div>
            <button onClick={() => setNotice(null)} className="text-zinc-500 hover:text-zinc-300">✕</button>
          </div>
        </div>
      )}

      <div className="text-xs text-zinc-400 font-mono">
        <span className="text-amber-400 font-bold">{items.length}</span> mega-condominios detectados
      </div>

      {loading ? (
        <div className="surface p-8 text-center text-zinc-500">
          <Loader2 size={16} className="inline animate-spin mr-2"/> Cargando…
        </div>
      ) : items.length === 0 ? (
        <div className="surface p-12 text-center text-zinc-500 text-sm">
          Aún no se han detectado mega-condominios (+200 casas). Ve a <strong>Caza-Leads</strong> y ejecuta el Sabueso, o marca manualmente alguno como Mega editando &quot;casas estimadas&quot;.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((l) => {
            const ucol = URG_COLOR[l.urgencia] || "zinc";
            return (
              <div key={l.id} className="surface p-5 border border-amber-500/30" data-testid={`mega-${l.id}`}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Building2 size={16} className="text-amber-400"/>
                      <h3 className="text-lg font-bold">{l.condominio_nombre}</h3>
                    </div>
                    <div className="text-xs text-zinc-400">{l.ubicacion}</div>
                  </div>
                  <span className="text-amber-400 font-mono text-2xl font-black">~{l.num_casas_estimado}</span>
                </div>

                <div className="flex items-center gap-2 mb-3 flex-wrap text-[10px] font-mono">
                  <span className={`uppercase bg-${ucol}-500/10 text-${ucol}-400 border border-${ucol}-500/30 px-1.5 py-0.5`}>
                    {l.urgencia}
                  </span>
                  <span className="text-rose-400 font-bold bg-rose-500/10 border border-rose-500/30 px-1.5 py-0.5 uppercase">
                    <Crown size={9} className="inline mr-1"/>Mega
                  </span>
                  <span className="text-zinc-400">{l.estado}</span>
                </div>

                {l.contacto_nombre && (
                  <div className="text-xs mb-2">
                    <strong>{l.contacto_nombre}</strong> <span className="text-zinc-500">· {l.contacto_puesto}</span>
                  </div>
                )}
                <div className="text-[11px] font-mono space-y-1 mb-3">
                  {l.telefono && <div className="text-sky-400"><Phone size={10} className="inline mr-1"/>{l.telefono}</div>}
                  {l.email && <div className="text-emerald-400"><Mail size={10} className="inline mr-1"/>{l.email}</div>}
                </div>

                {l.problema_principal && l.problema_principal !== "—" && (
                  <div className="text-xs text-zinc-300 italic mb-3 border-l-2 border-amber-500/40 pl-2">
                    &ldquo;{l.problema_principal}&rdquo;
                  </div>
                )}

                <div className="flex items-center gap-2 pt-3 border-t border-white/5">
                  <button onClick={() => waManual(l)} disabled={!l.telefono}
                          className="btn-ghost text-[10px] flex-1 disabled:opacity-30"
                          data-testid={`btn-mega-wa-${l.id}`}>
                    <MessageCircle size={11} className="inline mr-1"/>WhatsApp
                  </button>
                  <button onClick={() => promover(l)} className="btn-primary text-[10px] flex-1"
                          data-testid={`btn-mega-promover-${l.id}`}>
                    <ArrowUpRight size={11} className="inline mr-1"/>A CRM
                  </button>
                  <button onClick={() => eliminar(l)} className="text-rose-400 hover:text-rose-300" title="Eliminar">
                    <Trash2 size={12}/>
                  </button>
                </div>

                {l.source_url && (
                  <a href={l.source_url} target="_blank" rel="noreferrer"
                     className="text-[9px] text-sky-400/60 hover:underline mt-2 inline-block">
                    fuente <ExternalLink size={7} className="inline"/>
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
