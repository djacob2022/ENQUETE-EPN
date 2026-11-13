"""F-16 : questionnaire bilingue (français / anglais) pour l'établissement répondant."""
import io
import json

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from openpyxl import load_workbook

from enquete import editeur
from enquete.models import Reponse

from .test_cahier import REGLAGES, Outils
from .test_parcours import VALEURS

EN = {"HTTP_X_LANGUE": "en"}


@override_settings(**REGLAGES)
class BilingueTests(Outils):
    def post_en(self, nom, args=(), donnees=None):
        return self.client.post(reverse(nom, args=args), json.dumps(donnees or {}), content_type="application/json", **EN)

    def test_questionnaire_traduit_et_francais_par_defaut(self):
        fr = self.client.get(reverse("api:questionnaire")).json()
        en = self.client.get(reverse("api:questionnaire"), **EN).json()
        self.assertEqual(fr["modules"][0]["titre"], "Identification de l'établissement")
        self.assertEqual(en["modules"][0]["titre"], "Institution identification")
        q_fr = {q["code"]: q for m in fr["modules"] for q in m["questions"]}
        q_en = {q["code"]: q for m in en["modules"] for q in m["questions"]}
        self.assertEqual(q_en["B03"]["choix"], [{"valeur": "oui", "libelle": "Yes"}, {"valeur": "non", "libelle": "No"}])
        self.assertEqual(q_fr["B03"]["choix"][0]["libelle"], "Oui")
        self.assertEqual(q_en["C04"]["choix"][1], {"valeur": "regionale", "libelle": "Regional"})
        self.assertEqual(q_en["D01"]["unite"], "staff")
        self.assertEqual(q_en["G04"]["colonnes"][1]["libelle"], "Target")
        # Chaque libellé du questionnaire par défaut a sa traduction.
        for m in en["modules"]:
            for q in m["questions"]:
                self.assertNotEqual(q["libelle"], q_fr[q["code"]]["libelle"], q["code"]) if q["code"] not in (
                    "A11",) else None

    def test_erreurs_en_anglais_et_langue_memorisee(self):
        r = self.nouvelle_reponse()
        resp = self.post_en("api:identification", [r.jeton], {"nom": "", "prenom": "Ann", "email": "pas-une-adresse"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("This field is required.", resp.json()["erreurs"]["nom"])
        self.identifier(r)
        resp = self.post_en("api:module", [r.jeton, "D"], {"valeurs": VALEURS["D"] | {"D02": 10}, "valider": True})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("which differs from", " ".join(sum(resp.json()["erreurs"].values(), [])))
        r.refresh_from_db()
        self.assertEqual(r.langue, "en")
        resp = self.post_en("api:soumettre", [r.jeton], {"certification": True})
        self.assertTrue(resp.json()["erreur"].startswith("Sections to complete before submitting:"))
        # Requête suivante sans en-tête : retour au français.
        resp = self.post("api:soumettre", [r.jeton], {"certification": True})
        self.assertTrue(resp.json()["erreur"].startswith("Rubriques à compléter"))

    def test_accuse_et_pdf_en_anglais(self):
        r = self.reponse_complete(Reponse.Statut.EN_COURS)
        r.langue = "en"
        r.save()
        from enquete import services

        services.soumettre(r, True)
        accuse = mail.outbox[-1]
        self.assertTrue(accuse.subject.startswith("Acknowledgement of receipt"))
        self.assertIn("?langue=en", accuse.body)
        self.assertTrue(accuse.attachments[0][1].startswith(b"%PDF"))
        pdf_en = self.client.get(reverse("api:recapitulatif_pdf", args=[r.jeton]) + "?langue=en")
        self.assertEqual(pdf_en.status_code, 200)
        self.assertTrue(pdf_en.content.startswith(b"%PDF"))
        # L'équipe d'enquête garde le français : la réponse affichée côté gestion n'est pas traduite.
        self.client.force_login(self.admin)
        detail = self.client.get(reverse("api:reponse_detail", args=[r.pk]), **EN).json()
        self.assertEqual(detail["modules"][0]["titre"], "Identification de l'établissement")

    def test_modele_excel_anglais_reimporte(self):
        r = self.nouvelle_reponse()
        self.identifier(r)
        contenu = self.client.get(reverse("api:modele_xlsx", args=[r.jeton]) + "?langue=en").content
        wb = load_workbook(io.BytesIO(contenu))
        self.assertEqual(wb.sheetnames, ["Read me", "Questionnaire"])
        ws = wb["Questionnaire"]
        self.assertEqual(ws["G1"].value, "Your answer")
        lignes = {row[1].value: row for row in ws.iter_rows(min_row=2)}
        lignes["B03"][6].value = "Yes"
        lignes["C04"][6].value = "Regional"
        tampon = io.BytesIO()
        wb.save(tampon)
        tampon.name = "q.xlsx"
        tampon.seek(0)
        # Importé depuis l'interface en français : les libellés anglais sont reconnus.
        resp = self.client.post(reverse("api:import_xlsx", args=[r.jeton]), {"fichier": tampon})
        self.assertEqual(resp.status_code, 200, resp.content)
        r.refresh_from_db()
        self.assertEqual((r.donnees["B03"], r.donnees["C04"]), ("oui", "regionale"))

    def test_editeur_conserve_la_version_anglaise(self):
        self.client.force_login(self.admin)
        url = reverse("api:campagne_questionnaire", args=[self.campagne.pk])
        d = self.client.get(url).json()
        self.assertEqual(d["modules"][0]["titre_en"], "Institution identification")
        a01 = d["modules"][0]["questions"][0]
        self.assertEqual(a01["libelle_en"], "Full name")
        a01["libelle"], a01["libelle_en"] = "Nom officiel", "Official name"
        a03 = d["modules"][0]["questions"][2]
        a03["choix"][2]["libelle_en"] = "Something else"
        resp = self.client.put(url, json.dumps(d), content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.client.logout()
        en = self.client.get(reverse("api:questionnaire"), **EN).json()
        q = {x["code"]: x for x in en["modules"][0]["questions"]}
        self.assertEqual(q["A01"]["libelle"], "Official name")
        self.assertEqual(q["A03"]["choix"][2]["libelle"], "Something else")
        # Seules les traductions retouchées sont enregistrées.
        stockee = self.campagne.__class__.objects.get(pk=self.campagne.pk).questionnaire
        self.assertEqual(stockee["modules"][0]["questions"][0]["libelle_en"], "Official name")
        self.assertNotIn("libelle_en", stockee["modules"][0]["questions"][1])
        self.assertNotIn("titre_en", stockee["modules"][0])
        # Français modifié, anglais (automatique) laissé tel quel : repli sur le français, jamais une traduction périmée.
        self.client.force_login(self.admin)
        d = self.client.get(url).json()
        d["modules"][0]["questions"][1]["libelle"] = "Sigle officiel"
        d["modules"][0]["questions"][0]["libelle"] = "Nom officiel complet"
        propre, _, _ = editeur.normaliser(d, stockee)
        self.assertNotIn("libelle_en", propre["modules"][0]["questions"][1])
        self.assertEqual(propre["modules"][0]["questions"][0]["libelle_en"], "Official name")  # saisie : conservée
