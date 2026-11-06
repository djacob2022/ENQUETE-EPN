# Publier ENQUÊTE-EPN avec Cloudflare

ENQUÊTE-EPN a besoin d'un serveur Python et d'une base PostgreSQL : il ne s'héberge pas sur Cloudflare Pages ou Workers, qui ne servent que des sites statiques ou du code JavaScript. La bonne solution est **Cloudflare Tunnel** : l'application tourne avec Docker sur votre machine (serveur ou ordinateur allumé en permanence), et Cloudflare la publie sur Internet.

- HTTPS automatique, certificat géré par Cloudflare.
- Aucun port à ouvrir, aucune adresse IP publique nécessaire : la machine ouvre une connexion sortante vers Cloudflare.
- Protection contre les attaques par saturation (DDoS) et pare-feu de Cloudflare.
- Gratuit (offre Free de Cloudflare).

## Ce qu'il faut

1. Un compte Cloudflare (gratuit) : https://dash.cloudflare.com/sign-up
2. Un nom de domaine géré par Cloudflare, par exemple `enquete-epn.org`. S'il est acheté ailleurs, ajoutez-le dans Cloudflare (**Add a domain**) puis remplacez les serveurs DNS chez votre registraire par ceux indiqués par Cloudflare. Vous pouvez aussi l'acheter directement dans Cloudflare (**Domain Registration**).
3. Une machine avec Docker et Git, allumée en permanence : un serveur Linux (recommandé) ou un ordinateur avec Docker Desktop.
4. Un vrai serveur d'envoi d'e-mails (SMTP) : celui de l'institution, ou un service comme Brevo, Mailjet ou Amazon SES. Mailpit ne sert qu'aux tests.

## 1. Créer le tunnel dans Cloudflare

1. Dans le tableau de bord Cloudflare, ouvrez **Zero Trust**, puis **Networks** → **Tunnels** → **Create a tunnel**.
2. Choisissez **Cloudflared**, nommez le tunnel `enquete-epn`, puis **Save tunnel**.
3. À l'étape d'installation, choisissez **Docker**. La commande affichée contient un long jeton après `--token` : **copiez seulement ce jeton** (il commence en général par `eyJ`). N'exécutez pas la commande : le fichier Docker de l'application lance déjà le connecteur.
4. Étape **Public Hostname** :
   - **Subdomain** : `enquete` (ou vide pour utiliser le domaine nu) ;
   - **Domain** : votre domaine ;
   - **Service** : type `HTTP`, URL `web:8000`.
5. **Save tunnel**. Cloudflare crée lui-même l'enregistrement DNS.

Le jeton donne le droit de publier sur votre domaine : gardez-le secret, comme un mot de passe.

## 2. Préparer l'application sur la machine

```bash
git clone https://github.com/djacob2022/ENQUETE-EPN.git
cd ENQUETE-EPN
cp .env.example .env
```

Ouvrez `.env` et réglez au minimum (exemple pour `https://enquete.enquete-epn.org`) :

| Variable | Valeur |
| --- | --- |
| `DJANGO_SECRET_KEY` | une longue chaîne aléatoire (50 caractères) |
| `DJANGO_ALLOWED_HOSTS` | `enquete.enquete-epn.org` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://enquete.enquete-epn.org` |
| `SITE_URL` | `https://enquete.enquete-epn.org` |
| `DJANGO_SUPERUSER_PASSWORD` | le mot de passe du premier administrateur (12 caractères au moins) |
| `POSTGRES_PASSWORD` | une autre chaîne aléatoire |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | les réglages de votre serveur d'e-mails |
| `CLOUDFLARE_TUNNEL_TOKEN` | le jeton copié à l'étape 1 |

Dans `.env`, un caractère `$` s'écrit `$$`.

## 3. Démarrer

```bash
docker compose -f docker-compose.yml -f deploiement/docker-compose.cloudflare.yml up -d --build
```

Au bout d'une minute, le tunnel apparaît **Healthy** dans Cloudflare, et l'application répond à l'adresse choisie :

- lien à diffuser aux établissements : `https://enquete.enquete-epn.org/formulaire` ;
- espace de gestion : `https://enquete.enquete-epn.org/connexion`.

Vérification depuis la machine :

