"""Affiche (et au besoin génère) le lien personnel de chaque EPN pour la campagne active."""
from django.core.management.base import BaseCommand, CommandError

from enquete.models import Campagne


class Command(BaseCommand):
    help = "Affiche le lien unique de chaque EPN pour la campagne active (--generer crée les liens manquants)."

    def add_arguments(self, parser):
        parser.add_argument("--generer", action="store_true", help="Crée d'abord les liens des EPN qui n'en ont pas.")

    def handle(self, *args, generer=False, **options):
        campagne = Campagne.courante()
        if campagne is None:
            raise CommandError("Aucune campagne active : créez-en une dans l'espace administrateur.")
        if generer:
            self.stdout.write(f"{campagne.generer_liens()} lien(s) généré(s).")
        reponses = campagne.reponses.select_related("epn").order_by("epn__nom")
        if not reponses:
            self.stdout.write("Aucun lien. Relancez avec --generer.")
        for r in reponses:
            self.stdout.write(f"{r.epn.nom}\n  {r.lien}\n")
