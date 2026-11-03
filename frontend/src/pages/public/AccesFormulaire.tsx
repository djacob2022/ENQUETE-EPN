import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Building2, CalendarClock, Check, Lock, MailCheck, Search, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import BoutonTheme from "@/composants/BoutonTheme";
import { BandeauOfficiel } from "@/composants/Officiel";
import { api, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Campagne } from "@/lib/types";
import { Bouton, Carte, cx, Squelette } from "@/ui";

interface Etablissement { id: number; nom: string; sigle: string; tutelle: string }
interface Donnees { campagne: Campagne | null; ouverte: boolean; etablissements: Etablissement[] }
interface Resultat { email_masque: string; deja_soumis: boolean; deja_envoye: boolean; epn: string }

const normaliser = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Le lien unique, identique pour tous les EPN : chacun choisit son établissement et reçoit son lien personnel. */
export default function AccesFormulaire() {
  const q = useQuery({ queryKey: ["formulaire-public"], queryFn: () => api.get<Donnees>("/api/formulaire/") });
  const [recherche, setRecherche] = useState("");
  const [choisi, setChoisi] = useState<Etablissement | null>(null);
  const demande = useMutation({ mutationFn: (id: number) => api.post<Resultat>("/api/formulaire/", { epn: id }) });

  const resultats = useMemo(() => {
    const t = normaliser(recherche.trim());
    const liste = q.data?.etablissements ?? [];
    return t ? liste.filter((e) => normaliser(`${e.nom} ${e.sigle} ${e.tutelle}`).includes(t)) : liste;
  }, [q.data, recherche]);

  const campagne = q.data?.campagne;

  return (
    <div className="min-h-screen">
      <BandeauOfficiel droite={<BoutonTheme />} />

      <section className="motif-officiel relative overflow-hidden bg-institution text-white">
        <div className="mx-auto max-w-7xl px-4 pb-28 pt-12 sm:px-6 sm:pt-16">
          <p className="inline-flex items-center gap-2 rounded-md bg-white/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-[.12em] text-white/85">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" /> Enquête officielle
          </p>
          <h1 className="titre-display mt-4 max-w-3xl text-4xl leading-[1.1] sm:text-5xl">
            {campagne ? campagne.nom : "Enquête sur les Établissements Publics Nationaux"}
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-white/80">
            Chaque établissement public national est invité à renseigner le questionnaire de l'exercice {campagne?.exercice ?? "de référence"}.
          </p>
          {campagne && (
            <p className="mt-6 inline-flex items-center gap-2 text-sm text-white/85">
              <CalendarClock className="h-4 w-4 text-accent" /> Date limite de réponse : <strong className="text-white">{date(campagne.date_cloture)}</strong>
            </p>
          )}
        </div>
      </section>

      <main className="relative mx-auto -mt-20 max-w-7xl px-4 pb-20 sm:px-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Carte className="overflow-hidden">
            <AnimatePresence mode="wait">
              {demande.data ? (
                <motion.div key="ok" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="p-8 sm:p-10">
                  <span className="grid h-14 w-14 place-items-center rounded-full bg-succes-doux text-succes"><MailCheck className="h-7 w-7" /></span>
                  <h2 className="mt-5 text-2xl font-bold tracking-tight">{demande.data.deja_envoye ? "Lien déjà envoyé" : "Lien envoyé au point focal"}</h2>
                  {demande.data.deja_envoye ? (
                    <p className="mt-2 max-w-xl text-discret">
                      Un lien a déjà été envoyé à <strong className="font-mono text-encre">{demande.data.email_masque}</strong> il y a quelques minutes.
                      Vérifiez la boîte de réception et les courriers indésirables avant de faire une nouvelle demande.
                    </p>
                  ) : (
                    <p className="mt-2 max-w-xl text-discret">
                      Le lien du questionnaire de <strong className="text-encre">{demande.data.epn}</strong> a été envoyé
                      à <strong className="font-mono text-encre">{demande.data.email_masque}</strong>, l'adresse officielle enregistrée pour votre établissement.
                    </p>
                  )}
                  <p className="mt-4 max-w-xl rounded-lg border border-trait bg-relief/60 px-4 py-3 text-sm">
                    <strong>Vous n'êtes pas le point focal ?</strong> Demandez-lui de vous transférer l'e-mail « Votre lien d'accès au questionnaire ».
                  </p>
                  {demande.data.deja_soumis && (
                    <p className="mt-4 rounded-lg border border-succes/30 bg-succes-doux px-4 py-3 text-sm text-succes">
                      Cet établissement a déjà envoyé ses réponses : le lien permet de consulter le récapitulatif.
                    </p>
                  )}
                  <ol className="mt-6 space-y-3 text-sm">
                    {["Ouvrez l'e-mail « Votre lien d'accès au questionnaire ».", "Cliquez sur le lien : le questionnaire de votre établissement s'ouvre.",
                      "Renseignez vos coordonnées puis les rubriques. Tout est enregistré au fur et à mesure."].map((t, i) => (
                      <li key={t} className="flex gap-3"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-marque text-xs font-bold text-white dark:text-[#04140c]">{i + 1}</span>{t}</li>
                    ))}
                  </ol>
                  <p className="mt-6 text-sm text-discret">Rien reçu après 10 minutes ? Vérifiez les courriers indésirables. Si l'adresse du point focal n'est plus à jour, contactez l'administration de tutelle.</p>
                  <Bouton variante="fantome" className="mt-4" onClick={() => { demande.reset(); setChoisi(null); }}>Choisir un autre établissement</Bouton>
                </motion.div>
              ) : (
                <motion.div key="choix" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div className="border-b border-trait px-6 pb-5 pt-6 sm:px-8">
                    <p className="text-xs font-bold uppercase tracking-[.12em] text-marque">Accès au questionnaire</p>
                    <h2 className="mt-1 text-2xl font-bold tracking-tight">Sélectionnez votre établissement</h2>
                    <p className="mt-1 text-sm text-discret">Nous enverrons le lien du questionnaire à l'adresse e-mail officielle du point focal de votre établissement.</p>
                    <label className="relative mt-5 block">
                      <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-discret" />
                      <input value={recherche} onChange={(e) => setRecherche(e.target.value)} autoFocus disabled={!q.data?.ouverte}
                        placeholder="Nom, sigle ou ministère de tutelle…" aria-label="Rechercher votre établissement"
                        className="h-12 w-full rounded-lg border border-trait bg-surface pl-10 pr-3 text-[15px] focus:border-marque focus:shadow-anneau focus:outline-none" />
                    </label>
                  </div>

                  {q.isLoading ? <div className="space-y-2 p-6">{[0, 1, 2, 3].map((i) => <Squelette key={i} className="h-14" />)}</div>
                    : !q.data?.ouverte ? (
                      <div className="flex items-start gap-3 p-8 text-discret"><Lock className="mt-0.5 h-5 w-5" />
                        <p>Le questionnaire n'est pas ouvert en ce moment.{campagne ? ` La campagne se déroule du ${date(campagne.date_ouverture)} au ${date(campagne.date_cloture)}.` : ""}</p></div>
                    ) : (
                      <ul role="listbox" aria-label="Établissements" className="defilement-fin max-h-[420px] divide-y divide-trait overflow-y-auto">
                        {resultats.map((e) => {
                          const actif = choisi?.id === e.id;
                          return (
                            <li key={e.id} role="option" aria-selected={actif}>
                              <button onClick={() => setChoisi(e)}
                                className={cx("flex w-full items-center gap-4 px-6 py-3.5 text-left transition sm:px-8", actif ? "bg-marque-doux" : "hover:bg-relief/60")}>
                                <span className={cx("grid h-10 w-10 shrink-0 place-items-center rounded-lg", actif ? "bg-marque text-white dark:text-[#04140c]" : "bg-relief text-discret")}>
                                  {actif ? <Check className="h-5 w-5" strokeWidth={3} /> : <Building2 className="h-5 w-5" />}
                                </span>
                                <span className="min-w-0 flex-1">
                                  <span className="block truncate font-semibold">{e.nom}</span>
                                  <span className="block truncate text-xs text-discret">{[e.sigle, e.tutelle].filter(Boolean).join(" · ")}</span>
                                </span>
                              </button>
                            </li>
                          );
                        })}
                        {resultats.length === 0 && <li className="px-8 py-10 text-center text-sm text-discret">Aucun établissement ne correspond. Contactez l'administration de tutelle si le vôtre n'apparaît pas.</li>}
                      </ul>
                    )}

                  {q.data?.ouverte && (
                    <div className="flex flex-col gap-3 border-t border-trait bg-relief/40 px-6 py-4 sm:flex-row sm:items-center sm:px-8">
                      <p className="flex-1 text-sm text-discret">{choisi ? <>Établissement choisi : <strong className="text-encre">{choisi.nom}</strong></> : "Choisissez votre établissement dans la liste ci-dessus."}</p>
                      <Bouton variante="primaire" taille="lg" disabled={!choisi} chargement={demande.isPending} onClick={() => choisi && demande.mutate(choisi.id)}>
                        Envoyer le lien au point focal <ArrowRight className="h-4 w-4" />
                      </Bouton>
                    </div>
                  )}
                  {demande.error && <p role="alert" className="border-t border-danger/20 bg-danger-doux px-8 py-3 text-sm font-medium text-danger">{(demande.error as ErreurApi).message}</p>}
                </motion.div>
              )}
            </AnimatePresence>
          </Carte>

          <aside className="space-y-4">
            <Carte className="p-6">
              <h2 className="flex items-center gap-2 font-bold"><ShieldCheck className="h-5 w-5 text-marque" /> Pourquoi passer par le point focal ?</h2>
              <p className="mt-2 text-sm leading-relaxed text-discret">
                Pour que personne ne puisse répondre au nom d'un autre établissement. Seul le lien envoyé à l'adresse officielle ouvre votre questionnaire.
              </p>
            </Carte>
            <Carte className="p-6">
              <h2 className="font-bold">Ce que contient le questionnaire</h2>
              <ul className="mt-3 space-y-2 text-sm text-discret">
                {["Identification et gouvernance", "Missions, ressources humaines et finances", "Patrimoine, performance et besoins", "Pièces justificatives (états financiers, rapport d'activités)"].map((t) => (
                  <li key={t} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-marque" />{t}</li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-discret">Préparez vos états financiers et votre rapport d'activités au format PDF.</p>
            </Carte>
          </aside>
        </div>
      </main>
      <footer className="border-t border-trait bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-discret sm:px-6">
          <span>Plateforme officielle de collecte · données traitées par l'administration de tutelle</span>
          <a href="/connexion" className="font-medium hover:text-encre">Espace administration</a>
        </div>
      </footer>
    </div>
  );
}
