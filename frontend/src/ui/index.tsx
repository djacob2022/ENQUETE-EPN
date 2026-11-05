import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Check, CircleAlert, Info, Loader2, X } from "lucide-react";
import {
  ButtonHTMLAttributes, createContext, forwardRef, InputHTMLAttributes, ReactNode, SelectHTMLAttributes,
  TextareaHTMLAttributes, useCallback, useContext, useEffect, useId, useState,
} from "react";
import { createPortal } from "react-dom";
import { Statut } from "@/lib/types";

export const cx = clsx;

/* ---------- Bouton ---------- */

type Variante = "primaire" | "secondaire" | "fantome" | "danger" | "succes";
const variantes: Record<Variante, string> = {
  primaire: "bg-marque text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.18),0_1px_2px_rgb(15_23_42/0.2)] hover:bg-marque-fonce dark:text-[#04140c] dark:hover:bg-marque-fonce",
  secondaire: "bg-surface text-encre border border-trait shadow-sm hover:bg-relief",
  fantome: "text-encre hover:bg-relief",
  danger: "bg-surface text-danger border border-danger/30 hover:bg-danger-doux",
  succes: "bg-succes text-white hover:brightness-110 dark:text-[#04140c]",
};

export interface BoutonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  taille?: "sm" | "md" | "lg";
  chargement?: boolean;
  icone?: ReactNode;
}

export const Bouton = forwardRef<HTMLButtonElement, BoutonProps>(function Bouton(
  { variante = "secondaire", taille = "md", chargement, icone, className, children, disabled, ...props }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled || chargement}
      className={cx(
        "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-[10px] font-medium transition-all duration-150",
        "active:scale-[.98] disabled:pointer-events-none disabled:opacity-50",
        taille === "sm" && "h-9 px-3 text-[13px]",
        taille === "md" && "h-11 px-4 text-sm",
        taille === "lg" && "h-12 px-6 text-[15px]",
        variantes[variante], className)}
      {...props}
    >
      {chargement ? <Loader2 className="h-4 w-4 animate-spin" /> : icone}
      {children}
    </button>
  );
});

/* ---------- Champs ---------- */

const baseChamp =
  "w-full rounded-[10px] border bg-surface px-3.5 text-[15px] text-encre placeholder:text-discret/60 transition-shadow " +
  "focus:outline-none focus:border-marque focus:shadow-anneau disabled:opacity-60";

export function Etiquette({ htmlFor, children, obligatoire, code }: {
  htmlFor?: string; children: ReactNode; obligatoire?: boolean; code?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="flex items-baseline gap-2 text-sm font-medium text-encre">
      {code && <span className="font-mono text-[11px] font-medium text-discret">{code}</span>}
      <span>{children}{obligatoire && <span className="ml-0.5 text-danger" aria-hidden>*</span>}</span>
    </label>
  );
}

export function MessageChamp({ erreurs, aide, id }: { erreurs?: string[]; aide?: ReactNode; id?: string }) {
  if (erreurs?.length)
    return (
      <p id={id} role="alert" className="flex items-start gap-1.5 text-[13px] font-medium text-danger">
        <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />{erreurs.join(" ")}
      </p>
    );
  return aide ? <p id={id} className="text-[13px] text-discret">{aide}</p> : null;
}

interface ChampProps extends InputHTMLAttributes<HTMLInputElement> {
  libelle: string; erreurs?: string[]; aide?: ReactNode; suffixe?: ReactNode; code?: string;
}

export const Champ = forwardRef<HTMLInputElement, ChampProps>(function Champ(
  { libelle, erreurs, aide, suffixe, code, className, required, id, ...props }, ref) {
  const auto = useId();
  const ident = id ?? auto;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <Etiquette htmlFor={ident} obligatoire={required} code={code}>{libelle}</Etiquette>
      <div className="relative">
        <input
          ref={ref} id={ident} aria-invalid={!!erreurs?.length} aria-describedby={`${ident}-m`}
          className={cx(baseChamp, "h-11", suffixe && "pr-16", erreurs?.length && "border-danger focus:border-danger focus:shadow-none")}
          {...props}
        />
        {suffixe && <span className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-[13px] text-discret">{suffixe}</span>}
      </div>
      <MessageChamp id={`${ident}-m`} erreurs={erreurs} aide={aide} />
    </div>
  );
});

export function ZoneTexte({ libelle, erreurs, aide, code, required, ...props }:
  TextareaHTMLAttributes<HTMLTextAreaElement> & { libelle: string; erreurs?: string[]; aide?: ReactNode; code?: string }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <Etiquette htmlFor={id} obligatoire={required} code={code}>{libelle}</Etiquette>
      <textarea id={id} rows={4} aria-invalid={!!erreurs?.length}
        className={cx(baseChamp, "min-h-[110px] resize-y py-3 leading-relaxed", erreurs?.length && "border-danger")} {...props} />
      <MessageChamp erreurs={erreurs} aide={aide} />
    </div>
  );
}

