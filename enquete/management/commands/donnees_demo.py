"""Crée des EPN fictifs, une campagne et des réponses d'exemple pour tester l'application."""
import random
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from enquete.models import EPN, Campagne, PieceJointe, Reponse
from enquete.questionnaire import MODULES

EPN_DEMO = [
    ("Agence nationale de la santé publique (exemple)", "ANSP", "EPA", "Santé", "Région 1"),
    ("Office national des cultures vivrières (exemple)", "ONCV", "EPIC", "Agriculture", "Région 2"),
    ("Institut national de formation (exemple)", "INF", "EPA", "Éducation", "Région 1"),
    ("Fonds national de garantie (exemple)", "FNG", "EPA", "Finances", "Région 1"),
    ("Société de développement agricole (exemple)", "SODEA", "EPIC", "Agriculture", "Région 3"),
    ("Agence de promotion des exportations (exemple)", "APEX", "EPA", "Commerce", "Région 1"),
    ("Centre national de recherche (exemple)", "CNR", "EPA", "Recherche", "Région 4"),
    ("Port autonome (exemple)", "PA", "EPIC", "Transports", "Région 2"),
    ("Office des transports urbains (exemple)", "OTU", "EPIC", "Transports", "Région 1"),
    ("Agence nationale de l'eau (exemple)", "ANE", "EPA", "Hydraulique", "Région 3"),
    ("Caisse de prévoyance (exemple)", "CP", "EPA", "Finances", "Région 1"),
    ("École nationale d'administration (exemple)", "ENA", "EPA", "Éducation", "Région 1"),
]


