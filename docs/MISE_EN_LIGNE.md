# Mise en ligne d'ENQUÊTE-EPN sur un serveur

Ce guide installe l'application sur un serveur accessible depuis Internet, en **HTTPS**, avec un certificat gratuit renouvelé automatiquement (Let's Encrypt, via Caddy).

Durée : 30 à 45 minutes, une fois le serveur et le domaine disponibles.

---

## 1. Ce qu'il faut avant de commencer

| Élément | Détail |
| --- | --- |
| **Un serveur** | Ubuntu 22.04 ou 24.04, 2 processeurs, 4 Go de mémoire, 40 Go de disque. Serveur de l'administration, ou serveur loué (OVHcloud, Scaleway, Hetzner, AWS…). Il doit avoir une **adresse IP publique** et être joignable sur les ports **80** et **443**. |
| **Un nom de domaine** | Par exemple `enquete.mon-ministere.ci`. Le service informatique crée un **enregistrement DNS de type A** qui pointe vers l'adresse IP publique du serveur. |
| **Un serveur d'envoi d'e-mails (SMTP)** | Indispensable pour les invitations, les liens d'accès et les relances : messagerie du ministère, ou service d'envoi (Brevo, Mailjet, Amazon SES…). Notez l'adresse du serveur SMTP, le port (587 en général), l'identifiant et le mot de passe. Faites autoriser l'adresse d'expédition (SPF/DKIM) pour que les e-mails n'arrivent pas en indésirables. |
| **Un accès SSH** | Avec un compte qui peut utiliser `sudo`. |

> **À vérifier avant de continuer :** depuis votre ordinateur, `ping enquete.mon-ministere.ci` doit répondre avec l'adresse IP du serveur. Sans cela, le certificat HTTPS ne peut pas être obtenu.

---

## 2. Installation

Connectez-vous au serveur :

```bash
ssh utilisateur@adresse-du-serveur
```

Récupérez le code :

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/djacob2022/ENQUETE-EPN.git
cd ENQUETE-EPN
git checkout claude/tender-cannon-9lvbtv
```

Lancez l'installation :

```bash
sudo sh deploiement/installer.sh
```

Le script vous pose quelques questions (domaine, e-mail du service informatique, serveur SMTP), puis :

1. installe Docker ;
2. ferme le pare-feu, sauf SSH, HTTP et HTTPS ;
3. crée le fichier `.env` de production, avec des mots de passe aléatoires, lisible par l'administrateur système seulement ;
4. vérifie que le domaine pointe bien vers le serveur ;
5. construit l'application et valide la configuration HTTPS ;
6. démarre le tout et affiche **l'identifiant et le mot de passe administrateur**. Notez-les.

À la fin, il affiche :

```
Lien à diffuser aux EPN : https://enquete.mon-ministere.ci/formulaire
Espace administrateur   : https://enquete.mon-ministere.ci/connexion
```

---

## 3. Personnaliser l'en-tête officiel

Ouvrez le fichier de configuration :

```bash
sudo nano .env
```

Renseignez :

```
PAYS=République de …
DEVISE=…
NOM_MINISTERE=…
NOM_INSTITUTION=…
```

Puis appliquez :

```bash
sudo sh deploiement/mettre-a-jour.sh
```

---

## 4. Vérifications avant d'ouvrir la campagne

1. **Configuration :** cette commande ne doit afficher **aucune** alerte `enquete.W…` :
   ```bash
   sudo docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml exec web python manage.py check --deploy
   ```
   Il peut rester `security.W005` et `security.W021`, deux recommandations facultatives sur les sous-domaines et le préchargement HSTS.
2. **HTTPS :** ouvrez `http://votre-domaine` : vous devez être redirigé vers `https://`, avec le cadenas.
3. **E-mails :** dans l'espace administrateur, ajoutez dans le **Répertoire** un EPN de test avec **votre propre adresse**. Ouvrez ensuite `https://votre-domaine/formulaire`, choisissez cet EPN, et vérifiez que l'e-mail arrive (et pas dans les indésirables).
4. **Parcours complet :** remplissez le questionnaire de test jusqu'à l'envoi, puis vérifiez la réponse, l'export Excel et les statistiques dans l'espace administrateur.
5. **Nettoyage :** supprimez l'EPN de test dans `/django-admin/`.

---

## 5. Préparer la campagne

1. **Changer le mot de passe administrateur :** `/django-admin/` → Utilisateurs → admin.
2. **Créer les comptes de l'équipe.** Un superviseur ne voit que ses tutelles ; le mot de passe est demandé à l'écran :
   ```bash
   sudo docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml exec web \
     python manage.py compte_equipe f.kone --nom "Fatou Koné" --tutelle "Santé"
   ```
3. **Importer les EPN** depuis un fichier Excel : menu **Répertoire des EPN**.
4. **Créer la campagne** (menu **Campagnes**), avec ses dates d'ouverture et de clôture.
5. **Diffuser le lien** `https://votre-domaine/formulaire`, ou envoyer les invitations depuis **Liens et invitations**.

---

## 6. Exploitation au quotidien

Pour éviter de retaper la commande complète, définissez un raccourci :

```bash
alias enquete='sudo docker compose -f docker-compose.yml -f deploiement/docker-compose.prod.yml'
```

| Besoin | Commande |
| --- | --- |
| État des services | `enquete ps` |
| Journal de l'application | `enquete logs -f web` (les liens personnels y sont masqués) |
| Mettre à jour l'application | `sudo sh deploiement/mettre-a-jour.sh` (sauvegarde de précaution incluse) |
| Lister les sauvegardes | `sudo sh deploiement/restaurer.sh` |
| Restaurer une sauvegarde | `sudo sh deploiement/restaurer.sh 2026-11-03_0200` |
| Copier les sauvegardes hors du serveur | `enquete cp backup:/backups ./sauvegardes`, puis transférez le dossier `sauvegardes/` vers un autre site (serveur, stockage du ministère) |

**Sauvegardes :** chaque jour, la base et les pièces jointes sont sauvegardées et conservées 30 jours **sur le serveur**. Une panne de disque les emporterait aussi : copiez-les régulièrement ailleurs, au moins chaque semaine pendant la campagne, et testez une restauration une fois avant l'ouverture.

---

## 7. En cas de problème

| Symptôme | Cause probable | Que faire |
| --- | --- | --- |
| Le navigateur affiche une erreur de certificat | Le domaine ne pointe pas vers le serveur, ou les ports 80/443 sont fermés | Vérifiez l'enregistrement DNS et le pare-feu de l'hébergeur, puis `enquete restart caddy` |
| Les EPN ne reçoivent pas les e-mails | Réglages SMTP faux, ou expéditeur non autorisé | `enquete logs web \| grep -i smtp` ; vérifiez `EMAIL_*` dans `.env` et la configuration SPF/DKIM |
| « Trop de demandes » pour tout le monde | `NB_PROXYS_DE_CONFIANCE` modifié à tort | Il doit valoir `1` avec Caddy ; il est imposé par `deploiement/docker-compose.prod.yml` |
| Page blanche ou erreur 502 | L'application ne démarre pas | `enquete logs web` |
