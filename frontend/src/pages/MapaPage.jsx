import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, SECTOR_LABEL } from "../lib/auth";
import { Hotness } from "../components/ui-deyma";
import { Filter, MapPin } from "lucide-react";

// Bajío region bounding box (approx):
// lat 19.0 to 26.5, lng -103.5 to -99.0
const BBOX = { latMin: 19.0, latMax: 26.5, lngMin: -103.5, lngMax: -99.0 };

function projectPoint(lat, lng, w, h) {
  const x = ((lng - BBOX.lngMin) / (BBOX.lngMax - BBOX.lngMin)) * w;
  const y = h - ((lat - BBOX.latMin) / (BBOX.latMax - BBOX.latMin)) * h;
  return { x, y };
}

const CITIES = [
  { name: "Querétaro", lat: 20.5888, lng: -100.3899 },
  { name: "San Luis Potosí", lat: 22.1565, lng: -100.9855 },
  { name: "León", lat: 21.1250, lng: -101.6850 },
  { name: "Aguascalientes", lat: 21.8853, lng: -102.2916 },
  { name: "Celaya", lat: 20.5167, lng: -100.8167 },
  { name: "Monterrey", lat: 25.6866, lng: -100.3161 },
  { name: "Saltillo", lat: 25.4232, lng: -100.9966 },
  { name: "CDMX (Norte)", lat: 19.5050, lng: -99.0830 },
  { name: "Toluca", lat: 19.2833, lng: -99.6500 },
  { name: "Silao", lat: 20.9489, lng: -101.4291 },
];

