import React, { useEffect } from "react";

export function Surface({ children, className = "", ...rest }) {
  return <div className={`surface ${className}`} {...rest}>{children}</div>;
}

export function KpiCard({ label, value, sub, accent = "amber", testId, icon: Icon }) {
  const accentMap = {
    amber: "text-amber-400",
    blue: "text-sky-400",
    green: "text-emerald-400",
    red: "text-rose-400",
    gray: "text-zinc-300",
  };
  return (
    <div className="surface p-4 flex flex-col gap-2" data-testid={testId}>
      <div className="flex items-center justify-between">
        <span className="label-overline">{label}</span>
        {Icon && <Icon size={14} className="text-zinc-500" strokeWidth={1.5} />}
      </div>
      <div className={`font-mono text-3xl font-semibold ${accentMap[accent]}`}>{value}</div>
      {sub && <div className="text-xs text-zinc-500 font-mono">{sub}</div>}
    </div>
  );
}

export function Hotness({ value }) {
  const map = {
    hot: { c: "text-orange-400 border-orange-400/60", label: "HOT" },
    warm: { c: "text-amber-300 border-amber-300/60", label: "WARM" },
    cold: { c: "text-zinc-500 border-zinc-500/60", label: "COLD" },
  };
  const v = map[value] || map.cold;
  return <span className={`badge ${v.c}`}>{v.label}</span>;
}

export function ScoreBar({ value }) {
  const color = value >= 75 ? "bg-orange-500" : value >= 50 ? "bg-amber-400" : "bg-zinc-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-white/10">
        <div className={`h-full ${color}`} style={{ width: `${Math.max(2, value)}%` }} />
      </div>
      <span className="font-mono text-xs w-8 text-right">{value}</span>
    </div>
  );
}

export function StageBadge({ stage }) {
  const map = {
    prospeccion: "text-zinc-400 border-zinc-400/40",
    calificada: "text-sky-400 border-sky-400/40",
    propuesta: "text-blue-400 border-blue-400/40",
    negociacion: "text-amber-400 border-amber-400/40",
    ganada: "text-emerald-400 border-emerald-400/40",
    perdida: "text-rose-400 border-rose-400/40",
  };
  const labels = {
    prospeccion: "PROSPECCIÓN",
    calificada: "CALIFICADA",
    propuesta: "PROPUESTA",
    negociacion: "NEGOCIACIÓN",
    ganada: "GANADA",
    perdida: "PERDIDA",
  };
  return <span className={`badge ${map[stage] || map.prospeccion}`}>{labels[stage] || stage}</span>;
}

export function Modal({ open, onClose, title, children, testId, size = "md" }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose && onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  const w = size === "lg" ? "max-w-3xl" : size === "xl" ? "max-w-5xl" : "max-w-md";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
      <div className={`surface w-full ${w} max-h-[90vh] overflow-auto`} onClick={(e) => e.stopPropagation()} data-testid={testId}>
        <div className="flex items-center justify-between p-4 divider">
          <h3 className="text-base font-semibold">{title}</h3>
          <button data-testid="modal-close-btn" onClick={onClose} className="text-zinc-400 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export function EmptyState({ title, hint }) {
  return (
    <div className="surface p-12 text-center text-zinc-500">
      <div className="font-mono text-xs mb-2">// NO DATA</div>
      <div className="text-base font-semibold text-zinc-300 mb-1">{title}</div>
      {hint && <div className="text-xs">{hint}</div>}
    </div>
  );
}