export function Liste({ libelle, children, className, ...props }:
  SelectHTMLAttributes<HTMLSelectElement> & { libelle?: string }) {
  const id = useId();
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      {libelle && <label htmlFor={id} className="text-[13px] font-medium text-discret">{libelle}</label>}
      <select id={id}
        className={cx(baseChamp, "h-10 cursor-pointer appearance-none bg-[length:16px] bg-[right_12px_center] bg-no-repeat pr-9 text-sm")}
        style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")" }}
        {...props}>{children}</select>
    </div>
  );
}

/* ---------- Surfaces ---------- */

export function Carte({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("rounded-2xl border border-trait bg-surface shadow-carte", className)} {...props}>{children}</div>;
}

export function EnTeteCarte({ titre, sous, actions }: { titre: ReactNode; sous?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-6 pt-5">
      <div>
        <h2 className="text-[15px] font-semibold tracking-tight">{titre}</h2>
        {sous && <p className="mt-0.5 text-[13px] text-discret">{sous}</p>}
      </div>
      {actions}
    </div>
  );
}

const couleursStatut: Record<Statut, string> = {
  valide: "bg-succes-doux text-succes ring-succes/20",
  soumis: "bg-marque-doux text-marque ring-marque/20",
  en_revue: "bg-accent-doux text-accent-fonce ring-accent/20",
  a_corriger: "bg-danger-doux text-danger ring-danger/20",
  en_cours: "bg-alerte-doux text-alerte ring-alerte/20",
  invite: "bg-relief text-discret ring-trait",
};
export const libellesStatut: Record<Statut, string> = {
  valide: "Validé", soumis: "Soumis", en_revue: "En revue", a_corriger: "À corriger", en_cours: "Brouillon", invite: "Non commencé",
};

export function BadgeStatut({ statut }: { statut: Statut }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", couleursStatut[statut])}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />{libellesStatut[statut]}
    </span>
  );
}

export function Badge({ children, ton = "neutre" }: { children: ReactNode; ton?: "neutre" | "marque" | "succes" | "alerte" | "danger" }) {
  const tons = {
    neutre: "bg-relief text-discret", marque: "bg-marque-doux text-marque", succes: "bg-succes-doux text-succes",
    alerte: "bg-alerte-doux text-alerte", danger: "bg-danger-doux text-danger",
  };
  return <span className={cx("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium", tons[ton])}>{children}</span>;
}

export function Progression({ valeur, className, ton = "marque" }: { valeur: number; className?: string; ton?: "marque" | "succes" }) {
  return (
    <div className={cx("h-1.5 overflow-hidden rounded-full bg-relief", className)} role="progressbar" aria-valuenow={valeur} aria-valuemin={0} aria-valuemax={100}>
      <motion.div className={cx("h-full rounded-full", ton === "succes" ? "bg-succes" : "bg-marque")}
        initial={{ width: 0 }} animate={{ width: `${valeur}%` }} transition={{ duration: 0.8, ease: [0.2, 0.8, 0.2, 1] }} />
    </div>
  );
}

export function Anneau({ valeur, taille = 120, epaisseur = 10, children }: { valeur: number; taille?: number; epaisseur?: number; children?: ReactNode }) {
  const r = (taille - epaisseur) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative grid place-items-center" style={{ width: taille, height: taille }}>
      <svg width={taille} height={taille} className="-rotate-90" aria-hidden>
        <circle cx={taille / 2} cy={taille / 2} r={r} fill="none" strokeWidth={epaisseur} className="stroke-relief" />
        <motion.circle cx={taille / 2} cy={taille / 2} r={r} fill="none" strokeWidth={epaisseur} strokeLinecap="round"
          className="stroke-marque" strokeDasharray={c} initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - valeur / 100) }} transition={{ duration: 1.1, ease: [0.2, 0.8, 0.2, 1] }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}

export function Squelette({ className }: { className?: string }) {
  return (
    <div className={cx("relative overflow-hidden rounded-lg bg-relief", className)}>
      <div className="absolute inset-0 -translate-x-full animate-miroiter bg-gradient-to-r from-transparent via-white/40 to-transparent dark:via-white/5" />
    </div>
  );
}

export function Vide({ icone, titre, texte, action }: { icone: ReactNode; titre: string; texte?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-relief text-discret">{icone}</div>
      <div>
        <p className="font-medium">{titre}</p>
        {texte && <p className="mx-auto mt-1 max-w-sm text-sm text-discret">{texte}</p>}
      </div>
      {action}
    </div>
  );
}

