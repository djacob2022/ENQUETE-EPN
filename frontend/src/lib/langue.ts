/**
 * Version anglaise du parcours de l'établissement (F-16).
 *
 * Les textes restent écrits en français dans le code : t("…") renvoie leur traduction anglaise quand le répondant a
 * choisi l'anglais. Les variables s'écrivent {nom} : t("{n} jours restants", { n: 3 }).
 * Le choix est mémorisé dans le navigateur et transmis au serveur (en-tête X-Langue) pour traduire le questionnaire,
 * les messages d'erreur, le PDF et le modèle Excel.
 */
import { useSyncExternalStore } from "react";

export type Langue = "fr" | "en";

const CLE = "enquete-epn-langue";
const abonnes = new Set<() => void>();

function initiale(): Langue {
  try {
    const p = new URLSearchParams(window.location.search).get("langue");
    if (p === "en" || p === "fr") {
      localStorage.setItem(CLE, p);
      return p;
    }
    return localStorage.getItem(CLE) === "en" ? "en" : "fr";
  } catch {
    return "fr";
  }
}

let courante: Langue = typeof window === "undefined" ? "fr" : initiale();
if (typeof document !== "undefined") document.documentElement.lang = courante;

/** L'équipe d'enquête travaille toujours en français : la langue choisie ne vaut que pour les pages publiques. */
const pagePublique = () => typeof window === "undefined" || !/^\/(gestion|connexion|mot-de-passe)/.test(window.location.pathname);

export const langue = (): Langue => (pagePublique() ? courante : "fr");

export function changerLangue(l: Langue) {
  if (l === courante) return;
  courante = l;
  document.documentElement.lang = l;
  try { localStorage.setItem(CLE, l); } catch { /* navigation privée */ }
  abonnes.forEach((f) => f());
}

/** Rafraîchit le composant quand la langue change. */
export function useLangue() {
  return useSyncExternalStore((f) => { abonnes.add(f); return () => abonnes.delete(f); }, langue, () => "fr" as Langue);
}

/** Ajoute ?langue=en aux liens de téléchargement (PDF, Excel), qui ne passent pas par fetch. */
export function avecLangue(url: string) {
  return langue() === "en" ? `${url}${url.includes("?") ? "&" : "?"}langue=en` : url;
}

export function t(fr: string, variables?: Record<string, string | number>) {
  let texte = langue() === "en" ? EN[fr] ?? fr : fr;
  if (variables) for (const [k, v] of Object.entries(variables)) texte = texte.split(`{${k}}`).join(String(v));
  return texte;
}

/** Accord simple : pluriel(n, "rubrique", "rubriques"). */
export const pluriel = (n: number, un: string, plusieurs: string) => (n > 1 ? plusieurs : un);

