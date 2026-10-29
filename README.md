# ENQUÊTE-EPN

Application web de collecte d'informations auprès des Établissements Publics Nationaux (EPN), avec export Excel, statistiques et graphiques.

## Fonctionnement

1. **L'administrateur** importe la liste des EPN (fichier Excel), crée une campagne, puis envoie les **invitations** : chaque EPN reçoit par e-mail un **lien personnel**.
2. **La personne qui reçoit le lien** clique dessus, saisit ses **nom, prénom, e-mail et téléphone**, clique sur **Suivant**, puis répond aux questions rubrique par rubrique. Les réponses sont enregistrées à chaque étape : elle peut reprendre plus tard avec le même lien. Elle relit un récapitulatif, certifie, puis clique sur **Envoyer**. Un accusé de réception est envoyé par e-mail.
3. **L'espace administrateur** (`/gestion/`) permet de :
   - suivre l'avancement (tableau de bord, taux de réponse par tutelle) ;
   - consulter chaque réponse et la rouvrir pour correction ;
   - **relancer les retardataires** par e-mail, un par un ou tous ensemble ;
   - **exporter en Excel** (feuilles Réponses, Dictionnaire, Statistiques, Indicateurs avec graphique) ;
   - afficher les **statistiques et graphiques** (moyenne, médiane, écart-type, fréquences, indicateurs financiers et RH).

Le questionnaire (8 rubriques, 43 questions) est défini dans `enquete/questionnaire.py`. Sa version imprimable est disponible dans l'espace administrateur, menu **Questionnaire**.

## Démarrage avec Docker

```bash
cp .env.example .env        # puis changer les mots de passe
docker compose up -d --build
```

- Application : http://localhost:8000 (espace administrateur : http://localhost:8000/connexion/)
- E-mails de test (Mailpit) : http://localhost:8025. Toutes les invitations et relances y arrivent sans être réellement envoyées.
- Le compte administrateur est créé au premier démarrage à partir de `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD`.
- Avec `CHARGER_DONNEES_DEMO=1`, des EPN et des réponses fictives sont chargés. **Mettre 0 en production.**

Services : `web` (Django + Gunicorn), `db` (PostgreSQL 16), `mailpit` (e-mails de test), `backup` (sauvegarde quotidienne, conservée 30 jours).

### Mise en production

- `DJANGO_DEBUG=0`, une `DJANGO_SECRET_KEY` longue et aléatoire, `DJANGO_ALLOWED_HOSTS` et `SITE_URL` = le domaine réel.
- Placer un proxy HTTPS (Nginx, Traefik…) devant le port 8000, puis `COOKIES_SECURE=1`.
- Renseigner le serveur SMTP réel (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, identifiants) et retirer le service `mailpit`.

## Développement sans Docker

```bash
pip install -r requirements.txt
export DJANGO_DEBUG=1 EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
python manage.py migrate
python manage.py donnees_demo        # facultatif
python manage.py createsuperuser
python manage.py runserver
```

Tests : `DJANGO_DEBUG=1 python manage.py test enquete`

## Importer les EPN

Menu **Répertoire des EPN** → fichier `.xlsx` avec, dans cet ordre : Dénomination, Sigle, Catégorie (EPA/EPIC/AUTRE), Tutelle, Région, E-mail du point focal. La première ligne contient les en-têtes.

## Documents

- `docs/Cahier_des_charges_ENQUETE-EPN.docx` : cahier des charges.
