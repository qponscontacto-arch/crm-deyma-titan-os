import React, { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { API, formatApiError, downloadPdf } from "../lib/auth";
import { Radar, Upload, ChevronRight, ChevronLeft, CheckCircle2, FileText, ArrowLeft, AlertCircle } from "lucide-react";

const REQUIRED_DOCS = [
  { key: "csf", label: "Constancia de Situación Fiscal (SAT)", accept: ".pdf" },
  { key: "acta_constitutiva", label: "Acta Constitutiva (notariada)", accept: ".pdf" },
  { key: "poder_representante", label: "Poder Notarial del Representante Legal", accept: ".pdf" },
  { key: "ine_representante", label: "INE del Representante Legal", accept: ".pdf,image/*" },
  { key: "comprobante_domicilio", label: "Comprobante de Domicilio Fiscal", accept: ".pdf" },
];

const POLITICAS = [
  { key: "politica_validacion_tecnica", label: "Acepto que TODOS los proyectos pasan por VALIDACIÓN TÉCNICA previa de DEYMA." },
  { key: "politica_firma_actas", label: "Me comprometo a FIRMAR ACTAS de avance/recepción para mantener el cronograma de pagos." },
  { key: "politica_separacion_errores", label: "Acepto la SEPARACIÓN DE ERRORES entre proveedores: cada quien responde por su parte." },
  { key: "politica_ordenes_cambio", label: "Acepto que toda modificación se gestiona vía ÓRDENES DE CAMBIO por escrito." },
  { key: "politica_cero_fianzas", label: "Acepto la política CERO FIANZAS de DEYMA (no entregamos fianzas de cumplimiento)." },
];

const FINANCIERAS = [
  { key: "fin_recepcion_oc", label: "Recepción y validación de Orden de Compra (OC) en PDF firmado." },
  { key: "fin_anticipo", label: "Anticipo del 50% al arranque (contra OC validada)." },
  { key: "fin_dia_1", label: "Día 1 = día de entrada del anticipo al banco DEYMA." },
];

export default function AltaClientePage() {
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    razon_social: "", rfc: "", domicilio_fiscal: "", domicilio_planta: "",
    email: "", password: "", password2: "",
    contacto_tecnico_nombre: "", contacto_tecnico_tel: "", contacto_tecnico_correo: "",
    contacto_compras_nombre: "", contacto_compras_tel: "", contacto_compras_correo: "",
    contacto_cxp_nombre: "", contacto_cxp_tel: "", contacto_cxp_correo: "",
    politica_validacion_tecnica: false, politica_firma_actas: false,
    politica_separacion_errores: false, politica_ordenes_cambio: false, politica_cero_fianzas: false,
    fin_recepcion_oc: false, fin_anticipo: false, fin_dia_1: false,
    firma_representante_nombre: "", firma_representante_sello: "",
    firma_tecnico_nombre: "", firma_tecnico_area: "",
  });
  const [files, setFiles] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setFile = (k, f) => setFiles((s) => ({ ...s, [k]: f }));

  const canStep1 = form.razon_social && form.rfc.length >= 12 && form.domicilio_fiscal && form.email && form.password.length >= 6 && form.password === form.password2;
  const canStep2 = form.contacto_tecnico_nombre && form.contacto_tecnico_correo && form.contacto_compras_nombre && form.contacto_compras_correo && form.contacto_cxp_nombre && form.contacto_cxp_correo;
  const canStep3 = POLITICAS.every((p) => form[p.key]) && FINANCIERAS.every((f) => form[f.key]);
  const canStep4 = form.firma_representante_nombre && form.firma_tecnico_nombre;
  const canStep5 = REQUIRED_DOCS.every((d) => files[d.key]);

  const submit = async () => {
    setErr(""); setBusy(true);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => {
      if (k === "password2") return;
      fd.append(k, typeof v === "boolean" ? String(v) : v);
    });
    fd.append("csf", files.csf);
    fd.append("acta_constitutiva", files.acta_constitutiva);
    fd.append("poder_representante", files.poder_representante);
    fd.append("ine_representante", files.ine_representante);
    fd.append("comprobante_domicilio", files.comprobante_domicilio);
    try {
      const { data } = await axios.post(`${API}/clientes/alta`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
      try { await downloadPdf(`/clientes/${data.id}/pdf-alta`, `DEYMA_alta_${data.folio_registro}.pdf`); } catch {}
    } catch (e) {
      setErr(formatApiError(e));
    } finally { setBusy(false); }
  };

  if (result) {
    return (
      <SuccessView result={result} onLogin={() => nav("/login")} />
    );
  }

  return (
    <div className="min-h-screen bg-black text-zinc-100">
      <header className="border-b border-white/10 bg-zinc-950">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-500 flex items-center justify-center"><Radar size={20} className="text-black" strokeWidth={2} /></div>
            <div>
              <div className="font-black tracking-tight text-base" style={{ fontFamily: "Chivo, sans-serif" }}>DEYMA · ALTA DE CLIENTES</div>
              <div className="label-overline text-amber-400/80 text-[10px]">Portal Oficial · Construcción Industrial</div>
            </div>
          </div>
          <Link to="/login" data-testid="back-to-login" className="text-xs text-zinc-400 hover:text-amber-400 flex items-center gap-1.5"><ArrowLeft size={14} /> Volver al inicio</Link>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8">
        <Stepper step={step} />

        <div className="mt-8 grid md:grid-cols-[1fr_280px] gap-8">
          <div className="space-y-6">
            {step === 1 && <Step1 form={form} set={set} />}
            {step === 2 && <Step2 form={form} set={set} />}
            {step === 3 && <Step3 form={form} set={set} />}
            {step === 4 && <Step4 form={form} set={set} />}
            {step === 5 && <Step5 files={files} setFile={setFile} />}

            {err && (
              <div className="border border-rose-500/60 bg-rose-500/10 text-rose-300 text-sm p-3 font-mono flex gap-2" data-testid="alta-error">
                <AlertCircle size={16} className="shrink-0 mt-0.5" /> {err}
              </div>
            )}

            <div className="flex items-center justify-between border-t border-white/10 pt-5">
              <button
                onClick={() => setStep((s) => Math.max(1, s - 1))}
                disabled={step === 1 || busy}
                data-testid="step-prev"
                className="btn-ghost flex items-center gap-1.5 disabled:opacity-40"
              ><ChevronLeft size={14} /> Anterior</button>

              {step < 5 ? (
                <button
                  onClick={() => setStep((s) => s + 1)}
                  data-testid="step-next"
                  disabled={(step === 1 && !canStep1) || (step === 2 && !canStep2) || (step === 3 && !canStep3) || (step === 4 && !canStep4)}
                  className="btn-primary flex items-center gap-1.5 disabled:opacity-40"
                >Siguiente <ChevronRight size={14} /></button>
              ) : (
                <button
                  onClick={submit}
                  disabled={!canStep5 || busy}
                  data-testid="alta-submit"
                  className="btn-primary flex items-center gap-1.5 disabled:opacity-40"
                >{busy ? "Enviando…" : "Enviar solicitud"} <ChevronRight size={14} /></button>
              )}
            </div>
          </div>

          <aside className="space-y-3">
            <div className="border border-white/10 bg-zinc-950 p-4">
              <div className="label-overline text-amber-400 mb-2">¿Para qué este alta?</div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                DEYMA opera bajo un modelo industrial profesional. Este registro garantiza un proceso transparente, ágil y libre de fricciones administrativas durante todo el proyecto.
              </p>
            </div>
            <div className="border border-white/10 bg-zinc-950 p-4">
              <div className="label-overline text-amber-400 mb-2">¿Ya tengo trámite?</div>
              <p className="text-xs text-zinc-400 mb-3">Consulta el estado con tu folio o DFNUM.</p>
              <Link to="/consulta-tramite" data-testid="link-consulta" className="text-xs text-amber-400 hover:underline">→ Consultar estado</Link>
            </div>
            <div className="border border-white/10 bg-zinc-950 p-4">
              <div className="label-overline text-amber-400 mb-2">Requisitos</div>
              <ul className="text-xs text-zinc-400 space-y-1 list-disc pl-4">
                <li>Documentos en PDF (máx 10 MB c/u)</li>
                <li>RFC válido (12-13 caracteres)</li>
                <li>Aprobación toma 2-3 días hábiles</li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function Stepper({ step }) {
  const steps = ["Datos fiscales", "Contactos", "Políticas", "Firmas", "Documentos"];
  return (
    <div className="flex items-center gap-2" data-testid="stepper">
      {steps.map((s, i) => {
        const n = i + 1;
        const active = step === n;
        const done = step > n;
        return (
          <React.Fragment key={s}>
            <div className={`flex items-center gap-2 ${active ? "text-amber-400" : done ? "text-emerald-400" : "text-zinc-500"}`}>
              <div className={`w-7 h-7 flex items-center justify-center font-mono text-xs font-bold border ${active ? "border-amber-500 bg-amber-500/10" : done ? "border-emerald-500 bg-emerald-500/10" : "border-white/10"}`}>
                {done ? <CheckCircle2 size={14} /> : n}
              </div>
              <span className="text-xs label-overline hidden md:inline">{s}</span>
            </div>
            {n < steps.length && <div className={`flex-1 h-px ${done ? "bg-emerald-500/50" : "bg-white/10"}`} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

const Field = ({ label, children, required, span }) => (
  <div className={span === 2 ? "md:col-span-2" : ""}>
    <label className="label-overline mb-1 block">{label}{required && <span className="text-amber-400"> *</span>}</label>
    {children}
  </div>
);

function Step1({ form, set }) {
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>1. Datos fiscales y de acceso</h2>
      <div className="grid md:grid-cols-2 gap-4">
        <Field label="Razón social" required span={2}>
          <input data-testid="razon-social" className="input-field" value={form.razon_social} onChange={(e) => set("razon_social", e.target.value)} placeholder="EJ. MANUFACTURAS DEL BAJÍO S.A. DE C.V." />
        </Field>
        <Field label="RFC" required>
          <input data-testid="rfc" className="input-field uppercase" value={form.rfc} onChange={(e) => set("rfc", e.target.value.toUpperCase())} placeholder="MDB210515ABC" maxLength={13} />
        </Field>
        <Field label="Correo de contacto (para acceso al portal)" required>
          <input data-testid="email" type="email" className="input-field" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="cuentas@empresa.mx" />
        </Field>
        <Field label="Domicilio fiscal" required span={2}>
          <input data-testid="domicilio-fiscal" className="input-field" value={form.domicilio_fiscal} onChange={(e) => set("domicilio_fiscal", e.target.value)} placeholder="Calle, número, colonia, CP, ciudad, estado" />
        </Field>
        <Field label="Domicilio de planta (si distinto)" span={2}>
          <input data-testid="domicilio-planta" className="input-field" value={form.domicilio_planta} onChange={(e) => set("domicilio_planta", e.target.value)} placeholder="Opcional" />
        </Field>
        <Field label="Contraseña (mín. 6 caracteres)" required>
          <input data-testid="password" type="password" className="input-field" value={form.password} onChange={(e) => set("password", e.target.value)} />
        </Field>
        <Field label="Confirmar contraseña" required>
          <input data-testid="password2" type="password" className="input-field" value={form.password2} onChange={(e) => set("password2", e.target.value)} />
          {form.password2 && form.password !== form.password2 && <div className="text-xs text-rose-400 mt-1">No coinciden</div>}
        </Field>
      </div>
    </section>
  );
}

const ContactoBlock = ({ title, prefix, form, set }) => (
  <div className="border border-white/10 bg-zinc-950 p-4 space-y-3">
    <div className="label-overline text-amber-400">{title}</div>
    <div className="grid md:grid-cols-3 gap-3">
      <input data-testid={`${prefix}-nombre`} className="input-field" placeholder="Nombre completo" value={form[`${prefix}_nombre`]} onChange={(e) => set(`${prefix}_nombre`, e.target.value)} />
      <input data-testid={`${prefix}-tel`} className="input-field" placeholder="Teléfono" value={form[`${prefix}_tel`]} onChange={(e) => set(`${prefix}_tel`, e.target.value)} />
      <input data-testid={`${prefix}-correo`} type="email" className="input-field" placeholder="Correo" value={form[`${prefix}_correo`]} onChange={(e) => set(`${prefix}_correo`, e.target.value)} />
    </div>
  </div>
);

function Step2({ form, set }) {
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>2. Contactos clave</h2>
      <p className="text-sm text-zinc-400">Designa a las personas que coordinarán técnicamente, en compras y en pagos.</p>
      <ContactoBlock title="Contacto técnico" prefix="contacto_tecnico" form={form} set={set} />
      <ContactoBlock title="Contacto de compras" prefix="contacto_compras" form={form} set={set} />
      <ContactoBlock title="Contacto de cuentas por pagar" prefix="contacto_cxp" form={form} set={set} />
    </section>
  );
}

function Step3({ form, set }) {
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>3. Políticas y condiciones</h2>
      <div className="border border-white/10 bg-zinc-950 p-4 space-y-3">
        <div className="label-overline text-amber-400">Políticas operativas DEYMA</div>
        {POLITICAS.map((p) => (
          <label key={p.key} data-testid={`pol-${p.key}`} className="flex items-start gap-3 cursor-pointer text-sm text-zinc-300 hover:text-zinc-100">
            <input type="checkbox" className="mt-0.5 accent-amber-500" checked={form[p.key]} onChange={(e) => set(p.key, e.target.checked)} />
            <span>{p.label}</span>
          </label>
        ))}
      </div>
      <div className="border border-white/10 bg-zinc-950 p-4 space-y-3">
        <div className="label-overline text-amber-400">Condiciones financieras</div>
        {FINANCIERAS.map((p) => (
          <label key={p.key} data-testid={`fin-${p.key}`} className="flex items-start gap-3 cursor-pointer text-sm text-zinc-300 hover:text-zinc-100">
            <input type="checkbox" className="mt-0.5 accent-amber-500" checked={form[p.key]} onChange={(e) => set(p.key, e.target.checked)} />
            <span>{p.label}</span>
          </label>
        ))}
      </div>
    </section>
  );
}

function Step4({ form, set }) {
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>4. Firmas autorizadas</h2>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="border border-white/10 bg-zinc-950 p-4 space-y-3">
          <div className="label-overline text-amber-400">Representante legal</div>
          <Field label="Nombre completo" required>
            <input data-testid="firma-rep-nombre" className="input-field" value={form.firma_representante_nombre} onChange={(e) => set("firma_representante_nombre", e.target.value)} />
          </Field>
          <Field label="Cargo / sello (opcional)">
            <input data-testid="firma-rep-sello" className="input-field" value={form.firma_representante_sello} onChange={(e) => set("firma_representante_sello", e.target.value)} placeholder="Apoderado Legal" />
          </Field>
        </div>
        <div className="border border-white/10 bg-zinc-950 p-4 space-y-3">
          <div className="label-overline text-amber-400">Responsable técnico</div>
          <Field label="Nombre completo" required>
            <input data-testid="firma-tec-nombre" className="input-field" value={form.firma_tecnico_nombre} onChange={(e) => set("firma_tecnico_nombre", e.target.value)} />
          </Field>
          <Field label="Área / puesto">
            <input data-testid="firma-tec-area" className="input-field" value={form.firma_tecnico_area} onChange={(e) => set("firma_tecnico_area", e.target.value)} placeholder="Gerente de Mantenimiento" />
          </Field>
        </div>
      </div>
    </section>
  );
}

function Step5({ files, setFile }) {
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>5. Documentos requeridos</h2>
      <p className="text-sm text-zinc-400">Sube los siguientes documentos en PDF (máximo 10 MB cada uno). El INE puede ser imagen.</p>
      <div className="space-y-3">
        {REQUIRED_DOCS.map((d) => (
          <DocUpload key={d.key} doc={d} file={files[d.key]} onChange={(f) => setFile(d.key, f)} />
        ))}
      </div>
    </section>
  );
}

function DocUpload({ doc, file, onChange }) {
  const ref = React.useRef();
  return (
    <div className={`border ${file ? "border-emerald-500/60 bg-emerald-500/5" : "border-white/10 bg-zinc-950"} p-4 flex items-center gap-4`}>
      <div className={`w-10 h-10 flex items-center justify-center border ${file ? "border-emerald-500/60 text-emerald-400" : "border-white/10 text-zinc-500"}`}>
        {file ? <CheckCircle2 size={18} /> : <FileText size={18} strokeWidth={1.5} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold">{doc.label}</div>
        <div className="text-xs text-zinc-500 truncate">{file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB` : "Sin archivo seleccionado"}</div>
      </div>
      <input
        ref={ref} type="file" accept={doc.accept} className="hidden"
        data-testid={`file-${doc.key}`}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onChange(f); }}
      />
      <button type="button" onClick={() => ref.current?.click()} className="btn-ghost text-xs flex items-center gap-1.5">
        <Upload size={14} /> {file ? "Cambiar" : "Subir"}
      </button>
    </div>
  );
}

function SuccessView({ result, onLogin }) {
  return (
    <div className="min-h-screen bg-black text-zinc-100 flex items-center justify-center p-6">
      <div className="max-w-2xl w-full border border-emerald-500/40 bg-zinc-950 p-10 space-y-6" data-testid="alta-success">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-emerald-500 flex items-center justify-center"><CheckCircle2 size={26} className="text-black" /></div>
          <div>
            <div className="label-overline text-emerald-400">Solicitud recibida</div>
            <h2 className="text-3xl font-black" style={{ fontFamily: "Chivo, sans-serif" }}>¡Bienvenido a DEYMA!</h2>
          </div>
        </div>
        <p className="text-zinc-400 text-sm leading-relaxed">
          Tu solicitud fue recibida correctamente. Iniciamos la <b className="text-amber-400">validación documental</b> y la doble aprobación del <b>Director General</b> y un <b>Socio</b> de DEYMA. Te notificaremos por correo en cuanto se complete (típicamente 2-3 días hábiles).
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-white/10 p-4">
            <div className="label-overline text-amber-400">Folio de registro</div>
            <div className="font-mono text-2xl font-bold mt-1" data-testid="result-folio">{result.folio_registro}</div>
          </div>
          <div className="border border-white/10 p-4">
            <div className="label-overline text-amber-400">Estado actual</div>
            <div className="font-mono text-sm font-bold mt-1 text-amber-300 uppercase">{result.estado}</div>
          </div>
        </div>
        <div className="border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-amber-200">
          <b>Importante:</b> Se descargó automáticamente tu PDF de Alta. Guárdalo. Una vez aprobado, recibirás tu identificador <b>DFNUM-XXXXXX</b> con el que podrás ingresar al portal cliente.
        </div>
        <div className="flex items-center justify-between gap-3 pt-2">
          <button onClick={() => downloadPdf(`/clientes/${result.id}/pdf-alta`, `DEYMA_alta_${result.folio_registro}.pdf`)} data-testid="download-alta-pdf" className="btn-ghost flex items-center gap-1.5"><FileText size={14} /> Re-descargar PDF</button>
          <button onClick={onLogin} data-testid="goto-login" className="btn-primary">Volver al inicio</button>
        </div>
      </div>
    </div>
  );
}
