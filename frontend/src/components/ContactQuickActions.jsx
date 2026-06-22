import React from "react";
import { MessageCircle, Mail, Phone, Linkedin } from "lucide-react";

/**
 * Botones inline reutilizables para CUALQUIER contacto del CRM.
 * Click-to-action directo a WhatsApp/Email/Teléfono/LinkedIn con plantilla opcional.
 *
 * Props:
 *   tel: string (cualquier formato — se normaliza)
 *   email: string
 *   linkedin: string (URL completa)
 *   mensaje: string (plantilla pre-llenada para WhatsApp/Email body)
 *   subject: string (asunto del email)
 *   size: "xs" | "sm" (default "xs")
 *   testIdPrefix: string (default "cqa")
 */
export default function ContactQuickActions({
  tel,
  email,
  linkedin,
  mensaje = "",
  subject = "DEYMA · Seguimiento comercial",
  size = "xs",
  testIdPrefix = "cqa",
}) {
  const normTel = (tel || "").replace(/[^\d+]/g, "").replace(/^\+/, "");
  const waLink = normTel ? `https://wa.me/${normTel}${mensaje ? `?text=${encodeURIComponent(mensaje)}` : ""}` : null;
  const telLink = normTel ? `tel:+${normTel}` : null;
  const mailLink = email
    ? `mailto:${email}?subject=${encodeURIComponent(subject)}${mensaje ? `&body=${encodeURIComponent(mensaje)}` : ""}`
    : null;

  const sz = size === "sm" ? { btn: "p-1.5", icon: 13 } : { btn: "p-1", icon: 11 };

  if (!waLink && !mailLink && !telLink && !linkedin) {
    return <span className="text-[10px] text-zinc-600 font-mono">— sin contacto —</span>;
  }

  return (
    <div className="inline-flex items-center gap-1" data-testid={`${testIdPrefix}-actions`}>
      {waLink && (
        <a
          href={waLink}
          target="_blank"
          rel="noreferrer"
          title="WhatsApp"
          data-testid={`${testIdPrefix}-wa`}
          className={`${sz.btn} bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/30 transition-colors`}
        >
          <MessageCircle size={sz.icon} strokeWidth={2.4}/>
        </a>
      )}
      {telLink && (
        <a
          href={telLink}
          title={`Llamar ${normTel}`}
          data-testid={`${testIdPrefix}-tel`}
          className={`${sz.btn} bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 border border-sky-500/30 transition-colors`}
        >
          <Phone size={sz.icon} strokeWidth={2.4}/>
        </a>
      )}
      {mailLink && (
        <a
          href={mailLink}
          title={`Email a ${email}`}
          data-testid={`${testIdPrefix}-mail`}
          className={`${sz.btn} bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-500/30 transition-colors`}
        >
          <Mail size={sz.icon} strokeWidth={2.4}/>
        </a>
      )}
      {linkedin && (
        <a
          href={linkedin}
          target="_blank"
          rel="noreferrer"
          title="LinkedIn"
          data-testid={`${testIdPrefix}-li`}
          className={`${sz.btn} bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 border border-indigo-500/30 transition-colors`}
        >
          <Linkedin size={sz.icon} strokeWidth={2.4}/>
        </a>
      )}
    </div>
  );
}
