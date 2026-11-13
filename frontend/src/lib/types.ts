export type TypeQuestion =
  | "texte" | "texte_long" | "url" | "entier" | "montant" | "pourcentage" | "date"
  | "choix" | "choix_multiple" | "oui_non" | "echelle" | "tableau" | "fichier";

export interface Choix { valeur: string; libelle: string; libelle_en?: string }

export interface Question {
  code: string;
  libelle: string;
  type: TypeQuestion;
  obligatoire: boolean;
  min?: number;
  max?: number;
  unite?: string;
  aide?: string;
  annee?: boolean;
  choix?: Choix[];
  si?: { question: string; valeurs: string[] };
  colonnes?: { code: string; libelle: string; type: "texte" | "nombre"; libelle_en?: string }[];
  libelle_min?: string;
  libelle_max?: string;
  // Version anglaise (F-16), éditeur seulement
  libelle_en?: string;
  aide_en?: string;
  unite_en?: string;
  libelle_min_en?: string;
  libelle_max_en?: string;
}

export interface Module { code: string; titre: string; intro: string; actif?: boolean; questions: Question[]; titre_en?: string; intro_en?: string }

export interface Regle { type: "somme" | "inferieur"; total?: string; parties?: string[]; petit?: string; grand?: string; message?: string; message_en?: string }

export interface Questionnaire { modules: Module[]; version: number; fichiers: { accept: string; taille_max: number } }

export interface QuestionnaireEditeur extends Questionnaire {
  regles: Regle[];
  types: Choix[];
  modifie_le?: string;
  modifie_par?: string;
  avec_reponses: number;
  campagne: Campagne;
}

export type LigneTableau = Record<string, string | number | null>;

export interface Campagne {
  id: number;
  nom: string;
  exercice: number;
  date_ouverture: string;
  date_cloture: string;
  active: boolean;
  ouverte: boolean;
  cible_tutelles: string;
  cible_categories: string;
  relances_auto: string;
  version_questionnaire: number;
  total?: number;
  soumis?: number;
  validees?: number;
}

export interface Piece { id?: number; code: string; nom: string; taille: number; date_depot: string; url: string }

export type Valeur = string | number | string[] | LigneTableau[] | null | undefined;

export interface Identification { nom: string; prenom: string; fonction: string; email: string; telephone: string }

export interface ReponsePublique {
  etat: "ouvert" | "soumis" | "ferme";
  statut: Statut;
  epn: { nom: string; sigle: string; categorie: string; tutelle: string };
  campagne: Campagne;
  identification: Identification;
  identifie: boolean;
  donnees: Record<string, Valeur>;
  modules_completes: string[];
  avancement: number;
  pieces: Record<string, Piece>;
  date_soumission: string | null;
  date_modification: string | null;
  date_limite: string;
  commentaires: Record<string, string>;
  precedente: number | null;
}

export type Statut = "invite" | "en_cours" | "soumis" | "en_revue" | "a_corriger" | "valide";

export interface EPN {
  id: number; nom: string; sigle: string; categorie: string; tutelle: string; region: string;
  secteur: string; email_contact: string; actif: boolean; etat: "actif" | "liquidation" | "dissous"; etat_libelle: string;
}

export interface ReponseResume {
  id: number;
  statut: Statut;
  statut_libelle: string;
  avancement: number;
  epn: EPN;
  repondant: string;
  email: string;
  telephone: string;
  fonction: string;
  date_invitation: string | null;
  date_soumission: string | null;
  date_modification: string | null;
  nombre_relances: number;
  date_derniere_relance: string | null;
  lien: string;
  date_validation: string | null;
  valide_par: string;
  date_limite: string | null;
  a_des_commentaires: boolean;
}

