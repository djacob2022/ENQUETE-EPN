import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, CircleCheck, History, MessageSquareWarning, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, ErreurApi } from "@/lib/api";
import { nombre } from "@/lib/format";
import { Module, ReponsePublique, Valeur } from "@/lib/types";
import { Bouton, Carte, cx, useToast } from "@/ui";
import { ChampQuestion, CommentaireTutelle, DepotFichier, estPosee, versEnvoi } from "./Questions";
import { urlApi, useFormulaire } from "./Formulaire";

type Valeurs = Record<string, Valeur>;

function valeursInitiales(module: Module, donnees: Record<string, Valeur>): Valeurs {
  const v: Valeurs = {};
  module.questions.forEach((q) => {
    if (q.type === "fichier") return;
    const d = donnees[q.code];
    v[q.code] = q.type === "choix_multiple" || q.type === "tableau" ? (Array.isArray(d) ? d : [])
      : d === null || d === undefined ? "" : String(d);
  });
  return v;
}

export default function Rubrique() {
  const { code = "" } = useParams();
  const { questionnaire, reponse, jeton } = useFormulaire();
  const index = questionnaire.modules.findIndex((m) => m.code === code);
  if (index < 0) return <Navigate to={`/r/${jeton}`} replace />;
  // La clé recrée le formulaire à chaque changement de rubrique (valeurs et erreurs repartent de zéro).
  return <FormulaireRubrique key={code} module={questionnaire.modules[index]} index={index} donnees={reponse.donnees} />;
}

