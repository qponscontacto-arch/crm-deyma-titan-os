import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, SECTOR_LABEL } from "../lib/auth";
import { Hotness, ScoreBar } from "../components/ui-deyma";
import { Sparkles, ExternalLink, Filter, Radar as RadarIcon } from "lucide-react";

const SOURCE_LABEL = { licitacion: "Licitación", noticia: "Noticia", referencia: "Referencia", prospeccion: "Prospección" };

export default function RadarPage() {
  const [items, setItems] = useState([]);
  const [sector, setSector] = useState("todos");
  const [scoring, setScoring] = useState(null);

  const load = async () => { const { data } = await api.get("/radar"); setItems(data); };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    const list = sector === "todos" ? items : items.filter((p) => p.sector === sector);
    return [...list].sort((a, b) => (b.score || 0) - (a.score || 0));
  }, [items, sector]);

  const scoreOne = async (id) => {
    setScoring(id);
    try { await api.post(`/radar/${id}/score`); await load(); }
    finally { setScoring(null); }
  };

  const scoreAll = async () => {
    for (const p of items) { if (!p.score) await api.post(`/radar/${p.id}/score`); }
    await load();
  };

  return (
    <div className="p-6 space-y-5" data-testid="radar-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Inteligencia de Mercado · Bajío</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Radar de Proyectos</h1>
        </div>
        <button data-testid="score-all-btn" onClick={scoreAll} className="btn-primary flex items-center gap-2"><Sparkles size={14} strokeWidth={2}/> Calificar pendientes</button>
      </div>

      <div className="surface p-3 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-zinc-500" strokeWidth={1.5}/>
        <span className="label-overline">Filtros</span>
        <select data-testid="radar-sector-filter" className="input-field max-w-xs" value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="todos">Todos los sectores</option>
          {Object.entries(SECTOR_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="ml-auto font-mono text-xs text-zinc-500">{filtered.length} proyectos detectados</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((p) => (
          <div key={p.id} className="surface flex flex-col" data-testid={`radar-card-${p.id}`}>
            <div className="relative h-32 overflow-hidden border-b border-white/10">
              <img src={p.score >= 75 ? "https://images.unsplash.com/photo-1623428454599-0b106ed85f67" : "https://images.pexels.com/photos/25461690/pexels-photo-25461690.jpeg"}
                   alt={p.titulo} className="absolute inset-0 w-full h-full object-cover opacity-40" />
              <div className="absolute inset-0 bg-gradient-to-t from-black via-black/30 to-transparent" />
              <div className="absolute top-3 left-3 flex items-center gap-2">
                <Hotness value={p.hotness} />
                <span className="badge text-zinc-300 border-zinc-400/40">{SOURCE_LABEL[p.fuente] || p.fuente}</span>
              </div>
              <div className="absolute bottom-2 right-3 font-mono text-xs text-amber-400">{p.ciudad}, {p.estado}</div>
            </div>
            <div className="p-4 flex-1 flex flex-col gap-3">
              <h3 className="text-sm font-bold leading-tight">{p.titulo}</h3>
              <div className="label-overline text-zinc-400">{SECTOR_LABEL[p.sector]}</div>
              <p className="text-xs text-zinc-400 line-clamp-3">{p.descripcion}</p>
              <div className="mt-auto space-y-2">
                <div className="flex items-baseline justify-between">
                  <span className="label-overline">Monto estimado</span>
                  <span className="font-mono text-amber-400 text-base">{fmtMXN(p.monto_estimado)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="label-overline">AI Score</span>
                  <ScoreBar value={p.score || 0} />
                </div>
                {p.score_reasons?.length > 0 && (
                  <ul className="space-y-1 text-[11px] text-zinc-400 pt-1">
                    {p.score_reasons.slice(0, 3).map((r, i) => <li key={i} className="terminal-line">{r}</li>)}
                  </ul>
                )}
                <div className="flex items-center gap-2 pt-2">
                  <button data-testid={`radar-score-btn-${p.id}`} onClick={() => scoreOne(p.id)} disabled={scoring === p.id} className="btn-ghost text-[10px] flex items-center gap-1">
                    <Sparkles size={11} strokeWidth={2}/> {scoring === p.id ? "Calificando…" : "Calificar IA"}
                  </button>
                  {p.url_fuente && <a href={`https://${p.url_fuente.replace(/^https?:\/\//, "")}`} target="_blank" rel="noreferrer" className="text-[10px] text-sky-400 hover:text-sky-300 flex items-center gap-1"><ExternalLink size={10}/>{p.url_fuente}</a>}
                </div>
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="col-span-full surface p-12 text-center">
            <RadarIcon size={40} strokeWidth={1} className="mx-auto text-zinc-700 mb-3"/>
            <div className="text-zinc-400">Sin proyectos para este filtro</div>
          </div>
        )}
      </div>
    </div>
  );
}
