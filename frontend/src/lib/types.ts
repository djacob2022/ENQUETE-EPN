export type TypeQuestion =
  | "texte" | "texte_long" | "url" | "entier" | "montant" | "pourcentage"
  | "choix" | "choix_multiple" | "oui_non" | "fichier";

export interface Choix { valeur: string; libelle: string }

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
}

export interface Module { code: string; titre: string; intro: string; questions: Question[] }

export interface Questionnaire { modules: Module[]; fichiers: { accept: string; taille_max: number } }

export interface Campagne {
  id: number;
  nom: string;
  exercice: number;
  date_ouverture: string;
  date_cloture: string;
  active: boolean;
  ouverte: boolean;
  total?: number;
  soumis?: number;
}

export interface Piece { id?: number; code: string; nom: string; taille: number; date_depot: string; url: string }

export type Valeur = string | number | string[] | null | undefined;

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
}

export type Statut = "invite" | "en_cours" | "soumis";

export interface EPN {
  id: number; nom: string; sigle: string; categorie: string; tutelle: string; region: string;
  email_contact: string; actif: boolean;
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
}

export interface ReponseDetail extends ReponseResume {
  campagne: Campagne;
  modules: { code: string; titre: string; complet: boolean;
    lignes: { code: string; libelle: string; type: TypeQuestion; valeur: string; piece?: Piece | null }[] }[];
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
  sans_lien: number;
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
  categories: Choix[];
  statuts: Choix[];
}

export interface StatNumerique { n: number; somme?: number; moyenne?: number; mediane?: number; min?: number; max?: number; ecart_type?: number }
export interface StatFrequence { n: number; lignes: { code: string; libelle: string; effectif: number; pourcentage: number }[] }

export interface Statistiques {
  campagne: Campagne;
  n: number;
  blocs: { code: string; titre: string; questions: ({ code: string; libelle: string; type: TypeQuestion } &
    ({ genre: "numerique"; stats: StatNumerique } | { genre: "frequence"; stats: StatFrequence }))[] }[];
  indicateurs: Indicateur[];
  historique: { libelle: string; taux: number }[];
}

export interface Moi { identifiant: string; nom: string; superutilisateur: boolean }
