"""Exigences complétées : F-03, F-26, F-27, F-32, F-49."""
import io
import zipfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from enquete import totp
from enquete.models import EPN, Journal, Reponse

from .test_cahier import REGLAGES, Outils
from .test_parcours import VALEURS


@override_settings(**REGLAGES)
class DoubleAuthentificationTests(Outils):
    def activer(self):
        self.client.force_login(self.admin)
        secret = self.post("api:deux_facteurs").json()["secret"]
        codes = self.post("api:deux_facteurs", donnees={"code": totp._code(secret, totp.pas_courant())}).json()
        self.client.logout()
        return secret, codes["codes_secours"]

    def test_mise_en_place_puis_connexion_en_deux_etapes(self):
        self.client.force_login(self.admin)
        debut = self.post("api:deux_facteurs").json()
        self.assertTrue(debut["uri"].startswith("otpauth://totp/"))
        self.assertIn("<svg", debut["qr_svg"])
        self.assertEqual(self.post("api:deux_facteurs", donnees={"code": "000000"}).status_code, 400)
        self.client.logout()
        secret, codes = self.activer()
        self.assertEqual(len(codes), 8)
        # Mot de passe seul : pas de session ouverte.
        resp = self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "motdepasse-solide"})
        self.assertEqual(resp.json(), {"deux_facteurs": True})
        self.assertEqual(self.client.get(reverse("api:moi")).status_code, 401)
        self.assertEqual(self.post("api:verification_deux_facteurs", donnees={"code": "123456"}).status_code, 401)
        # Le code d'un pas futur (pas encore consommé) passe ; il ne peut pas être rejoué.
        code = totp._code(secret, totp.pas_courant() + 1)
        moi = self.post("api:verification_deux_facteurs", donnees={"code": code}).json()
        self.assertTrue(moi["deux_facteurs"])
        self.client.logout()
        self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "motdepasse-solide"})
        self.assertEqual(self.post("api:verification_deux_facteurs", donnees={"code": code}).status_code, 401)
        # Code de secours : accepté une seule fois.
        self.assertEqual(self.post("api:verification_deux_facteurs", donnees={"code": codes[0]}).status_code, 200)
        self.client.logout()
        self.post("api:connexion", donnees={"identifiant": "admin", "mot_de_passe": "motdepasse-solide"})
        self.assertEqual(self.post("api:verification_deux_facteurs", donnees={"code": codes[0]}).status_code, 401)

    def test_desactivation_exige_le_mot_de_passe_et_reinitialisation_par_un_admin(self):
        self.activer()
        u = self.admin
        self.client.force_login(u)
        resp = self.client.delete(reverse("api:deux_facteurs"), '{"mot_de_passe": "faux"}', content_type="application/json")
        self.assertEqual(resp.status_code, 403)
        autre = User.objects.create_user("chef", password="Mot-de-passe-1", is_staff=True, is_superuser=True)
        self.client.force_login(autre)
        self.post("api:compte", [u.pk], {"action": "reinitialiser_2fa"})
        u.refresh_from_db()
        self.assertFalse(hasattr(u, "double_auth") and u.double_auth.active)


@override_settings(**REGLAGES)
class RecapitulatifPdfTests(Outils):
    def test_pdf_par_lien_et_joint_a_l_accuse(self):
        r = self.nouvelle_reponse()
        self.assertEqual(self.client.get(reverse("api:recapitulatif_pdf", args=[r.jeton])).status_code, 409)
        r.delete()
        r = self.reponse_complete(Reponse.Statut.EN_COURS)
        r.date_soumission = None
        r.save()
        pdf = self.client.get(reverse("api:recapitulatif_pdf", args=[r.jeton]))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertEqual(self.post("api:soumettre", [r.jeton], {"certification": True}).status_code, 200)
        accuse = mail.outbox[-1]
        self.assertIn("Accusé", accuse.subject)
        self.assertEqual(accuse.attachments[0][2], "application/pdf")
        self.client.force_login(self.admin)
        self.assertTrue(self.client.get(reverse("api:reponse_pdf", args=[r.pk])).content.startswith(b"%PDF"))


