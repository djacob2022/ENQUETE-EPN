"""Fonctions ajoutées pour la conformité au cahier des charges (codes F-xx)."""
import copy
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from enquete.models import EPN, Campagne, Journal, ProfilEquipe, Reponse

from .test_parcours import MEDIA_TEST, VALEURS, Base, pdf

REGLAGES = dict(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="http://testserver",
                MEDIA_ROOT=MEDIA_TEST)


def compte(identifiant, role, tutelles=""):
    u = User.objects.create_user(identifiant, email=f"{identifiant}@admin.test", password="Mot-de-passe-1", is_staff=True)
    ProfilEquipe.objects.create(utilisateur=u, role=role, tutelles=tutelles)
    return u


class Outils(Base):
    def reponse_complete(self, statut=Reponse.Statut.SOUMIS, epn=None):
        r = Reponse.objects.create(campagne=self.campagne, epn=epn or self.epn, nom="Bamba", prenom="Karim",
                                   email="k@epn.test", statut=statut, date_soumission=timezone.now())
        for m in VALEURS.values():
            r.donnees.update(m)
        r.modules_completes = self.campagne.q.codes_modules()
        r.save()
        from enquete.models import PieceJointe
        for code in ("J01", "J02"):
            p = PieceJointe(reponse=r, code=code, nom_original=f"{code}.pdf", taille=10)
            p.fichier.save(f"{code}.pdf", pdf(), save=True)
        return r


@override_settings(**REGLAGES)
class ConditionsEtTypesTests(Outils):
    def test_question_conditionnelle_non_posee_et_reponse_effacee(self):
        """F-13 : sans conseil de gestion (B03 = non), B04 et B05 ne sont ni obligatoires ni conservées."""
        r = self.nouvelle_reponse()
        self.identifier(r)
        resp = self.post("api:module", [r.jeton, "B"], {"valeurs": VALEURS["B"] | {"B03": "non", "B04": "", "B05": ""},
                                                        "valider": True})
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertIn("B", resp.json()["reponse"]["modules_completes"])
        self.post("api:module", [r.jeton, "B"], {"valeurs": VALEURS["B"]})
        r.refresh_from_db()
        self.assertEqual(r.donnees["B04"], 9)
        self.post("api:module", [r.jeton, "B"], {"valeurs": {"B03": "non"}})
        r.refresh_from_db()
        self.assertIsNone(r.donnees["B04"])
        # Avec « oui », B04 redevient obligatoire.
        resp = self.post("api:module", [r.jeton, "B"], {"valeurs": VALEURS["B"] | {"B04": ""}, "valider": True})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("B04", resp.json()["erreurs"])

    def test_date_echelle_et_tableau_controles(self):
        r = self.nouvelle_reponse()
        self.identifier(r)
        resp = self.post("api:module", [r.jeton, "I"], {"valeurs": VALEURS["I"] | {"I02": 9}, "valider": True})
        self.assertIn("I02", resp.json()["erreurs"])
        resp = self.post("api:module", [r.jeton, "A"], {"valeurs": VALEURS["A"] | {"A05": "12/05/1990"}, "valider": True})
        self.assertIn("A05", resp.json()["erreurs"])
        tableau = [{"indicateur": "X", "cible": "beaucoup", "realise": "1"}]
        resp = self.post("api:module", [r.jeton, "G"], {"valeurs": VALEURS["G"] | {"G04": tableau}, "valider": True})
        self.assertIn("G04", resp.json()["erreurs"])