function FormulaireRubrique({ module, index, donnees }: { module: Module; index: number; donnees: Record<string, Valeur> }) {
  const { jeton, questionnaire, reponse, mettreAJour, setSauvegarde } = useFormulaire();
  const naviguer = useNavigate();
  const toast = useToast();
  const [valeurs, setValeurs] = useState<Valeurs>(() => valeursInitiales(module, donnees));
  const [erreurs, setErreurs] = useState<Record<string, string[]>>({});
  const [envoi, setEnvoi] = useState(false);
  const [reprise, setReprise] = useState(false);
  const minuterie = useRef<number>();
  const modifie = useRef(false);
  const total = questionnaire.modules.length;

  const enregistrer = useCallback(async (valider: boolean) => {
    window.clearTimeout(minuterie.current);
    setSauvegarde("enregistrement");
    try {
      const resultat = await api.post<{ erreurs: Record<string, string[]>; reponse: ReponsePublique }>(
        urlApi(jeton, `modules/${module.code}/`), { valeurs: versEnvoi(module, valeurs), valider });
      mettreAJour(resultat.reponse);
      modifie.current = false;
      setSauvegarde("enregistre");
      return resultat.erreurs;
    } catch (e) {
      setSauvegarde("erreur");
      throw e;
    }
  }, [jeton, module, valeurs, mettreAJour, setSauvegarde]);

  // Sauvegarde automatique, une seconde après la dernière frappe.
  useEffect(() => {
    if (!modifie.current) return;
    minuterie.current = window.setTimeout(() => {
      enregistrer(false).then((e) => setErreurs((ancien) => ({ ...filtrerFormat(ancien), ...e }))).catch(() => {});
    }, 1000);
    return () => window.clearTimeout(minuterie.current);
  }, [valeurs, enregistrer]);

  const changer = (code: string, v: Valeur) => {
    modifie.current = true;
    setValeurs((anc) => ({ ...anc, [code]: v }));
    setErreurs(({ [code]: _, ...reste }) => reste);
  };

  async function suivant() {
    setEnvoi(true);
    try {
      const e = await enregistrer(true);
      if (Object.keys(e).length) return signaler(e);
      setErreurs({});
      const prochain = questionnaire.modules[index + 1];
      naviguer(`/r/${jeton}/${prochain ? prochain.code : "recapitulatif"}`);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const e = err as ErreurApi;
      if (e.erreurs) signaler(e.erreurs);
      else toast("erreur", e.message);
    } finally {
      setEnvoi(false);
    }
  }

  function signaler(e: Record<string, string[]>) {
    setErreurs(e);
    const n = Object.keys(e).length;
    toast("erreur", n > 1 ? `${n} réponses sont à compléter ou à corriger.` : "Une réponse est à compléter ou à corriger.");
    requestAnimationFrame(() => document.querySelector("[data-erreur='true']")?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  async function precedent() {
    if (modifie.current) await enregistrer(false).catch(() => {});
    naviguer(`/r/${jeton}/${index === 0 ? "identification" : questionnaire.modules[index - 1].code}`);
  }

  const verifications = useMemo(() => controlesEnDirect(module.code, valeurs), [module.code, valeurs]);
  // Conditions d'affichage : réponses des autres rubriques + saisie en cours de celle-ci.
  const contexte = useMemo(() => ({ ...reponse.donnees, ...valeurs }), [reponse.donnees, valeurs]);
  const posees = module.questions.filter((q) => estPosee(q, contexte));
  const commentaires = reponse.commentaires ?? {};
  const aCorriger = module.questions.filter((q) => commentaires[q.code]).length;

  async function reprendre() {
    setReprise(true);
    try {
      const r = await api.post<{ repris: number; exercice: number; reponse: ReponsePublique }>(urlApi(jeton, `modules/${module.code}/preremplir/`));
      mettreAJour(r.reponse);
      setValeurs(valeursInitiales(module, r.reponse.donnees));
      toast("succes", r.repris ? `${r.repris} réponse${r.repris > 1 ? "s" : ""} reprise${r.repris > 1 ? "s" : ""} de l'exercice ${r.exercice}. Vérifiez-les et mettez-les à jour.` : "Rien à reprendre pour cette rubrique.");
    } catch (e) {
      toast("erreur", (e as ErreurApi).message);
    } finally {
      setReprise(false);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
      className="mx-auto max-w-3xl">
      <div className="mb-6">
        <p className="text-sm font-medium text-marque">Rubrique {module.code} · {index + 1} sur {total}</p>
        <h1 className="titre-display mt-1 text-4xl sm:text-[44px]">{module.titre}</h1>
        {module.intro && <p className="mt-2 max-w-2xl text-discret">{module.intro}</p>}
        {reponse.precedente && module.questions.some((q) => q.type !== "fichier") && (
          <Bouton taille="sm" className="mt-4" chargement={reprise} onClick={reprendre}>
            <History className="h-4 w-4" /> Reprendre mes réponses de l'exercice {reponse.precedente}
          </Bouton>
        )}
      </div>

      {aCorriger > 0 && (
        <div className="mb-4 flex gap-3 rounded-2xl border border-danger/30 bg-danger-doux p-4 text-sm">
          <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <p><strong className="text-danger">La tutelle demande {aCorriger > 1 ? `${aCorriger} corrections` : "une correction"} dans cette rubrique.</strong> Les questions concernées sont signalées ci-dessous.</p>
        </div>
      )}

      <AnimatePresence>
        {verifications.length > 0 && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="mb-4 flex flex-wrap gap-2">
            {verifications.map((v) => (
              <span key={v.texte} className={cx("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
                v.ok ? "bg-succes-doux text-succes" : "bg-alerte-doux text-alerte")}>
                {v.ok ? <CircleCheck className="h-3.5 w-3.5" /> : <TriangleAlert className="h-3.5 w-3.5" />}{v.texte}
              </span>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <Carte>
        <div className="divide-y divide-trait">
          {posees.map((q) => (
            <motion.div key={q.code} initial={q.si ? { opacity: 0, height: 0 } : false} animate={{ opacity: 1, height: "auto" }}
              className="px-6 py-6 sm:px-8" data-erreur={!!erreurs[q.code]}>
              <CommentaireTutelle texte={commentaires[q.code]} />
              {q.type === "fichier"
                ? <DepotFichier question={q} piece={reponse.pieces[q.code]} erreurs={erreurs[q.code]}
                    effacerErreur={() => setErreurs(({ [q.code]: _, ...r }) => r)} />
                : <ChampQuestion question={q} valeur={valeurs[q.code]} erreurs={erreurs[q.code]} changer={(v) => changer(q.code, v)} />}
            </motion.div>
          ))}
        </div>
      </Carte>

      <div className="sticky bottom-4 z-20 mt-6 flex items-center gap-3 rounded-2xl border border-trait bg-surface/90 p-3 shadow-flottant backdrop-blur-xl">
        <Bouton variante="fantome" onClick={precedent}><ArrowLeft className="h-4 w-4" /> Précédent</Bouton>
        <span className="hidden flex-1 text-center text-xs text-discret sm:block">Vos réponses sont enregistrées automatiquement.</span>
        <Bouton variante="primaire" className="ml-auto" chargement={envoi} onClick={suivant}>
          {index + 1 === total ? "Vérifier et envoyer" : "Suivant"} <ArrowRight className="h-4 w-4" />
        </Bouton>
      </div>
    </motion.div>
  );
}

/** Garde seulement les erreurs « de format » : les obligatoires ne s'affichent qu'au clic sur Suivant. */
function filtrerFormat(e: Record<string, string[]>) {
  return Object.fromEntries(Object.entries(e).filter(([, m]) => !m.some((x) => x.includes("obligatoire"))));
}

/** Aides visuelles calculées pendant la saisie, avant même la validation par le serveur. */
function controlesEnDirect(code: string, v: Valeurs) {
  const n = (c: string) => (v[c] === "" || v[c] === undefined ? null : Number(String(v[c]).replace(/\s/g, "").replace(",", ".")));
  const res: { ok: boolean; texte: string }[] = [];
  const somme = (total: string, a: string, b: string, libelle: string) => {
    const [t, x, y] = [n(total), n(a), n(b)];
    if (t === null || x === null || y === null || [t, x, y].some(Number.isNaN)) return;
    res.push(x + y === t ? { ok: true, texte: `${libelle} = effectif total` }
      : { ok: false, texte: `${libelle} = ${nombre(x + y)}, effectif total ${nombre(t)}` });
  };
  if (code === "D") {
    somme("D01", "D02", "D03", "Femmes + hommes");
    somme("D01", "D04", "D05", "Fonctionnaires + contractuels");
  }
  if (code === "G") {
    const [suivis, atteints] = [n("G01"), n("G02")];
    if (suivis !== null && atteints !== null && suivis > 0)
      res.push(atteints <= suivis ? { ok: true, texte: `${Math.round((100 * atteints) / suivis)} % des indicateurs atteints` }
        : { ok: false, texte: "Plus d'indicateurs atteints que suivis" });
  }
  if (code === "E") {
    const [prevu, execute] = [n("E01"), n("E02")];
    if (prevu && execute !== null) res.push({ ok: execute <= prevu * 1.2, texte: `Exécution budgétaire : ${Math.round((100 * execute) / prevu)} %` });
  }
  return res;
}