export default function MapaPage() {
  const [points, setPoints] = useState([]);
  const [hover, setHover] = useState(null);
  const [sector, setSector] = useState("todos");
  const [tipo, setTipo] = useState("todos");

  useEffect(() => { api.get("/mapa/puntos").then((r) => setPoints(r.data.points || [])); }, []);

  const filtered = useMemo(() => points.filter((p) =>
    (sector === "todos" || p.sector === sector) &&
    (tipo === "todos" || p.tipo === tipo)
  ), [points, sector, tipo]);

  const W = 900, H = 600;

  const totalMonto = filtered.reduce((s, p) => s + (p.monto || 0), 0);
  const hot = filtered.filter((p) => p.hotness === "hot" || p.score >= 75).length;

  return (
    <div className="p-6 space-y-5" data-testid="mapa-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Geolocalización · Bajío · México Central</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Mapa de Oportunidades</h1>
        </div>
        <div className="flex gap-6 font-mono text-xs">
          <div><div className="label-overline">Puntos</div><div className="text-amber-400 text-lg">{filtered.length}</div></div>
          <div><div className="label-overline">Hot</div><div className="text-orange-400 text-lg">{hot}</div></div>
          <div><div className="label-overline">Monto total</div><div className="text-zinc-200 text-lg">{fmtMXN(totalMonto)}</div></div>
        </div>
      </div>

      <div className="surface p-3 flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-zinc-500" strokeWidth={1.5}/>
        <select data-testid="mapa-sector-filter" className="input-field max-w-xs" value={sector} onChange={(e) => setSector(e.target.value)}>
          <option value="todos">Todos los sectores</option>
          {Object.entries(SECTOR_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select data-testid="mapa-tipo-filter" className="input-field max-w-xs" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="todos">Todos los tipos</option>
          <option value="radar">Radar (proyectos detectados)</option>
          <option value="oportunidad">Oportunidades CRM</option>
        </select>
      </div>

      <div className="surface p-4 relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" style={{ background: "#0c0c0e" }}>
          {/* grid */}
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1"/>
            </pattern>
            <pattern id="grid-major" width="120" height="120" patternUnits="userSpaceOnUse">
              <path d="M 120 0 L 0 0 0 120" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1"/>
            </pattern>
            <radialGradient id="hotPulse">
              <stop offset="0%" stopColor="#f97316" stopOpacity="0.9"/>
              <stop offset="100%" stopColor="#f97316" stopOpacity="0"/>
            </radialGradient>
          </defs>
          <rect width={W} height={H} fill="url(#grid)" />
          <rect width={W} height={H} fill="url(#grid-major)" />

          {/* schematic land mass (approximate Mexico central region polygon for visual reference) */}
          <path
            d={schematicMexico(W, H)}
            fill="rgba(245, 158, 11, 0.04)"
            stroke="rgba(245, 158, 11, 0.25)"
            strokeWidth="1"
          />

          {/* cities labels */}
          {CITIES.map((c) => {
            const { x, y } = projectPoint(c.lat, c.lng, W, H);
            return (
              <g key={c.name}>
                <circle cx={x} cy={y} r="2" fill="rgba(255,255,255,0.3)"/>
                <text x={x + 6} y={y + 4} fill="rgba(255,255,255,0.4)" fontSize="9" fontFamily="IBM Plex Mono, monospace">{c.name}</text>
              </g>
            );
          })}

          {/* axis labels */}
          <text x="6" y="14" fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="IBM Plex Mono, monospace">DEYMA · BAJÍO RADAR · 19.0°N – 26.5°N</text>
          <text x="6" y={H - 6} fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="IBM Plex Mono, monospace">-103.5°W ◀ ▶ -99.0°W</text>

          {/* points */}
          {filtered.map((p) => {
            const { x, y } = projectPoint(p.lat, p.lng, W, H);
            const isHot = p.hotness === "hot" || (p.score || 0) >= 75;
            const color = isHot ? "#f97316" : p.score >= 50 ? "#fbbf24" : "#71717a";
            const r = Math.max(4, Math.min(14, Math.log10((p.monto || 1) / 100000) * 3));
            return (
              <g key={p.id} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }} data-testid={`map-point-${p.id}`}>
                {isHot && <circle cx={x} cy={y} r={r + 8} fill="url(#hotPulse)" opacity="0.5">
                  <animate attributeName="r" values={`${r+4};${r+14};${r+4}`} dur="2s" repeatCount="indefinite"/>
                </circle>}
                <rect x={x - r/2} y={y - r/2} width={r} height={r} fill={color} stroke="#000" strokeWidth="1" transform={`rotate(45 ${x} ${y})`}/>
              </g>
            );
          })}
        </svg>

        {hover && (
          <div className="absolute top-6 right-6 surface-elev p-3 max-w-xs pointer-events-none" data-testid="map-hover-card">
            <div className="flex items-center gap-2 mb-2">
              <Hotness value={hover.hotness} />
              <span className="label-overline text-zinc-400">{hover.tipo === "radar" ? "RADAR" : "CRM"}</span>
            </div>
            <h4 className="font-bold text-sm mb-1">{hover.titulo}</h4>
            <div className="label-overline mb-1">{SECTOR_LABEL[hover.sector]}</div>
            <div className="text-xs text-zinc-400 mb-2">{hover.ciudad}, {hover.estado}</div>
            <div className="font-mono text-amber-400 text-sm">{fmtMXN(hover.monto)}</div>
            <div className="text-[10px] text-zinc-500 mt-1">Score: {hover.score}/100</div>
          </div>
        )}

        <div className="mt-4 flex items-center gap-4 font-mono text-[10px] text-zinc-500">
          <span className="flex items-center gap-1"><span className="w-3 h-3 inline-block bg-orange-500 rotate-45"></span>HOT (≥75)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 inline-block bg-amber-400 rotate-45"></span>WARM (50-74)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 inline-block bg-zinc-500 rotate-45"></span>COLD (&lt;50)</span>
          <span className="ml-auto">▸ Tamaño = log(monto MXN). Pasa el cursor sobre los pines.</span>
        </div>
      </div>

      <div className="surface">
        <table className="dtable">
          <thead><tr><th>Tipo</th><th>Título</th><th>Sector</th><th>Ubicación</th><th className="text-right">Monto</th><th>Score</th></tr></thead>
          <tbody>
            {filtered.slice(0, 20).map((p) => (
              <tr key={p.id} data-testid={`map-table-row-${p.id}`}>
                <td><span className="badge text-zinc-400 border-zinc-400/40">{p.tipo === "radar" ? "RADAR" : "CRM"}</span></td>
                <td className="font-semibold">{p.titulo}</td>
                <td className="text-xs">{SECTOR_LABEL[p.sector]}</td>
                <td className="text-xs"><MapPin size={10} className="inline mr-1"/>{p.ciudad}, {p.estado}</td>
                <td className="font-mono text-right text-amber-400">{fmtMXN(p.monto)}</td>
                <td><Hotness value={p.hotness}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Schematic polygon roughly outlining Mexico's central plateau
function schematicMexico(W, H) {
  const pts = [
    [19.2, -99.1], [19.5, -99.6], [20.2, -100.0], [20.6, -100.4], [21.0, -101.0],
    [21.5, -101.5], [22.0, -102.0], [22.8, -102.3], [24.0, -101.5], [25.0, -100.8],
    [25.8, -100.4], [26.0, -99.8], [25.0, -99.5], [23.5, -99.7], [22.0, -99.5],
    [20.5, -99.3], [19.5, -99.2], [19.0, -99.1],
  ];
  return "M " + pts.map(([lat, lng]) => {
    const { x, y } = projectPoint(lat, lng, W, H);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" L ") + " Z";
}