@override_settings(**REGLAGES)
class CircuitDeValidationTests(Outils):
    def test_revue_correction_par_question_puis_validation(self):
        """F-29, F-30 : soumis → en revue → à corriger (commentaires) → soumis → validé."""
        superviseur = compte("sup", "superviseur", "Agriculture")
        r = self.reponse_complete()
        self.client.force_login(superviseur)
        self.assertEqual(self.post("api:reponse_action", [r.pk, "revue"]).json()["reponse"]["statut"], "en_revue")
        self.assertEqual(self.post("api:reponse_action", [r.pk, "corriger"], {"commentaires": {}}).status_code, 400)
        resp = self.post("api:reponse_action", [r.pk, "corriger"],
                         {"commentaires": {"E02": "Montant à vérifier", "general": "Voir Finances", "ZZ99": "ignoré"}})
        self.assertEqual(resp.json()["reponse"]["statut"], "a_corriger")
        self.assertIn("E02 · Budget exécuté : Montant à vérifier", mail.outbox[-1].body)
        # Le répondant voit les commentaires et peut corriger, même après la date de clôture.
        self.campagne.date_cloture = timezone.localdate() - timedelta(days=1)
        self.campagne.save()
        publique = self.client.get(reverse("api:reponse", args=[r.jeton])).json()
        self.assertEqual((publique["etat"], publique["commentaires"]["E02"]), ("ouvert", "Montant à vérifier"))
        self.assertNotIn("ZZ99", publique["commentaires"])
        self.assertEqual(self.post("api:module", [r.jeton, "E"], {"valeurs": VALEURS["E"] | {"E02": 950}}).status_code, 200)
        self.assertEqual(self.post("api:soumettre", [r.jeton], {"certification": True}).status_code, 200)
        self.client.force_login(superviseur)
        resp = self.post("api:reponse_action", [r.pk, "valider"])
        self.assertEqual(resp.json()["reponse"]["statut"], "valide")
        self.assertEqual(resp.json()["reponse"]["valide_par"], "sup")
        actions = list(Journal.objects.order_by("pk").values_list("action", flat=True))
        for a in ("revue", "correction", "soumission", "validation"):
            self.assertIn(a, actions)

    def test_prolongation_du_delai_pour_un_epn(self):
        """F-20 : un délai propre à l'EPN rouvre la saisie après la clôture."""
        r = self.nouvelle_reponse()
        self.campagne.date_cloture = timezone.localdate() - timedelta(days=2)
        self.campagne.save()
        self.assertEqual(self.client.get(reverse("api:reponse", args=[r.jeton])).json()["etat"], "ferme")
        self.client.force_login(self.admin)
        self.assertEqual(self.post("api:reponse_action", [r.pk, "prolonger"], {"date": "2000-01-01"}).status_code, 400)
        demain = (timezone.localdate() + timedelta(days=5)).isoformat()
        self.assertEqual(self.post("api:reponse_action", [r.pk, "prolonger"], {"date": demain}).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:reponse", args=[r.jeton])).json()["etat"], "ouvert")

    def test_statistiques_et_export_sur_les_validees_par_defaut(self):
        self.reponse_complete(Reponse.Statut.VALIDE)
        autre = EPN.objects.create(nom="Autre", tutelle="Agriculture", email_contact="a@epn.test")
        self.reponse_complete(Reponse.Statut.SOUMIS, epn=autre)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("api:statistiques")).json()["n"], 1)
        self.assertEqual(self.client.get(reverse("api:statistiques") + "?base=envoyees").json()["n"], 2)
        ws = load_workbook(BytesIO(self.client.get(reverse("api:export")).content))["Réponses"]
        self.assertEqual(ws.max_row, 2)


