import React, { useState, useEffect, useRef } from "react";
import { useAuth, api, fmtMXN, formatApiError, downloadPdf } from "../lib/auth";
import {
  MapPin, Navigation, Sparkles, Loader2, Download, Save, Trash2, History,
  ArrowRight, Brain, AlertCircle, Clock, Target, Locate, Wallet
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import polyline from "@mapbox/polyline";
import "leaflet/dist/leaflet.css";

// Fix Leaflet default icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const iconColor = (color, label) => L.divIcon({
  className: "",
  html: `<div style="background:${color};width:32px;height:32px;border:3px solid white;border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 2px 6px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;"><span style="transform:rotate(45deg);color:white;font-weight:bold;font-size:11px;font-family:monospace;">${label}</span></div>`,
  iconSize: [32, 32], iconAnchor: [16, 32], popupAnchor: [0, -28],
});

const FitBounds = ({ points }) => {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) map.fitBounds(points, { padding: [50, 50] });
  }, [points, map]);
  return null;
};

export default function AdminRutaVentasPage() {
  const { user } = useAuth();
  const allowed = ["comercial", "director", "socio"].includes(user?.role);
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [modo, setModo] = useState("corredor");
  const [maxDesvio, setMaxDesvio] = useState(40);
  const [maxParadas, setMaxParadas] = useState(5);
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState(null);
  const [err, setErr] = useState("");
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  const loadHistory = async () => {
    try { const r = await api.get("/ruta-ventas"); setHistory(r.data); } catch {}
  };
  useEffect(() => { if (allowed) loadHistory(); }, [allowed]);

  if (!allowed) {
    return <div className="p-10 text-center text-rose-400 font-mono text-sm" data-testid="ruta-denied">Acceso denegado. Solo Comercial, Director y Socio.</div>;
  }

  const detectarUbicacion = () => {
    if (!navigator.geolocation) return setErr("Tu navegador no soporta geolocalización.");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const r = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`);
          const d = await r.json();
          const ciudad = d?.address?.city || d?.address?.town || d?.address?.village || d?.display_name?.split(",")[0];
          setOrigen(`${ciudad}, ${d?.address?.state || "MX"}`);
        } catch { setOrigen(`${latitude},${longitude}`); }
      },
      (e) => setErr(`Geolocalización denegada: ${e.message}`)
    );
  };

  const generar = async () => {
    if (!origen) return setErr("Captura el origen");
    setBusy(true); setErr(""); setPlan(null);
    try {
      const { data } = await api.post("/ruta-ventas/generar", {
        origen, destino: modo === "corredor" ? destino : null,
        modo, max_desvio_km: +maxDesvio, max_paradas: +maxParadas, fecha,
      });
      setPlan(data);
    } catch (e) { setErr(formatApiError(e)); }
    finally { setBusy(false); }
  };

  const guardar = async () => {
    if (!plan) return;
    try {
      await api.post("/ruta-ventas/guardar", { ...plan, fecha });
      await loadHistory();
      alert("✅ Ruta guardada en histórico");
    } catch (e) { setErr(formatApiError(e)); }
  };

  const pdf = async () => {
    if (!plan) return;
    const res = await api.post("/ruta-ventas/pdf", { ...plan, fecha }, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a"); a.href = url;
    a.download = `DEYMA_ruta_${fecha}.pdf`;
    document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="label-overline text-amber-400">Inteligencia comercial · Agente IA de ventas</div>
          <h1 className="text-3xl font-black flex items-center gap-3" style={{ fontFamily: "Chivo, sans-serif" }}>
            <Navigation size={26} className="text-amber-400" /> Ruta de Ventas
          </h1>
          <p className="text-xs text-zinc-500 mt-1">Genera tu plan de prospección óptimo con GPT-5.2. Detecta clientes potenciales en tu corredor.</p>
        </div>
        <button onClick={() => setShowHistory(!showHistory)} data-testid="ruta-history-btn" className="btn-ghost flex items-center gap-2 text-xs">
          <History size={14} /> Histórico ({history.length})
        </button>
      </header>

      {showHistory && <HistoryPanel items={history} reload={loadHistory} />}

      <div className="grid lg:grid-cols-[420px_1fr] gap-5">
        {/* Form */}
        <div className="border border-white/10 bg-zinc-950 p-5 space-y-4 h-fit sticky top-4">
          <div className="label-overline text-amber-400">Configurar ruta</div>

          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => setModo("corredor")} data-testid="modo-corredor"
              className={`p-3 border text-xs label-overline flex flex-col items-center gap-1 ${modo === "corredor" ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}>
              <ArrowRight size={14} /> Origen → Destino
            </button>
            <button onClick={() => setModo("local")} data-testid="modo-local"
              className={`p-3 border text-xs label-overline flex flex-col items-center gap-1 ${modo === "local" ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-white/10 text-zinc-400 hover:text-zinc-200"}`}>
              <Target size={14} /> Prospección local
            </button>
          </div>

          <div>
            <label className="label-overline">Origen</label>
            <div className="flex gap-2 mt-1">
              <input data-testid="ruta-origen" className="input-field flex-1" value={origen} onChange={(e) => setOrigen(e.target.value)} placeholder="Ej. Morelia, Michoacán" />
              <button onClick={detectarUbicacion} data-testid="ruta-detectar" title="Usar mi ubicación" className="btn-ghost px-3"><Locate size={14} /></button>
            </div>
          </div>

          {modo === "corredor" && (
            <div>
              <label className="label-overline">Destino</label>
              <input data-testid="ruta-destino" className="input-field mt-1" value={destino} onChange={(e) => setDestino(e.target.value)} placeholder="Ej. Querétaro, Querétaro" />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label-overline">{modo === "corredor" ? "Desvío máx (km)" : "Radio (km)"}</label>
              <input data-testid="ruta-desvio" type="number" min="5" max="200" className="input-field mt-1" value={maxDesvio} onChange={(e) => setMaxDesvio(e.target.value)} />
            </div>
            <div>
              <label className="label-overline">Max paradas</label>
              <input data-testid="ruta-paradas" type="number" min="1" max="15" className="input-field mt-1" value={maxParadas} onChange={(e) => setMaxParadas(e.target.value)} />
            </div>
          </div>

          <div>
            <label className="label-overline">Fecha</label>
            <input data-testid="ruta-fecha" type="date" className="input-field mt-1" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>

          {err && <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-xs p-2 font-mono flex gap-1.5" data-testid="ruta-error"><AlertCircle size={14} /> {err}</div>}

          <button onClick={generar} disabled={busy} data-testid="ruta-generar" className="btn-primary w-full flex items-center justify-center gap-2 py-3">
            {busy ? <><Loader2 size={16} className="animate-spin" /> Analizando con IA…</> : <><Sparkles size={16} /> Generar plan con IA</>}
          </button>

          {plan && (
            <div className="border-t border-white/10 pt-3 flex gap-2">
              <button onClick={guardar} data-testid="ruta-guardar" className="btn-ghost flex-1 flex items-center justify-center gap-1.5 text-xs"><Save size={12} /> Guardar</button>
              <button onClick={pdf} data-testid="ruta-pdf" className="btn-primary flex-1 flex items-center justify-center gap-1.5 text-xs"><Download size={12} /> PDF</button>
            </div>
          )}
        </div>

        {/* Result */}
        <div className="space-y-4">
          {!plan && !busy && (
            <div className="border border-white/10 bg-zinc-950 p-10 text-center text-zinc-500" data-testid="ruta-empty">
              <Brain size={42} className="mx-auto mb-3 text-amber-500/50" />
              <p className="text-sm">Captura tu origen y destino para que el agente IA trace tu ruta de prospección óptima.</p>
              <p className="text-xs mt-2 text-zinc-600">El sistema cruzará automáticamente tu CRM y el Radar para priorizar las visitas con mayor potencial de cierre.</p>
            </div>
          )}

          {busy && (
            <div className="border border-amber-500/30 bg-amber-500/5 p-10 text-center" data-testid="ruta-loading">
              <Loader2 size={42} className="mx-auto mb-3 text-amber-400 animate-spin" />
              <p className="text-sm text-amber-200">El agente IA está analizando el corredor, evaluando oportunidades del CRM y generando briefing personalizado…</p>
              <p className="text-xs text-zinc-500 mt-2">Esto puede tardar 15-30 segundos</p>
            </div>
          )}

          {plan && <PlanResult plan={plan} />}
        </div>
      </div>
    </div>
  );
}

function PlanResult({ plan }) {
  const route = plan.route || {};
  const linePoints = route.geometry ? polyline.decode(route.geometry).map(([lat, lng]) => [lat, lng]) : null;
  const allPoints = [];
  if (plan.origen) allPoints.push([plan.origen.lat, plan.origen.lng]);
  plan.paradas?.forEach((p) => allPoints.push([p.lat, p.lng]));
  if (plan.destino) allPoints.push([plan.destino.lat, plan.destino.lng]);

  return (
    <>
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="ruta-stats">
        <Stat k="Distancia" v={`${route.distance_km || 0} km`} icon={Navigation} />
        <Stat k="Duración" v={`${Math.round((route.duration_min || 0) / 60)}h ${(route.duration_min || 0) % 60}m`} icon={Clock} />
        <Stat k="Paradas" v={plan.paradas?.length || 0} icon={MapPin} highlight />
        <Stat k="Candidatos" v={plan.total_candidatos_corredor || 0} icon={Target} />
      </div>

      {/* Mapa */}
      {allPoints.length > 0 && (
        <div className="border border-white/10 h-[420px] overflow-hidden" data-testid="ruta-map">
          <MapContainer center={allPoints[0]} zoom={6} style={{ height: "100%", width: "100%" }}>
            <TileLayer attribution='&copy; OSM' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitBounds points={allPoints} />
            {plan.origen && (
              <Marker position={[plan.origen.lat, plan.origen.lng]} icon={iconColor("#0F1F4D", "A")}>
                <Popup><b>Origen</b><br />{plan.origen.display_name}</Popup>
              </Marker>
            )}
            {plan.paradas?.map((p, i) => (
              <Marker key={p.empresa_id} position={[p.lat, p.lng]} icon={iconColor("#F37021", String(i + 1))}>
                <Popup>
                  <b>{p.empresa_nombre}</b><br />
                  {p.ciudad} · {p.mejor_etapa}<br />
                  Score: {p.score} · {fmtMXN(p.monto_total)}
                </Popup>
              </Marker>
            ))}
            {plan.destino && (
              <Marker position={[plan.destino.lat, plan.destino.lng]} icon={iconColor("#10B981", "B")}>
                <Popup><b>Destino</b><br />{plan.destino.display_name}</Popup>
              </Marker>
            )}
            {linePoints && <Polyline positions={linePoints} pathOptions={{ color: "#F37021", weight: 4, opacity: 0.85 }} />}
          </MapContainer>
        </div>
      )}

      {/* Resumen IA */}
      {plan.plan_ia_resumen && (
        <div className="border border-amber-500/40 bg-gradient-to-br from-amber-500/5 to-transparent p-4" data-testid="ruta-resumen-ia">
          <div className="flex items-start gap-3">
            <Brain size={18} className="text-amber-400 shrink-0 mt-0.5" />
            <div className="text-sm text-zinc-200 leading-relaxed">{plan.plan_ia_resumen}</div>
          </div>
        </div>
      )}

      {/* Paradas */}
      <div className="space-y-3" data-testid="ruta-paradas-list">
        {plan.paradas?.length === 0 ? (
          <div className="border border-white/10 p-6 text-center text-sm text-zinc-500">
            Sin candidatos en el corredor con los criterios actuales. Aumenta el radio o cambia el destino.
          </div>
        ) : (
          plan.paradas?.map((p, i) => (
            <ParadaCard key={p.empresa_id} parada={p} index={i + 1} />
          ))
        )}
      </div>

      {plan.plan_ia_recomendacion && (
        <div className="border border-emerald-500/40 bg-emerald-500/5 p-4" data-testid="ruta-recomendacion">
          <div className="label-overline text-emerald-400 mb-2 flex items-center gap-2">
            <Sparkles size={12} /> Recomendación final del agente IA
          </div>
          <p className="text-sm text-zinc-200 leading-relaxed">{plan.plan_ia_recomendacion}</p>
        </div>
      )}
    </>
  );
}

function ParadaCard({ parada, index }) {
  const etapaColor = {
    propuesta: "amber", negociacion: "emerald", calificada: "sky",
    prospeccion: "zinc", ganada: "emerald", perdida: "rose",
  }[parada.mejor_etapa] || "zinc";

  return (
    <div className="border border-white/10 bg-zinc-950 p-4 hover:border-amber-500/40 transition-colors" data-testid={`parada-${parada.empresa_id}`}>
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 bg-amber-500 text-black font-black flex items-center justify-center font-mono text-base shrink-0">
          {index}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            <h3 className="text-base font-bold truncate" style={{ fontFamily: "Chivo, sans-serif" }}>{parada.empresa_nombre}</h3>
            <span className={`px-1.5 py-0.5 text-[10px] font-mono uppercase border border-${etapaColor}-500/40 bg-${etapaColor}-500/10 text-${etapaColor}-400`}>
              {parada.mejor_etapa}
            </span>
            <span className="text-xs text-zinc-500 font-mono">Score IA <b className="text-amber-400">{parada.score}</b></span>
          </div>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            📍 {parada.ciudad || "Sin ciudad"} · 💰 {fmtMXN(parada.monto_total)} · 🎯 {parada.n_oportunidades} opp · 📊 radar {parada.radar_score}
            {parada.ultima_actividad_dias !== null && <> · ⏱ últ. {parada.ultima_actividad_dias}d</>}
            {parada.desvio_km !== undefined && <> · ↔ {parada.desvio_km}km del corredor</>}
          </div>
          <div className="mt-2 pl-3 border-l-2 border-amber-500/40">
            <div className="text-[10px] label-overline text-amber-400 flex items-center gap-1.5">
              <Brain size={10} /> Briefing IA · {parada.accion_clave} · {parada.tiempo_min} min
            </div>
            <p className="text-sm text-zinc-200 mt-1 leading-relaxed">{parada.briefing}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ k, v, icon: Icon, highlight }) {
  return (
    <div className={`p-3 border ${highlight ? "border-amber-500/40 bg-amber-500/5" : "border-white/10 bg-zinc-950"}`}>
      <div className="flex items-center gap-2">
        <Icon size={14} className={highlight ? "text-amber-400" : "text-zinc-500"} />
        <div className="label-overline text-[10px]">{k}</div>
      </div>
      <div className={`text-xl font-black mt-1 font-mono ${highlight ? "text-amber-400" : "text-zinc-100"}`}>{v}</div>
    </div>
  );
}

function HistoryPanel({ items, reload }) {
  const del = async (rid) => {
    if (!window.confirm("¿Eliminar esta ruta del histórico?")) return;
    await api.delete(`/ruta-ventas/${rid}`); reload();
  };
  return (
    <div className="border border-white/10 bg-zinc-950" data-testid="ruta-history-panel">
      <div className="p-3 border-b border-white/10 label-overline text-amber-400">Histórico de rutas generadas</div>
      {items.length === 0 ? (
        <div className="p-6 text-center text-sm text-zinc-500">Aún no has guardado rutas.</div>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-zinc-500 label-overline border-b border-white/10">
              <th className="p-3">Fecha</th><th className="p-3">Vendedor</th><th className="p-3">Origen</th><th className="p-3">Destino</th><th className="p-3 text-right">Paradas</th><th className="p-3 text-right">Km</th><th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="border-b border-white/5 hover:bg-white/5">
                <td className="p-3 font-mono">{r.fecha}</td>
                <td className="p-3">{r.vendedor_nombre}</td>
                <td className="p-3 truncate max-w-[160px]">{(r.origen || {}).display_name || "—"}</td>
                <td className="p-3 truncate max-w-[160px]">{(r.destino || {}).display_name || "Local"}</td>
                <td className="p-3 text-right font-mono">{(r.paradas || []).length}</td>
                <td className="p-3 text-right font-mono">{(r.route || {}).distance_km || "—"}</td>
                <td className="p-3 text-right">
                  <button onClick={() => del(r.id)} className="text-rose-400 hover:text-rose-300"><Trash2 size={12} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