def _donnees_fictives(epn, rnd):
    total = rnd.randint(25, 900)
    femmes = rnd.randint(total // 5, total // 2)
    fonctionnaires = rnd.randint(0, total)
    budget = rnd.randint(500, 30000) * 1_000_000
    subvention = int(budget * rnd.uniform(0.3, 0.9))
    indicateurs = rnd.randint(5, 20)
    return {
        "A01": epn.nom, "A02": epn.sigle, "A03": epn.categorie, "A04": "Décret n° [À COMPLÉTER]",
        "A05": rnd.randint(1960, 2020), "A06": f"Ministère – {epn.tutelle}", "A07": "Capitale", "A08": None,
        "B01": "oui", "B02": rnd.randint(1, 6), "B03": rnd.choice(["oui", "non"]), "B04": rnd.choice(["oui", "non"]),
        "B05": rnd.choice(["oui", "oui", "non"]),
        "C01": "Missions de service public définies par le texte de création.", "C02": rnd.choice(["nationale", "regionale"]),
        "C03": rnd.randint(1000, 200000),
        "D01": total, "D02": femmes, "D03": total - femmes, "D04": fonctionnaires, "D05": total - fonctionnaires,
        "D06": rnd.randint(0, total // 10), "D07": rnd.randint(0, total // 12), "D08": total * rnd.randint(3, 9) * 1_000_000,
        "E01": budget, "E02": int(budget * rnd.uniform(0.6, 1.0)), "E03": subvention,
        "E04": int(budget * rnd.uniform(0.05, 0.5)), "E05": int(budget * 0.45), "E06": int(budget * 0.35),
        "E07": int(budget * 0.2), "E08": rnd.choice([0, int(budget * 0.1)]),
        "F01": rnd.randint(1, 15), "F02": rnd.randint(2, 40), "F03": rnd.randint(10, 400), "F04": rnd.choice(["oui", "oui", "non"]),
        "F05": rnd.sample(["comptabilite", "paie", "courrier", "metier"], rnd.randint(1, 3)),
        "G01": indicateurs, "G02": rnd.randint(0, indicateurs), "G03": rnd.randint(40, 100),
        "H01": rnd.sample(["financieres", "humaines", "materielles", "juridiques", "numeriques"], rnd.randint(1, 3)),
        "H02": "Renforcement des capacités et équipements.", "H03": None,
    }


class Command(BaseCommand):
    help = "Charge des données fictives de démonstration (EPN, campagne, réponses)."

    def handle(self, *args, **options):
        rnd = random.Random(2025)
        epns = []
        for i, (nom, sigle, cat, tutelle, region) in enumerate(EPN_DEMO, start=1):
            epn, _ = EPN.objects.get_or_create(nom=nom, defaults={
                "sigle": sigle, "categorie": cat, "tutelle": tutelle, "region": region,
                "email_contact": f"point.focal{i}@epn-exemple.test"})
            epns.append(epn)

        aujourd_hui = timezone.localdate()
        Campagne.objects.get_or_create(nom="Enquête annuelle 2024 (démo)", defaults={
            "exercice": 2023, "date_ouverture": aujourd_hui - timedelta(days=380),
            "date_cloture": aujourd_hui - timedelta(days=350), "active": False})
        campagne, _ = Campagne.objects.get_or_create(nom="Enquête annuelle 2025 (démo)", defaults={
            "exercice": 2024, "date_ouverture": aujourd_hui - timedelta(days=15),
            "date_cloture": aujourd_hui + timedelta(days=15), "active": True})
        if not campagne.active:
            campagne.active = True
            campagne.save()

        noms = [("Kouassi", "Awa"), ("Traoré", "Moussa"), ("Diallo", "Fatou"), ("Koné", "Ibrahim"), ("Yao", "Akissi"),
                ("Bamba", "Karim"), ("Ouattara", "Mariam"), ("Sylla", "Seydou")]
        codes = [m["code"] for m in MODULES]
        for i, epn in enumerate(epns):
            reponse, cree = Reponse.objects.get_or_create(campagne=campagne, epn=epn,
                                                         defaults={"date_invitation": timezone.now()})
            if not cree:
                continue
            if i < 7:  # envoyées
                nom, prenom = noms[i % len(noms)]
                reponse.nom, reponse.prenom, reponse.fonction = nom, prenom, "Directeur administratif et financier"
                reponse.email, reponse.telephone = epn.email_contact, f"+000 {rnd.randint(10, 99)} {rnd.randint(100000, 999999)}"
                reponse.donnees = _donnees_fictives(epn, rnd)
                reponse.modules_completes = codes
                reponse.statut = Reponse.Statut.SOUMIS
                reponse.date_debut = timezone.now() - timedelta(days=10 - i)
                reponse.date_soumission = timezone.now() - timedelta(days=7 - i)
            elif i < 10:  # en cours
                nom, prenom = noms[i % len(noms)]
                reponse.nom, reponse.prenom, reponse.fonction = nom, prenom, "Chef du personnel"
                reponse.email, reponse.telephone = epn.email_contact, "+000 00 000000"
                donnees = _donnees_fictives(epn, rnd)
                faits = codes[: rnd.randint(1, 5)]
                reponse.donnees = {k: v for k, v in donnees.items() if k[0] in faits}
                reponse.modules_completes = faits
                reponse.statut = Reponse.Statut.EN_COURS
                reponse.date_debut = timezone.now() - timedelta(days=3)
            reponse.save()
            if reponse.statut == Reponse.Statut.SOUMIS:
                for code_q, nom in (("J01", "etats_financiers.pdf"), ("J02", "rapport_activites.pdf")):
                    contenu = b"%PDF-1.4\n% Document fictif de demonstration\n%%EOF\n"
                    piece = PieceJointe(reponse=reponse, code=code_q, nom_original=nom, taille=len(contenu))
                    piece.fichier.save(nom, ContentFile(contenu), save=True)
                    reponse.donnees[code_q] = nom
                reponse.save(update_fields=["donnees"])

        self.stdout.write(self.style.SUCCESS(
            f"{len(epns)} EPN, campagne « {campagne} » : {campagne.reponses.filter(statut='soumis').count()} réponses envoyées."))
        exemple = campagne.reponses.filter(statut="invite").first()
        if exemple:
            self.stdout.write(f"Lien d'exemple à ouvrir (EPN non commencé) : {exemple.lien}")
