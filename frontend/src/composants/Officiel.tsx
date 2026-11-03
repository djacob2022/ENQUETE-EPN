import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cx } from "@/ui";

export interface Config { pays: string; devise: string; ministere: string; institution: string; lien_public: string }

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => api.get<Config>("/api/config/"), staleTime: Infinity }).data;
}

/** Emblème neutre (écu tricolore) : à remplacer par les armoiries officielles fournies par l'institution. */
export function Embleme({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 46" className={cx("h-10 w-9 shrink-0", className)} role="img" aria-label="Emblème">
      <defs>
        <clipPath id="ecu"><path d="M20 1.5 37.5 7v15.5C37.5 33.5 29.8 41 20 44.5 10.2 41 2.5 33.5 2.5 22.5V7Z" /></clipPath>
      </defs>
      <g clipPath="url(#ecu)">
        <rect width="14" height="46" fill="rgb(var(--accent))" />
        <rect x="13.33" width="13.34" height="46" fill="#fff" />
        <rect x="26.66" width="14" height="46" fill="rgb(var(--marque))" />
      </g>
      <path d="M20 1.5 37.5 7v15.5C37.5 33.5 29.8 41 20 44.5 10.2 41 2.5 33.5 2.5 22.5V7Z" fill="none" stroke="rgb(var(--institution))" strokeWidth="1.6" />
      <path d="m20 15.5 2.1 4.4 4.8.6-3.5 3.3.9 4.8-4.3-2.3-4.3 2.3.9-4.8-3.5-3.3 4.8-.6Z" fill="rgb(var(--institution))" />
    </svg>
  );
}

/** Bandeau tricolore + en-tête officiel, en haut de toutes les pages. */
export function BandeauOfficiel({ compact = false, droite }: { compact?: boolean; droite?: React.ReactNode }) {
  const c = useConfig();
  return (
    <div className="bg-surface">
      <div className="tricolore h-1.5" aria-hidden />
      <div className={cx("mx-auto flex max-w-7xl items-center gap-4 px-4 sm:px-6", compact ? "py-2.5" : "py-4")}>
        <Embleme className={compact ? "h-8 w-7" : undefined} />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-[13px] font-extrabold uppercase tracking-[.08em] text-institution dark:text-encre">{c?.pays ?? " "}</p>
          <p className="truncate text-[12px] italic text-discret">{c?.devise ?? " "}</p>
        </div>
        {!compact && c && (
          <div className="hidden max-w-xs border-l border-trait pl-4 text-right leading-tight md:block">
            <p className="text-[13px] font-semibold">{c.ministere}</p>
            <p className="text-[12px] text-discret">{c.institution}</p>
          </div>
        )}
        {droite}
      </div>
      <div className="h-px bg-trait" />
    </div>
  );
}
