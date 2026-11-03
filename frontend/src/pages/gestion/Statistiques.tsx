import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download } from "lucide-react";
import { useState } from "react";
import { api, avecParams } from "@/lib/api";
import { decimal, nombre, pourcent } from "@/lib/format";
import { StatFrequence, StatNumerique, Statistiques as Stats } from "@/lib/types";
import { Carte, cx, Liste, Squelette, Vide } from "@/ui";
import { EnTetePage, SansCampagne, useGestion } from "./Gestion";

export default function Statistiques() {
  const { campagne, options } = useGestion();
  const [filtres, setFiltres] = useState({ tutelle: "", categorie: "", toutes: "" });
  const q = useQuery({
    queryKey: ["stats", campagne?.id, filtres],
    queryFn: () => api.get<Stats>(avecParams("/api/gestion/statistiques/", { campagne: campagne?.id, ...filtres })),
    enabled: !!campagne, placeholderData: (p) => p,
  });
  if (!campagne) return <SansCampagne />;
  const d = q.data;

  return (
    <>
      <EnTetePage titre="Statistiques"
        sous={d ? `Calculées sur ${d.n} réponse${d.n > 1 ? "s" : ""} ${filtres.toutes ? "(envoyées et en cours)" : "envoyée" + (d.n > 1 ? "s" : "")} · ${campagne.nom}` : "…"}
        actions={<a href={avecParams("/api/gestion/export.xlsx", { campagne: campagne.id, ...filtres })}
          className="inline-flex h-11 items-center gap-2 rounded-[10px] bg-marque px-4 text-sm font-medium text-white shadow-sm hover:bg-marque-fonce dark:text-[#06101f]">
          <Download className="h-4 w-4" /> Exporter en Excel</a>} />

      <Carte className="mb-6 flex flex-wrap items-end gap-3 p-4">
        <Liste libelle="Tutelle" value={filtres.tutelle} onChange={(e) => setFiltres({ ...filtres, tutelle: e.target.value })} className="w-52">
          <option value="">Toutes</option>{options.tutelles.map((t) => <option key={t}>{t}</option>)}
        </Liste>
        <Liste libelle="Catégorie" value={filtres.categorie} onChange={(e) => setFiltres({ ...filtres, categorie: e.target.value })} className="w-44">
          <option value="">Toutes</option>{options.categories.map((c) => <option key={c.valeur} value={c.valeur}>{c.libelle}</option>)}
        </Liste>
        <label className="flex h-10 cursor-pointer items-center gap-2.5 rounded-[10px] border border-trait px-3 text-sm">
          <input type="checkbox" checked={!!filtres.toutes} onChange={(e) => setFiltres({ ...filtres, toutes: e.target.checked ? "1" : "" })} className="h-4 w-4 accent-[rgb(var(--marque))]" />
          Inclure les réponses en cours
        </label>
        {q.isFetching && <span className="ml-auto text-xs text-discret">Mise à jour…</span>}
      </Carte>

      {!d ? <div className="grid gap-4 sm:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Squelette key={i} className="h-28 rounded-2xl" />)}</div> : d.n === 0 ? (
        <Carte><Vide icone={<BarChart3 className="h-5 w-5" />} titre="Pas encore de données" texte="Les statistiques apparaissent dès qu'un établissement a envoyé ses réponses." /></Carte>
      ) : (
        <div className={cx("space-y-8 transition-opacity", q.isFetching && "opacity-60")}>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {d.indicateurs.map((i) => (
              <Carte key={i.libelle} className="p-5">
                <p className="text-sm text-discret">{i.libelle}</p>
                <p className="chiffres mt-2 text-3xl font-semibold tracking-tight">{pourcent(i.valeur)}</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-relief"><div className="h-full rounded-full bg-marque" style={{ width: `${Math.min(i.valeur ?? 0, 100)}%` }} /></div>
                <p className="mt-2 text-xs text-discret">{i.formule}</p>
              </Carte>
            ))}
          </section>

          {d.blocs.map((b) => {
            const numeriques = b.questions.filter((x) => x.genre === "numerique") as { code: string; libelle: string; stats: StatNumerique }[];
            const frequences = b.questions.filter((x) => x.genre === "frequence") as { code: string; libelle: string; type: string; stats: StatFrequence }[];
            return (
              <section key={b.code}>
                <h2 className="mb-3 flex items-baseline gap-3 text-lg font-semibold tracking-tight"><span className="font-mono text-sm text-discret">{b.code}</span>{b.titre}</h2>
                {numeriques.length > 0 && (
                  <Carte className="mb-4 overflow-hidden">
                    <div className="defilement-fin overflow-x-auto">
                      <table className="w-full min-w-[760px] text-sm">
                        <thead className="bg-relief/50 text-right text-xs uppercase tracking-wider text-discret">
                          <tr>{["Variable", "n", "Somme", "Moyenne", "Médiane", "Min", "Max", "Écart-type"].map((h, i) =>
                            <th key={h} className={cx("px-4 py-3 font-medium", i === 0 && "pl-6 text-left")}>{h}</th>)}</tr>
                        </thead>
                        <tbody className="chiffres divide-y divide-trait text-right">
                          {numeriques.map(({ code, libelle, stats: s }) => (
                            <tr key={code} className="hover:bg-relief/40">
                              <td className="py-2.5 pl-6 pr-4 text-left"><span className="mr-2 font-mono text-xs text-discret">{code}</span>{libelle}</td>
                              <td className="px-4 text-discret">{s.n}</td>
                              <td className="px-4 font-medium">{nombre(s.somme)}</td><td className="px-4">{decimal(s.moyenne)}</td>
                              <td className="px-4">{decimal(s.mediane)}</td><td className="px-4 text-discret">{nombre(s.min)}</td>
                              <td className="px-4 text-discret">{nombre(s.max)}</td><td className="px-4 pr-6 text-discret">{decimal(s.ecart_type)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Carte>
                )}
                {frequences.length > 0 && (
                  <div className="grid gap-4 lg:grid-cols-2">
                    {frequences.map(({ code, libelle, type, stats: s }) => (
                      <Carte key={code} className="p-5">
                        <p className="text-sm font-medium"><span className="mr-2 font-mono text-xs text-discret">{code}</span>{libelle}</p>
                        <p className="text-xs text-discret">n = {s.n}{type === "choix_multiple" && " · plusieurs réponses possibles"}</p>
                        <ul className="mt-4 space-y-3">
                          {s.lignes.map((l) => {
                            const max = Math.max(...s.lignes.map((x) => x.effectif));
                            return (
                              <li key={l.code}>
                                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                                  <span className="min-w-0">{l.libelle}</span>
                                  <span className="chiffres shrink-0 text-discret"><strong className="text-encre">{Math.round(l.pourcentage)} %</strong> · {l.effectif}</span>
                                </div>
                                <div className="h-2 overflow-hidden rounded-full bg-relief">
                                  <div className={cx("h-full rounded-full transition-all duration-700", l.effectif === max && max > 0 ? "bg-marque" : "bg-marque/45")}
                                    style={{ width: `${l.pourcentage}%` }} />
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      </Carte>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
