# Assistant IA et rapport annuel automatique

## Rapport annuel (aucune configuration)

Page **Assistant IA et rapport** (ou bouton « Rapport annuel » de la page Statistiques) : téléchargement du PDF de la
campagne choisie, sur la base de calcul choisie (réponses validées par défaut), dans le périmètre du compte connecté.

Contenu : chiffres clés ; synthèse (constats chiffrés rédigés automatiquement, plus la synthèse IA si elle a été
rédigée) ; participation par tutelle, catégorie et région ; indicateurs de la section 6.3 comparés à l'exercice
précédent ; résultats par rubrique (tableaux et graphiques) ; contrôle qualité (valeurs atypiques, sans nom
d'établissement) ; méthodologie. Aucune donnée nominative.

**Envoi automatique** : le service `taches` (docker compose) envoie le rapport par e-mail aux administrateurs (comptes
actifs avec e-mail, administrateurs d'enquête sans limite de tutelle ou super-administrateurs) `RAPPORT_AUTO_JOURS`
jours après la date de clôture (15 par défaut ; vide = jamais). Un seul envoi par campagne, tracé au journal
(« Rapport annuel envoyé automatiquement »). Si l'assistant IA est configuré, sa synthèse est rédigée et jointe.

## Assistant IA (facultatif)

Il utilise Claude, le modèle d'Anthropic, par son API. Pour l'activer :

1. Créer un compte API au nom de l'institution sur https://console.anthropic.com et générer une clé.
2. Dans le fichier `.env` du serveur : `ANTHROPIC_API_KEY=sk-ant-…`
3. Relancer : `./deploiement/mettre-a-jour.sh` (ou `docker compose up -d`).
4. Le serveur doit pouvoir joindre `https://api.anthropic.com` (sortie HTTPS).

Réglages : `ASSISTANT_IA_MODELE` (défaut `claude-opus-5-5`), `ASSISTANT_IA_EFFORT` (`low`, `medium`, `high` : plus
élevé = analyses plus fouillées, plus lentes et plus chères), `ASSISTANT_IA_QUESTIONS_PAR_HEURE` (30 par compte).
Si le modèle décline une demande, l'API la rejoue automatiquement sur le modèle de repli recommandé par Anthropic
(paramètre `fallbacks`).

Usages :
- **Questions** en langage naturel sur la campagne (« quels EPN ont le taux d'exécution le plus faible ? »,
  « compare avec l'an dernier »…), avec une conversation suivie ;
- **Synthèse du rapport annuel** : analyse rédigée, points forts, points de vigilance, besoins des EPN,
  recommandations. Elle est enregistrée et reprise dans chaque PDF jusqu'à ce qu'on la rédige à nouveau.

### Données transmises à Anthropic

| Compte | Envoyé |
| --- | --- |
| Tous | Chiffres agrégés de la campagne dans le périmètre du compte : participation, indicateurs, statistiques et fréquences par question, N-1 |
| Administrateur, superviseur, analyste (droit « voir les réponses ») | En plus : valeurs chiffrées et réponses aux questions à choix par établissement (nom, sigle, tutelle, catégorie, région), réponses aux questions ouvertes (700 caractères au plus chacune) |
| Lecteur | Rien de plus que les agrégats ; pas de synthèse IA |

Jamais envoyé : nom, fonction, e-mail et téléphone des répondants, pièces jointes, comptes de l'équipe, journal.

Selon les conditions commerciales de l'API d'Anthropic, les données envoyées ne servent pas à entraîner les modèles ;
elles sont conservées un temps limité pour la sécurité du service. Avant activation, faites valider ce traitement par
le délégué à la protection des données de l'institution (hébergement hors du pays, nature des réponses ouvertes).

Chaque question et chaque synthèse sont tracées au journal d'audit (auteur, campagne, base). Les réponses de
l'assistant sont générées automatiquement : vérifier les chiffres importants dans les statistiques avant diffusion.
