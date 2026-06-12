import React, { useEffect, useMemo, useState } from "react";
import { api, fmtMXN, SECTOR_LABEL } from "../lib/auth";
import { Hotness } from "../components/ui-deyma";
import { Filter, MapPin } from "lucide-react";

// Mexico bounding box (continental + Yucatán + Baja California Sur)
const BBOX = { latMin: 14.4, latMax: 32.8, lngMin: -118.5, lngMax: -86.5 };

function projectPoint(lat, lng, w, h) {
  const x = ((lng - BBOX.lngMin) / (BBOX.lngMax - BBOX.lngMin)) * w;
  const y = h - ((lat - BBOX.latMin) / (BBOX.latMax - BBOX.latMin)) * h;
  return { x, y };
}

// Major industrial cities across Mexico
const CITIES = [
  // Norte
  { name: "Tijuana", lat: 32.5149, lng: -117.0382 },
  { name: "Mexicali", lat: 32.6519, lng: -115.4683 },
  { name: "Hermosillo", lat: 29.0892, lng: -110.9613 },
  { name: "Cd. Juárez", lat: 31.7333, lng: -106.4859 },
  { name: "Chihuahua", lat: 28.6353, lng: -106.0889 },
  { name: "Monterrey", lat: 25.6866, lng: -100.3161 },
  { name: "Saltillo", lat: 25.4232, lng: -100.9966 },
  { name: "Torreón", lat: 25.5428, lng: -103.4068 },
  { name: "Reynosa", lat: 26.0922, lng: -98.2779 },
  { name: "Culiacán", lat: 24.8091, lng: -107.3940 },
  // Bajío
  { name: "Querétaro", lat: 20.5888, lng: -100.3899 },
  { name: "León", lat: 21.1250, lng: -101.6850 },
  { name: "Aguascalientes", lat: 21.8853, lng: -102.2916 },
  { name: "San Luis Potosí", lat: 22.1565, lng: -100.9855 },
  { name: "Celaya", lat: 20.5167, lng: -100.8167 },
  { name: "Silao", lat: 20.9489, lng: -101.4291 },
  // Occidente
  { name: "Guadalajara", lat: 20.6597, lng: -103.3496 },
  { name: "Manzanillo", lat: 19.1138, lng: -104.3370 },
  { name: "Morelia", lat: 19.7008, lng: -101.1844 },
  // Centro
  { name: "CDMX", lat: 19.4326, lng: -99.1332 },
  { name: "Toluca", lat: 19.2833, lng: -99.6500 },
  { name: "Puebla", lat: 19.0414, lng: -98.2063 },
  { name: "Cuernavaca", lat: 18.9215, lng: -99.2340 },
  // Sureste
  { name: "Veracruz", lat: 19.1738, lng: -96.1342 },
  { name: "Mérida", lat: 20.9674, lng: -89.5926 },
  { name: "Cancún", lat: 21.1619, lng: -86.8515 },
  { name: "Villahermosa", lat: 17.9892, lng: -92.9281 },
  { name: "Tuxtla", lat: 16.7530, lng: -93.1156 },
  { name: "Oaxaca", lat: 17.0732, lng: -96.7266 },
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

  const W = 1100, H = 640;

  const totalMonto = filtered.reduce((s, p) => s + (p.monto || 0), 0);
  const hot = filtered.filter((p) => p.hotness === "hot" || p.score >= 75).length;

  return (
    <div className="p-6 space-y-5" data-testid="mapa-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Geolocalización · República Mexicana</div>
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

          {/* schematic Mexico outline */}
          <path d={mexicoOutline(W, H)} fill="rgba(245, 158, 11, 0.04)" stroke="rgba(245, 158, 11, 0.30)" strokeWidth="1"/>
          {/* Baja California Sur (peninsula) */}
          <path d={bajaSur(W, H)} fill="rgba(245, 158, 11, 0.04)" stroke="rgba(245, 158, 11, 0.30)" strokeWidth="1"/>
          {/* Yucatán peninsula */}
          <path d={yucatan(W, H)} fill="rgba(245, 158, 11, 0.04)" stroke="rgba(245, 158, 11, 0.30)" strokeWidth="1"/>

          {/* USA border line */}
          <line x1={projectPoint(32.7, -117, W, H).x} y1={projectPoint(32.7, -117, W, H).y}
                x2={projectPoint(25.9, -97.1, W, H).x} y2={projectPoint(25.9, -97.1, W, H).y}
                stroke="rgba(255,255,255,0.15)" strokeWidth="1" strokeDasharray="4,4"/>
          <text x={projectPoint(33, -106, W, H).x} y={projectPoint(33, -106, W, H).y - 6} fill="rgba(255,255,255,0.25)" fontSize="9" fontFamily="IBM Plex Mono, monospace">FRONTERA EE.UU.</text>

          {/* cities */}
          {CITIES.map((c) => {
            const { x, y } = projectPoint(c.lat, c.lng, W, H);
            return (
              <g key={c.name}>
                <circle cx={x} cy={y} r="1.5" fill="rgba(255,255,255,0.4)"/>
                <text x={x + 5} y={y + 3} fill="rgba(255,255,255,0.45)" fontSize="8" fontFamily="IBM Plex Mono, monospace">{c.name}</text>
              </g>
            );
          })}

          {/* axis labels */}
          <text x="6" y="14" fill="rgba(255,255,255,0.35)" fontSize="9" fontFamily="IBM Plex Mono, monospace">DEYMA · MÉXICO RADAR · 14.4°N – 32.8°N</text>
          <text x="6" y={H - 6} fill="rgba(255,255,255,0.35)" fontSize="9" fontFamily="IBM Plex Mono, monospace">-118.5°W ◀ ▶ -86.5°W</text>

          {/* points */}
          {filtered.map((p) => {
            const { x, y } = projectPoint(p.lat, p.lng, W, H);
            const isHot = p.hotness === "hot" || (p.score || 0) >= 75;
            const color = isHot ? "#f97316" : p.score >= 50 ? "#fbbf24" : "#71717a";
            const r = Math.max(4, Math.min(14, Math.log10((p.monto || 1) / 100000) * 3));
            return (
              <g key={p.id} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }} data-testid={`map-point-${p.id}`}>
                {isHot && <circle cx={x} cy={y} r={r + 8} fill="url(#hotPulse)" opacity="0.6">
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

        <div className="mt-4 flex items-center gap-4 font-mono text-[10px] text-zinc-500 flex-wrap">
          <span className="flex items-center gap-1"><span className="w-3 h-3 inline-block bg-orange-500 rotate-45"></span>HOT (≥75)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 inline-block bg-amber-400 rotate-45"></span>WARM (50-74)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 inline-block bg-zinc-500 rotate-45"></span>COLD (&lt;50)</span>
          <span className="ml-auto">▸ Tamaño = log(monto MXN) · Cobertura: 32 estados de la República Mexicana</span>
        </div>
      </div>

      <div className="surface">
        <table className="dtable">
          <thead><tr><th>Tipo</th><th>Título</th><th>Sector</th><th>Ubicación</th><th className="text-right">Monto</th><th>Score</th></tr></thead>
          <tbody>
            {filtered.slice(0, 30).map((p) => (
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

// Schematic outline of mainland Mexico (rough but recognizable)
function mexicoOutline(W, H) {
  const pts = [
    // Pacific coast (Tijuana → Manzanillo → Acapulco → Salina Cruz)
    [32.5, -117.0], [30.5, -115.7], [27.9, -114.0], [24.4, -111.9], [23.2, -109.4],
    [22.9, -106.6], [20.6, -105.3], [19.1, -104.3], [17.5, -101.5], [16.6, -99.9],
    [15.9, -97.4], [16.2, -95.2], [15.6, -94.0],
    // Southern border (Chiapas/Guatemala)
    [14.6, -92.2], [15.5, -91.7], [16.5, -91.3], [17.3, -91.0],
    // Yucatán bay
    [17.8, -90.5], [18.3, -90.0], [18.7, -89.3], [19.0, -89.5],
    [20.0, -90.5], [20.8, -91.5],
    // Gulf coast going up to Tamaulipas
    [21.5, -97.0], [22.4, -97.5], [24.0, -97.9], [25.9, -97.5],
    // US border going west to Tijuana
    [26.5, -99.5], [28.6, -103.4], [29.4, -104.5], [31.7, -106.5],
    [31.9, -109.0], [32.5, -114.7], [32.7, -117.1],
  ];
  return "M " + pts.map(([lat, lng]) => {
    const { x, y } = projectPoint(lat, lng, W, H);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" L ") + " Z";
}

function bajaSur(W, H) {
  const pts = [
    [27.9, -114.0], [27.3, -114.3], [26.3, -113.0], [25.0, -111.5],
    [23.5, -110.0], [22.9, -109.4], [23.0, -109.9], [23.7, -110.7],
    [24.6, -111.5], [25.5, -112.4], [26.6, -113.5], [27.9, -114.3],
  ];
  return "M " + pts.map(([lat, lng]) => {
    const { x, y } = projectPoint(lat, lng, W, H);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" L ") + " Z";
}

function yucatan(W, H) {
  const pts = [
    [21.6, -88.1], [21.6, -86.9], [21.2, -86.7], [20.5, -86.9],
    [19.5, -87.5], [18.5, -88.3], [18.0, -88.7], [17.9, -89.2],
    [18.5, -89.7], [19.4, -89.9], [20.4, -90.3], [21.2, -90.3], [21.5, -88.5],
  ];
  return "M " + pts.map(([lat, lng]) => {
    const { x, y } = projectPoint(lat, lng, W, H);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" L ") + " Z";
}
