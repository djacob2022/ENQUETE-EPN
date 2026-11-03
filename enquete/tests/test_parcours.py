import json
import shutil
import tempfile
import zipfile
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from enquete.models import EPN, Campagne, Envoi, Reponse
from enquete.questionnaire import MODULES

VALEURS = {
    "A": {"A01": "Office test", "A02": "OT", "A03": "EPIC", "A04": "Décret 1", "A05": 1990, "A06": "Agriculture",
          "A07": "Ville", "A08": ""},
    "B": {"B01": "oui", "B02": 4, "B03": "oui", "B04": "non", "B05": "oui"},
    "C": {"C01": "Missions", "C02": "nationale", "C03": 1000},
    "D": {"D01": 100, "D02": 40, "D03": 60, "D04": 30, "D05": 70, "D06": 5, "D07": 3, "D08": 250000000},
    "E": {"E01": 1000, "E02": 900, "E03": 600, "E04": 200, "E05": 400, "E06": 300, "E07": 200, "E08": None},
    "F": {"F01": 2, "F02": 5, "F03": 40, "F04": "oui", "F05": ["comptabilite", "paie"]},
    "G": {"G01": 10, "G02": 7, "G03": 85.5},
    "H": {"H01": ["financieres"], "H02": "Besoins", "H03": ""},
    "J": {},
}
PDF = b"%PDF-1.4\n%test\n%%EOF\n"
MEDIA_TEST = tempfile.mkdtemp()


def pdf(nom="etats.pdf", contenu=PDF):
    return SimpleUploadedFile(nom, contenu, content_type="application/pdf")


class Base(TestCase):
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

    def post(self, nom, args=(), donnees=None, client=None):
        return (client or self.client).post(reverse(nom, args=args), json.dumps(donnees or {}),
                                            content_type="application/json")

    def nouvelle_reponse(self):
        return Reponse.objects.create(campagne=self.campagne, epn=self.epn)

    def identifier(self, r):
        return self.post("api:identification", [r.jeton], {
            "nom": "Bamba", "prenom": "Karim", "fonction": "DAF", "email": "karim@epn.test",
            "telephone": "+000 01 02 03 04"})

    def deposer(self, r, code, fichier):
        return self.client.post(reverse("api:piece_publique", args=[r.jeton, code]), {"fichier": fichier})


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver",
                   MEDIA_ROOT=MEDIA_TEST)
