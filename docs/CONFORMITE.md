# Conformité au cahier des charges

Correspondance entre les exigences du cahier des charges (`docs/Cahier_des_charges_ENQUETE-EPN.docx`, version 1.0) et l'application. Elle sert de base au cahier de recette (section 9).

Légende : **Conforme** · **Partiel** (l'écart est décrit) · **Non traité** (hors version, avec la raison).

## Synthèse

| Priorité | Exigences | Conformes | Partielles | Non traitées |
| --- | --- | --- | --- | --- |
| M (indispensable) | 37 | 36 | 1 | 0 |
| S (souhaitable) | 11 | 7 | 1 | 3 |
| C (optionnel) | 2 | 0 | 0 | 2 |

Le seul écart de priorité M concerne F-27 : le récapitulatif PDF est produit par l'impression du navigateur (« Enregistrer en PDF »), pas par le serveur.

## Section 3 · Acteurs et rôles

| Rôle | Mise en œuvre | Statut |
| --- | --- | --- |
| Super-administrateur | Compte `is_superuser` : tous les droits, comptes des autres super-administrateurs, `/django-admin/` | Conforme |
| Administrateur d'enquête | Rôle `administrateur` : campagnes, questionnaire, répertoire, comptes, journal, paramètres, validation | Conforme |
| Superviseur de tutelle | Rôle `superviseur`, rattaché à une ou plusieurs tutelles : ne voit que leurs EPN ; valide, renvoie pour correction, relance | Conforme |
| Répondant EPN | Lien personnel de 192 bits, envoyé à l'adresse officielle du point focal ; ne voit que son EPN | Conforme |
| Valideur EPN | Case de certification nominative avant l'envoi (nom, fonction) | Conforme |
| Analyste | Rôle `analyste` : consultation et exports, aucune modification | Conforme |
| Lecteur | Rôle `lecteur` : tableaux de bord et statistiques agrégés ; listes, fiches, exports nominatifs et pièces refusés (403) | Conforme |

Le cloisonnement est contrôlé côté serveur à chaque requête (`enquete/api.py`, `_exiger` et `_dans_perimetre`).

## Section 4 · Contenu de l'enquête

Modules A à J conformes au tableau du cahier : identification (dont région et contacts), gouvernance (directeur général et date de nomination, conseil, contrat de performance, audit interne, plan stratégique), missions, ressources humaines (sexe, statut, catégorie, tranches d'âge, recrutements, départs, masse salariale), finances, patrimoine et moyens, performance (dont tableau des indicateurs du contrat), numérique, difficultés et besoins (dont échelle d'intensité), pièces justificatives.

Chaque question porte un code unique, un libellé, une aide, un type, un caractère obligatoire, des règles de contrôle et, le cas échéant, une condition d'affichage. Les modules s'activent ou se désactivent dans l'éditeur, sans développement.

## Section 5 · Fonctionnalités

### 5.1 Authentification et comptes

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-01 | Connexion e-mail et mot de passe, politique robuste | M | Connexion par e-mail ou identifiant ; 12 caractères minimum, trois types de caractères, mots courants refusés ; Argon2 | Conforme |
| F-02 | Réinitialisation par lien e-mail | M | « Mot de passe oublié ? » : lien à usage unique valable 24 h ; réponse identique que le compte existe ou non | Conforme |
| F-03 | Double authentification administrateurs | S | — | Non traité (prévu en évolution : code par e-mail ou TOTP) |
| F-04 | Création des comptes, rôles, rattachement | M | Page **Comptes et rôles** ; la personne choisit son mot de passe via le lien reçu | Conforme |
| F-05 | Import en masse des EPN et points focaux | M | Import Excel du répertoire (dénomination, sigle, catégorie, tutelle, région, e-mail du point focal, secteur, statut) | Conforme |
| F-06 | Désactivation, expiration à 30 min d'inactivité | M | Case « Compte actif » ; session de 30 minutes repoussée à chaque requête (`SESSION_MINUTES`) | Conforme |

### 5.2 Référentiel des EPN

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-07 | Répertoire : fiche, catégorie, tutelle, région, statut | M | Fiche modifiable à l'écran ; statut Actif, En liquidation, Dissous ; seuls les actifs sont interrogés | Conforme |
| F-08 | Listes de référence | M | Ministères de tutelle, régions, secteurs ; catégories fixes (EPA, EPIC, Autre) | Conforme |
| F-09 | Historique des modifications d'une fiche | S | Changements champ par champ (avant → après, auteur, date) affichés sur la fiche | Conforme |

### 5.3 Conception des questionnaires

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-10 | Éditeur sans code, ordre par glisser-déposer | M | Menu **Questionnaire** : rubriques et questions par glisser-déposer (et flèches, accessibles au clavier) | Conforme |
| F-11 | Types de questions | M | Texte, texte long, nombre, montant, pourcentage, date, choix unique, choix multiple, oui/non, échelle, tableau à lignes répétables, adresse web, fichier joint | Conforme |
| F-12 | Règles de contrôle | M | Obligatoire, bornes min/max, format ; règles de somme (A + B = total) et de comparaison (A ≤ B) | Conforme |
| F-13 | Questions conditionnelles | M | « Afficher seulement si » une réponse précédente vaut l'une des valeurs choisies ; une question masquée n'est pas exigée et sa réponse est effacée | Conforme |
| F-14 | Versionnage, duplication d'une campagne à l'autre | M | Version incrémentée à chaque enregistrement ; une nouvelle campagne reprend le questionnaire choisi. Une question déjà renseignée ne peut être ni supprimée ni changée de type | Conforme |
| F-15 | Aperçu répondant | S | Aperçu interactif, conditions comprises | Conforme |
| F-16 | Questionnaire bilingue | C | — | Non traité |

### 5.4 Gestion des campagnes

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-17 | Intitulé, exercice, dates, EPN ciblés | M | Ciblage par catégorie et par tutelle (rien coché = tous les EPN actifs) | Conforme |
| F-18 | Invitation automatique des points focaux | M | Envoi groupé des invitations ; lien commun `/formulaire` qui envoie le lien personnel au point focal officiel | Conforme |
| F-19 | Relances automatiques paramétrables et manuelles | M | Champ « Relances automatiques » (ex. `-7,-2,1`) ; service `taches` horaire ; relance manuelle unitaire ou groupée | Conforme |
| F-20 | Prolongation pour un EPN, réouverture | S | « Prolonger le délai » sur la fiche ; « Rouvrir » une réponse validée | Conforme |

### 5.5 Saisie des réponses

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-21 | Tableau de bord du répondant | M | Avancement en %, rubriques complètes, jours restants, date limite | Conforme |
| F-22 | Saisie par section, brouillon automatique | M | Enregistrement une seconde après la frappe | Conforme |
| F-23 | Contrôles en temps réel | M | Messages par champ ; sommes et taux recalculés pendant la saisie | Conforme |
| F-24 | Pré-remplissage depuis la campagne précédente | S | Bouton par rubrique, inscrit au journal | Conforme |
| F-25 | Pièces justificatives, 10 Mo | M | PDF, Word, Excel, JPG, PNG ; contrôle du contenu réel du fichier | Conforme |
| F-26 | Import des réponses depuis un modèle Excel | S | — | Non traité (la saisie en ligne avec pré-remplissage couvre le besoin courant) |
| F-27 | Certification, accusé de réception, PDF récapitulatif | M | Certification et accusé par e-mail ; récapitulatif imprimable ou enregistrable en PDF depuis le navigateur | Partiel (pas de PDF généré par le serveur) |
| F-28 | Ordinateur, tablette, téléphone | M | Interface responsive | Conforme |

### 5.6 Validation et suivi

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-29 | Circuit brouillon, soumis, en revue, à corriger, validé | M | Statuts et actions « Prendre en revue », « Valider », « Renvoyer pour correction », « Rouvrir » ; e-mail à chaque décision | Conforme |
| F-30 | Renvoi pour correction avec commentaire par question | M | Commentaire général et par question, affichés au répondant à côté des questions concernées ; correction possible après la clôture | Conforme |
| F-31 | Suivi : taux global, par tutelle, par catégorie, retardataires | M | Tableau de bord (aussi par région), liste des retardataires et des réponses à examiner | Conforme |
| F-32 | Détection d'anomalies | S | Écart de plus de 50 % avec la réponse de l'année précédente signalé sur la fiche | Partiel (pas de détection des valeurs aberrantes au sein d'une même campagne) |

### 5.9 Administration et traçabilité

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-46 | Journal d'audit | M | Connexions, échecs, exports, soumissions, décisions de validation, relances, modifications de campagne, de questionnaire, de fiches EPN, de comptes et de paramètres. Non modifiable par l'application | Conforme |
| F-47 | Notifications dans l'application et par e-mail | M | Cloche « Activité récente » ; e-mails d'invitation, relance, accusé, correction, validation, compte | Conforme |
| F-48 | Logo, nom de l'institution, modèles d'e-mails, serveur d'envoi | M | Page **Paramètres** ; le serveur SMTP est affiché et se règle dans `.env` (le mot de passe ne va jamais en base) | Conforme |
| F-49 | Sauvegarde et restauration depuis l'interface | S | Sauvegarde quotidienne automatique ; restauration par `deploiement/restaurer.sh` | Non traité dans l'interface |
| F-50 | Aide en ligne, FAQ, guide téléchargeable | M | Page `/aide` : FAQ des établissements, guide par rôle, imprimable en PDF | Conforme |

## Section 6 · Exports, graphiques et statistiques

| Code | Exigence | P | Mise en œuvre | Statut |
| --- | --- | --- | --- | --- |
| F-33 | Réponse d'un EPN, une feuille par module | M | Bouton « Excel » de la fiche | Conforme |
| F-34 | Export consolidé et feuille Dictionnaire | M | Une ligne par EPN, une colonne par question ; feuilles Dictionnaire, Statistiques, Fréquences, Indicateurs | Conforme |
| F-35 | Filtres avant export | M | Campagne, tutelle, catégorie, région, statut ; réponses validées par défaut | Conforme |
| F-36 | Tableaux statistiques et graphiques | S | Classeur avec graphique Excel natif ; graphiques à l'écran | Conforme (PNG via l'impression du navigateur) |
| F-37 | CSV UTF-8 | S | Séparateur point-virgule, codes bruts des modalités | Conforme |
| F-38 | Tableau de bord d'accueil | M | Nombre d'EPN, taux de réponse et de validation, effectifs, budget, part des ressources propres | Conforme |
| F-39 | Graphiques automatiques | M | Barres pour les choix, histogramme pour les nombres, courbe des taux annuels | Conforme |
| F-40 | Comparaison N-1 / N | M | Indicateurs et sommes comparés à la campagne précédente | Conforme |
| F-41 | Graphiques personnalisés | S | Choix des deux variables croisées et du type (barres empilées, groupées, tableau) | Conforme |
| F-42 | Carte des EPN par région | C | Répartition par région en tableau et en barres | Non traité (carte) |
| F-43 | Filtres communs | M | Tutelle, catégorie, région, base de réponses | Conforme |
| F-44 | Statistiques descriptives | M | Effectif, somme, moyenne, médiane, minimum, quartiles, maximum, écart-type | Conforme |
| F-45 | Fréquences et tableaux croisés | M | Effectifs et pourcentages en ligne | Conforme |

Règles de format respectées : montants en nombres, dates au format date Excel, en-têtes figés, filtres automatiques, nom `EPN_<exercice>_<date>.xlsx`, injection de formules neutralisée. Les statistiques portent par défaut sur les réponses validées et affichent toujours n. Les exports sont produits immédiatement ; le traitement en tâche de fond prévu au-delà de 500 EPN n'est pas nécessaire aux volumes actuels.

## Section 7 · Exigences non fonctionnelles

| Domaine | Mise en œuvre | Statut |
| --- | --- | --- |
| Sécurité des accès | HTTPS par Caddy (TLS 1.2 minimum), HSTS ; Argon2 ; blocage après 5 échecs ; droits contrôlés côté serveur | Conforme |
| Sécurité applicative | Protection CSRF, échappement XSS, requêtes paramétrées, politique de sécurité du contenu, audit de sécurité réalisé | Conforme (test d'intrusion externe à commander avant la production) |
| Données personnelles | Collecte limitée aux coordonnées du répondant | À compléter par le maître d'ouvrage (déclaration, durées de conservation) |
| Confidentialité | Hébergement sur le serveur de l'administration ; sauvegardes locales | Partiel (chiffrement et copie hors site des sauvegardes à organiser) |
| Traçabilité | Journal non modifiable par l'application ; aucune purge automatique (conservation ≥ 3 ans) | Conforme |
| Performance, disponibilité | Gunicorn (3 processus), contrôles de santé, redémarrage automatique | À mesurer en recette (tests de charge) |
| Ergonomie, accessibilité | Français, responsive, clavier, contrastes, libellés ARIA | Conforme (audit WCAG 2.1 AA formel à réaliser) |
| Maintenabilité | Code documenté, 70 tests automatisés, couverture du code métier 86 %, dépôt Git, CI | Conforme |
| Évolutivité | Modules, questions et règles sans développement ; API JSON | Partiel (pas de documentation OpenAPI publiée) |

## Section 8 · Architecture et déploiement

La pile retenue est équivalente à celle recommandée, comme le cahier l'autorise (section 8) :

| Recommandé | Retenu | Justification |
| --- | --- | --- |
| Nginx + Let's Encrypt | Caddy 2.8 | Certificat HTTPS obtenu et renouvelé automatiquement, configuration de 10 lignes |
| Celery + Redis | Service `taches` (même image, commande `manage.py taches --boucle`) | Seules tâches planifiées : relances horaires ; deux conteneurs de moins à exploiter |
| MinIO | Volume Docker `media` | Volumes modestes (10 Mo par pièce) ; sauvegarde quotidienne avec la base |
| Django REST Framework | API JSON en vues Django | Mêmes garanties (session, CSRF, droits), moins de dépendances |
| ECharts / Chart.js | Recharts | Bibliothèque React équivalente |

Exigences de déploiement : `docker compose up -d` démarre tout et applique les migrations ; aucun secret dans l'image ni dans le dépôt ; conteneur applicatif sans droits root, avec contrôle de santé et redémarrage automatique ; image versionnée (`ENQUETE_VERSION`) ; CI GitHub Actions (tests, interface, image, analyse Trivy) ; mise à jour et retour arrière par `deploiement/mettre-a-jour.sh` et `restaurer.sh`. La supervision Prometheus/Grafana n'est pas fournie : le point `/api/sante/` peut y être branché.
