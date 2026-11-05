import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, BarChart3, FileSpreadsheet, Grid3x3, LineChart as IconeCourbe } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, avecParams } from "@/lib/api";
import { compacte, decimal, nombre, pourcent } from "@/lib/format";
import { StatFrequence, StatNumerique, Statistiques as Stats, TableauCroise } from "@/lib/types";
import { Carte, cx, EnTeteCarte, Liste, Squelette, Vide } from "@/ui";
import { EnTetePage, peut, SansCampagne, useGestion } from "./Gestion";
import { MenuExport } from "./Reponses";
import { COULEURS, InfoBulle } from "./TableauDeBord";

// Teintes nettement distinctes (vert, orange, bleu, violet, rouge, ocre, gris) : lisibles dans les deux thèmes.
const SERIES = ["rgb(var(--marque))", "rgb(var(--accent))", "#3b82f6", "#8b5cf6", "rgb(var(--danger))", "rgb(var(--alerte))", "rgb(var(--discret))"];
const BASES = { validees: "réponses validées", envoyees: "réponses envoyées", toutes: "réponses, brouillons compris", statut: "réponses du statut choisi" };

function Evolution({ n, n1 }: { n?: number | null; n1?: number | null }) {
  if (n === null || n === undefined || !n1) return <span className="text-discret">—</span>;
  const e = (100 * (n - n1)) / Math.abs(n1);
  const I = e >= 0 ? ArrowUpRight : ArrowDownRight;
  return <span className={cx("inline-flex items-center gap-0.5", Math.abs(e) > 50 ? "font-medium text-alerte" : "text-discret")}><I className="h-3 w-3" />{e > 0 ? "+" : ""}{decimal(e)} %</span>;
}