class ParcoursTests(Base):
    def test_parcours_complet_jusqua_l_envoi(self):
        r = self.nouvelle_reponse()
        etat = self.client.get(reverse("api:reponse", args=[r.jeton])).json()
        self.assertEqual(etat["etat"], "ouvert")
        self.assertFalse(etat["identifie"])
        self.assertEqual(self.identifier(r).status_code, 200)
        self.deposer(r, "J01", pdf("etats_financiers.pdf"))
        self.deposer(r, "J02", pdf("rapport.pdf"))
        for module in MODULES:
            resp = self.post("api:module", [r.jeton, module["code"]], {"valeurs": VALEURS[module["code"]], "valider": True})
            self.assertEqual(resp.status_code, 200, f"{module['code']} : {resp.json()['erreurs']}")
        resp = self.post("api:soumettre", [r.jeton], {"certification": True})
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reponse.Statut.SOUMIS)
        self.assertEqual(r.donnees["D01"], 100)
        self.assertEqual(r.donnees["G03"], 85.5)
        self.assertEqual(r.donnees["F05"], ["comptabilite", "paie"])
        self.assertEqual(r.telephone, "+000 01 02 03 04")
        self.assertIn("Accusé", mail.outbox[-1].subject)
        # Une fois envoyée, la réponse n'est plus modifiable.
        resp = self.post("api:module", [r.jeton, "A"], {"valeurs": VALEURS["A"]})
        self.assertEqual(resp.status_code, 409)

    def test_identification_obligatoire_et_telephone_controle(self):
        r = self.nouvelle_reponse()
        self.assertEqual(self.post("api:module", [r.jeton, "A"], {"valeurs": {}}).status_code, 409)
        resp = self.post("api:identification", [r.jeton], {"nom": "B", "prenom": "K", "fonction": "DAF",
                                                            "email": "k@epn.test", "telephone": "12"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("telephone", resp.json()["erreurs"])

    def test_regle_de_coherence_et_brouillon_conserve(self):
        r = self.nouvelle_reponse()
        self.identifier(r)
        incoherent = VALEURS["D"] | {"D03": 61}
        resp = self.post("api:module", [r.jeton, "D"], {"valeurs": incoherent, "valider": True})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("différent de l'effectif total", resp.json()["erreurs"]["D02"][0])
        r.refresh_from_db()
        self.assertEqual(r.donnees["D03"], 61)  # rien n'est perdu
        self.assertNotIn("D", r.modules_completes)
        resp = self.post("api:module", [r.jeton, "D"], {"valeurs": {"D03": 60}})  # sauvegarde automatique
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertIn("D", r.modules_completes)

    def test_format_invalide_signale_sans_effacer_le_reste(self):
        r = self.nouvelle_reponse()
        self.identifier(r)
        resp = self.post("api:module", [r.jeton, "D"], {"valeurs": {"D01": "beaucoup", "D02": 40}})
        self.assertIn("D01", resp.json()["erreurs"])
        r.refresh_from_db()
        self.assertEqual(r.donnees["D02"], 40)
        self.assertNotIn("D01", r.donnees)

    def test_envoi_refuse_si_rubriques_incompletes(self):
        r = self.nouvelle_reponse()
        self.identifier(r)
        resp = self.post("api:soumettre", [r.jeton], {"certification": True})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Rubriques à compléter", resp.json()["erreur"])

    def test_campagne_fermee(self):
        self.campagne.date_cloture = timezone.localdate() - timedelta(days=1)
        self.campagne.save()
        r = self.nouvelle_reponse()
        self.assertEqual(self.client.get(reverse("api:reponse", args=[r.jeton])).json()["etat"], "ferme")
        self.assertEqual(self.identifier(r).status_code, 403)

    def test_lien_invalide(self):
        self.assertEqual(self.client.get(reverse("api:reponse", args=["inconnu"])).status_code, 404)

    def test_csrf_exige_pour_les_ecritures(self):
        r = self.nouvelle_reponse()
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("api:identification", [r.jeton], {}, client=client).status_code, 403)
        client.get(reverse("api:csrf"))
        jeton = client.cookies["csrftoken"].value
        resp = client.post(reverse("api:identification", args=[r.jeton]), "{}", content_type="application/json",
                           HTTP_X_CSRFTOKEN=jeton)
        self.assertEqual(resp.status_code, 422)  # passe le CSRF, échoue seulement sur la validation

    def test_pages_de_l_interface_servies(self):
        r = self.nouvelle_reponse()
        for url in ("/", r.lien.replace("http://testserver", ""), "/gestion/", "/gestion/reponses/12", "/connexion/"):
            self.assertIn(self.client.get(url).status_code, (200, 503), url)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", MEDIA_ROOT=MEDIA_TEST)
class PiecesJointesTests(Base):
    def setUp(self):
        super().setUp()
        self.r = self.nouvelle_reponse()
        self.identifier(self.r)

    def test_depot_puis_telechargement_par_le_lien(self):
        resp = self.deposer(self.r, "J01", pdf("etats_financiers.pdf"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["pieces"]["J01"]["nom"], "etats_financiers.pdf")
        piece = self.r.pieces.get(code="J01")
        self.assertNotIn("etats_financiers", piece.fichier.name)  # nom de stockage aléatoire
        resp = self.client.get(reverse("api:piece_publique", args=[self.r.jeton, "J01"]))
        self.assertEqual(b"".join(resp.streaming_content), PDF)
        self.assertIn('filename="etats_financiers.pdf"', resp["Content-Disposition"])

    def test_pieces_obligatoires(self):
        resp = self.post("api:module", [self.r.jeton, "J"], {"valeurs": {}, "valider": True})
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(set(resp.json()["erreurs"]), {"J01", "J02"})
        self.deposer(self.r, "J01", pdf())
        self.deposer(self.r, "J02", pdf())
        self.assertEqual(self.post("api:module", [self.r.jeton, "J"], {"valeurs": {}, "valider": True}).status_code, 200)

    def test_format_contenu_et_taille_controles(self):
        resp = self.deposer(self.r, "J01", SimpleUploadedFile("virus.exe", b"MZ..."))
        self.assertIn("Format non accepté", resp.json()["erreur"])
        resp = self.deposer(self.r, "J01", SimpleUploadedFile("faux.pdf", b"MZ\x90\x00"))
        self.assertIn("ne correspond pas", resp.json()["erreur"])
        from enquete import pieces
        ancien, pieces.TAILLE_MAX = pieces.TAILLE_MAX, 10
        try:
            self.assertIn("trop volumineux", self.deposer(self.r, "J01", pdf()).json()["erreur"])
        finally:
            pieces.TAILLE_MAX = ancien
        self.assertFalse(self.r.pieces.exists())

    def test_remplacement_et_suppression(self):
        self.deposer(self.r, "J01", pdf())
        ancien = self.r.pieces.get(code="J01").fichier.path
        self.deposer(self.r, "J01", pdf("v2.pdf"))
        self.assertEqual(self.r.pieces.get(code="J01").nom_original, "v2.pdf")
        self.assertFalse(Path(ancien).exists())
        resp = self.client.delete(reverse("api:piece_publique", args=[self.r.jeton, "J01"]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.r.pieces.filter(code="J01").exists())

    def test_acces_aux_fichiers(self):
        self.deposer(self.r, "J01", pdf("etats.pdf"))
        self.deposer(self.r, "J02", pdf("rapport.pdf"))
        piece = self.r.pieces.get(code="J01")
        self.assertEqual(self.client.get(reverse("api:piece_publique", args=["autre", "J01"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("api:piece_admin", args=[piece.pk])).status_code, 401)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("api:piece_admin", args=[piece.pk])).status_code, 200)
        resp = self.client.get(reverse("api:pieces_zip", args=[self.r.pk]))
        self.assertEqual(sorted(zipfile.ZipFile(BytesIO(resp.content)).namelist()), ["J01_etats.pdf", "J02_rapport.pdf"])


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver")
class GestionTests(Base):
    def test_connexion_et_acces_reserve(self):
        self.assertEqual(self.client.get(reverse("api:tableau_de_bord")).status_code, 401)
        resp = self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "faux"})
        self.assertEqual(resp.status_code, 401)
        User.objects.create_user("lambda", password="motdepasse-solide")
        self.assertEqual(self.post("api:connexion", donnees={"identifiant": "lambda",
                                                             "mot_de_passe": "motdepasse-solide"}).status_code, 401)
        resp = self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "motdepasse-solide"})
        self.assertEqual(resp.json()["identifiant"], "admin")
        self.assertEqual(self.client.get(reverse("api:tableau_de_bord")).status_code, 200)
        self.post("api:deconnexion")
        self.assertEqual(self.client.get(reverse("api:moi")).status_code, 401)

    def test_liens_uniques_invitations_et_relances(self):
        EPN.objects.create(nom="Autre", tutelle="Santé", email_contact="autre@epn.test")
        EPN.objects.create(nom="Inactif", tutelle="T", email_contact="x@epn.test", actif=False)
        self.client.force_login(self.admin)
        resp = self.post("api:liens")
        self.assertEqual(resp.json()["crees"], 2)
        liens = [l["lien"] for l in resp.json()["liens"]]
        self.assertEqual(len(set(liens)), 2)
        self.assertEqual(len(mail.outbox), 0)  # générer un lien n'envoie rien
        self.assertEqual(self.post("api:liens").json()["crees"], 0)  # idempotent
        resp = self.post("api:liens", donnees={"envoyer": True})
        self.assertEqual(resp.json()["envoyees"], 2)
        self.assertIn(liens[0], " ".join(m.body for m in mail.outbox))
        mail.outbox.clear()
        resp = self.post("api:relancer_retardataires")
        self.assertEqual(resp.json(), {"envoyees": 2, "total": 2})
        self.assertTrue(all("Rappel" in m.subject for m in mail.outbox))
        self.assertEqual(Envoi.objects.filter(type=Envoi.Type.RELANCE).count(), 2)
        ws = load_workbook(BytesIO(self.client.get(reverse("api:liens_xlsx")).content))["Liens"]
        self.assertEqual(ws.max_row, 3)

    def test_tableau_de_bord_export_statistiques_detail(self):
        r = self.nouvelle_reponse()
        r.statut = Reponse.Statut.SOUMIS
        r.nom, r.prenom = "Bamba", "Karim"
        r.donnees = {"D01": 100, "D02": 40, "E01": 1000, "E02": 900, "A03": "EPIC", "A05": 1990, "F05": ["paie"]}
        r.date_soumission = timezone.now()
        r.save()
        self.client.force_login(self.admin)
        tdb = self.client.get(reverse("api:tableau_de_bord")).json()
        self.assertEqual((tdb["taux"], tdb["effectif_total"]), (100, 100))
        stats = self.client.get(reverse("api:statistiques")).json()
        self.assertEqual(stats["n"], 1)
        detail = self.client.get(reverse("api:reponse_detail", args=[r.pk])).json()
        lignes = {l["code"]: l["valeur"] for m in detail["modules"] for l in m["lignes"]}
        self.assertEqual(lignes["A05"], "1990")
        self.assertTrue(lignes["A03"].startswith("Établissement public à caractère industriel"))
        wb = load_workbook(BytesIO(self.client.get(reverse("api:export")).content))
        self.assertEqual(wb.sheetnames, ["Réponses", "Dictionnaire", "Statistiques", "Indicateurs"])
        entetes = [c.value for c in wb["Réponses"][1]]
        self.assertEqual(wb["Réponses"].cell(row=2, column=entetes.index("D01") + 1).value, 100)
        resp = self.post("api:reponse_action", [r.pk, "rouvrir"])
        self.assertEqual(resp.json()["reponse"]["statut"], "en_cours")
        self.assertEqual(self.client.get(reverse("api:options")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:epn")).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:campagnes")).status_code, 200)

    def test_creation_de_campagne_validee(self):
        self.client.force_login(self.admin)
        resp = self.post("api:campagnes", donnees={"nom": "2026", "exercice": 2025, "date_ouverture": "2026-03-01",
                                                   "date_cloture": "2026-02-01", "active": False})
        self.assertEqual(resp.status_code, 422)
        resp = self.post("api:campagnes", donnees={"nom": "2026", "exercice": 2025, "date_ouverture": "2026-03-01",
                                                   "date_cloture": "2026-03-31", "active": False})
        self.assertEqual(resp.status_code, 201)

    def test_commande_liens_epn(self):
        sortie = StringIO()
        call_command("liens_epn", "--generer", stdout=sortie)
        self.assertIn("1 lien(s) généré(s)", sortie.getvalue())
        self.assertIn("/formulaire", sortie.getvalue())
        self.assertEqual(sortie.getvalue().count("/r/"), 1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver")
class LienPublicTests(Base):
    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()

    def test_liste_puis_envoi_du_lien_au_point_focal_officiel(self):
        d = self.client.get(reverse("api:formulaire_public")).json()
        self.assertTrue(d["ouverte"])
        self.assertEqual([e["nom"] for e in d["etablissements"]], ["Office test"])
        self.assertNotIn("email_contact", d["etablissements"][0])  # l'adresse n'est pas exposée
        resp = self.post("api:formulaire_public", donnees={"epn": self.epn.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email_masque"], "f••••@epn.test")
        self.assertNotIn("/r/", json.dumps(resp.json()))  # le lien personnel n'est jamais renvoyé au navigateur
        r = Reponse.objects.get(epn=self.epn)
        self.assertEqual(mail.outbox[0].to, ["focal@epn.test"])
        self.assertIn(r.lien, mail.outbox[0].body)
        # Une deuxième demande dans les 5 minutes ne renvoie pas d'e-mail et ne crée pas de second lien.
        self.post("api:formulaire_public", donnees={"epn": self.epn.pk})
        self.assertEqual((len(mail.outbox), Reponse.objects.count()), (1, 1))

    def test_etablissement_inconnu_ou_inactif(self):
        inactif = EPN.objects.create(nom="Fermé", tutelle="T", email_contact="x@epn.test", actif=False)
        self.assertEqual(self.post("api:formulaire_public", donnees={"epn": inactif.pk}).status_code, 400)
        self.assertEqual(self.post("api:formulaire_public", donnees={"epn": 9999}).status_code, 400)

    def test_limite_de_demandes(self):
        for _ in range(10):
            self.post("api:formulaire_public", donnees={"epn": 9999})
        self.assertEqual(self.post("api:formulaire_public", donnees={"epn": self.epn.pk}).status_code, 429)

    def test_campagne_fermee(self):
        self.campagne.date_cloture = timezone.localdate() - timedelta(days=1)
        self.campagne.save()
        self.assertFalse(self.client.get(reverse("api:formulaire_public")).json()["ouverte"])
        self.assertEqual(self.post("api:formulaire_public", donnees={"epn": self.epn.pk}).status_code, 403)

    def test_page_et_config(self):
        self.assertIn(self.client.get("/formulaire").status_code, (200, 503))
        self.assertEqual(self.client.get(reverse("api:config")).json()["lien_public"], "http://testserver/formulaire")