```bash
docker compose -f docker-compose.yml -f deploiement/docker-compose.cloudflare.yml ps
docker compose -f docker-compose.yml -f deploiement/docker-compose.cloudflare.yml logs cloudflared --tail 20
```

## 4. Réglages conseillés dans Cloudflare

- **SSL/TLS** → **Edge Certificates** : activez **Always Use HTTPS** ; **Minimum TLS Version** : 1.2 (exigence de la section 7 du cahier des charges).
- **Caching** : laissez le réglage standard. Cloudflare ne met en cache que les fichiers statiques (`/static/…`) ; les pages et l'API ne le sont jamais.
- **Security** → **WAF** (facultatif) : une règle de limitation de débit sur `/api/auth/connexion/` renforce le blocage déjà fait par l'application après 5 échecs.

## Option : base de données chez Supabase

Par défaut, la base PostgreSQL tourne dans un conteneur sur la machine. Avec Supabase, elle est hébergée et sauvegardée par Supabase : les données ne dépendent plus de la machine. Le projet `enquete-epn` (région Paris, `eu-west-3`) est déjà créé, avec :

- un compte réservé à l'application, `enquete_app`, sans aucun autre droit ;
- un schéma `enquete` que l'API publique de Supabase n'expose pas : les rôles `anon` et `authenticated` n'y ont aucun accès.

1. Dans Supabase, ouvrez le projet **enquete-epn** → **SQL Editor**, et exécutez (en choisissant un mot de passe long, sans `@` ni `/`) :

   ```sql
   alter role enquete_app with password 'VOTRE-MOT-DE-PASSE';
   ```

2. Cliquez sur **Connect** (en haut de la page du projet), onglet **Session pooler**, et notez l'hôte, du type `aws-0-eu-west-3.pooler.supabase.com`. Le pooler est nécessaire : l'adresse directe de la base n'est joignable qu'en IPv6.

3. Dans `.env`, ajoutez (l'utilisateur est `enquete_app.` suivi de l'identifiant du projet) :

   ```
   DATABASE_URL=postgresql://enquete_app.pdikhxvedaaeoeykforu:VOTRE-MOT-DE-PASSE@aws-0-eu-west-3.pooler.supabase.com:5432/postgres
   ```

4. Démarrez avec les deux surcouches :

   ```bash
   docker compose -f docker-compose.yml -f deploiement/docker-compose.cloudflare.yml -f deploiement/docker-compose.supabase.yml up -d --build
   ```

Les tables sont créées au premier démarrage. Les scripts `mettre-a-jour.sh` et `restaurer.sh` détectent `DATABASE_URL` et ajoutent la surcouche Supabase d'eux-mêmes. La sauvegarde quotidienne copie alors la base Supabase sur la machine, en plus des sauvegardes de Supabase.

À vérifier avec le maître d'ouvrage : la section 7 du cahier des charges demande un hébergement des données sur le territoire national ou chez un hébergeur agréé. Supabase héberge ici les données en France (Union européenne).

## Mettre à jour, sauvegarder, restaurer

Les scripts détectent le jeton dans `.env` et utilisent automatiquement la surcouche Cloudflare :

```bash
sudo sh deploiement/mettre-a-jour.sh
sudo sh deploiement/restaurer.sh
```

La sauvegarde quotidienne fonctionne comme avec Caddy (base et pièces jointes, 30 jours sur la machine). Copiez-la régulièrement ailleurs : voir `docs/MISE_EN_LIGNE.md`, section 6.

## En cas de problème

| Symptôme | Cause probable | Que faire |
| --- | --- | --- |
| Erreur Cloudflare 1033 ou 502 | Le connecteur ou l'application ne tourne pas | `… ps` puis `… logs cloudflared` et `… logs web` |
| « Bad Request (400) » | Domaine absent de `DJANGO_ALLOWED_HOSTS` | Corriger `.env`, puis relancer la commande de démarrage |
| Connexion refusée : « CSRF verification failed » | `DJANGO_CSRF_TRUSTED_ORIGINS` ne correspond pas à l'adresse exacte (avec `https://`) | Corriger `.env`, puis relancer |
| Les liens des e-mails pointent vers `localhost` | `SITE_URL` non réglé | Corriger `.env`, puis relancer |
| Le tunnel reste « Inactive » | Jeton incomplet ou erroné | Recopier le jeton entier dans `.env` |