export default function Statistiques() {
  const { campagne, options, moi } = useGestion();
  const [filtres, setFiltres] = useState({ tutelle: "", categorie: "", region: "", base: "validees" });
  const [variable, setVariable] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["stats", campagne?.id, filtres],
    queryFn: () => api.get<Stats>(avecParams("/api/gestion/statistiques/", { campagne: campagne?.id, ...filtres })),
    enabled: !!campagne, placeholderData: keepPreviousData,
  });
  if (!campagne) return <SansCampagne />;
  const d = q.data;
  const params = { campagne: campagne.id, ...filtres };
  const numeriques = d?.blocs.flatMap((b) => b.questions.filter((x) => x.genre === "numerique")) as
    ({ code: string; libelle: string; unite?: string; stats: StatNumerique; precedent?: StatNumerique }[] | undefined);
  const avecHisto = (x: { stats: StatNumerique }) => (x.stats.histogramme?.length ?? 0) > 0;
  const choisie = numeriques?.find((x) => x.code === variable && avecHisto(x)) ?? numeriques?.find((x) => x.code === "D01" && avecHisto(x))
    ?? numeriques?.find(avecHisto);
  const prec = d?.precedente;

  return (
    <>
      <EnTetePage titre="Statistiques"
        sous={d ? `n = ${d.n} ${BASES[d.base]} · ${campagne.nom}${prec ? ` · comparaison avec ${prec.campagne.nom} (n = ${prec.n})` : ""}` : "…"}
        actions={<>
          <a href={avecParams("/api/gestion/statistiques.xlsx", params)}
            className="inline-flex h-11 items-center gap-2 rounded-[10px] border border-trait bg-surface px-4 text-sm font-medium shadow-sm hover:bg-relief">
            <FileSpreadsheet className="h-4 w-4 text-succes" /> Tableaux et graphiques Excel</a>
          {peut(moi, "exporter") && <MenuExport params={{ campagne: campagne.id, tutelle: filtres.tutelle, categorie: filtres.categorie, region: filtres.region }} />}
        </>} />

      <Carte className="mb-6 flex flex-wrap items-end gap-3 p-4">
        <Liste libelle="Réponses prises en compte" value={filtres.base} onChange={(e) => setFiltres({ ...filtres, base: e.target.value })} className="w-60">
          <option value="validees">Validées (par défaut)</option><option value="envoyees">Envoyées (soumises et validées)</option><option value="toutes">Toutes, brouillons compris</option>
        </Liste>
        <Liste libelle="Tutelle" value={filtres.tutelle} onChange={(e) => setFiltres({ ...filtres, tutelle: e.target.value })} className="w-48">
          <option value="">Toutes</option>{options.tutelles.map((t) => <option key={t}>{t}</option>)}
        </Liste>
        <Liste libelle="Catégorie" value={filtres.categorie} onChange={(e) => setFiltres({ ...filtres, categorie: e.target.value })} className="w-40">
          <option value="">Toutes</option>{options.categories.map((c) => <option key={c.valeur} value={c.valeur}>{c.libelle}</option>)}
        </Liste>
        <Liste libelle="Région" value={filtres.region} onChange={(e) => setFiltres({ ...filtres, region: e.target.value })} className="w-40">
          <option value="">Toutes</option>{options.regions.map((t) => <option key={t}>{t}</option>)}
        </Liste>
        {q.isFetching && <span className="ml-auto text-xs text-discret">Mise à jour…</span>}
      </Carte>

      {!d ? <div className="grid gap-4 sm:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <Squelette key={i} className="h-28 rounded-2xl" />)}</div> : d.n === 0 ? (
        <Carte><Vide icone={<BarChart3 className="h-5 w-5" />} titre="Pas encore de données"
          texte={filtres.base === "validees" ? "Aucune réponse validée pour ces critères. Choisissez « Envoyées » pour voir les réponses en attente de validation." : "Aucune réponse pour ces critères."} /></Carte>
      ) : (
        <div className={cx("space-y-8 transition-opacity", q.isFetching && "opacity-60")}>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {d.indicateurs.map((i) => {
              const avant = prec?.indicateurs.find((x) => x.libelle === i.libelle)?.valeur;
              return (
                <Carte key={i.libelle} className="p-5">
                  <p className="text-sm text-discret">{i.libelle}</p>
                  <p className="chiffres mt-2 text-3xl font-semibold tracking-tight">{pourcent(i.valeur)}</p>
                  {prec && <p className="chiffres mt-1 text-xs text-discret">N-1 : {pourcent(avant)} {avant !== null && avant !== undefined && i.valeur !== null &&
                    <span>({i.valeur >= avant ? "+" : ""}{decimal(i.valeur - avant)} pt)</span>}</p>}
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-relief"><div className="h-full rounded-full bg-marque" style={{ width: `${Math.min(i.valeur ?? 0, 100)}%` }} /></div>
                  <p className="mt-2 text-xs text-discret">{i.formule} · n = {d.n}</p>
                </Carte>
              );
            })}
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            {choisie && (
              <Carte>
                <EnTeteCarte titre="Répartition d'une variable" sous={`Histogramme · n = ${choisie.stats.n}`}
                  actions={<Liste value={choisie.code} onChange={(e) => setVariable(e.target.value)} aria-label="Variable" className="w-56">
                    {numeriques!.filter((x) => (x.stats.histogramme?.length ?? 0) > 0).map((x) => <option key={x.code} value={x.code}>{x.code} · {x.libelle}</option>)}
                  </Liste>} />
                <div className="h-[260px] px-2 pb-4 pt-4">
                  <ResponsiveContainer>
                    <BarChart data={(choisie.stats.histogramme ?? []).map((c) => ({ libelle: `${compacte(c.de)} – ${compacte(c.a)}`, effectif: c.effectif }))} margin={{ left: 0, right: 12, top: 8 }}>
                      <CartesianGrid vertical={false} stroke={COULEURS.trait} strokeDasharray="3 3" />
                      <XAxis dataKey="libelle" tick={{ fill: COULEURS.discret, fontSize: 11 }} axisLine={false} tickLine={false} interval={0} />
                      <YAxis allowDecimals={false} tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} width={32} />
                      <Tooltip cursor={{ fill: "rgb(var(--relief))" }} content={<InfoBulle suffixe=" EPN" />} />
                      <Bar dataKey="effectif" name="EPN" fill={COULEURS.marque} radius={[6, 6, 0, 0]} isAnimationActive={false} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Carte>
            )}
            {d.historique.length >= 2 && (
              <Carte>
                <EnTeteCarte titre="Évolution du taux de réponse" sous="Par exercice de référence" />
                <div className="h-[260px] px-2 pb-4 pt-4">
                  <ResponsiveContainer>
                    <LineChart data={d.historique} margin={{ left: 0, right: 16, top: 8 }}>
                      <CartesianGrid vertical={false} stroke={COULEURS.trait} strokeDasharray="3 3" />
                      <XAxis dataKey="libelle" tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tickFormatter={(v) => `${v} %`} tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} width={48} />
                      <Tooltip content={<InfoBulle suffixe=" %" />} />
                      <Line type="monotone" dataKey="taux" name="Taux" stroke={COULEURS.marque} strokeWidth={2.5} dot={{ r: 4, fill: COULEURS.marque }} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Carte>
            )}
          </div>

          <Croisement variables={d.variables} params={params} />

          {d.blocs.map((b) => {
            const nums = b.questions.filter((x) => x.genre === "numerique") as { code: string; libelle: string; stats: StatNumerique; precedent?: StatNumerique }[];
            const frequences = b.questions.filter((x) => x.genre === "frequence") as { code: string; libelle: string; type: string; stats: StatFrequence }[];
            return (
              <section key={b.code}>
                <h2 className="mb-3 flex items-baseline gap-3 text-lg font-semibold tracking-tight"><span className="font-mono text-sm text-discret">{b.code}</span>{b.titre}</h2>
                {nums.length > 0 && (
                  <Carte className="mb-4 overflow-hidden">
                    <div className="defilement-fin overflow-x-auto">
                      <table className="w-full min-w-[980px] text-sm">
                        <thead className="bg-relief/50 text-right text-xs uppercase tracking-wider text-discret">
                          <tr>{["Variable", "n", "Somme", "Moyenne", "Médiane", "Min", "Q1", "Q3", "Max", "Écart-type", ...(prec ? ["Somme N-1", "Évolution"] : [])].map((h, i) =>
                            <th key={h} className={cx("px-3 py-3 font-medium", i === 0 && "pl-6 text-left")}>{h}</th>)}</tr>
                        </thead>
                        <tbody className="chiffres divide-y divide-trait text-right">
                          {nums.map(({ code, libelle, stats: s, precedent: p }) => (
                            <tr key={code} className="cursor-pointer hover:bg-relief/40" onClick={() => setVariable(code)}>
                              <td className="py-2.5 pl-6 pr-3 text-left"><span className="mr-2 font-mono text-xs text-discret">{code}</span>{libelle}</td>
                              <td className="px-3 text-discret">{s.n}</td>
                              <td className="px-3 font-medium">{nombre(s.somme)}</td><td className="px-3">{decimal(s.moyenne)}</td>
                              <td className="px-3">{decimal(s.mediane)}</td><td className="px-3 text-discret">{nombre(s.min)}</td>
                              <td className="px-3 text-discret">{decimal(s.q1)}</td><td className="px-3 text-discret">{decimal(s.q3)}</td>
                              <td className="px-3 text-discret">{nombre(s.max)}</td><td className={cx("px-3 text-discret", !prec && "pr-6")}>{decimal(s.ecart_type)}</td>
                              {prec && <><td className="px-3 text-discret">{nombre(p?.somme)}</td><td className="px-3 pr-6"><Evolution n={s.somme} n1={p?.somme} /></td></>}
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
                        <p className="mt-4 text-xs text-discret">n = {s.n}{type === "choix_multiple" && " · plusieurs réponses possibles"}</p>
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

/* ---------- Tableau croisé et graphique personnalisé (F-41, F-45) ---------- */

function Croisement({ variables, params }: { variables: Stats["variables"]; params: Record<string, string | number> }) {
  const [ligne, setLigne] = useState("categorie");
  const [colonne, setColonne] = useState(variables.find((v) => v.groupe !== "Établissement")?.valeur ?? "tutelle");
  const [vue, setVue] = useState<"empile" | "groupe" | "tableau">("empile");
  const [mesure, setMesure] = useState<"effectifs" | "pourcentages">("pourcentages");
  const q = useQuery({
    queryKey: ["croisement", params, ligne, colonne],
    queryFn: () => api.get<TableauCroise>(avecParams("/api/gestion/croisement/", { ...params, ligne, colonne })),
    enabled: ligne !== colonne, placeholderData: keepPreviousData,
  });
  const t = q.data;
  const groupes = [...new Set(variables.map((v) => v.groupe))];
  const choix = (valeur: string, changer: (v: string) => void, libelle: string) => (
    <Liste libelle={libelle} value={valeur} onChange={(e) => changer(e.target.value)} className="min-w-[220px] flex-1">
      {groupes.map((g) => <optgroup key={g} label={g}>{variables.filter((v) => v.groupe === g).map((v) => <option key={v.valeur} value={v.valeur}>{v.libelle}</option>)}</optgroup>)}
    </Liste>
  );
  const donnees = t?.lignes.map((l) => ({ libelle: l.libelle, ...Object.fromEntries(t.colonnes.map((c, i) => [c, mesure === "effectifs" ? l.effectifs[i] : Math.round(l.pourcentages[i])])) }));

  return (
    <Carte>
      <EnTeteCarte titre="Croisement de variables" sous="Choisissez deux variables qualitatives et le type de graphique." />
      <div className="flex flex-wrap items-end gap-3 px-5 pt-4">
        {choix(ligne, setLigne, "En ligne")}
        {choix(colonne, setColonne, "En colonne")}
        <div className="flex gap-1 rounded-[10px] border border-trait p-1">
          {([["empile", BarChart3, "Barres empilées"], ["groupe", IconeCourbe, "Barres groupées"], ["tableau", Grid3x3, "Tableau"]] as const).map(([v, I, l]) => (
            <button key={v} onClick={() => setVue(v)} aria-pressed={vue === v} title={l} aria-label={l}
              className={cx("grid h-8 w-9 place-items-center rounded-lg", vue === v ? "bg-marque text-white dark:text-[#04140c]" : "text-discret hover:bg-relief")}><I className="h-4 w-4" /></button>
          ))}
        </div>
        <Liste value={mesure} onChange={(e) => setMesure(e.target.value as typeof mesure)} aria-label="Mesure" className="w-40">
          <option value="pourcentages">% en ligne</option><option value="effectifs">Effectifs</option>
        </Liste>
      </div>
      {ligne === colonne ? <p className="p-6 text-sm text-discret">Choisissez deux variables différentes.</p> : !t ? <Squelette className="m-5 h-64" /> : (
        <div className="p-5">
          {vue === "tableau" ? (
            <div className="defilement-fin overflow-x-auto rounded-xl border border-trait">
              <table className="w-full text-sm">
                <thead className="bg-relief/50 text-right text-xs text-discret">
                  <tr><th className="px-4 py-2.5 text-left font-medium">{t.ligne} \ {t.colonne}</th>{t.colonnes.map((c) => <th key={c} className="px-4 py-2.5 font-medium">{c}</th>)}<th className="px-4 py-2.5 font-medium">Total</th></tr>
                </thead>
                <tbody className="chiffres divide-y divide-trait text-right">
                  {t.lignes.map((l) => (
                    <tr key={l.libelle}>
                      <td className="px-4 py-2 text-left">{l.libelle}</td>
                      {l.effectifs.map((e, i) => <td key={i} className="px-4 py-2">{e}<span className="ml-1.5 text-xs text-discret">({Math.round(l.pourcentages[i])} %)</span></td>)}
                      <td className="px-4 py-2 font-medium">{l.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="h-[320px]">
              <ResponsiveContainer>
                <BarChart data={donnees} margin={{ left: 0, right: 12, top: 8 }}>
                  <CartesianGrid vertical={false} stroke={COULEURS.trait} strokeDasharray="3 3" />
                  <XAxis dataKey="libelle" tick={{ fill: COULEURS.discret, fontSize: 11 }} axisLine={false} tickLine={false} interval={0} />
                  <YAxis tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} width={40} tickFormatter={(v) => (mesure === "pourcentages" ? `${v} %` : String(v))} />
                  <Tooltip cursor={{ fill: "rgb(var(--relief))" }} content={<InfoBulle suffixe={mesure === "pourcentages" ? " %" : ""} />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {t.colonnes.map((c, i) => (
                    <Bar key={c} dataKey={c} name={c} stackId={vue === "empile" ? "a" : undefined} fill={SERIES[i % SERIES.length]} isAnimationActive={false}
                      radius={vue === "empile" ? (i === t.colonnes.length - 1 ? [6, 6, 0, 0] : 0) : [4, 4, 0, 0]} maxBarSize={48} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <p className="mt-3 text-xs text-discret">n = {t.n} établissements renseignant les deux variables.</p>
        </div>
      )}
    </Carte>
  );
}
