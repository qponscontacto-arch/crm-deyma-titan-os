import React, { useEffect, useState } from "react";
import { api, ACTIVIDAD_LABEL } from "../lib/auth";
import { CheckCircle2, Circle, Phone, Mail, Users, MapPin, FileText, ListTodo, Calendar } from "lucide-react";

const TIPO_ICON = {
  llamada: Phone, correo: Mail, reunion: Users, visita: MapPin, nota: FileText, tarea: ListTodo,
};
const TIPO_COLOR = {
  llamada: "text-emerald-400 border-emerald-400/40",
  correo: "text-sky-400 border-sky-400/40",
  reunion: "text-blue-400 border-blue-400/40",
  visita: "text-amber-400 border-amber-400/40",
  nota: "text-zinc-400 border-zinc-400/40",
  tarea: "text-orange-400 border-orange-400/40",
};

export default function MisTareasPage() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("pendientes");
  const [ops, setOps] = useState([]);

  const load = async () => {
    const params = { mias: true };
    if (filter === "pendientes") params.pendientes = true;
    const [{ data }, { data: o }] = await Promise.all([
      api.get("/actividades", { params }),
      api.get("/oportunidades"),
    ]);
    setItems(data); setOps(o);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const opTitle = (id) => ops.find((o) => o.id === id)?.titulo || "—";

  const toggle = async (a) => {
    await api.patch(`/actividades/${a.id}`, { completada: !a.completada });
    load();
  };

  return (
    <div className="p-6 space-y-5" data-testid="mis-tareas-page">
      <div className="divider pb-4 flex items-end justify-between">
        <div>
          <div className="label-overline text-amber-400">Productividad personal</div>
          <h1 className="text-3xl font-black tracking-tight" style={{ fontFamily: "Chivo, sans-serif" }}>Mis Tareas</h1>
        </div>
        <div className="flex gap-1">
          {[["pendientes", "Pendientes"], ["todas", "Todas"]].map(([k, l]) => (
            <button key={k} onClick={() => setFilter(k)} data-testid={`tab-${k}`}
              className={`px-4 py-2 text-xs font-bold tracking-wider uppercase border ${
                filter === k ? "border-amber-500 text-amber-400 bg-amber-500/10" : "border-white/10 text-zinc-500 hover:text-zinc-300"
              }`} style={{ fontFamily: "Chivo, sans-serif" }}>{l}</button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <div className="surface p-12 text-center">
          <Calendar size={48} strokeWidth={1} className="mx-auto text-zinc-700 mb-3"/>
          <div className="text-zinc-400">{filter === "pendientes" ? "Sin tareas pendientes. ¡Buen trabajo!" : "No tienes actividades registradas."}</div>
          <div className="text-xs text-zinc-500 mt-2">Crea actividades desde el panel de cada oportunidad en CRM.</div>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((a) => {
            const Icon = TIPO_ICON[a.tipo] || FileText;
            const overdue = !a.completada && new Date(a.fecha) < new Date();
            return (
              <div key={a.id} className={`surface p-3 flex items-start gap-3 ${overdue ? "border-l-4 border-l-rose-500" : ""}`} data-testid={`task-${a.id}`}>
                <button onClick={() => toggle(a)} className="mt-1" data-testid={`task-toggle-${a.id}`}>
                  {a.completada
                    ? <CheckCircle2 size={20} className="text-emerald-400" strokeWidth={1.5}/>
                    : <Circle size={20} className="text-zinc-500 hover:text-amber-400" strokeWidth={1.5}/>}
                </button>
                <Icon size={16} className="mt-1.5 text-zinc-500 shrink-0" strokeWidth={1.5}/>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={`badge ${TIPO_COLOR[a.tipo]}`}>{ACTIVIDAD_LABEL[a.tipo].toUpperCase()}</span>
                    {overdue && <span className="badge text-rose-400 border-rose-400/40">VENCIDA</span>}
                    {a.completada && <span className="badge text-emerald-400 border-emerald-400/40">COMPLETADA</span>}
                  </div>
                  <div className={`text-sm ${a.completada ? "line-through text-zinc-500" : ""}`}>{a.descripcion}</div>
                  <div className="text-[10px] text-zinc-500 mt-1 font-mono">▸ Oportunidad: {opTitle(a.oportunidad_id)}</div>
                </div>
                <div className="text-right shrink-0 font-mono text-[10px] text-zinc-500">
                  {new Date(a.fecha).toLocaleString("es-MX", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
