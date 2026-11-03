# ENQUÊTE-EPN

Application web de collecte d'informations auprès des Établissements Publics Nationaux (EPN), avec export Excel, statistiques et graphiques.

## Architecture

| Couche | Technologies | Rôle |
| --- | --- | --- |
| Interface (`frontend/`) | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts, Framer Motion | Formulaire des EPN, espace administrateur, thème clair/sombre, mobile |
| API (`enquete/`, `config/`) | Python 3.12, Django 5 | API JSON, règles de validation et de cohérence, e-mails, exports Excel, pièces jointes |
| Données | PostgreSQL 16 | Établissements, campagnes, réponses, fichiers |

L'interface appelle l'API sous `/api/` (même origine, session et jeton CSRF). En production, l'image Docker construit l'interface React, puis Django la sert avec ses fichiers statiques.

## Fonctionnement

**Le lien à diffuser à toutes les entités : `https://<votre-domaine>/formulaire`** (en local : http://localhost:8000/formulaire).
C'est le même lien pour tous. L'entité y choisit son établissement ; son lien personnel est alors envoyé à l'adresse e-mail officielle de son point focal (enregistrée dans le répertoire). Personne ne peut donc répondre à la place d'un autre établissement.

1. **L'administrateur** importe la liste des EPN (fichier Excel), crée une campagne, puis envoie les **invitations** : chaque EPN reçoit par e-mail un **lien personnel**.
2. **La personne qui reçoit le lien** clique dessus, saisit ses **nom, prénom, e-mail et téléphone**, clique sur **Suivant**, puis répond aux questions rubrique par rubrique. Les réponses sont enregistrées à chaque étape : elle peut reprendre plus tard avec le même lien. Elle relit un récapitulatif, certifie, puis clique sur **Envoyer**. Un accusé de réception est envoyé par e-mail.
3. **L'espace administrateur** (`/gestion/`) permet de :
   - suivre l'avancement (tableau de bord, taux de réponse par tutelle) ;
   - consulter chaque réponse, télécharger ses pièces jointes (une par une ou en ZIP) et la rouvrir pour correction ;
   - **relancer les retardataires** par e-mail, un par un ou tous ensemble ;
   - **exporter en Excel** (feuilles Réponses, Dictionnaire, Statistiques, Indicateurs avec graphique) ;
   - afficher les **statistiques et graphiques** (moyenne, médiane, écart-type, fréquences, indicateurs financiers et RH).

Le questionnaire (9 rubriques, 48 questions, dont 5 pièces justificatives) est défini dans `enquete/questionnaire.py`. Sa version imprimable est disponible dans l'espace administrateur, menu **Questionnaire**.

## Installer et tester sur votre ordinateur

**Prérequis :** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS) ou Docker Engine (Linux), démarré ; [Git](https://git-scm.com/downloads).

1. Récupérer le code :

   ```bash
   git clone https://github.com/djacob2022/ENQUETE-EPN.git
   cd ENQUETE-EPN
   git checkout claude/tender-cannon-9lvbtv
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
docker compose up -d --build
```

- Application : http://localhost:8000 (espace administrateur : http://localhost:8000/connexion/)
- E-mails de test (Mailpit) : http://localhost:8025. Toutes les invitations et relances y arrivent sans être réellement envoyées.
- Le compte administrateur est créé au premier démarrage à partir de `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD`.
- Avec `CHARGER_DONNEES_DEMO=1`, des EPN et des réponses fictives sont chargés. **Mettre 0 en production.**

Services : `web` (Django + Gunicorn), `db` (PostgreSQL 16), `mailpit` (e-mails de test), `backup` (sauvegarde quotidienne de la base et des pièces jointes, conservée 30 jours).

### Mise en production

- `DJANGO_DEBUG=0`, une `DJANGO_SECRET_KEY` longue et aléatoire, `DJANGO_ALLOWED_HOSTS` et `SITE_URL` = le domaine réel.
- Placer un proxy HTTPS (Nginx, Traefik…) devant le port 8000, puis `COOKIES_SECURE=1` et `NB_PROXYS_DE_CONFIANCE=1`. Ce dernier réglage permet à la limite anti-abus du lien unique de reconnaître chaque visiteur, et non le seul proxy.
- Renseigner le serveur SMTP réel (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, identifiants) et retirer le service `mailpit`.

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

Tests de l'API : `DJANGO_DEBUG=1 python manage.py test enquete`. Vérification des types de l'interface : `cd frontend && npm run typecheck`.

## Importer les EPN

Menu **Répertoire des EPN** → fichier `.xlsx` avec, dans cet ordre : Dénomination, Sigle, Catégorie (EPA/EPIC/AUTRE), Tutelle, Région, E-mail du point focal. La première ligne contient les en-têtes.

## Documents

- `docs/Cahier_des_charges_ENQUETE-EPN.docx` : cahier des charges.
