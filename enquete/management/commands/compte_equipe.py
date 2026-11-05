"""Crée ou met à jour un compte de l'équipe, éventuellement limité à certaines tutelles."""
from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from enquete.models import ProfilEquipe


class Command(BaseCommand):
    help = ("Crée ou met à jour un compte de l'équipe. Avec --tutelle (répétable), le compte ne voit que les "
            "établissements de ces tutelles ; sans --tutelle, il voit tout.")

    def add_arguments(self, parser):
        parser.add_argument("identifiant")
        parser.add_argument("--tutelle", action="append", default=[], help="Tutelle visible (répétable).")
        parser.add_argument("--role", default="administrateur", choices=ProfilEquipe.Role.values,
                            help="administrateur, superviseur, analyste ou lecteur.")
        parser.add_argument("--email", default="")
        parser.add_argument("--nom", default="", help="Prénom et nom affichés.")
        parser.add_argument("--mot-de-passe", dest="mot_de_passe", default=None,
                            help="À éviter en production (reste dans l'historique du terminal) : sans cette option, "
                                 "le mot de passe est demandé.")

    def handle(self, identifiant, tutelle, role, email, nom, mot_de_passe, **options):
        if role == "superviseur" and not tutelle:
            raise CommandError("Un superviseur de tutelle doit avoir au moins une --tutelle.")
        Utilisateur = get_user_model()
        utilisateur, cree = Utilisateur.objects.get_or_create(username=identifiant)
        if cree or mot_de_passe is not None:
            mot_de_passe = mot_de_passe or getpass("Mot de passe : ")
            try:
                validate_password(mot_de_passe, utilisateur)
            except ValidationError as e:
                if cree:
                    utilisateur.delete()
                raise CommandError(" ".join(e.messages))
            utilisateur.set_password(mot_de_passe)
        utilisateur.is_staff = True
        if email:
            utilisateur.email = email
        if nom:
            utilisateur.first_name, _, utilisateur.last_name = nom.partition(" ")
        utilisateur.save()
        ProfilEquipe.objects.update_or_create(utilisateur=utilisateur, defaults={"tutelles": ", ".join(tutelle), "role": role})
        portee = ", ".join(tutelle) if tutelle else "tous les établissements"
        self.stdout.write(self.style.SUCCESS(f"Compte « {identifiant} » {'créé' if cree else 'mis à jour'} ({role}) : {portee}."))
