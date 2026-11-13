import { motion } from "framer-motion";
import { ArrowRight, CalendarClock, FileText, Save } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { t } from "@/lib/langue";
import { Identification as Ident, ReponsePublique } from "@/lib/types";
import { Bouton, Carte, Champ, useToast } from "@/ui";
import { urlApi, useFormulaire } from "./Formulaire";

export default function Identification() {
  const { reponse, questionnaire, jeton, mettreAJour } = useFormulaire();
  const naviguer = useNavigate();
  const toast = useToast();
  const [valeurs, setValeurs] = useState<Ident>(reponse.identification);
  const [erreurs, setErreurs] = useState<Record<string, string[]>>({});
  const [envoi, setEnvoi] = useState(false);
  const nbQuestions = questionnaire.modules.reduce((n, m) => n + m.questions.length, 0);

  const champ = (cle: keyof Ident) => ({
    value: valeurs[cle],
    erreurs: erreurs[cle],
    required: true,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      setValeurs((v) => ({ ...v, [cle]: e.target.value }));
      setErreurs(({ [cle]: _, ...reste }) => reste);
    },
  });

  async function valider(e: FormEvent) {
    e.preventDefault();
    setEnvoi(true);
    try {
      const r = await api.post<ReponsePublique>(urlApi(jeton, "identification/"), valeurs);
      mettreAJour(r);
      const suite = questionnaire.modules.find((m) => !r.modules_completes.includes(m.code))?.code ?? "recapitulatif";
      naviguer(`/r/${jeton}/${suite}`);
    } catch (err) {
      const e = err as ErreurApi;
      setErreurs(e.erreurs ?? {});
      toast("erreur", e.erreurs ? t("Vérifiez les champs signalés.") : e.message);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        className="motif-officiel relative overflow-hidden rounded-2xl bg-institution p-8 text-white shadow-flottant sm:p-10">
        <div className="tricolore absolute inset-x-0 top-0 h-1" aria-hidden />
        <p className="relative text-xs font-medium uppercase tracking-[.18em] text-white/60">{reponse.campagne.nom}</p>
        <h1 className="titre-display relative mt-3 text-4xl leading-tight sm:text-5xl">{reponse.epn.nom}</h1>
        <p className="relative mt-3 max-w-xl text-white/75">
          {t("Merci de renseigner le questionnaire de votre établissement pour l'exercice {exercice}.", { exercice: reponse.campagne.exercice })}
        </p>
        <dl className="relative mt-8 grid gap-3 sm:grid-cols-3">
          {[
            { icone: CalendarClock, titre: t("Date limite"), texte: date(reponse.campagne.date_cloture) },
            { icone: FileText, titre: t("Contenu"), texte: t("{m} rubriques · {q} questions", { m: questionnaire.modules.length, q: nbQuestions }) },
            { icone: Save, titre: t("Sauvegarde"), texte: t("Automatique, reprise possible") },
          ].map((i) => (
            <div key={i.titre} className="rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur">
              <i.icone className="h-4 w-4 text-white/60" />
              <dt className="mt-2 text-xs text-white/60">{i.titre}</dt>
              <dd className="text-sm font-medium">{i.texte}</dd>
            </div>
          ))}
        </dl>
      </motion.section>

      <Carte className="mt-6 animate-apparaitre">
        <form onSubmit={valider} noValidate className="p-6 sm:p-8">
          <h2 className="text-lg font-semibold tracking-tight">{t("Vos coordonnées")}</h2>
          <p className="mt-1 text-sm text-discret">{t("La personne qui remplit le questionnaire pour l'établissement.")}</p>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <Champ libelle={t("Nom")} autoComplete="family-name" {...champ("nom")} />
            <Champ libelle={t("Prénom")} autoComplete="given-name" {...champ("prenom")} />
            <Champ libelle={t("Adresse e-mail")} type="email" autoComplete="email" {...champ("email")} />
            <Champ libelle={t("Téléphone")} type="tel" autoComplete="tel" placeholder="+225 07 00 00 00 00" {...champ("telephone")} />
            <Champ libelle={t("Fonction dans l'établissement")} className="sm:col-span-2" placeholder={t("Directeur administratif et financier")} {...champ("fonction")} />
          </div>
          <div className="mt-8 flex flex-col-reverse items-stretch justify-between gap-4 border-t border-trait pt-6 sm:flex-row sm:items-center">
            <p className="text-xs text-discret">{t("Ces informations servent uniquement au suivi de l'enquête.")}</p>
            <Bouton type="submit" variante="primaire" taille="lg" chargement={envoi}>
              {reponse.identifie ? t("Continuer") : t("Commencer le questionnaire")} <ArrowRight className="h-4 w-4" />
            </Bouton>
          </div>
        </form>
      </Carte>
    </div>
  );
}
