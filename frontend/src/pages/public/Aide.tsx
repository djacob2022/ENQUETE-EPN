import { ChevronDown, Download, Printer } from "lucide-react";
import { BandeauOfficiel, useConfig } from "@/composants/Officiel";
import BoutonTheme from "@/composants/BoutonTheme";
import { Bouton, Carte } from "@/ui";

const FAQ_EPN: [string, string][] = [
  ["Je n'ai pas reçu de lien : que faire ?", "Ouvrez le lien commun du questionnaire, choisissez votre établissement : votre lien personnel part aussitôt à l'adresse officielle du point focal. Vérifiez aussi le dossier des courriers indésirables."],
  ["Puis-je répondre en plusieurs fois ?", "Oui. Chaque réponse est enregistrée automatiquement une seconde après la saisie. Rouvrez le même lien pour reprendre où vous en étiez, sur ordinateur, tablette ou téléphone."],
  ["Plusieurs personnes peuvent-elles remplir le questionnaire ?", "Oui, avec le même lien, mais pas en même temps sur la même rubrique : la dernière saisie enregistrée l'emporte. Le lien est propre à votre établissement : ne le diffusez pas en dehors."],
  ["Pourquoi une question apparaît-elle ou disparaît-elle ?", "Certaines questions ne sont posées que selon une réponse précédente (par exemple, le nombre de sessions du conseil seulement si l'établissement a un conseil)."],
  ["Un message signale une incohérence : est-ce bloquant ?", "Les contrôles (ex. femmes + hommes = effectif total) doivent être respectés pour valider la rubrique. Corrigez les valeurs signalées ; le brouillon, lui, est toujours conservé."],
  ["Quels fichiers puis-je joindre ?", "PDF, Word, Excel, JPG ou PNG, 10 Mo maximum par fichier. Un fichier déposé peut être remplacé ou supprimé tant que le questionnaire n'est pas envoyé."],
  ["Puis-je reprendre les réponses de l'an dernier ?", "Oui : dans chaque rubrique, le bouton « Reprendre mes réponses de l'exercice précédent » préremplit les champs. Vérifiez et mettez à jour chaque valeur."],
  ["Qui certifie les réponses ?", "Avant l'envoi, le responsable de l'établissement (ou la personne qu'il désigne) coche la certification d'exactitude. Un accusé de réception est envoyé par e-mail ; le récapitulatif s'imprime ou s'enregistre en PDF."],
  ["La tutelle m'a renvoyé le questionnaire : que faire ?", "Les commentaires de la tutelle s'affichent à côté des questions concernées. Corrigez, puis renvoyez depuis « Vérification et envoi ». Vous pouvez corriger même après la date de clôture."],
  ["J'ai besoin de plus de temps.", "Contactez votre tutelle : elle peut prolonger le délai pour votre établissement."],
];

const GUIDE_EQUIPE: [string, string[]][] = [
  ["Administrateur d'enquête", [
    "Campagnes : créer la campagne (exercice, dates, EPN ciblés, relances automatiques J-7, J-2, J+1).",
    "Questionnaire : ajouter, modifier, réordonner les questions par glisser-déposer, définir conditions et règles ; l'aperçu montre le formulaire tel que le verra le répondant.",
    "Répertoire : importer les EPN et points focaux depuis Excel, tenir à jour les fiches et listes de référence.",
    "Liens et invitations : envoyer les invitations ; partager le lien commun.",
    "Comptes et rôles : créer les comptes de l'équipe ; journal d'audit et paramètres.",
  ]],
  ["Superviseur de tutelle", [
    "Réponses : examiner les réponses soumises des EPN de sa tutelle, les valider ou les renvoyer pour correction avec un commentaire par question.",
    "Relancer les retardataires, prolonger un délai pour un établissement.",
  ]],
  ["Analyste", [
    "Statistiques : descriptifs, fréquences, tableaux croisés, comparaison avec l'exercice précédent.",
    "Exports Excel (avec dictionnaire des variables) et CSV pour SPSS, Stata ou R.",
  ]],
  ["Lecteur", ["Tableau de bord et statistiques agrégés, sans données nominatives."]],
];

/** Aide en ligne, foire aux questions et guide utilisateur imprimable (F-50). */
export default function Aide() {
  const config = useConfig();
  return (
    <div className="min-h-screen">
      <BandeauOfficiel droite={<span className="pas-imprimer"><BoutonTheme /></span>} />
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-sm font-medium text-marque">Aide en ligne</p>
        <h1 className="titre-display mt-1 text-4xl sm:text-5xl">Guide de l'enquête sur les EPN</h1>
        <p className="mt-3 text-discret">Questions fréquentes des établissements et guide de l'équipe d'enquête, par rôle.</p>
        <div className="pas-imprimer mt-6 flex flex-wrap gap-2">
          <Bouton icone={<Printer className="h-4 w-4" />} onClick={() => window.print()}>Imprimer le guide</Bouton>
          <Bouton variante="fantome" icone={<Download className="h-4 w-4" />} onClick={() => window.print()}>Enregistrer en PDF</Bouton>
        </div>

        <h2 className="mb-4 mt-12 text-xl font-semibold tracking-tight">Établissements : questions fréquentes</h2>
        <div className="space-y-2">
          {FAQ_EPN.map(([q, r]) => (
            <details key={q} className="group rounded-2xl border border-trait bg-surface px-5 py-4 open:shadow-carte">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                {q}<ChevronDown className="h-4 w-4 shrink-0 text-discret transition group-open:rotate-180" />
              </summary>
              <p className="mt-3 text-[15px] leading-relaxed text-discret">{r}</p>
            </details>
          ))}
        </div>

        <h2 className="mb-4 mt-12 text-xl font-semibold tracking-tight">Équipe d'enquête : guide par rôle</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {GUIDE_EQUIPE.map(([role, points]) => (
            <Carte key={role} className="break-inside-avoid p-5">
              <h3 className="font-semibold">{role}</h3>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-discret">{points.map((p) => <li key={p}>{p}</li>)}</ul>
            </Carte>
          ))}
        </div>

        {config?.assistance && (
          <p className="mt-12 rounded-2xl bg-marque-doux px-5 py-4 text-sm">Besoin d'aide ? Écrivez à <a href={`mailto:${config.assistance}`} className="font-semibold text-marque underline">{config.assistance}</a>.</p>
        )}
      </main>
    </div>
  );
}