const EN: Record<string, string> = {
  // Commun
  "Passer en thème clair": "Switch to light theme",
  "Passer en thème sombre": "Switch to dark theme",
  "Fermer": "Close",
  "Logo de l'institution": "Institution logo",
  "Emblème": "Emblem",
  "Langue": "Language",
  "Connexion impossible. Vérifiez votre réseau puis réessayez.": "Unable to connect. Check your network and try again.",
  "Certaines réponses sont à corriger.": "Some answers need to be corrected.",
  "Connexion impossible.": "Unable to connect.",
  "obligatoire": "required",
  // Page d'accès (lien commun)
  "Enquête officielle": "Official survey",
  "Enquête sur les Établissements Publics Nationaux": "Survey of National Public Institutions",
  "Chaque établissement public national est invité à renseigner le questionnaire de l'exercice {exercice}.":
    "Every national public institution is invited to complete the questionnaire for the {exercice} financial year.",
  "de référence": "of reference",
  "Date limite de réponse :": "Response deadline:",
  "Lien déjà envoyé": "Link already sent",
  "Lien envoyé au point focal": "Link sent to the focal point",
  "Un lien a déjà été envoyé à {email} il y a quelques minutes. Vérifiez la boîte de réception et les courriers indésirables avant de faire une nouvelle demande.":
    "A link was already sent to {email} a few minutes ago. Check the inbox and the spam folder before making a new request.",
  "Le lien du questionnaire de {epn} a été envoyé à {email}, l'adresse officielle enregistrée pour votre établissement.":
    "The questionnaire link for {epn} has been sent to {email}, the official address registered for your institution.",
  "Vous n'êtes pas le point focal ?": "Not the focal point?",
  "Demandez-lui de vous transférer l'e-mail « Votre lien d'accès au questionnaire ».":
    "Ask them to forward you the email “Your link to the questionnaire”.",
  "Cet établissement a déjà envoyé ses réponses : le lien permet de consulter le récapitulatif.":
    "This institution has already submitted its answers: the link lets you view the summary.",
  "Ouvrez l'e-mail « Votre lien d'accès au questionnaire ».": "Open the email “Your link to the questionnaire”.",
  "Cliquez sur le lien : le questionnaire de votre établissement s'ouvre.":
    "Click the link: your institution's questionnaire opens.",
  "Renseignez vos coordonnées puis les rubriques. Tout est enregistré au fur et à mesure.":
    "Enter your contact details, then the sections. Everything is saved as you go.",
  "Rien reçu après 10 minutes ? Vérifiez les courriers indésirables. Si l'adresse du point focal n'est plus à jour, contactez l'administration de tutelle.":
    "Nothing received after 10 minutes? Check the spam folder. If the focal point's address is out of date, contact the supervising authority.",
  "Choisir un autre établissement": "Choose another institution",
  "Accès au questionnaire": "Access to the questionnaire",
  "Sélectionnez votre établissement": "Select your institution",
  "Nous enverrons le lien du questionnaire à l'adresse e-mail officielle du point focal de votre établissement.":
    "We will send the questionnaire link to the official email address of your institution's focal point.",
  "Nom, sigle ou ministère de tutelle…": "Name, acronym or supervising ministry…",
  "Rechercher votre établissement": "Search for your institution",
  "Le questionnaire n'est pas ouvert en ce moment.": "The questionnaire is not open at the moment.",
  "La campagne se déroule du {debut} au {fin}.": "The survey runs from {debut} to {fin}.",
  "Établissements": "Institutions",
  "Aucun établissement ne correspond. Contactez l'administration de tutelle si le vôtre n'apparaît pas.":
    "No institution matches. Contact the supervising authority if yours is not listed.",
  "Établissement choisi :": "Selected institution:",
  "Choisissez votre établissement dans la liste ci-dessus.": "Choose your institution from the list above.",
  "Envoyer le lien au point focal": "Send the link to the focal point",
  "Pourquoi passer par le point focal ?": "Why go through the focal point?",
  "Pour que personne ne puisse répondre au nom d'un autre établissement. Seul le lien envoyé à l'adresse officielle ouvre votre questionnaire.":
    "So that nobody can answer on behalf of another institution. Only the link sent to the official address opens your questionnaire.",
  "Ce que contient le questionnaire": "What the questionnaire covers",
  "Identification et gouvernance": "Identification and governance",
  "Missions, ressources humaines et finances": "Mandate, human resources and finance",
  "Patrimoine, performance et besoins": "Assets, performance and needs",
  "Pièces justificatives (états financiers, rapport d'activités)": "Supporting documents (financial statements, activity report)",
  "Préparez vos états financiers et votre rapport d'activités au format PDF.":
    "Have your financial statements and activity report ready in PDF format.",
  "Plateforme officielle de collecte · données traitées par l'administration de tutelle":
    "Official data collection platform · data processed by the supervising authority",
  "Espace administration": "Administration area",
  // Formulaire : cadre
  "Ce lien n'est pas valide": "This link is not valid",
  "Connexion impossible": "Unable to connect",
  "Vérifiez que vous avez copié le lien complet. S'il a été remplacé par l'administration, utilisez le dernier lien reçu par e-mail, ou demandez-en un nouveau sur la page du questionnaire.":
    "Check that you copied the whole link. If the administration replaced it, use the latest link received by email, or request a new one on the questionnaire page.",
  "La saisie n'est pas ouverte": "Input is not open",
  "La campagne « {nom} » est ouverte du {debut} au {fin}. Pour un délai supplémentaire, contactez l'administration de tutelle.":
    "The survey “{nom}” is open from {debut} to {fin}. For an extension, contact the supervising authority.",
  "Votre réponse vous a été renvoyée pour correction.": "Your answers have been sent back to you for correction.",
  "Corrigez les points signalés, puis renvoyez vos réponses depuis « Vérification et envoi ».":
    "Correct the flagged items, then resubmit your answers from “Review and submit”.",
  "{n} / {total} rubriques": "{n} / {total} sections",
  "{n} jours restants": "{n} days left",
  "Dernier jour": "Last day",
  "Date limite atteinte": "Deadline reached",
  "Étapes du questionnaire": "Questionnaire steps",
  "Vos coordonnées": "Your contact details",
  "Vérification et envoi": "Review and submit",
  "Correction demandée": "Correction requested",
  "Connexion difficile ?": "Poor connection?",
  "Remplissez le questionnaire dans Excel, sans Internet, puis importez-le ici.":
    "Fill in the questionnaire in Excel, offline, then import it here.",
  "Télécharger le fichier Excel": "Download the Excel file",
  "Importer le fichier rempli": "Import the completed file",
  "Fichier importé": "File imported",
  "{n} réponse(s) enregistrée(s) en brouillon dans {r} rubrique(s). Relisez chaque rubrique avant d'envoyer.":
    "{n} answer(s) saved as a draft in {r} section(s). Review each section before submitting.",
  "{n} valeur(s) à corriger en ligne": "{n} value(s) to correct online",
  "Compris": "Got it",
  "Enregistré {quand}": "Saved {quand}",
  "Prêt": "Ready",
  "Enregistrement…": "Saving…",
  "Enregistré": "Saved",
  "Non enregistré": "Not saved",
  // Identification
  "Merci de renseigner le questionnaire de votre établissement pour l'exercice {exercice}.":
    "Please complete your institution's questionnaire for the {exercice} financial year.",
  "Date limite": "Deadline",
  "Contenu": "Content",
  "{m} rubriques · {q} questions": "{m} sections · {q} questions",
  "Sauvegarde": "Saving",
  "Automatique, reprise possible": "Automatic, you can resume later",
  "La personne qui remplit le questionnaire pour l'établissement.": "The person completing the questionnaire for the institution.",
  "Nom": "Last name",
  "Prénom": "First name",
  "Adresse e-mail": "Email address",
  "Téléphone": "Telephone",
  "Fonction dans l'établissement": "Position in the institution",
  "Directeur administratif et financier": "Director of Administration and Finance",
  "Ces informations servent uniquement au suivi de l'enquête.": "This information is used only to follow up the survey.",
  "Continuer": "Continue",
  "Commencer le questionnaire": "Start the questionnaire",
  "Vérifiez les champs signalés.": "Check the highlighted fields.",
  // Rubrique
  "{n} réponses sont à compléter ou à corriger.": "{n} answers need to be completed or corrected.",
  "Une réponse est à compléter ou à corriger.": "One answer needs to be completed or corrected.",
  "{n} réponse(s) reprise(s) de l'exercice {exercice}. Vérifiez-les et mettez-les à jour.":
    "{n} answer(s) carried over from the {exercice} financial year. Check and update them.",
  "Rien à reprendre pour cette rubrique.": "Nothing to carry over for this section.",
  "Rubrique {code} · {n} sur {total}": "Section {code} · {n} of {total}",
  "Reprendre mes réponses de l'exercice {exercice}": "Reuse my answers from the {exercice} financial year",
  "La tutelle demande une correction dans cette rubrique.": "The supervising authority requests a correction in this section.",
  "La tutelle demande {n} corrections dans cette rubrique.": "The supervising authority requests {n} corrections in this section.",
  "Les questions concernées sont signalées ci-dessous.": "The questions concerned are flagged below.",
  "Précédent": "Previous",
  "Vos réponses sont enregistrées automatiquement.": "Your answers are saved automatically.",
  "Vérifier et envoyer": "Review and submit",
  "Suivant": "Next",
  "{libelle} = effectif total": "{libelle} = total staff",
  "{libelle} = {somme}, effectif total {total}": "{libelle} = {somme}, total staff {total}",
  "Femmes + hommes": "Women + men",
  "Fonctionnaires + contractuels": "Civil servants + contract staff",
  "{n} % des indicateurs atteints": "{n}% of indicators met",
  "Plus d'indicateurs atteints que suivis": "More indicators met than monitored",
  "Exécution budgétaire : {n} %": "Budget execution: {n}%",
  // Questions
  "Correction demandée : ": "Correction requested: ",
  "Plusieurs réponses possibles.": "Several answers possible.",
  "monnaie locale": "local currency",
  "AAAA": "YYYY",
  "Entre {min} et {max}.": "Between {min} and {max}.",
  "{colonne}, ligne {n}": "{colonne}, row {n}",
  "Supprimer la ligne {n}": "Delete row {n}",
  "Ajouter une ligne": "Add a row",
  "Format non accepté : PDF, Word, Excel, JPG ou PNG.": "Format not accepted: PDF, Word, Excel, JPG or PNG.",
  "Fichier trop volumineux ({taille}). Maximum : {max}.": "File too large ({taille}). Maximum: {max}.",
  "« {nom} » déposé.": "“{nom}” uploaded.",
  "Fichier supprimé.": "File deleted.",
  "déposé le {date}": "uploaded on {date}",
  "Télécharger": "Download",
  "Remplacer": "Replace",
  "Supprimer": "Delete",
  "Envoi en cours… {n} %": "Uploading… {n}%",
  "Choisissez un fichier": "Choose a file",
  "ou glissez-le ici": "or drag it here",
  "PDF, Word, Excel, JPG ou PNG · {max} maximum": "PDF, Word, Excel, JPG or PNG · {max} maximum",
  // Récapitulatif
  "Complet": "Complete",
  "À compléter": "To complete",
  "Modifier": "Edit",
  "Non renseigné": "Not provided",
  "Dernière étape": "Last step",
  "Vérifiez avant d'envoyer": "Check before submitting",
  "Relisez vos réponses. Après l'envoi, elles ne seront plus modifiables sans l'accord de la tutelle.":
    "Review your answers. Once submitted, they can no longer be changed without the supervising authority's agreement.",
  "{n} rubrique(s) à compléter": "{n} section(s) to complete",
  "Toutes les rubriques sont complètes.": "All sections are complete.",
  "Certification": "Certification",
  "Je soussigné(e), {nom}, certifie l'exactitude et l'exhaustivité des informations transmises pour {epn}.":
    "I, the undersigned, {nom}, certify that the information submitted for {epn} is accurate and complete.",
  "Un accusé de réception, avec le récapitulatif en PDF, sera envoyé à {email}.":
    "An acknowledgement of receipt, with the PDF summary, will be sent to {email}.",
  "Aperçu du PDF": "Preview the PDF",
  "Envoyer mes réponses": "Submit my answers",
  "Merci, c'est envoyé.": "Thank you, it's been submitted.",
  "Les réponses de {epn} ont été reçues le {date}.": "The answers from {epn} were received on {date}.",
  "Un accusé de réception a été envoyé à {email}.": "An acknowledgement of receipt has been sent to {email}.",
  "Télécharger le récapitulatif (PDF)": "Download the summary (PDF)",
  "Imprimer": "Print",
  "Récapitulatif de vos réponses": "Summary of your answers",
  "Une correction est nécessaire ? Contactez l'administration de tutelle : elle peut rouvrir votre questionnaire.":
    "Need a correction? Contact the supervising authority: it can reopen your questionnaire.",
  // Aide
  "Aide en ligne": "Online help",
  "Guide de l'enquête sur les EPN": "Guide to the survey of national public institutions",
  "Questions fréquentes des établissements et guide de l'équipe d'enquête, par rôle.":
    "Frequently asked questions from institutions, and the survey team's guide by role.",
  "Imprimer le guide": "Print the guide",
  "Enregistrer en PDF": "Save as PDF",
  "Établissements : questions fréquentes": "Institutions: frequently asked questions",
  "Équipe d'enquête : guide par rôle": "Survey team: guide by role (in French)",
  "Besoin d'aide ? Écrivez à": "Need help? Write to",
};

