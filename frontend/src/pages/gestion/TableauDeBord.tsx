import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowUpRight, BellRing, CircleCheckBig, CircleDollarSign, Inbox, Link2, ScanSearch, Send, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, avecParams, ErreurApi } from "@/lib/api";
import { compacte, ilYa, initiales, joursRestants, nombre, pourcent } from "@/lib/format";
import { TableauDeBord as TDB } from "@/lib/types";
import { Anneau, Avatar, BadgeStatut, Bouton, Carte, cx, Dialogue, EnTeteCarte, Progression, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, peut, SansCampagne, useGestion } from "./Gestion";
import { MenuExport } from "./Reponses";

const SEGMENTS = [
  { s: ["valide"], l: "Validés", c: "bg-succes" }, { s: ["soumis", "en_revue"], l: "À examiner", c: "bg-marque/45" },
  { s: ["a_corriger"], l: "À corriger", c: "bg-danger" }, { s: ["en_cours"], l: "Brouillons", c: "bg-alerte" },
  { s: ["invite"], l: "Non commencés", c: "bg-trait" },
] as const;

export const COULEURS = { marque: "rgb(var(--marque))", succes: "rgb(var(--succes))", alerte: "rgb(var(--alerte))", trait: "rgb(var(--trait))", discret: "rgb(var(--discret))" };

export function InfoBulle({ active, payload, label, suffixe = "" }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-trait bg-surface px-3 py-2 text-xs shadow-flottant">
      <p className="font-medium">{label ?? payload[0].payload.libelle}</p>
      {payload.map((p: any) => <p key={p.dataKey} className="chiffres text-discret">{p.name ?? ""} {nombre(p.value)}{suffixe}</p>)}
    </div>
  );
}