@override_settings(**REGLAGES)
class ModeleExcelTests(Outils):
    def test_telecharger_remplir_reimporter(self):
        r = self.nouvelle_reponse()
        self.identifier(r)
        contenu = self.client.get(reverse("api:modele_xlsx", args=[r.jeton])).content
        wb = load_workbook(io.BytesIO(contenu))
        ws = wb["Questionnaire"]
        lignes = {ws.cell(row=i, column=2).value: i for i in range(2, ws.max_row + 1)}
        reponses = {"A03": "Établissement public à caractère industriel et commercial (EPIC)", "A05": "12/05/1990",
                    "D01": 100, "D02": 40, "D03": "beaucoup", "B03": "Oui", "H04": "Comptabilité ; Paie / RH"}
        for code, v in reponses.items():
            ws.cell(row=lignes[code], column=7, value=v)
        tampon = io.BytesIO()
        wb.save(tampon)
        resp = self.client.post(reverse("api:import_xlsx", args=[r.jeton]),
                                {"fichier": SimpleUploadedFile("q.xlsx", tampon.getvalue())})
        self.assertEqual(resp.status_code, 200, resp.content)
        corps = resp.json()
        self.assertIn("D03", corps["erreurs"])  # format refusé, le reste est gardé
        r.refresh_from_db()
        self.assertEqual((r.donnees["A03"], r.donnees["A05"], r.donnees["D01"], r.donnees["B03"]),
                         ("EPIC", "1990-05-12", 100, "oui"))
        self.assertEqual(r.donnees["H04"], ["comptabilite", "paie"])
        mauvais = self.client.post(reverse("api:import_xlsx", args=[r.jeton]),
                                   {"fichier": SimpleUploadedFile("x.xlsx", b"pas un classeur")})
        self.assertEqual(mauvais.status_code, 400)


@override_settings(**REGLAGES)
class AtypiquesTests(Outils):
    def test_valeur_atypique_signalee_dans_la_campagne(self):
        rep = []
        for i, effectif in enumerate([100, 110, 120, 105, 115, 5000]):
            e = EPN.objects.create(nom=f"EPN {i}", tutelle="Agriculture", email_contact=f"e{i}@epn.test")
            r = self.reponse_complete(Reponse.Statut.SOUMIS, epn=e)
            r.donnees["D01"] = effectif
            r.save()
            rep.append(r)
        self.client.force_login(self.admin)
        lignes = {l["code"]: l for m in self.client.get(reverse("api:reponse_detail", args=[rep[-1].pk])).json()["modules"]
                  for l in m["lignes"]}
        self.assertEqual(lignes["D01"].get("atypique"), "haut")
        stats = self.client.get(reverse("api:statistiques") + "?base=envoyees").json()
        self.assertIn(("EPN 5", "D01"), {(a["epn"], a["code"]) for a in stats["atypiques"]})


@override_settings(**REGLAGES)
class SauvegardeTests(Outils):
    def test_sauvegarde_puis_restauration_complete(self):
        r = self.reponse_complete()
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("api:sauvegarde")).status_code, 403)  # pas super-administrateur
        self.admin.is_superuser = True
        self.admin.save()
        archive = self.client.get(reverse("api:sauvegarde")).content
        self.assertIn("donnees.json", zipfile.ZipFile(io.BytesIO(archive)).namelist())
        import json
        modeles = [o["model"] for o in json.loads(zipfile.ZipFile(io.BytesIO(archive)).read("donnees.json"))]
        self.assertIn("enquete.reponse", modeles, sorted(set(modeles)))
        identifiant = r.pk
        r.delete()
        EPN.objects.create(nom="Créé après la sauvegarde", tutelle="T", email_contact="x@epn.test")
        refus = self.client.post(reverse("api:restauration"), {"fichier": SimpleUploadedFile("s.zip", archive)})
        self.assertEqual(refus.status_code, 400)  # sans confirmation
        ok = self.client.post(reverse("api:restauration"), {"fichier": SimpleUploadedFile("s.zip", archive),
                                                            "confirmation": "RESTAURER"})
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertTrue(Reponse.objects.filter(pk=identifiant).exists())
        self.assertFalse(EPN.objects.filter(nom="Créé après la sauvegarde").exists())
        self.assertTrue(Journal.objects.filter(action="restauration").exists())
        piege = io.BytesIO()
        with zipfile.ZipFile(piege, "w") as z:
            z.writestr("version.json", '{"version": 1}')
            z.writestr("donnees.json", "[]")
            z.writestr("media/../../evasion.txt", "x")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("api:restauration"), {
            "fichier": SimpleUploadedFile("p.zip", piege.getvalue()), "confirmation": "RESTAURER"}).status_code, 400)
