"""Rapport annuel automatique et assistant IA (client Claude simulé : aucun appel réseau)."""
import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from enquete import assistant, rapport
from enquete.models import EPN, Journal, ProfilEquipe, Reponse, SyntheseIA

from .test_cahier import REGLAGES, Outils

SYNTHESE = {"synthese": "La participation progresse.\nLes finances restent tendues.",
            "points_forts": ["Taux de réponse élevé"], "points_vigilance": ["Dépendance à la subvention"],
            "besoins": ["Formation du personnel"], "recommandations": ["Renforcer le suivi budgétaire"]}


def reponse_modele(texte, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, model="claude-opus-5-5",
                           content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=texte)])


class FluxSimule:
    """Remplace client.beta.messages.stream(...) : mémorise les paramètres et rend une réponse préparée."""
    def __init__(self, reponse):
        self.reponse, self.appels = reponse, []

    def __call__(self, **kwargs):
        self.appels.append(kwargs)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.reponse


def simuler(reponse):
    flux = FluxSimule(reponse)
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=flux)))
    return flux, mock.patch.object(assistant, "_client", return_value=client)


@override_settings(**REGLAGES, ANTHROPIC_API_KEY="")
class RapportAnnuelTests(Outils):
    def preparer(self):
        for i, statut in enumerate([Reponse.Statut.VALIDE, Reponse.Statut.VALIDE, Reponse.Statut.SOUMIS]):
            e = EPN.objects.create(nom=f"Agence {i}", tutelle="Santé" if i else "Agriculture", categorie="EPA",
                                   email_contact=f"a{i}@epn.test")
            r = self.reponse_complete(statut, epn=e)
            r.donnees["I03"] = f"Besoin {i} : former les agents"
            r.save()
        EPN.objects.create(nom="Sans réponse", tutelle="Santé", email_contact="x@epn.test")
        Reponse.objects.create(campagne=self.campagne, epn=EPN.objects.get(nom="Sans réponse"))

    def test_pdf_genere_sans_ia_avec_constats(self):
        self.preparer()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("api:rapport_annuel"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertIn("Rapport_annuel_EPN_2024.pdf", resp["Content-Disposition"])
        self.assertTrue(Journal.objects.filter(action="rapport_annuel").exists())
        d = rapport.collecter(self.campagne, self.campagne.reponses.select_related("epn"))
        self.assertEqual((d["participation"]["invites"], d["participation"]["soumis"]), (4, 3))
        self.assertEqual(len(d["reponses"]), 2)  # base par défaut : réponses validées
        self.assertIn("taux de réponse de 75 %", rapport.constats(d)[0])

    def test_rapport_limite_au_perimetre_du_superviseur(self):
        self.preparer()
        sup = User.objects.create_user("sup", password="x", is_staff=True)
        ProfilEquipe.objects.create(utilisateur=sup, role="superviseur", tutelles="Santé")
        self.client.force_login(sup)
        self.assertEqual(self.client.get(reverse("api:rapport_annuel")).status_code, 200)
        from enquete.api import _donnees_rapport
        requete = SimpleNamespace(user=sup, GET={})
        d = _donnees_rapport(requete, self.campagne)
        self.assertEqual({r.epn.tutelle for r in d["toutes"]}, {"Santé"})

    def test_contexte_sans_coordonnees_des_repondants(self):
        self.preparer()
        d = rapport.collecter(self.campagne, self.campagne.reponses.select_related("epn"), "envoyees")
        texte = assistant.contexte(d, nominatif=True)
        self.assertIn("Agence 1", texte)
        self.assertIn("former les agents", texte)
        for interdit in ("Bamba", "Karim", "k@epn.test", "a1@epn.test"):
            self.assertNotIn(interdit, texte)
        agrege = assistant.contexte(d, nominatif=False)
        self.assertNotIn("Agence 1", agrege)
        self.assertNotIn("former les agents", agrege)

    def test_envoi_automatique_apres_cloture_une_seule_fois(self):
        from enquete.management.commands.taches import rapports_automatiques

        self.preparer()
        self.admin.email = "admin@institution.test"
        self.admin.save()
        self.campagne.date_cloture = timezone.localdate() - timedelta(days=20)
        self.campagne.save()
        with override_settings(RAPPORT_AUTO_JOURS="15"):
            self.assertEqual(rapports_automatiques(), 1)
            self.assertEqual(rapports_automatiques(), 0)
        self.assertEqual(mail.outbox[-1].to, ["admin@institution.test"])
        self.assertEqual(mail.outbox[-1].attachments[0][0], "Rapport_annuel_EPN_2024.pdf")
        with override_settings(RAPPORT_AUTO_JOURS=""):
            self.assertEqual(rapports_automatiques(), 0)

    def test_assistant_non_configure(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.client.get(reverse("api:assistant_ia")).json()["disponible"])
        resp = self.post("api:assistant_ia", donnees={"question": "Bonjour"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("ANTHROPIC_API_KEY", resp.json()["erreur"])


@override_settings(**REGLAGES, ANTHROPIC_API_KEY="cle-de-test")
class AssistantIATests(Outils):
    def setUp(self):
        super().setUp()
        RapportAnnuelTests.preparer(self)

    def test_question_avec_historique_et_journal(self):
        flux, patch = simuler(reponse_modele("Le taux de réponse est de **75 %**."))
        self.client.force_login(self.admin)
        with patch:
            resp = self.post("api:assistant_ia", donnees={"question": "Quel est le taux de réponse ?", "historique": [
                {"role": "assistant", "contenu": "ignoré : la conversation commence par l'utilisateur"},
                {"role": "user", "contenu": "Bonjour"}, {"role": "assistant", "contenu": "Bonjour !"}]})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("75 %", resp.json()["reponse"])
        appel = flux.appels[0]
        self.assertEqual(appel["model"], "claude-opus-5-5")
        self.assertEqual(appel["thinking"], {"type": "adaptive"})
        self.assertEqual(appel["fallbacks"], "default")
        self.assertEqual([m["role"] for m in appel["messages"]], ["user", "assistant", "user"])
        self.assertIn("<donnees>", appel["system"][1]["text"])
        self.assertNotIn("k@epn.test", json.dumps(appel, default=str))
        self.assertTrue(Journal.objects.filter(action="assistant_ia").exists())

    def test_refus_du_modele_et_quota(self):
        _, patch = simuler(reponse_modele("", stop="refusal"))
        self.client.force_login(self.admin)
        with patch:
            self.assertEqual(self.post("api:assistant_ia", donnees={"question": "?"}).status_code, 422)
        with override_settings(ASSISTANT_IA_QUESTIONS_PAR_HEURE=1):
            Journal.objects.create(auteur="admin", action="assistant_ia")
            self.assertEqual(self.post("api:assistant_ia", donnees={"question": "?"}).status_code, 429)

    def test_synthese_enregistree_puis_reprise_dans_le_rapport(self):
        flux, patch = simuler(reponse_modele(json.dumps(SYNTHESE)))
        self.client.force_login(self.admin)
        with patch:
            resp = self.post("api:synthese_ia", donnees={"base": "validees"})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["synthese"]["contenu"]["besoins"], ["Formation du personnel"])
        self.assertEqual(flux.appels[0]["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(SyntheseIA.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("api:synthese_ia")).json()["synthese"]["contenu"]["synthese"],
                         SYNTHESE["synthese"])
        pdf = self.client.get(reverse("api:rapport_annuel"))
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertTrue(Journal.objects.get(action="rapport_annuel").detail["ia"])

    def test_lecteur_sans_synthese_ni_detail(self):
        lecteur = User.objects.create_user("lecteur", password="x", is_staff=True)
        ProfilEquipe.objects.create(utilisateur=lecteur, role="lecteur")
        self.client.force_login(lecteur)
        self.assertEqual(self.post("api:synthese_ia", donnees={}).status_code, 403)
        flux, patch = simuler(reponse_modele("Réponse agrégée."))
        with patch:
            self.assertEqual(self.post("api:assistant_ia", donnees={"question": "Résumé ?"}).status_code, 200)
        self.assertNotIn("Agence 1", flux.appels[0]["system"][1]["text"])