export default function TableauDeBord() {
  const { campagne, moi } = useGestion();
  const client = useQueryClient();
  const toast = useToast();
  const [confirmer, setConfirmer] = useState(false);
  const q = useQuery({
    queryKey: ["tableau", campagne?.id],
    queryFn: () => api.get<TDB>(avecParams("/api/gestion/tableau-de-bord/", { campagne: campagne?.id })),
    enabled: !!campagne, refetchInterval: 60_000,
  });
  const relance = useMutation({
    mutationFn: () => api.post<{ envoyees: number; total: number }>(avecParams("/api/gestion/relancer-retardataires/", { campagne: campagne?.id })),
    onSuccess: (r) => { setConfirmer(false); client.invalidateQueries(); toast(r.envoyees === r.total ? "succes" : "erreur", `${r.envoyees} relance(s) envoyée(s) sur ${r.total}.`); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  const relancerUn = useMutation({
    mutationFn: (id: number) => api.post<{ message: string }>(`/api/gestion/reponses/${id}/relancer/`),
    onSuccess: (r) => { client.invalidateQueries({ queryKey: ["tableau"] }); toast("succes", r.message); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  if (!campagne) return <SansCampagne />;
  const d = q.data;
  const jours = joursRestants(campagne.date_cloture);
  const prenom = moi.nom.split(" ")[0];
  const retard = d ? d.compte.invite + d.compte.en_cours + d.compte.a_corriger : 0;
  const envoyees = d ? d.compte.soumis + d.compte.en_revue + d.compte.valide : 0;
  const somme = (statuts: readonly string[]) => (d ? statuts.reduce((n, x) => n + d.compte[x as keyof typeof d.compte], 0) : 0);
  const baseIndic = d?.base_indicateurs === "validees" ? "validées" : "envoyées (aucune encore validée)";

  return (
    <>
      <EnTetePage titre={`Bonjour ${prenom}`}
        sous={<>{campagne.nom} · {jours > 0 ? <><strong className="text-encre">{jours} jours</strong> avant la clôture</> : "campagne clôturée"}</>}
        actions={<>
          {peut(moi, "relancer") && <Bouton icone={<BellRing className="h-4 w-4" />} onClick={() => setConfirmer(true)} disabled={!retard}>Relancer les retardataires</Bouton>}
          {peut(moi, "exporter") && <MenuExport params={{ campagne: campagne.id }} />}
        </>} />

      {d && d.sans_lien > 0 && peut(moi, "gerer_liens") && (
        <Link to="/gestion/liens" className="mb-6 flex items-center gap-3 rounded-2xl border border-marque/25 bg-marque-doux/60 px-5 py-4 text-sm transition hover:bg-marque-doux">
          <Link2 className="h-4 w-4 text-marque" />
          <span className="flex-1"><strong>{d.sans_lien} établissement{d.sans_lien > 1 ? "s" : ""}</strong> n'{d.sans_lien > 1 ? "ont" : "a"} pas encore de lien personnel.</span>
          <span className="font-medium text-marque">Générer et envoyer →</span>
        </Link>
      )}

      {!d ? <ChargementTDB /> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Carte className="flex items-center gap-5 p-5 sm:col-span-2 xl:col-span-1">
              <Anneau valeur={d.taux} taille={92} epaisseur={9}><span className="chiffres text-xl font-semibold">{d.taux}%</span></Anneau>
              <div>
                <p className="text-sm text-discret">Taux de réponse</p>
                <p className="chiffres mt-1 text-2xl font-semibold tracking-tight">{envoyees}<span className="text-base font-normal text-discret"> / {d.invites}</span></p>
                <p className="text-xs text-discret">EPN ciblés ayant répondu · {d.nombre_epn} EPN au répertoire</p>
              </div>
            </Carte>
            <Kpi icone={CircleCheckBig} libelle="Réponses validées" valeur={nombre(d.compte.valide)} note={`${d.taux_validation} % des EPN ciblés · ${d.compte.soumis + d.compte.en_revue} à examiner`} />
            <Kpi icone={Users} libelle="Effectif total" valeur={nombre(d.effectif_total)} note={`agents · n = ${d.n_indicateurs} réponses ${baseIndic}`} />
            <Kpi icone={CircleDollarSign} libelle="Budget total" valeur={compacte(d.budget_total)} note={`crédits ouverts · n = ${d.n_indicateurs}`} />
          </div>

          <div className="grid gap-6 xl:grid-cols-5">
            <Carte className="xl:col-span-2">
              <EnTeteCarte titre="Avancement de la campagne" sous={`${d.invites} établissements invités`} />
              <div className="px-6 pb-6 pt-5">
                <div className="flex h-3 overflow-hidden rounded-full bg-relief">
                  {SEGMENTS.map((x) => (
                    <motion.div key={x.l} className={x.c} initial={{ width: 0 }} animate={{ width: `${d.invites ? (100 * somme(x.s)) / d.invites : 0}%` }} transition={{ duration: 0.9 }} />
                  ))}
                </div>
                <div className="mt-5 grid grid-cols-3 gap-2 sm:grid-cols-5 xl:grid-cols-3 2xl:grid-cols-5">
                  {SEGMENTS.map((x) => (
                    <div key={x.l} className="rounded-xl bg-relief/60 p-3">
                      <span className="flex items-center gap-1.5 text-xs text-discret"><span className={cx("h-2 w-2 shrink-0 rounded-full", x.c)} />{x.l}</span>
                      <span className="chiffres mt-1 block text-xl font-semibold">{somme(x.s)}</span>
                    </div>
                  ))}
                </div>
                <h3 className="mb-3 mt-6 text-sm font-medium">Par catégorie</h3>
                <div className="space-y-3">
                  {d.par_categorie.map((c) => (
                    <div key={c.libelle}>
                      <div className="mb-1.5 flex justify-between text-sm"><span>{c.libelle}</span><span className="chiffres text-discret">{c.soumis}/{c.total} · <strong className="text-encre">{c.taux} %</strong></span></div>
                      <Progression valeur={c.taux} />
                    </div>
                  ))}
                </div>
              </div>
            </Carte>

            <Carte className="xl:col-span-3">
              <EnTeteCarte titre="Taux de réponse par tutelle" sous="Part des établissements invités ayant envoyé leurs réponses" />
              <div className="h-[330px] px-2 pb-4 pt-2">
                <ResponsiveContainer>
                  <BarChart data={d.par_tutelle} layout="vertical" margin={{ left: 8, right: 36, top: 8 }} barCategoryGap={8}>
                    <CartesianGrid horizontal={false} stroke={COULEURS.trait} strokeDasharray="3 3" />
                    <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v} %`} tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="libelle" width={110} tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: "rgb(var(--relief))" }} content={<InfoBulle suffixe=" %" />} />
                    <Bar dataKey="taux" name="Taux" radius={[0, 6, 6, 0]} maxBarSize={22} isAnimationActive={false} label={{ position: "right", fill: COULEURS.discret, fontSize: 12, formatter: (v: number) => `${v} %` }}>
                      {d.par_tutelle.map((t) => <Cell key={t.libelle} fill={t.taux >= 90 ? COULEURS.succes : t.taux < 50 ? COULEURS.alerte : COULEURS.marque} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Carte>
          </div>

          {peut(moi, "valider") && d.a_examiner.length > 0 && (
            <Carte className="overflow-hidden">
              <EnTeteCarte titre="À examiner" sous="Réponses soumises en attente de validation par la tutelle"
                actions={<Link to="/gestion/reponses?statut=soumis" className="text-sm font-medium text-marque hover:underline">Tout voir</Link>} />
              <ul className="mt-3 divide-y divide-trait">
                {d.a_examiner.map((r) => (
                  <li key={r.id} className="flex items-center gap-4 px-6 py-3">
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-marque-doux text-marque"><Inbox className="h-4 w-4" /></span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{r.epn.nom}</p>
                      <p className="text-xs text-discret">{r.epn.tutelle} · envoyé {ilYa(r.date_soumission)}</p>
                    </div>
                    <BadgeStatut statut={r.statut} />
                    <Link to={`/gestion/reponses?ouvrir=${r.id}`} className="inline-flex h-9 items-center gap-1.5 rounded-[10px] border border-trait px-3 text-[13px] font-medium hover:bg-relief">
                      <ScanSearch className="h-3.5 w-3.5" /> Examiner</Link>
                  </li>
                ))}
              </ul>
            </Carte>
          )}

          <div className="grid gap-6 xl:grid-cols-5">
            <Carte className="overflow-hidden xl:col-span-3">
              <EnTeteCarte titre="À relancer" sous={`${retard} établissement${retard > 1 ? "s" : ""} n'ont pas encore envoyé`}
                actions={peut(moi, "voir_nominatif") && <Link to="/gestion/reponses?statut=en_cours" className="text-sm font-medium text-marque hover:underline">Tout voir</Link>} />
              {d.retardataires.length === 0
                ? <Vide icone={<Send className="h-5 w-5" />} titre="Aucun retardataire" texte="Tous les établissements invités ont envoyé leurs réponses." />
                : (
                  <ul className="mt-3 divide-y divide-trait">
                    {d.retardataires.map((r) => (
                      <li key={r.id} className="flex items-center gap-4 px-6 py-3">
                        <div className="min-w-0 flex-1">
                          {peut(moi, "voir_nominatif") ? <Link to={`/gestion/reponses?ouvrir=${r.id}`} className="block truncate text-sm font-medium hover:text-marque">{r.epn.nom}</Link>
                            : <p className="truncate text-sm font-medium">{r.epn.nom}</p>}
                          <p className="text-xs text-discret">{r.epn.tutelle}{r.nombre_relances ? ` · ${r.nombre_relances} relance${r.nombre_relances > 1 ? "s" : ""}` : ""}</p>
                        </div>
                        <div className="hidden w-32 sm:block"><Progression valeur={r.avancement} /><p className="chiffres mt-1 text-right text-xs text-discret">{r.avancement} %</p></div>
                        <BadgeStatut statut={r.statut} />
                        {peut(moi, "relancer") && <Bouton taille="sm" chargement={relancerUn.isPending && relancerUn.variables === r.id} onClick={() => relancerUn.mutate(r.id)}>Relancer</Bouton>}
                      </li>
                    ))}
                  </ul>
                )}
            </Carte>

            <Carte className="xl:col-span-2">
              <EnTeteCarte titre="Dernières réponses" />
              {d.dernieres.length === 0 ? <Vide icone={<Send className="h-5 w-5" />} titre="Pas encore de réponse envoyée" /> : (
                <ul className="mt-3 space-y-1 px-3 pb-4">
                  {d.dernieres.map((r) => (
                    <li key={r.id}>
                      <Link to={peut(moi, "voir_nominatif") ? `/gestion/reponses?ouvrir=${r.id}` : "/gestion"} className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-relief">
                        <Avatar texte={initiales(r.repondant || r.epn.nom)} className="bg-succes-doux text-succes" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{r.epn.nom}</p>
                          <p className="truncate text-xs text-discret">{r.repondant ? `par ${r.repondant} · ` : ""}{ilYa(r.date_soumission)}</p>
                        </div>
                        <ArrowUpRight className="h-4 w-4 text-discret opacity-0 transition group-hover:opacity-100" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Carte>
          </div>

          <div className="grid gap-6 xl:grid-cols-5">
            {d.historique.length >= 2 && (
              <Carte className="xl:col-span-3">
                <EnTeteCarte titre="Évolution du taux de réponse" sous="Par exercice de référence" />
                <div className="h-[260px] px-2 pb-4 pt-4">
                  <ResponsiveContainer>
                    <AreaChart data={d.historique} margin={{ left: 0, right: 16, top: 8 }}>
                      <defs><linearGradient id="degrade" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={COULEURS.marque} stopOpacity={0.25} /><stop offset="100%" stopColor={COULEURS.marque} stopOpacity={0} /></linearGradient></defs>
                      <CartesianGrid vertical={false} stroke={COULEURS.trait} strokeDasharray="3 3" />
                      <XAxis dataKey="libelle" tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tickFormatter={(v) => `${v} %`} tick={{ fill: COULEURS.discret, fontSize: 12 }} axisLine={false} tickLine={false} width={48} />
                      <Tooltip content={<InfoBulle suffixe=" %" />} />
                      <Area type="monotone" dataKey="taux" name="Taux" stroke={COULEURS.marque} strokeWidth={2.5} fill="url(#degrade)" dot={{ r: 4, fill: COULEURS.marque }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </Carte>
            )}
            <Carte className={d.historique.length >= 2 ? "xl:col-span-2" : "xl:col-span-5"}>
              <EnTeteCarte titre="Indicateurs clés" sous={`Sur les ${d.n_indicateurs} réponses ${baseIndic}`}
                actions={<Link to="/gestion/statistiques" className="text-sm font-medium text-marque hover:underline">Toutes les statistiques</Link>} />
              <dl className={cx("mt-3 px-6 pb-4", d.historique.length >= 2 ? "divide-y divide-trait" : "grid gap-x-8 sm:grid-cols-2 xl:grid-cols-3")}>
                {d.indicateurs.map((i) => (
                  <div key={i.libelle} className={cx("flex items-baseline justify-between gap-4 py-3", d.historique.length < 2 && "border-t border-trait")}>
                    <dt className="text-sm text-discret">{i.libelle}</dt>
                    <dd className="chiffres text-lg font-semibold">{pourcent(i.valeur)}</dd>
                  </div>
                ))}
              </dl>
            </Carte>
          </div>
        </div>
      )}

      <Dialogue ouvert={confirmer} fermer={() => setConfirmer(false)} titre="Relancer les retardataires ?"
        description={`Un e-mail de rappel, avec leur lien personnel, sera envoyé aux ${retard} établissements qui n'ont pas encore envoyé leurs réponses (brouillons, non commencés et à corriger).`}>
        <div className="flex justify-end gap-2">
          <Bouton variante="fantome" onClick={() => setConfirmer(false)}>Annuler</Bouton>
          <Bouton variante="primaire" chargement={relance.isPending} onClick={() => relance.mutate()}><Send className="h-4 w-4" /> Envoyer {retard} relance{retard > 1 ? "s" : ""}</Bouton>
        </div>
      </Dialogue>
    </>
  );
}

export function Kpi({ icone: Icone, libelle, valeur, note }: { icone: any; libelle: string; valeur: string; note?: string }) {
  return (
    <Carte className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-discret">{libelle}</p>
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-relief text-discret"><Icone className="h-4 w-4" /></span>
      </div>
      <p className="chiffres mt-3 text-[28px] font-semibold leading-none tracking-tight">{valeur}</p>
      {note && <p className="mt-2 text-xs text-discret">{note}</p>}
    </Carte>
  );
}

function ChargementTDB() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <Squelette key={i} className="h-[132px] rounded-2xl" />)}</div>
      <div className="grid gap-6 xl:grid-cols-5"><Squelette className="h-[400px] rounded-2xl xl:col-span-2" /><Squelette className="h-[400px] rounded-2xl xl:col-span-3" /></div>
    </div>
  );
}
