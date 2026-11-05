import { motion } from "framer-motion";
import { Check, CircleAlert, FileText, PenLine, Printer, Send } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import BoutonTheme from "@/composants/BoutonTheme";
import { BandeauOfficiel } from "@/composants/Officiel";
import { api, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { ReponsePublique } from "@/lib/types";
import { Badge, Bouton, Carte, cx, useToast } from "@/ui";
import { urlApi, useFormulaire } from "./Formulaire";
import { estPosee, lisible } from "./Questions";

function Synthese({ modifiable }: { modifiable: boolean }) {
  const { reponse, questionnaire, jeton } = useFormulaire();
  return (
    <div className="space-y-4">
      {questionnaire.modules.map((m) => {
        const complet = reponse.modules_completes.includes(m.code);
        return (
          <Carte key={m.code} className="overflow-hidden">
            <div className="flex flex-wrap items-center gap-3 border-b border-trait px-6 py-4">
              <span className="font-mono text-xs text-discret">{m.code}</span>
              <h2 className="flex-1 font-semibold tracking-tight">{m.titre}</h2>
              {modifiable && (complet ? <Badge ton="succes"><Check className="h-3 w-3" /> Complet</Badge> : <Badge ton="alerte">À compléter</Badge>)}
              {modifiable && <Link to={`/r/${jeton}/${m.code}`} className="pas-imprimer inline-flex items-center gap-1 text-sm font-medium text-marque hover:underline"><PenLine className="h-3.5 w-3.5" /> Modifier</Link>}
            </div>
            <dl className="divide-y divide-trait">
              {m.questions.filter((q) => estPosee(q, reponse.donnees)).map((q) => {
                const piece = reponse.pieces[q.code];
                const v = q.type === "fichier" ? piece?.nom ?? "" : lisible(q, reponse.donnees[q.code]);
                return (
                  <div key={q.code} className={cx("grid gap-1 px-6 py-3 sm:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] sm:gap-6",
                    modifiable && reponse.commentaires?.[q.code] && "bg-danger-doux/50")}>
                    <dt className="text-sm text-discret">{q.libelle}
                      {modifiable && reponse.commentaires?.[q.code] && <span className="mt-1 block text-xs font-medium text-danger">Correction demandée : {reponse.commentaires[q.code]}</span>}
                    </dt>
                    <dd className={cx("text-sm font-medium", !v && "font-normal text-discret/70")}>
                      {q.type === "fichier" && piece
                        ? <a href={piece.url} className="inline-flex items-center gap-1.5 text-marque hover:underline"><FileText className="h-3.5 w-3.5" />{v}</a>
                        : v || "Non renseigné"}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </Carte>
        );
      })}
    </div>
  );
}

export function Recapitulatif() {
  const { reponse, questionnaire, jeton, mettreAJour } = useFormulaire();
  const naviguer = useNavigate();
  const toast = useToast();
  const [certifie, setCertifie] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const manquants = questionnaire.modules.filter((m) => !reponse.modules_completes.includes(m.code));
  const { identification: id } = reponse;

  async function envoyer() {
    setEnvoi(true);
    try {
      mettreAJour(await api.post<ReponsePublique>(urlApi(jeton, "soumettre/"), { certification: certifie }));
      naviguer(`/r/${jeton}`, { replace: true });
      window.scrollTo({ top: 0 });
    } catch (e) {
      toast("erreur", (e as ErreurApi).message);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <p className="text-sm font-medium text-marque">Dernière étape</p>
      <h1 className="titre-display mt-1 text-4xl sm:text-[44px]">Vérifiez avant d'envoyer</h1>
      <p className="mt-2 text-discret">Relisez vos réponses. Après l'envoi, elles ne seront plus modifiables sans l'accord de la tutelle.</p>

      {manquants.length > 0 ? (
        <div className="mt-6 flex gap-3 rounded-2xl border border-alerte/30 bg-alerte-doux p-5">
          <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-alerte" />
          <div className="text-sm">
            <p className="font-semibold text-alerte">{manquants.length} rubrique{manquants.length > 1 ? "s" : ""} à compléter</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {manquants.map((m) => (
                <Link key={m.code} to={`/r/${jeton}/${m.code}`} className="rounded-lg bg-surface px-3 py-1.5 font-medium shadow-sm hover:text-marque">
                  {m.code}. {m.titre}
                </Link>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-succes/30 bg-succes-doux p-5 text-sm font-medium text-succes">
          <Check className="h-5 w-5" /> Toutes les rubriques sont complètes.
        </div>
      )}

      <div className="mt-6"><Synthese modifiable /></div>

      <Carte className="mt-6 p-6 sm:p-8">
        <h2 className="text-lg font-semibold tracking-tight">Certification</h2>
        <label className="mt-4 flex cursor-pointer gap-3 rounded-xl border border-trait p-4 transition hover:bg-relief/50">
          <input type="checkbox" checked={certifie} onChange={(e) => setCertifie(e.target.checked)} className="mt-0.5 h-5 w-5 accent-[rgb(var(--marque))]" />
          <span className="text-sm leading-relaxed">
            Je soussigné(e), <strong>{id.prenom} {id.nom}</strong>{id.fonction && `, ${id.fonction}`}, certifie l'exactitude et
            l'exhaustivité des informations transmises pour <strong>{reponse.epn.nom}</strong>.
          </span>
        </label>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-discret">Un accusé de réception sera envoyé à {id.email}.</p>
          <Bouton variante="primaire" taille="lg" disabled={!certifie || manquants.length > 0} chargement={envoi} onClick={envoyer}>
            <Send className="h-4 w-4" /> Envoyer mes réponses
          </Bouton>
        </div>
      </Carte>
    </div>
  );
}

export function Merci() {
  const { reponse } = useFormulaire();
  return (
    <div className="min-h-screen">
      <BandeauOfficiel droite={<span className="pas-imprimer"><BoutonTheme /></span>} />
      <div className="h-8" />
      <main className="mx-auto max-w-3xl px-6 pb-20">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="relative overflow-hidden rounded-2xl border border-trait bg-surface p-10 text-center shadow-flottant">
          <div className="grille-fond pointer-events-none absolute inset-0 opacity-60" />
          <motion.div initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", delay: 0.15, damping: 12 }}
            className="relative mx-auto grid h-20 w-20 place-items-center rounded-full bg-succes text-white shadow-[0_12px_40px_-8px_rgb(var(--succes)/.6)] dark:text-[#04140c]">
            <motion.svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <motion.path d="M5 12.5l4.5 4.5L19 7.5" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.45, duration: 0.5 }} />
            </motion.svg>
          </motion.div>
          <h1 className="titre-display relative mt-6 text-4xl sm:text-5xl">Merci, c'est envoyé.</h1>
          <p className="relative mx-auto mt-3 max-w-md text-discret">
            Les réponses de <strong className="text-encre">{reponse.epn.nom}</strong> ont été reçues le {date(reponse.date_soumission, true)}.
            Un accusé de réception a été envoyé à {reponse.identification.email}.
          </p>
          <div className="pas-imprimer relative mt-8 flex justify-center">
            <Bouton onClick={() => window.print()}><Printer className="h-4 w-4" /> Imprimer le récapitulatif</Bouton>
          </div>
        </motion.div>
        <h2 className="mb-4 mt-12 text-lg font-semibold tracking-tight">Récapitulatif de vos réponses</h2>
        <Synthese modifiable={false} />
        <p className="mt-8 text-center text-sm text-discret">Une correction est nécessaire ? Contactez l'administration de tutelle : elle peut rouvrir votre questionnaire.</p>
      </main>
    </div>
  );
}
