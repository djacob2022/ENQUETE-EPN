"""Sauvegarde et restauration depuis l'interface (F-49), réservées aux super-administrateurs.

L'archive (.zip) contient toutes les données (donnees.json : comptes, répertoire, campagnes, réponses, journal…)
et les fichiers déposés (pièces jointes, logo). La restauration remplace l'intégralité des données actuelles.
"""
import json
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone

EXCLUS = ["contenttypes", "sessions", "admin.logentry", "auth.permission", "enquete.echecconnexion",
          "enquete.demandeacces"]
VERSION = 1


def creer():
    sortie = StringIO()
    call_command("dumpdata", exclude=EXCLUS, natural_foreign=True, stdout=sortie)
    tampon = BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("donnees.json", sortie.getvalue())
        z.writestr("version.json", json.dumps({"version": VERSION, "date": timezone.now().isoformat()}))
        racine = Path(settings.MEDIA_ROOT)
        if racine.exists():
            for f in racine.rglob("*"):
                if f.is_file():
                    z.write(f, "media/" + f.relative_to(racine).as_posix())
    return tampon.getvalue()


def restaurer(fichier):
    """Vérifie l'archive, puis remplace données et fichiers. Lève ValueError si l'archive est invalide."""
    from .services import Refus

    try:
        z = zipfile.ZipFile(fichier)
        noms = set(z.namelist())
        version = json.loads(z.read("version.json")) if "version.json" in noms else {}
        donnees = z.read("donnees.json")
        json.loads(donnees)
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise Refus("Ce fichier n'est pas une sauvegarde ENQUÊTE-EPN.")
    if version.get("version") != VERSION:
        raise Refus("Version de sauvegarde non reconnue.")
    racine = Path(settings.MEDIA_ROOT).resolve()
    fichiers = []
    for nom in noms:
        if nom.startswith("media/") and not nom.endswith("/"):
            cible = (racine / nom[len("media/"):]).resolve()
            if racine not in cible.parents:  # chemin piégé (../) : refusé
                raise Refus("Archive invalide : chemin de fichier non autorisé.")
            fichiers.append((nom, cible))

    import tempfile

    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tmp:
        tmp.write(donnees)
        chemin = tmp.name
    try:
        with transaction.atomic():
            postgres = connection.vendor == "postgresql"
            if postgres:
                # Les contrôles de clés étrangères différés encore en attente empêchent TRUNCATE : on les exécute,
                # puis on rétablit le report pour que loaddata puisse insérer les lignes dans n'importe quel ordre.
                with connection.cursor() as c:
                    c.execute("SET CONSTRAINTS ALL IMMEDIATE")
            call_command("flush", interactive=False, verbosity=0)
            if postgres:
                with connection.cursor() as c:
                    c.execute("SET CONSTRAINTS ALL DEFERRED")
            call_command("loaddata", chemin, verbosity=0)
    finally:
        Path(chemin).unlink(missing_ok=True)
    for nom, cible in fichiers:
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(z.read(nom))
    return {"fichiers": len(fichiers), "date_sauvegarde": version.get("date")}
