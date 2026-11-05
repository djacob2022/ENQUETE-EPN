import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, History, Lock, Search } from "lucide-react";
import { useState } from "react";
import { api, avecParams } from "@/lib/api";
import { date } from "@/lib/format";
import { Choix, LigneJournal } from "@/lib/types";
import { Badge, Bouton, Carte, Liste, Squelette, Vide } from "@/ui";
import { EnTetePage } from "./Gestion";

const TONS: Record<string, "succes" | "danger" | "alerte" | "marque" | "neutre"> = {
  validation: "succes", soumission: "succes", correction: "alerte", connexion_echec: "danger", export: "marque", compte: "marque",
};

function resume(d: Record<string, unknown>) {
  const morceaux: string[] = [];
  if (d.format) morceaux.push(String(d.format).toUpperCase());
  if (d.n !== undefined) morceaux.push(`${d.n} réponse(s)`);
  if (d.base) morceaux.push(`base : ${d.base}`);
  if (d.version) morceaux.push(`version ${d.version}`);
  if (d.role) morceaux.push(`rôle : ${d.role}`);
  if (d.changements && typeof d.changements === "object")
    morceaux.push(Object.entries(d.changements as Record<string, unknown[]>).map(([k, [a, b]]) => `${k} : ${a || "∅"} → ${b || "∅"}`).join(" ; "));
  if (d.commentaires && typeof d.commentaires === "object") morceaux.push(`${Object.keys(d.commentaires as object).length} commentaire(s)`);
  return morceaux.join(" · ");
}

/** Journal d'audit (F-46) : consultation seule. */
export default function Journal() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [texte, setTexte] = useState("");
  const q = useQuery({
    queryKey: ["journal", page, action, texte],
    queryFn: () => api.get<{ lignes: LigneJournal[]; page: number; pages: number; total: number; actions: Choix[] }>(
      avecParams("/api/gestion/journal/", { page, action, q: texte })),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <EnTetePage titre="Journal d'audit"
        sous={<span className="inline-flex items-center gap-1.5"><Lock className="h-3.5 w-3.5" /> Qui a créé, modifié, validé ou exporté quoi, et quand. Non modifiable, conservé au moins 3 ans.</span>} />
      <Carte className="overflow-hidden">
        <div className="flex flex-wrap items-end gap-3 border-b border-trait p-4">
          <label className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-discret" />
            <input value={texte} onChange={(e) => { setTexte(e.target.value); setPage(1); }} placeholder="Rechercher une personne, un établissement…" aria-label="Rechercher"
              className="h-10 w-full rounded-[10px] border border-trait bg-surface pl-9 pr-3 text-sm focus:border-marque focus:outline-none" />
          </label>
          <Liste value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} aria-label="Action" className="w-56">
            <option value="">Toutes les actions</option>
            {q.data?.actions.map((a) => <option key={a.valeur} value={a.valeur}>{a.libelle}</option>)}
          </Liste>
        </div>
        <div className="defilement-fin overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="bg-relief/50 text-left text-xs uppercase tracking-wider text-discret">
              <tr><th className="px-6 py-3 font-medium">Date</th><th className="px-4 py-3 font-medium">Auteur</th><th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Objet</th><th className="px-4 py-3 pr-6 font-medium">Détail</th></tr>
            </thead>
            <tbody className="divide-y divide-trait">
              {q.isLoading && <tr><td colSpan={5} className="p-6"><Squelette className="h-40" /></td></tr>}
              {q.data?.lignes.map((l) => (
                <tr key={l.id}>
                  <td className="whitespace-nowrap px-6 py-2.5 text-discret chiffres">{date(l.date, true)}</td>
                  <td className="px-4 py-2.5 font-medium">{l.auteur || "—"}<span className="block text-[11px] font-normal text-discret">{l.ip}</span></td>
                  <td className="px-4 py-2.5"><Badge ton={TONS[l.action] ?? "neutre"}>{l.libelle}</Badge></td>
                  <td className="px-4 py-2.5">{l.objet}</td>
                  <td className="px-4 py-2.5 pr-6 text-xs text-discret">{resume(l.detail)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {q.data && !q.data.lignes.length && <Vide icone={<History className="h-5 w-5" />} titre="Aucune entrée" />}
        </div>
        {q.data && q.data.pages > 1 && (
          <div className="flex items-center justify-between border-t border-trait px-6 py-3 text-sm text-discret">
            <span>{q.data.total} entrées · page {q.data.page} sur {q.data.pages}</span>
            <div className="flex gap-1">
              <Bouton taille="sm" variante="fantome" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Page précédente"><ChevronLeft className="h-4 w-4" /></Bouton>
              <Bouton taille="sm" variante="fantome" disabled={page >= q.data.pages} onClick={() => setPage((p) => p + 1)} aria-label="Page suivante"><ChevronRight className="h-4 w-4" /></Bouton>
            </div>
          </div>
        )}
      </Carte>
    </>
  );
}