@override_settings(**REGLAGES)
class RolesEtComptesTests(Outils):
    def test_lecteur_sans_donnees_nominatives(self):
        r = self.reponse_complete()
        self.client.force_login(compte("lecteur", "lecteur"))
        tdb = self.client.get(reverse("api:tableau_de_bord")).json()
        self.assertEqual(tdb["dernieres"][0]["repondant"], "")
        for nom, args in (("api:reponses", []), ("api:reponse_detail", [r.pk]), ("api:export", []), ("api:liens", [])):
            self.assertEqual(self.client.get(reverse(nom, args=args)).status_code, 403, nom)
        self.assertEqual(self.client.get(reverse("api:statistiques")).status_code, 200)
        wb = load_workbook(BytesIO(self.client.get(reverse("api:statistiques_xlsx")).content))
        self.assertNotIn("Réponses", wb.sheetnames)

    def test_analyste_exporte_mais_n_agit_pas(self):
        r = self.reponse_complete()
        self.client.force_login(compte("analyste", "analyste"))
        self.assertEqual(self.client.get(reverse("api:export")).status_code, 200)
        self.assertEqual(self.post("api:reponse_action", [r.pk, "valider"]).status_code, 403)
        self.assertEqual(self.post("api:campagnes", donnees={}).status_code, 403)
        moi = self.client.get(reverse("api:moi")).json()
        self.assertEqual((moi["role"], moi["administrateur"]), ("analyste", False))

    def test_creation_de_compte_puis_mot_de_passe_par_lien(self):
        """F-04 puis F-02 : l'administrateur crée le compte, la personne choisit son mot de passe via le lien."""
        self.client.force_login(self.admin)
        resp = self.post("api:comptes", donnees={"email": "Agent@Tutelle.test", "prenom": "Awa", "nom": "Koné",
                                                 "role": "superviseur", "tutelles": []})
        self.assertEqual(resp.status_code, 400)  # superviseur sans tutelle
        resp = self.post("api:comptes", donnees={"email": "Agent@Tutelle.test", "prenom": "Awa", "nom": "Koné",
                                                 "role": "superviseur", "tutelles": ["Agriculture"]})
        self.assertEqual(resp.status_code, 201, resp.json())
        lien = next(l for l in mail.outbox[-1].body.split() if "/mot-de-passe/" in l)
        uid, jeton = lien.rstrip("/").split("/")[-2:]
        self.client.logout()
        self.assertEqual(self.post("api:nouveau_mot_de_passe", donnees={"uid": uid, "jeton": jeton,
                                                                         "mot_de_passe": "simple"}).status_code, 422)
        self.assertEqual(self.post("api:nouveau_mot_de_passe", donnees={"uid": uid, "jeton": jeton,
                                                                         "mot_de_passe": "Riviere-Bleue-48"}).status_code, 200)
        # Le lien ne sert qu'une fois ; la connexion se fait par e-mail (F-01).
        self.assertEqual(self.post("api:nouveau_mot_de_passe", donnees={"uid": uid, "jeton": jeton,
                                                                         "mot_de_passe": "Autre-2026!"}).status_code, 400)
        moi = self.post("api:connexion", donnees={"identifiant": "agent@tutelle.test", "mot_de_passe": "Riviere-Bleue-48"}).json()
        self.assertEqual((moi["role"], moi["perimetre"]), ("superviseur", ["Agriculture"]))

    def test_mot_de_passe_oublie_ne_revele_pas_les_comptes(self):
        self.admin.email = "admin@tutelle.test"
        self.admin.save()
        self.assertEqual(self.post("api:mot_de_passe_oublie", donnees={"email": "inconnu@x.test"}).status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.post("api:mot_de_passe_oublie", donnees={"email": "admin@tutelle.test"}).status_code, 200)
        self.assertIn("Réinitialisation", mail.outbox[-1].subject)

    def test_session_expire_apres_30_minutes(self):
        from django.conf import settings
        self.assertEqual((settings.SESSION_COOKIE_AGE, settings.SESSION_SAVE_EVERY_REQUEST), (1800, True))


@override_settings(**REGLAGES)
class JournalTests(Outils):
    def test_journal_non_modifiable_et_reserve(self):
        self.client.force_login(self.admin)
        self.client.get(reverse("api:export"))
        j = Journal.objects.get(action="export")
        self.assertEqual(j.auteur, "admin")
        with self.assertRaises(PermissionError):
            j.objet = "falsifié"
            j.save()
        with self.assertRaises(PermissionError):
            j.delete()
        self.assertEqual(self.client.get(reverse("api:journal")).json()["total"], 1)
        self.client.force_login(compte("sup", "superviseur", "Agriculture"))
        self.assertEqual(self.client.get(reverse("api:journal")).status_code, 403)


