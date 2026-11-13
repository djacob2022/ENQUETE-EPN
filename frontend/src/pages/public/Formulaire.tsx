import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Check, CloudOff, Download, FileSpreadsheet, Link2Off, Loader2, Lock, MessageSquareWarning, Send, Upload, UserRound } from "lucide-react";
import { createContext, useContext, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import BoutonTheme from "@/composants/BoutonTheme";
import ChoixLangue from "@/composants/ChoixLangue";
import { Embleme, useConfig } from "@/composants/Officiel";
import { api, envoyerFichier, ErreurApi } from "@/lib/api";
import { date, ilYa, joursRestants } from "@/lib/format";
import { avecLangue, t, useLangue } from "@/lib/langue";
import { Questionnaire, ReponsePublique } from "@/lib/types";
import { Anneau, Bouton, cx, Dialogue, Squelette, useToast } from "@/ui";
import Identification from "./Identification";
import { Merci, Recapitulatif } from "./Recapitulatif";
import Rubrique from "./Rubrique";

/* ---------- Contexte partagé par les étapes ---------- */

export type EtatSauvegarde = "repos" | "enregistrement" | "enregistre" | "erreur";

interface Contexte {
  jeton: string;
  reponse: ReponsePublique;
  questionnaire: Questionnaire;
  mettreAJour: (r: ReponsePublique) => void;
  sauvegarde: EtatSauvegarde;
  setSauvegarde: (e: EtatSauvegarde) => void;
}

const ContexteFormulaire = createContext<Contexte | null>(null);
export const useFormulaire = () => useContext(ContexteFormulaire)!;

export function urlApi(jeton: string, suite = "") {
  return `/api/r/${encodeURIComponent(jeton)}/${suite}`;
}

/* ---------- Page ---------- */

export default function Formulaire() {
  const { jeton = "" } = useParams();
  useLangue();
  const client = useQueryClient();
  const [sauvegarde, setSauvegarde] = useState<EtatSauvegarde>("repos");
  const rq = useQuery({ queryKey: ["reponse", jeton], queryFn: () => api.get<ReponsePublique>(urlApi(jeton)) });
  const idCampagne = rq.data?.campagne.id;
  const qq = useQuery({
    queryKey: ["questionnaire", idCampagne],
    queryFn: () => api.get<Questionnaire>(`/api/questionnaire/?campagne=${idCampagne}`),
    enabled: !!idCampagne, staleTime: 5 * 60_000,
  });

  const contexte = useMemo<Contexte | null>(() => rq.data && qq.data ? {
    jeton, reponse: rq.data, questionnaire: qq.data, sauvegarde, setSauvegarde,
    mettreAJour: (r) => client.setQueryData<ReponsePublique>(["reponse", jeton], r),
  } : null, [rq.data, qq.data, jeton, sauvegarde, client]);

  if (rq.error) {
    const introuvable = (rq.error as ErreurApi).statut === 404;
    return (
      <PageSimple icone={introuvable ? <Link2Off /> : <CloudOff />}
        titre={introuvable ? t("Ce lien n'est pas valide") : t("Connexion impossible")}
        texte={introuvable
          ? t("Vérifiez que vous avez copié le lien complet. S'il a été remplacé par l'administration, utilisez le dernier lien reçu par e-mail, ou demandez-en un nouveau sur la page du questionnaire.")
          : (rq.error as Error).message} />
    );
  }
  if (!contexte) return <ChargementFormulaire />;

  const { reponse } = contexte;
  if (reponse.etat === "ferme") {
    return (
      <PageSimple icone={<Lock />} titre={t("La saisie n'est pas ouverte")}
        texte={t("La campagne « {nom} » est ouverte du {debut} au {fin}. Pour un délai supplémentaire, contactez l'administration de tutelle.",
          { nom: reponse.campagne.nom, debut: date(reponse.campagne.date_ouverture), fin: date(reponse.date_limite) })} />
    );
  }

  return (
    <ContexteFormulaire.Provider value={contexte}>
      {reponse.etat === "soumis" ? <Merci /> : (
        <Cadre>
          <Routes>
            <Route index element={<Navigate to={reponse.identifie ? premiereEtape(contexte) : "identification"} replace />} />
            <Route path="identification" element={<Identification />} />
            <Route path="recapitulatif" element={reponse.identifie ? <Recapitulatif /> : <Navigate to="../identification" replace />} />
            <Route path=":code" element={reponse.identifie ? <Rubrique /> : <Navigate to="../identification" replace />} />
          </Routes>
        </Cadre>
      )}
    </ContexteFormulaire.Provider>
  );
}

function premiereEtape({ reponse, questionnaire }: Contexte) {
  const m = questionnaire.modules.find((m) => !reponse.modules_completes.includes(m.code));
  return m ? m.code : "recapitulatif";
}

/* ---------- Mise en page ---------- */

function Cadre({ children }: { children: React.ReactNode }) {
  const { reponse, questionnaire, jeton } = useFormulaire();
  const { pathname } = useLocation();
  const courant = pathname.split("/").filter(Boolean)[2] ?? "";
  const jours = joursRestants(reponse.date_limite);
  const nbCommentaires = Object.keys(reponse.commentaires ?? {}).length;
  const base = `/r/${jeton}`;
  const config = useConfig();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-trait bg-surface/90 backdrop-blur-xl">
        <div className="tricolore h-1" aria-hidden />
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
          <Embleme className="h-9 w-8" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold tracking-tight">{reponse.epn.nom}</p>
            <p className="truncate text-xs text-discret">{config?.pays ? `${config.pays} · ` : ""}{reponse.campagne.nom}</p>
          </div>
          <IndicateurSauvegarde />
          <ChoixLangue />
          <BoutonTheme />
        </div>
        <div className="h-0.5 bg-relief lg:hidden">
          <motion.div className="h-full bg-marque" animate={{ width: `${reponse.avancement}%` }} />
        </div>
      </header>

      {nbCommentaires > 0 && (
        <div className="border-b border-danger/20 bg-danger-doux">
          <div className="mx-auto flex max-w-7xl items-start gap-3 px-4 py-3 text-sm sm:px-6">
            <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
            <p><strong className="text-danger">{t("Votre réponse vous a été renvoyée pour correction.")}</strong>{" "}
              {reponse.commentaires.general ? `« ${reponse.commentaires.general} » ` : ""}
              {t("Corrigez les points signalés, puis renvoyez vos réponses depuis « Vérification et envoi ».")}</p>
          </div>
        </div>
      )}

      <div className="mx-auto flex max-w-7xl gap-10 px-4 py-8 sm:px-6 lg:py-12">
        <aside className="sticky top-28 hidden h-fit w-72 shrink-0 lg:block">
          <div className="flex items-center gap-4 rounded-2xl border border-trait bg-surface p-5 shadow-carte">
            <Anneau valeur={reponse.avancement} taille={64} epaisseur={7}>
              <span className="chiffres text-sm font-semibold">{reponse.avancement}%</span>
            </Anneau>
            <div>
              <p className="text-sm font-semibold">{t("{n} / {total} rubriques", { n: reponse.modules_completes.length, total: questionnaire.modules.length })}</p>
              <p className={cx("text-xs", jours <= 3 ? "font-medium text-alerte" : "text-discret")}>
                {jours > 1 ? t("{n} jours restants", { n: jours }) : jours === 1 ? t("Dernier jour") : t("Date limite atteinte")}
              </p>
            </div>
          </div>

          {reponse.identifie && <HorsConnexion />}

          <nav aria-label={t("Étapes du questionnaire")} className="mt-6">
            <ol className="relative space-y-1 before:absolute before:bottom-4 before:left-[19px] before:top-4 before:w-px before:bg-trait">
              <Etape to={`${base}/identification`} actif={courant === "identification"} fait={reponse.identifie} numero={<UserRound className="h-3.5 w-3.5" />}>
                {t("Vos coordonnées")}
              </Etape>
              {questionnaire.modules.map((m, i) => (
                <Etape key={m.code} to={`${base}/${m.code}`} actif={courant === m.code} fait={reponse.modules_completes.includes(m.code)} numero={i + 1}
                  alerte={m.questions.some((q) => reponse.commentaires?.[q.code])}>
                  {m.titre}
                </Etape>
              ))}
              <Etape to={`${base}/recapitulatif`} actif={courant === "recapitulatif"} fait={false} numero={<Send className="h-3.5 w-3.5" />}>
                {t("Vérification et envoi")}
              </Etape>
            </ol>
          </nav>
        </aside>

        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

function Etape({ to, actif, fait, numero, children, alerte = false }: { to: string; actif: boolean; fait: boolean; numero: React.ReactNode; children: React.ReactNode; alerte?: boolean }) {
  return (
    <li className="relative">
      <Link to={to} aria-current={actif ? "step" : undefined}
        className={cx("group flex items-center gap-3 rounded-xl px-2 py-2 text-sm transition",
          actif ? "bg-surface font-semibold text-encre shadow-carte ring-1 ring-trait" : "text-discret hover:text-encre")}>
        <span className={cx("relative z-10 grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold ring-4 ring-fond transition",
          actif ? "bg-marque text-white dark:text-[#04140c]" : fait ? "bg-succes text-white dark:text-[#04140c]" : "border border-trait bg-surface text-discret")}
          style={{ marginLeft: 6 }}>
          {fait && !actif ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : numero}
        </span>
        <span className="truncate">{children}</span>
        {alerte && <span className="ml-auto h-2 w-2 shrink-0 rounded-full bg-danger" aria-label={t("Correction demandée")} />}
      </Link>
    </li>
  );
}

/** F-26 : remplir le questionnaire hors connexion dans Excel, puis le réimporter. */
function HorsConnexion() {
  const { jeton, mettreAJour, questionnaire } = useFormulaire();
  const toast = useToast();
  const champ = useRef<HTMLInputElement>(null);
  const [progres, setProgres] = useState<number | null>(null);
  const [bilan, setBilan] = useState<{ valeurs: number; rubriques: number; erreurs: Record<string, string[]> } | null>(null);
  async function importer(f: File) {
    setProgres(0);
    try {
      const r = await envoyerFichier<{ valeurs: number; rubriques: number; erreurs: Record<string, string[]>; reponse: ReponsePublique }>(
        urlApi(jeton, "import/"), f, setProgres);
      mettreAJour(r.reponse);
      setBilan(r);
    } catch (e) {
      toast("erreur", (e as ErreurApi).message);
    } finally {
      setProgres(null);
    }
  }
  const libelle = (code: string) => questionnaire.modules.flatMap((m) => m.questions).find((q) => q.code === code)?.libelle ?? code;
  return (
    <div className="mt-4 rounded-2xl border border-trait bg-surface p-4 shadow-carte">
      <p className="flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet className="h-4 w-4 text-succes" /> {t("Connexion difficile ?")}</p>
      <p className="mt-1 text-xs leading-relaxed text-discret">{t("Remplissez le questionnaire dans Excel, sans Internet, puis importez-le ici.")}</p>
      <div className="mt-3 grid gap-2">
        <a href={avecLangue(urlApi(jeton, "modele.xlsx"))} className="inline-flex h-9 items-center justify-center gap-2 rounded-[10px] border border-trait text-[13px] font-medium hover:bg-relief">
          <Download className="h-3.5 w-3.5" /> {t("Télécharger le fichier Excel")}</a>
        <input ref={champ} type="file" accept=".xlsx" className="sr-only" tabIndex={-1} aria-hidden
          onChange={(e) => { const f = e.target.files?.[0]; if (f) importer(f); e.target.value = ""; }} />
        <Bouton taille="sm" icone={<Upload className="h-3.5 w-3.5" />} chargement={progres !== null} onClick={() => champ.current?.click()}>{t("Importer le fichier rempli")}</Bouton>
      </div>
      <Dialogue ouvert={!!bilan} fermer={() => setBilan(null)} titre={t("Fichier importé")}
        description={bilan ? t("{n} réponse(s) enregistrée(s) en brouillon dans {r} rubrique(s). Relisez chaque rubrique avant d'envoyer.", { n: bilan.valeurs, r: bilan.rubriques }) : ""}>
        {bilan && Object.keys(bilan.erreurs).length > 0 && (
          <div className="rounded-xl border border-alerte/30 bg-alerte-doux p-3 text-sm">
            <p className="font-semibold text-alerte">{t("{n} valeur(s) à corriger en ligne", { n: Object.keys(bilan.erreurs).length })}</p>
            <ul className="mt-1 space-y-1">{Object.entries(bilan.erreurs).map(([c, m]) => <li key={c}><span className="font-mono text-xs">{c}</span> · {libelle(c)} : {m.join(" ")}</li>)}</ul>
          </div>
        )}
        <div className="mt-4 flex justify-end"><Bouton variante="primaire" onClick={() => setBilan(null)}>{t("Compris")}</Bouton></div>
      </Dialogue>
    </div>
  );
}

function IndicateurSauvegarde() {
  const { sauvegarde, reponse } = useFormulaire();
  const contenu = {
    repos: { icone: <Check className="h-3.5 w-3.5" />, texte: reponse.date_modification ? t("Enregistré {quand}", { quand: ilYa(reponse.date_modification) }) : t("Prêt"), ton: "text-discret" },
    enregistrement: { icone: <Loader2 className="h-3.5 w-3.5 animate-spin" />, texte: t("Enregistrement…"), ton: "text-discret" },
    enregistre: { icone: <Check className="h-3.5 w-3.5" />, texte: t("Enregistré"), ton: "text-succes" },
    erreur: { icone: <CloudOff className="h-3.5 w-3.5" />, texte: t("Non enregistré"), ton: "text-danger" },
  }[sauvegarde];
  if (!reponse.identifie && sauvegarde === "repos") return null;
  return (
    <span className={cx("hidden items-center gap-1.5 rounded-full border border-trait bg-surface px-3 py-1 text-xs font-medium sm:flex", contenu.ton)} aria-live="polite">
      {contenu.icone}{contenu.texte}
    </span>
  );
}

function ChargementFormulaire() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-12">
      <Squelette className="h-8 w-72" />
      <div className="mt-10 flex gap-10">
        <div className="hidden w-72 space-y-3 lg:block">{Array.from({ length: 8 }, (_, i) => <Squelette key={i} className="h-9" />)}</div>
        <div className="flex-1 space-y-4"><Squelette className="h-40" /><Squelette className="h-72" /></div>
      </div>
    </div>
  );
}

export function PageSimple({ icone, titre, texte, enfants }: { icone: React.ReactNode; titre: string; texte: string; enfants?: React.ReactNode }) {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden px-6">
      <div className="grille-fond pointer-events-none absolute inset-0" />
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-lg rounded-2xl border border-trait bg-surface p-8 text-center shadow-flottant">
        <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-relief text-discret [&>svg]:h-6 [&>svg]:w-6">{icone}</div>
        <h1 className="mt-5 text-xl font-semibold tracking-tight">{titre}</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-discret">{texte}</p>
        {enfants}
      </motion.div>
    </div>
  );
}
