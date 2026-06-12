import React, { useEffect, useState } from "react";
import { api, fmtMXN } from "../lib/auth";
import { EmptyState } from "../components/ui-deyma";

const ESTADO_COLOR = {
  planeacion: "border-zinc-500 text-zinc-300",
  ejecucion: "border-amber-500 text-amber-400",
  pausada: "border-rose-500 text-rose-400",
  completada: "border-emerald-500 text-emerald-400",
};

export default function ObrasPage() {
  const [obras, setObras] = useState([]);
  const [empresas, setEmpresas] = useState([]);

  useEffect(() => {
    Promise.all([api.get("/obras"), api.get("/empresas")]).then(([o, e]) => { setObras(o.data); setEmpresas(e.data); });
  }, []);

  const empName = (id) => empresas.find((e) => e.id === id)?.nombre || "—";

  return (
    <div className="p-6 space-y-5" data-testid="obras-page">
      <div className="divider pb-4">
        <div className="label-overline text-amber-400">Operaciones · ejecución de obras</div>
        <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Obras</h1>
      </div>

      {obras.length === 0 ? <EmptyState title="Sin obras registradas" /> : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {obras.map((o) => (
            <div key={o.id} className="surface p-5 space-y-3" data-testid={`obra-card-${o.id}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="label-overline text-amber-400">{empName(o.empresa_id)}</div>
                  <h3 className="text-base font-bold">{o.nombre}</h3>
                </div>
                <span className={`badge ${ESTADO_COLOR[o.estado]}`}>{o.estado.toUpperCase()}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div><div className="label-overline">Monto</div><div className="font-mono text-amber-400 text-lg">{fmtMXN(o.monto_contratado)}</div></div>
                <div><div className="label-overline">Ubicación</div><div className="font-mono">{o.ciudad}</div></div>
                <div><div className="label-overline">Inicio</div><div className="font-mono">{new Date(o.fecha_inicio).toLocaleDateString("es-MX")}</div></div>
                <div><div className="label-overline">Fin estimado</div><div className="font-mono">{new Date(o.fecha_fin_estimada).toLocaleDateString("es-MX")}</div></div>
              </div>
              <div>
                <div className="flex items-baseline justify-between mb-1">
                  <span className="label-overline">Avance</span>
                  <span className="font-mono text-amber-400">{o.avance_pct}%</span>
                </div>
                <div className="h-2 bg-white/5">
                  <div className="h-full bg-amber-500" style={{ width: `${o.avance_pct}%` }}/>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