@override_settings(**REGLAGES)
class EditeurQuestionnaireTests(Outils):
    def definition(self):
        self.client.force_login(self.admin)
        return self.client.get(reverse("api:campagne_questionnaire", args=[self.campagne.pk])).json()

    def put(self, definition):
        return self.client.put(reverse("api:campagne_questionnaire", args=[self.campagne.pk]), definition,
                               content_type="application/json")

    def test_ajout_de_question_code_automatique_et_version(self):
        d = self.definition()
        d["modules"][1]["questions"].append({"libelle": "Le DG est-il intérimaire ?", "type": "oui_non"})
        resp = self.put(d)
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertEqual(resp.json()["version"], 2)
        self.assertEqual(resp.json()["modules"][1]["questions"][-1]["code"], "B09")
        self.assertEqual(Journal.objects.filter(action="questionnaire").count(), 1)

    def test_refus_suppression_d_une_question_deja_renseignee(self):
        self.reponse_complete()
        d = self.definition()
        d["modules"][3]["questions"] = [q for q in d["modules"][3]["questions"] if q["code"] != "D08"]
        resp = self.put(d)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("D08", resp.json()["erreur"])

    def test_controles_de_la_definition(self):
        d = self.definition()
        mauvais = copy.deepcopy(d)
        mauvais["regles"].append({"type": "somme", "total": "A01", "parties": ["D02", "D03"]})
        self.assertIn("A01", self.put(mauvais).json()["erreur"])
        mauvais = copy.deepcopy(d)
        mauvais["modules"][0]["questions"][0]["si"] = {"question": "XX01", "valeurs": ["oui"]}
        self.assertEqual(self.put(mauvais).status_code, 400)
        mauvais = copy.deepcopy(d)
        mauvais["modules"][2]["questions"][2]["choix"] = [{"valeur": "a", "libelle": "Seul choix"}]
        self.assertIn("deux choix", self.put(mauvais).json()["erreur"])

    def test_module_desactive_disparait_du_parcours(self):
        d = self.definition()
        next(m for m in d["modules"] if m["code"] == "H")["actif"] = False
        self.assertEqual(self.put(d).status_code, 200)
        self.campagne.refresh_from_db()
        self.assertNotIn("H", self.campagne.q.codes_modules())
        codes = [m["code"] for m in self.client.get(reverse("api:questionnaire")).json()["modules"]]
        self.assertNotIn("H", codes)

    def test_nouvelle_campagne_reprend_le_questionnaire(self):
        """F-14 : duplication d'une campagne à l'autre."""
        d = self.definition()
        d["modules"][0]["titre"] = "Identification (version 2025)"
        self.put(d)
        resp = self.post("api:campagnes", donnees={"nom": "Suivante", "exercice": 2025, "date_ouverture": "2026-03-01",
                                                   "date_cloture": "2026-04-01", "active": False})
        c = Campagne.objects.get(pk=resp.json()["id"])
        self.assertEqual(c.q.modules[0]["titre"], "Identification (version 2025)")
        self.assertEqual(c.q.version, 1)


@override_settings(**REGLAGES)
class ExportsEtStatistiquesTests(Outils):
    def test_export_d_un_epn_une_feuille_par_module_et_csv(self):
        r = self.reponse_complete(Reponse.Statut.VALIDE)
        self.client.force_login(self.admin)
        wb = load_workbook(BytesIO(self.client.get(reverse("api:reponse_export", args=[r.pk])).content))
        self.assertEqual(len(wb.sheetnames), 1 + len(self.campagne.q.modules))
        csv = self.client.get(reverse("api:export_csv")).content.decode("utf-8-sig").splitlines()
        self.assertTrue(csv[0].startswith("epn;sigle;categorie"))
        self.assertIn("comptabilite|paie", csv[1])

    def test_quartiles_histogramme_croisement_et_n_1(self):
        precedente = Campagne.objects.create(nom="2023", exercice=2023, active=False,
                                             date_ouverture="2024-01-01", date_cloture="2024-02-01")
        Reponse.objects.create(campagne=precedente, epn=self.epn, statut="valide", donnees={"D01": 80})
        self.reponse_complete(Reponse.Statut.VALIDE)
        autre = EPN.objects.create(nom="Autre", categorie="EPA", tutelle="Santé", email_contact="a@epn.test")
        r2 = self.reponse_complete(Reponse.Statut.VALIDE, epn=autre)
        r2.donnees["D01"] = 300
        r2.save()
        self.client.force_login(self.admin)
        stats = self.client.get(reverse("api:statistiques")).json()
        d01 = next(q for b in stats["blocs"] for q in b["questions"] if q["code"] == "D01")
        self.assertEqual((d01["stats"]["q1"], d01["stats"]["q3"]), (150, 250))
        self.assertEqual(sum(c["effectif"] for c in d01["stats"]["histogramme"]), 2)
        self.assertEqual(d01["precedent"]["somme"], 80)
        croise = self.client.get(reverse("api:croisement") + "?ligne=categorie&colonne=B06").json()
        self.assertEqual(croise["n"], 2)
        self.assertEqual(croise["colonnes"], ["Oui", "Non"])

    def test_ecart_avec_l_annee_precedente_signale(self):
        """F-32 : un écart de plus de 50 % avec N-1 est signalé dans la fiche."""
        precedente = Campagne.objects.create(nom="2023", exercice=2023, active=False,
                                             date_ouverture="2024-01-01", date_cloture="2024-02-01")
        Reponse.objects.create(campagne=precedente, epn=self.epn, statut="valide", donnees={"D01": 20, "E01": 1000})
        r = self.reponse_complete()
        self.client.force_login(self.admin)
        lignes = {l["code"]: l for m in self.client.get(reverse("api:reponse_detail", args=[r.pk])).json()["modules"]
                  for l in m["lignes"]}
        self.assertTrue(lignes["D01"]["anomalie"])
        self.assertEqual(lignes["D01"]["ecart"], 400)
        self.assertFalse(lignes["E01"]["anomalie"])


