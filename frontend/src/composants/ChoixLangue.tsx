import { useQueryClient } from "@tanstack/react-query";
import { changerLangue, Langue, t, useLangue } from "@/lib/langue";
import { cx } from "@/ui";

/** Sélecteur FR / EN du parcours de l'établissement (F-16). Recharge le questionnaire dans la langue choisie. */
export default function ChoixLangue({ className }: { className?: string }) {
  const langue = useLangue();
  const client = useQueryClient();
  const choisir = (l: Langue) => {
    if (l === langue) return;
    changerLangue(l);
    client.invalidateQueries();
  };
  return (
    <div role="group" aria-label={t("Langue")} className={cx("inline-flex rounded-lg border border-trait bg-surface p-0.5 text-xs font-semibold", className)}>
      {(["fr", "en"] as const).map((l) => (
        <button key={l} type="button" onClick={() => choisir(l)} aria-pressed={langue === l} lang={l}
          title={l === "fr" ? "Français" : "English"}
          className={cx("rounded-md px-2.5 py-1 uppercase transition", langue === l ? "bg-marque text-white dark:text-[#04140c]" : "text-discret hover:text-encre")}>
          {l}
        </button>
      ))}
    </div>
  );
}