export function Avatar({ texte, className }: { texte: string; className?: string }) {
  return (
    <span className={cx("grid h-8 w-8 shrink-0 place-items-center rounded-full bg-marque-doux text-xs font-semibold text-marque", className)}>
      {texte}
    </span>
  );
}

/* ---------- Tiroir latéral et boîte de dialogue ---------- */

function useEchap(ouvert: boolean, fermer: () => void) {
  useEffect(() => {
    if (!ouvert) return;
    const f = (e: KeyboardEvent) => e.key === "Escape" && fermer();
    document.addEventListener("keydown", f);
    const ancien = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", f); document.body.style.overflow = ancien; };
  }, [ouvert, fermer]);
}

export function Tiroir({ ouvert, fermer, titre, children, largeur = 720 }: {
  ouvert: boolean; fermer: () => void; titre: ReactNode; children: ReactNode; largeur?: number;
}) {
  useEchap(ouvert, fermer);
  return createPortal(
    <AnimatePresence>
      {ouvert && (
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
          <motion.div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={fermer}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.aside
            className="absolute inset-y-0 right-0 flex w-full flex-col border-l border-trait bg-fond shadow-flottant"
            style={{ maxWidth: largeur }}
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 32, stiffness: 320 }}>
            <div className="flex items-center justify-between gap-4 border-b border-trait bg-surface px-6 py-4">
              <div className="min-w-0 flex-1">{titre}</div>
              <Bouton variante="fantome" taille="sm" onClick={fermer} aria-label="Fermer"><X className="h-4 w-4" /></Bouton>
            </div>
            <div className="defilement-fin flex-1 overflow-y-auto">{children}</div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export function Dialogue({ ouvert, fermer, titre, description, children }: {
  ouvert: boolean; fermer: () => void; titre: string; description?: string; children: ReactNode;
}) {
  useEchap(ouvert, fermer);
  return createPortal(
    <AnimatePresence>
      {ouvert && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={titre}>
          <motion.div className="absolute inset-0 bg-black/45 backdrop-blur-sm" onClick={fermer}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div className="relative w-full max-w-lg rounded-2xl border border-trait bg-surface p-6 shadow-flottant"
            initial={{ opacity: 0, scale: 0.96, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
            transition={{ duration: 0.18 }}>
            <h2 className="text-lg font-semibold tracking-tight">{titre}</h2>
            {description && <p className="mt-1 text-sm text-discret">{description}</p>}
            <div className="mt-5">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/* ---------- Notifications ---------- */

type Toast = { id: number; ton: "succes" | "erreur" | "info"; texte: string };
const ContexteToast = createContext<(ton: Toast["ton"], texte: string) => void>(() => {});
export const useToast = () => useContext(ContexteToast);

export function FournisseurToast({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const afficher = useCallback((ton: Toast["ton"], texte: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, ton, texte }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4800);
  }, []);
  return (
    <ContexteToast.Provider value={afficher}>
      {children}
      <div className="pointer-events-none fixed right-5 top-5 z-[60] flex w-[min(380px,calc(100vw-40px))] flex-col gap-2" aria-live="polite">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div key={t.id} layout initial={{ opacity: 0, y: -12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40 }} transition={{ duration: 0.2 }}
              className="pointer-events-auto flex items-start gap-3 rounded-xl border border-trait bg-surface px-4 py-3 text-sm shadow-flottant">
              <span className={cx("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full",
                t.ton === "succes" && "bg-succes-doux text-succes", t.ton === "erreur" && "bg-danger-doux text-danger",
                t.ton === "info" && "bg-marque-doux text-marque")}>
                {t.ton === "succes" ? <Check className="h-3 w-3" strokeWidth={3} /> : t.ton === "erreur" ? <X className="h-3 w-3" strokeWidth={3} /> : <Info className="h-3 w-3" />}
              </span>
              <span className="flex-1 leading-snug">{t.texte}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ContexteToast.Provider>
  );
}

/* ---------- Divers ---------- */

export function Logo({ compact = false, clair = false }: { compact?: boolean; clair?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className={cx("grid h-9 w-9 place-items-center rounded-lg", clair ? "bg-white" : "bg-institution")}>
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden
          stroke={clair ? "rgb(var(--institution))" : "#fff"}>
          <path d="M4 20h16M6 20V10M10 20V10M14 20V10M18 20V10M3 10h18L12 4Z" />
        </svg>
      </span>
      {!compact && (
        <span className="leading-tight">
          <span className={cx("block text-[15px] font-bold tracking-tight", clair && "text-white")}>Enquête EPN</span>
          <span className={cx("block text-[11px]", clair ? "text-white/70" : "text-discret")}>Établissements Publics Nationaux</span>
        </span>
      )}
    </span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded-md border border-trait bg-relief px-1.5 py-0.5 font-mono text-[11px] text-discret">{children}</kbd>;
}