export interface ReponseDetail extends ReponseResume {
  campagne: Campagne;
  modules: { code: string; titre: string; complet: boolean;
    lignes: { code: string; libelle: string; type: TypeQuestion; valeur: string; piece?: Piece | null;
      precedent?: string; ecart?: number; anomalie?: boolean; atypique?: "haut" | "bas" }[] }[];
  commentaires: Record<string, string>;
  exercice_precedent: number | null;
  export_url: string;
  pdf_url: string;
  pieces: Piece[];
  zip_url: string | null;
  envois: { type: string; date: string; succes: boolean; destinataires: string; par: string }[];
}

export interface Indicateur { libelle: string; valeur: number | null; formule: string }
export interface TauxGroupe { libelle: string; soumis: number; total: number; taux: number }

export interface TableauDeBord {
  campagne: Campagne;
  invites: number;
  compte: Record<Statut, number>;
  taux: number;
  taux_validation: number;
  sans_lien: number;
  nombre_epn: number;
  base_indicateurs: "validees" | "envoyees";
  n_indicateurs: number;
  a_examiner: ReponseResume[];
  par_region: TauxGroupe[];
  effectif_total: number;
  budget_total: number;
  par_tutelle: TauxGroupe[];
  par_categorie: TauxGroupe[];
  retardataires: ReponseResume[];
  dernieres: ReponseResume[];
  indicateurs: Indicateur[];
  historique: { libelle: string; taux: number }[];
}

export interface Options {
  campagnes: Campagne[];
  courante: Campagne | null;
  tutelles: string[];
  regions: string[];
  secteurs: string[];
  categories: Choix[];
  etats: Choix[];
  statuts: Choix[];
  roles: Choix[];
}

export interface StatNumerique {
  n: number; somme?: number; moyenne?: number; mediane?: number; min?: number; max?: number; ecart_type?: number;
  q1?: number; q3?: number; histogramme?: { de: number; a: number; effectif: number }[];
}
export interface StatFrequence { n: number; lignes: { code: string; libelle: string; effectif: number; pourcentage: number }[] }

export interface Statistiques {
  campagne: Campagne;
  n: number;
  base: "validees" | "envoyees" | "toutes" | "statut";
  blocs: { code: string; titre: string; questions: ({ code: string; libelle: string; type: TypeQuestion; unite?: string } &
    ({ genre: "numerique"; stats: StatNumerique; precedent?: StatNumerique } | { genre: "frequence"; stats: StatFrequence }))[] }[];
  indicateurs: Indicateur[];
  precedente: { campagne: Campagne; n: number; indicateurs: Indicateur[] } | null;
  historique: { libelle: string; taux: number }[];
  variables: { valeur: string; libelle: string; groupe: string }[];
  atypiques: { reponse: number; epn: string; code: string; libelle: string; valeur: number; bas: number; haut: number; sens: "haut" | "bas" }[];
}

export interface TableauCroise {
  ligne: string; colonne: string; colonnes: string[]; n: number;
  lignes: { libelle: string; effectifs: number[]; total: number; pourcentages: number[] }[];
}

export type Permission = "voir_nominatif" | "exporter" | "valider" | "relancer" | "gerer_liens" | "gerer_campagnes"
  | "gerer_questionnaire" | "gerer_repertoire" | "voir_journal" | "gerer_comptes" | "parametrer";

export interface Moi {
  identifiant: string; nom: string; email: string; superutilisateur: boolean; perimetre: string[] | null;
  administrateur: boolean; role: string; role_libelle: string; permissions: Permission[]; session_minutes: number;
  deux_facteurs: boolean;
}

export interface Compte {
  id: number; identifiant: string; email: string; prenom: string; nom: string; actif: boolean; superutilisateur: boolean;
  role: string; tutelles: string[]; derniere_connexion: string | null; mot_de_passe_defini: boolean; deux_facteurs: boolean;
}

export interface LigneJournal {
  id: number; date: string; auteur: string; action: string; libelle: string; objet: string;
  detail: Record<string, unknown>; ip: string | null;
}

export interface Notification { id: number; date: string; action: string; libelle: string; objet: string; auteur: string; reponse?: number }