/** FAQ de la page d'aide, en anglais. */
export const FAQ_EN: [string, string][] = [
  ["I have not received a link: what should I do?", "Open the common questionnaire link and choose your institution: your personal link is sent immediately to the focal point's official address. Also check the spam folder."],
  ["Can I answer in several sessions?", "Yes. Each answer is saved automatically one second after you type it. Reopen the same link to pick up where you left off, on a computer, tablet or phone."],
  ["Can several people fill in the questionnaire?", "Yes, with the same link, but not at the same time on the same section: the last saved input wins. The link belongs to your institution: do not share it outside."],
  ["Why does a question appear or disappear?", "Some questions are only asked depending on a previous answer (for example, the number of board meetings only if the institution has a board)."],
  ["A message reports an inconsistency: is it blocking?", "Checks (e.g. women + men = total staff) must be met to validate the section. Correct the flagged values; your draft is always kept."],
  ["Which files can I attach?", "PDF, Word, Excel, JPG or PNG, 10 MB maximum per file. An uploaded file can be replaced or deleted until the questionnaire is submitted."],
  ["Can I reuse last year's answers?", "Yes: in each section, the “Reuse my answers from the previous financial year” button pre-fills the fields. Check and update each value."],
  ["Who certifies the answers?", "Before submitting, the head of the institution (or the person they designate) ticks the accuracy certification. An acknowledgement of receipt is sent by email; the summary can be printed or saved as PDF."],
  ["The supervising authority sent the questionnaire back to me: what should I do?", "The authority's comments appear next to the questions concerned. Correct them, then resubmit from “Review and submit”. You can make corrections even after the closing date."],
  ["I need more time.", "Contact your supervising authority: it can extend the deadline for your institution."],
];
