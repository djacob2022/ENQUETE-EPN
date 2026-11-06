# ENQUÊTE-EPN

Application web de collecte d'informations auprès des Établissements Publics Nationaux (EPN), avec export Excel, statistiques et graphiques.

## Architecture

| Couche | Technologies | Rôle |
| --- | --- | --- |
| Interface (`frontend/`) | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts, Framer Motion | Formulaire des EPN, espace administrateur, thème clair/sombre, mobile |
| API (`enquete/`, `config/`) | Python 3.12, Django 5.2 LTS | API JSON, règles de validation et de cohérence, e-mails, exports Excel, pièces jointes |
| Données | PostgreSQL 16 | Établissements, campagnes, réponses, fichiers |

L'interface appelle l'API sous `/api/` (même origine, session et jeton CSRF). En production, l'image Docker construit l'interface React, puis Django la sert avec ses fichiers statiques.

## Fonctionnement

**Le lien à diffuser à toutes les entités : `https://<votre-domaine>/formulaire`** (en local : http://localhost:8000/formulaire).
C'est le même lien pour tous. L'entité y choisit son établissement ; son lien personnel est alors envoyé à l'adresse e-mail officielle de son point focal (enregistrée dans le répertoire). Personne ne peut donc répondre à la place d'un autre établissement.

1. **L'administrateur** importe la liste des EPN (fichier Excel), crée une campagne (EPN ciblés, relances automatiques J-7, J-2, J+1), ajuste le questionnaire dans l'**éditeur sans code**, puis envoie les **invitations** : chaque EPN reçoit par e-mail un **lien personnel**.
2. **La personne qui reçoit le lien** saisit ses **nom, prénom, e-mail et téléphone**, puis répond rubrique par rubrique (enregistrement automatique, contrôles en direct, questions conditionnelles, reprise des réponses de l'an dernier). Elle relit, certifie, puis envoie. Un accusé de réception part par e-mail.
3. **La tutelle** examine la réponse : elle la **valide** ou la **renvoie pour correction** avec un commentaire par question. L'EPN corrige et renvoie (circuit brouillon → soumis → en revue → à corriger → validé).
4. **L'espace de gestion** (`/gestion/`) permet aussi de :
   - suivre l'avancement (taux de réponse par tutelle, catégorie, région ; retardataires ; réponses à examiner) ;
   - relancer, prolonger le délai d'un EPN, remplacer un lien compromis ;
   - **exporter** en Excel (consolidé avec dictionnaire, ou une feuille par module pour un EPN) et en CSV ;
   - produire les **statistiques** (quartiles, histogrammes, fréquences, tableaux croisés, comparaison N-1 / N) sur les réponses **validées** par défaut ;
   - gérer les **comptes et rôles**, consulter le **journal d'audit**, régler les **paramètres** (logo, identité, textes des e-mails).

Le questionnaire de départ (10 rubriques A à J, 68 questions, section 4 du cahier des charges) est défini dans `enquete/questionnaire.py` ; chaque campagne en garde ensuite sa propre version, modifiable dans le menu **Questionnaire**.

### Rôles

| Rôle | Droits |
| --- | --- |
| Super-administrateur (`is_superuser`) | Tout, y compris les comptes des autres super-administrateurs |
| Administrateur d'enquête | Campagnes, questionnaire, répertoire, comptes, journal, paramètres, validation |
| Superviseur de tutelle | Réponses des EPN de sa tutelle : validation, renvoi pour correction, relances, liens |
| Analyste | Consultation de tous les résultats et exports, sans modification |
| Lecteur | Tableaux de bord et statistiques agrégés, sans données nominatives |

La correspondance exigence par exigence avec le cahier des charges est dans [`docs/CONFORMITE.md`](docs/CONFORMITE.md).

## Installer et tester sur votre ordinateur

**Prérequis :** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS) ou Docker Engine (Linux), démarré ; [Git](https://git-scm.com/downloads).

1. Récupérer le code :

   ```bash
   git clone https://github.com/djacob2022/ENQUETE-EPN.git
   cd ENQUETE-EPN
   ```

2. Lancer l'application :
   - Windows (PowerShell) : `.\lancer.ps1`. Si Windows bloque le script : `powershell -ExecutionPolicy Bypass -File .\lancer.ps1`.
   - macOS / Linux : `./lancer.sh`

   Au premier lancement, le script crée le fichier `.env` avec des mots de passe aléatoires et affiche l'identifiant administrateur (`admin`) et son mot de passe. La construction prend quelques minutes.

3. Tester :
   - **Espace administrateur :** http://localhost:8000/connexion/. Des EPN et des réponses fictives sont déjà chargés.
   - **Côté EPN :** menu **Liens des EPN**. Chaque EPN y a son lien unique, avec les boutons « Copier » et « Ouvrir ». Le bouton « Générer les liens manquants » crée les liens des nouveaux EPN, et « Exporter les liens (Excel) » donne la liste complète pour un publipostage. Le menu **Invitations** envoie ces mêmes liens automatiquement par e-mail.
   - **Lire l'e-mail reçu par l'EPN :** ouvrir http://localhost:8025 (Mailpit). Cliquer sur le lien qu'il contient pour remplir le questionnaire comme un EPN.
   - **Retour côté administrateur :** relances, export Excel, statistiques.

4. Arrêter : `.\lancer.ps1 arreter` ou `./lancer.sh arreter` (les données sont conservées). Tout effacer : `effacer` au lieu de `arreter`.

Personnaliser l'en-tête officiel : `PAYS`, `DEVISE`, `NOM_MINISTERE` et `NOM_INSTITUTION` dans `.env`. Les couleurs nationales se règlent dans `frontend/src/index.css` (`--marque`, `--accent`). L'emblème neutre (`frontend/src/composants/Officiel.tsx`) est à remplacer par les armoiries officielles.

Afficher tous les liens dans le terminal (`--generer` crée d'abord ceux qui manquent) :

```bash
docker compose exec web python manage.py liens_epn --generer
```

Commandes utiles : `docker compose ps` (état des services), `docker compose logs -f web` (journal), `docker compose up -d --build` (reconstruire après une mise à jour du code avec `git pull`).

Le port 8000 ou 8025 est déjà utilisé ? Dans `.env`, ajoutez `WEB_PORT=8080` et ouvrez http://localhost:8080 ; mettez aussi `SITE_URL=http://localhost:8080` et `DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8080`.

## Pièces justificatives

La rubrique J permet de déposer des fichiers : états financiers et rapport d'activités (obligatoires), organigramme, procès-verbaux et autre document (facultatifs).

- Formats acceptés : PDF, Word, Excel, JPG et PNG, 10 Mo maximum par fichier. Le contenu est contrôlé, pour refuser par exemple un exécutable renommé en `.pdf`.
- Les fichiers sont stockés sous un nom aléatoire dans le volume Docker `media`. Ils ne sont jamais publiés directement : seuls l'EPN, avec son lien personnel, et les administrateurs connectés peuvent les télécharger.
- Déposer un nouveau fichier remplace l'ancien. La sauvegarde quotidienne archive aussi ces fichiers.

## Démarrage avec Docker (manuel)

```bash
cp .env.example .env        # puis changer les mots de passe
docker compose --profile dev up -d --build
```

- Application : http://localhost:8000 (espace administrateur : http://localhost:8000/connexion/)
- E-mails de test (Mailpit) : http://localhost:8025. Toutes les invitations et relances y arrivent sans être réellement envoyées. Mailpit ne démarre qu'avec `--profile dev` et n'est accessible que depuis le poste lui-même : il conserve tous les liens personnels.
- Le compte administrateur est créé au premier démarrage à partir de `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD`.
- Avec `CHARGER_DONNEES_DEMO=1`, des EPN et des réponses fictives sont chargés. **Mettre 0 en production.**

Services : `web` (Django + Gunicorn), `db` (PostgreSQL 16), `mailpit` (e-mails de test), `backup` (sauvegarde quotidienne de la base et des pièces jointes, conservée 30 jours).

### Mise en production

**Guide complet : [`docs/MISE_EN_LIGNE.md`](docs/MISE_EN_LIGNE.md).** Sur un serveur Ubuntu, une commande suffit : `sudo sh deploiement/installer.sh`. Elle installe Docker, configure le pare-feu, crée la configuration de production et démarre le site en HTTPS (Caddy et Let's Encrypt). Les mises à jour et restaurations se font avec `deploiement/mettre-a-jour.sh` et `deploiement/restaurer.sh`.

Pour une installation manuelle :

- `DJANGO_DEBUG=0`, une `DJANGO_SECRET_KEY` longue et aléatoire, `DJANGO_ALLOWED_HOSTS` et `SITE_URL` = le domaine réel.
- Placer un proxy HTTPS (Nginx, Traefik…) devant le port 8000, puis `COOKIES_SECURE=1` et `NB_PROXYS_DE_CONFIANCE=1`. Ce dernier réglage permet à la limite anti-abus du lien unique de reconnaître chaque visiteur, et non le seul proxy.
- Renseigner le serveur SMTP réel (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, identifiants) et démarrer **sans** `--profile dev` (Mailpit reste arrêté) : `docker compose up -d --build`.
- Garder `CHARGER_DONNEES_DEMO=0` et `COOKIES_SECURE=1` (valeurs par défaut de `.env.example` ; seul le script `lancer` les assouplit pour un test sur poste).
- Avec `SITE_URL` en `https://`, HSTS est activé automatiquement (un an). `REDIRECTION_HTTPS=1` redirige le http vers le https si le proxy ne le fait pas.
- Vérifier la configuration avant l'ouverture : `docker compose exec web python manage.py check --deploy`. Les alertes `enquete.W001` à `W003` signalent un réglage de démonstration oublié.
- Limiter aussi la taille des envois dans le proxy (Nginx : `client_max_body_size 12m;`). L'application refuse déjà au-delà de 12 Mo.

### Sécurité intégrée

- Export Excel : aucune réponse saisie ne peut s'exécuter comme une formule.
- Connexion : après 5 mots de passe erronés, le compte est bloqué 15 minutes (20 échecs pour une même adresse IP), sur l'API comme sur `/django-admin/`.
- Journaux : les liens personnels n'y apparaissent jamais en clair (`/r/***`).
- Envois : toute requête de plus de 12 Mo est refusée avant d'être lue.
- Navigateur : politique de sécurité du contenu (seuls les scripts du site s'exécutent), HSTS en https, page non intégrable dans un autre site.
- Adresse IP : `X-Forwarded-For` n'est pris en compte que s'il vient du proxy (réseau privé) et contient une adresse valide.
- Import Excel : lecture XML protégée (`defusedxml`).

## Développement sans Docker

Deux terminaux : l'API Python, puis l'interface React (rechargement instantané).

```bash
pip install -r requirements.txt
export DJANGO_DEBUG=1 EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
python manage.py migrate
python manage.py donnees_demo        # facultatif
python manage.py createsuperuser
python manage.py runserver           # API sur http://localhost:8000
```

```bash
cd frontend
npm install
npm run dev                          # interface sur http://localhost:5173 (relaie /api vers :8000)
```

Tests de l'API : `DJANGO_DEBUG=1 python manage.py test enquete` (70 tests, couverture du code métier 86 %). L'intégration continue (`.github/workflows/ci.yml`) les rejoue sur PostgreSQL, construit l'interface et l'image Docker, et analyse l'image avec Trivy. Vérification des types de l'interface : `cd frontend && npm run typecheck`.

## Comptes de l'équipe et périmètre

Les comptes se créent dans **Comptes et rôles** : la personne reçoit un lien pour choisir son mot de passe (12 caractères, trois types de caractères), puis se connecte avec son adresse e-mail. « Mot de passe oublié ? » envoie un lien de réinitialisation. La session se ferme après 30 minutes d'inactivité.

Un compte peut être limité aux établissements d'une ou plusieurs tutelles : il ne voit, n'exporte et ne relance que ceux-là. En ligne de commande :

```bash
docker compose exec web python manage.py compte_equipe f.kone --role superviseur --nom "Fatou Koné" --tutelle "Santé" --tutelle "Éducation"
```

## Relances automatiques

Le service `taches` de `docker-compose.yml` vérifie toutes les heures les relances prévues par chaque campagne (champ « Relances automatiques », par défaut `-7,-2,1` : J-7, J-2 et J+1 par rapport à la clôture, ou au délai propre à l'EPN). Un EPN reçoit au plus une relance automatique par jour prévu. Hors Docker : `python manage.py taches` dans une tâche cron horaire.

## Lien compromis

Si le lien d'un établissement a été transmis à une mauvaise personne, ouvrez sa fiche (**Réponses**) puis cliquez sur **Remplacer le lien**. L'ancien lien cesse aussitôt de fonctionner, et les réponses déjà saisies sont conservées. Le nouveau lien peut être envoyé directement au point focal.

## Importer les EPN

Menu **Répertoire des EPN** → fichier `.xlsx` avec, dans cet ordre : Dénomination, Sigle, Catégorie (EPA/EPIC/AUTRE), Tutelle, Région, E-mail du point focal, Secteur (facultatif), Statut (Actif, En liquidation, Dissous ; facultatif). La première ligne contient les en-têtes. Chaque fiche se modifie aussi à l'écran ; l'historique des modifications y est affiché.

## Documents

- `docs/Cahier_des_charges_ENQUETE-EPN.docx` : cahier des charges.
- `docs/CONFORMITE.md` : matrice de conformité au cahier des charges (F-01 à F-50, sections 3, 4, 7 et 8).
- `docs/MISE_EN_LIGNE.md` : mise en ligne sur un serveur (HTTPS par Caddy).
- `docs/CLOUDFLARE.md` : publication par Cloudflare Tunnel, sans ouvrir de port.
- Aide en ligne et FAQ pour les établissements et l'équipe : page `/aide` de l'application.
