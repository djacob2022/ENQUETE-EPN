import shutil
from pathlib import Path
import tempfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from enquete.models import EPN, Campagne, Envoi, Reponse
from enquete.questionnaire import MODULES

REPONSES_VALIDES = {
    "A": {"A01": "Office test", "A02": "OT", "A03": "EPIC", "A04": "Décret 1", "A05": "1990", "A06": "Agriculture",
          "A07": "Ville", "A08": ""},
    "B": {"B01": "oui", "B02": "4", "B03": "oui", "B04": "non", "B05": "oui"},
    "C": {"C01": "Missions", "C02": "nationale", "C03": "1000"},
    "D": {"D01": "100", "D02": "40", "D03": "60", "D04": "30", "D05": "70", "D06": "5", "D07": "3", "D08": "250000000"},
    "E": {"E01": "1000", "E02": "900", "E03": "600", "E04": "200", "E05": "400", "E06": "300", "E07": "200", "E08": ""},
    "F": {"F01": "2", "F02": "5", "F03": "40", "F04": "oui", "F05": ["comptabilite", "paie"]},
    "G": {"G01": "10", "G02": "7", "G03": "85.5"},
    "H": {"H01": ["financieres"], "H02": "Besoins", "H03": ""},
    "J": {},
}
PDF = b"%PDF-1.4\n%test\n%%EOF\n"


def pdf(nom="etats.pdf", contenu=PDF):
    return SimpleUploadedFile(nom, contenu, content_type="application/pdf")


def fichiers_valides():
    return {"J01": pdf("etats_financiers.pdf"), "J02": pdf("rapport.pdf")}

MEDIA_TEST = tempfile.mkdtemp()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver",
                   MEDIA_ROOT=MEDIA_TEST)
class ParcoursTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEST, ignore_errors=True)

    def setUp(self):
        aujourd_hui = timezone.localdate()
        self.campagne = Campagne.objects.create(nom="Enquête test", exercice=2024, active=True,
                                                date_ouverture=aujourd_hui - timedelta(days=1),
                                                date_cloture=aujourd_hui + timedelta(days=10))
        self.epn = EPN.objects.create(nom="Office test", sigle="OT", categorie="EPIC", tutelle="Agriculture",
                                      email_contact="focal@epn.test")
        self.admin = User.objects.create_user("admin", password="motdepasse-solide", is_staff=True)

    def _inviter(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("gestion:invitations"), {"campagne": self.campagne.pk})
        self.client.logout()
        return Reponse.objects.get(epn=self.epn)

    def _identifier(self, reponse):
        return self.client.post(reverse("public:accueil", args=[reponse.jeton]), {
            "nom": "Bamba", "prenom": "Karim", "fonction": "DAF", "email": "karim@epn.test", "telephone": "+000 01 02 03 04"})

    def test_invitation_envoie_un_lien_personnel(self):
        reponse = self._inviter()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(reponse.lien, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["focal@epn.test"])
        self.assertTrue(Envoi.objects.filter(type=Envoi.Type.INVITATION, succes=True).exists())

    def test_parcours_complet_jusqua_l_envoi(self):
        reponse = self._inviter()
        r = self._identifier(reponse)
        self.assertRedirects(r, reverse("public:module", args=[reponse.jeton, "A"]))
        for module in MODULES:
            donnees = REPONSES_VALIDES[module["code"]] | {"action": "suivant"}
            if module["code"] == "J":
                donnees |= fichiers_valides()
            r = self.client.post(reverse("public:module", args=[reponse.jeton, module["code"]]), donnees)
            self.assertEqual(r.status_code, 302, f"module {module['code']} : {r.context and r.context['form'].errors}")
        r = self.client.post(reverse("public:recapitulatif", args=[reponse.jeton]), {"certification": "on"})
        self.assertRedirects(r, reverse("public:merci", args=[reponse.jeton]))
        reponse.refresh_from_db()
        self.assertEqual(reponse.statut, Reponse.Statut.SOUMIS)
        self.assertEqual(reponse.donnees["D01"], 100)
        self.assertEqual(reponse.donnees["G03"], 85.5)
        self.assertEqual(reponse.donnees["F05"], ["comptabilite", "paie"])
        self.assertEqual(reponse.telephone, "+000 01 02 03 04")
        # Une fois envoyée, la réponse n'est plus modifiable par le lien.
        r = self.client.get(reverse("public:module", args=[reponse.jeton, "A"]))
        self.assertContains(r, "déjà été envoyé")

    def test_regle_de_coherence_bloque_suivant_mais_pas_le_brouillon(self):
        reponse = self._inviter()
        self._identifier(reponse)
        incoherent = REPONSES_VALIDES["D"] | {"D03": "61"}
        url = reverse("public:module", args=[reponse.jeton, "D"])
        r = self.client.post(url, incoherent | {"action": "suivant"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "différent de l&#x27;effectif total")
        r = self.client.post(url, incoherent | {"action": "brouillon"})
        self.assertEqual(r.status_code, 302)
        reponse.refresh_from_db()
        self.assertEqual(reponse.donnees["D03"], 61)
        self.assertNotIn("D", reponse.modules_completes)

    def test_envoi_refuse_si_modules_incomplets(self):
        reponse = self._inviter()
        self._identifier(reponse)
        r = self.client.post(reverse("public:recapitulatif", args=[reponse.jeton]), {"certification": "on"})
        self.assertEqual(r.status_code, 200)
        reponse.refresh_from_db()
        self.assertNotEqual(reponse.statut, Reponse.Statut.SOUMIS)

    def test_lien_invalide_renvoie_404(self):
        self.assertEqual(self.client.get(reverse("public:accueil", args=["inconnu"])).status_code, 404)

    def test_relance_des_retardataires(self):
        self._inviter()
        mail.outbox.clear()
        self.client.force_login(self.admin)
        self.client.post(reverse("gestion:relancer_retardataires"), {"campagne": self.campagne.pk})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Rappel", mail.outbox[0].subject)
        self.assertEqual(Reponse.objects.get().nombre_relances, 1)

    def test_espace_gestion_reserve_au_personnel(self):
        r = self.client.get(reverse("gestion:tableau_de_bord"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/connexion/", r.url)

    def test_export_excel_et_statistiques(self):
        reponse = self._inviter()
        reponse.statut = Reponse.Statut.SOUMIS
        reponse.nom, reponse.prenom = "Bamba", "Karim"
        reponse.donnees = {"D01": 100, "D02": 40, "E01": 1000, "E02": 900, "A03": "EPIC", "F05": ["paie"]}
        reponse.date_soumission = timezone.now()
        reponse.save()
        self.client.force_login(self.admin)
        r = self.client.get(reverse("gestion:export"))
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ["Réponses", "Dictionnaire", "Statistiques", "Indicateurs"])
        ws = wb["Réponses"]
        entetes = [c.value for c in ws[1]]
        self.assertEqual(ws.cell(row=2, column=entetes.index("D01") + 1).value, 100)
        self.assertEqual(ws.cell(row=2, column=entetes.index("A03") + 1).value.split(" (")[0],
                         "Établissement public à caractère industriel et commercial")
        for nom in ("gestion:tableau_de_bord", "gestion:statistiques", "gestion:reponses", "gestion:questionnaire"):
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200, nom)
        self.assertEqual(self.client.get(reverse("gestion:reponse_detail", args=[reponse.pk])).status_code, 200)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", MEDIA_ROOT=MEDIA_TEST)
class PiecesJointesTests(TestCase):
    def setUp(self):
        aujourd_hui = timezone.localdate()
        campagne = Campagne.objects.create(nom="C", exercice=2024, active=True,
                                           date_ouverture=aujourd_hui, date_cloture=aujourd_hui + timedelta(days=5))
        epn = EPN.objects.create(nom="E", tutelle="T", email_contact="e@epn.test")
        self.reponse = Reponse.objects.create(campagne=campagne, epn=epn, nom="N", prenom="P",
                                              statut=Reponse.Statut.EN_COURS)
        self.url = reverse("public:module", args=[self.reponse.jeton, "J"])

    def test_depot_puis_telechargement_par_le_lien(self):
        r = self.client.post(self.url, fichiers_valides() | {"action": "suivant"})
        self.assertEqual(r.status_code, 302)
        self.reponse.refresh_from_db()
        self.assertIn("J", self.reponse.modules_completes)
        self.assertEqual(self.reponse.donnees["J01"], "etats_financiers.pdf")
        piece = self.reponse.pieces.get(code="J01")
        self.assertNotIn("etats_financiers", piece.fichier.name)  # nom de stockage aléatoire
        r = self.client.get(reverse("public:piece", args=[self.reponse.jeton, "J01"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), PDF)
        self.assertIn('filename="etats_financiers.pdf"', r["Content-Disposition"])

    def test_pieces_obligatoires(self):
        r = self.client.post(self.url, {"action": "suivant"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["form"].errors["J01"], ["Ce champ est obligatoire."])

    def test_fichier_valide_conserve_si_une_autre_piece_manque(self):
        r = self.client.post(self.url, {"J01": pdf("etats.pdf"), "action": "suivant"})
        self.assertEqual(r.status_code, 200)  # J02 manque : la rubrique n'est pas validée…
        self.assertIn("J02", r.context["form"].errors)
        self.assertTrue(self.reponse.pieces.filter(code="J01").exists())  # … mais J01 est gardé
        self.assertContains(r, "etats.pdf")
        r = self.client.post(self.url, {"J02": pdf("rapport.pdf"), "action": "suivant"})
        self.assertEqual(r.status_code, 302)

    def test_format_et_contenu_controles(self):
        r = self.client.post(self.url, {"J01": SimpleUploadedFile("virus.exe", b"MZ..."), "action": "brouillon"})
        self.assertContains(r, "Format non accepté")
        r = self.client.post(self.url, {"J01": SimpleUploadedFile("faux.pdf", b"MZ\x90\x00"), "action": "brouillon"})
        self.assertContains(r, "ne correspond pas à son extension")
        self.assertFalse(self.reponse.pieces.exists())

    def test_taille_maximale(self):
        from enquete import pieces
        ancien, pieces.TAILLE_MAX = pieces.TAILLE_MAX, 10
        try:
            r = self.client.post(self.url, {"J01": pdf(contenu=PDF * 2), "action": "brouillon"})
            self.assertContains(r, "Fichier trop volumineux")
        finally:
            pieces.TAILLE_MAX = ancien

    def test_remplacement_et_suppression(self):
        self.client.post(self.url, fichiers_valides() | {"action": "suivant"})
        ancien = self.reponse.pieces.get(code="J01").fichier.path
        self.client.post(self.url, {"J01": pdf("v2.pdf"), "action": "brouillon"})
        self.assertEqual(self.reponse.pieces.get(code="J01").nom_original, "v2.pdf")
        self.assertFalse(Path(ancien).exists())
        r = self.client.post(self.url, {"action": "supprimer:J01"})
        self.assertEqual(r.status_code, 302)
        self.reponse.refresh_from_db()
        self.assertFalse(self.reponse.pieces.filter(code="J01").exists())
        self.assertNotIn("J", self.reponse.modules_completes)

    def test_un_autre_lien_ou_un_anonyme_ne_peut_pas_telecharger(self):
        self.client.post(self.url, fichiers_valides() | {"action": "suivant"})
        piece = self.reponse.pieces.get(code="J01")
        self.assertEqual(self.client.get(reverse("public:piece", args=["autre-jeton", "J01"])).status_code, 404)
        r = self.client.get(reverse("gestion:piece", args=[piece.pk]))
        self.assertEqual(r.status_code, 302)
        admin = User.objects.create_user("a", password="motdepasse-solide", is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("gestion:piece", args=[piece.pk])).status_code, 200)
        r = self.client.get(reverse("gestion:pieces_zip", args=[self.reponse.pk]))
        self.assertEqual(r["Content-Type"], "application/zip")
        import zipfile
        self.assertEqual(sorted(zipfile.ZipFile(BytesIO(r.content)).namelist()),
                         ["J01_etats_financiers.pdf", "J02_rapport.pdf"])