@override_settings(**REGLAGES)
class CampagneEtRepertoireTests(Outils):
    def test_pre_remplissage_depuis_la_campagne_precedente(self):
        """F-24."""
        precedente = Campagne.objects.create(nom="2023", exercice=2023, active=False,
                                             date_ouverture="2024-01-01", date_cloture="2024-02-01")
        Reponse.objects.create(campagne=precedente, epn=self.epn, statut="valide", donnees=VALEURS["F"])
        r = self.nouvelle_reponse()
        self.identifier(r)
        resp = self.post("api:preremplir", [r.jeton, "F"])
        self.assertEqual(resp.json()["repris"], 5)
        self.assertIn("F", resp.json()["reponse"]["modules_completes"])

    def test_epn_cibles_et_relances_automatiques(self):
        """F-17 et F-19 : seuls les EPN ciblés reçoivent un lien ; relance à J-2, une seule fois par jour."""
        from enquete.management.commands.taches import relances_du_jour
        EPN.objects.create(nom="Santé 1", tutelle="Santé", email_contact="s@epn.test")
        self.campagne.cible_tutelles = "Agriculture"
        self.campagne.relances_auto = "-2"
        self.campagne.date_cloture = timezone.localdate() + timedelta(days=2)
        self.campagne.save()
        self.assertEqual(self.campagne.generer_liens(), 1)
        Reponse.objects.update(date_invitation=timezone.now())
        self.assertEqual(relances_du_jour(), 1)
        self.assertEqual(relances_du_jour(), 0)
        self.assertEqual(relances_du_jour(timezone.localdate() + timedelta(days=1)), 0)
        self.assertTrue(Journal.objects.filter(action="relance_auto").exists())

    def test_fiche_epn_historique_et_listes_de_reference(self):
        """F-07, F-08, F-09."""
        self.client.force_login(self.admin)
        self.assertEqual(self.post("api:references", donnees={"type": "region", "libelle": "Région Nord"}).status_code, 201)
        self.assertIn("Région Nord", self.client.get(reverse("api:options")).json()["regions"])
        resp = self.client.put(reverse("api:epn_fiche", args=[self.epn.pk]),
                               {"nom": self.epn.nom, "sigle": "OT", "categorie": "EPIC", "tutelle": "Agriculture",
                                "region": "Région Nord", "secteur": "", "email_contact": "focal@epn.test",
                                "etat": "liquidation"}, content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.json())
        self.epn.refresh_from_db()
        self.assertEqual((self.epn.etat, self.epn.actif), ("liquidation", False))
        historique = self.client.get(reverse("api:epn_fiche", args=[self.epn.pk])).json()["historique"]
        self.assertEqual(historique[0]["changements"]["etat"], ["actif", "liquidation"])

    def test_parametres_identite_et_textes_des_emails(self):
        """F-48."""
        self.client.force_login(self.admin)
        self.post("api:parametres", donnees={"pays": "République de Test", "texte_invitation": "Message du ministre."})
        self.assertEqual(self.client.get(reverse("api:config")).json()["pays"], "République de Test")
        r = self.nouvelle_reponse()
        self.post("api:reponse_action", [r.pk, "inviter"])
        self.assertIn("Message du ministre.", mail.outbox[-1].body)
        self.client.force_login(compte("analyste", "analyste"))
        self.assertEqual(self.post("api:parametres", donnees={"pays": "X"}).status_code, 403)
