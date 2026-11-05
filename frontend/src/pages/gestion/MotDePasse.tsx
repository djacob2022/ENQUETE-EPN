import { motion } from "framer-motion";
import { ArrowLeft, KeyRound, MailCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BandeauOfficiel } from "@/composants/Officiel";
import { api, ErreurApi } from "@/lib/api";
import { Bouton, Carte, Champ } from "@/ui";

/** Mot de passe oublié (F-02) et choix du mot de passe à l'activation d'un compte (F-04). */
export default function MotDePasse() {
  const { uid, jeton } = useParams();
  return (
    <div className="min-h-screen">
      <BandeauOfficiel compact />
      <main className="mx-auto max-w-md px-6 py-16">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <Carte className="p-8">{uid && jeton ? <Nouveau uid={uid} jeton={jeton} /> : <Oublie />}</Carte>
          <Link to="/connexion" className="mt-6 inline-flex items-center gap-1.5 text-sm text-discret hover:text-encre"><ArrowLeft className="h-4 w-4" /> Retour à la connexion</Link>
        </motion.div>
      </main>
    </div>
  );
}

function Oublie() {
  const [email, setEmail] = useState("");
  const [envoye, setEnvoye] = useState(false);
  const [erreur, setErreur] = useState<string>();
  const [envoi, setEnvoi] = useState(false);
  async function envoyer(e: FormEvent) {
    e.preventDefault();
    setEnvoi(true);
    setErreur(undefined);
    try { await api.post("/api/auth/mot-de-passe-oublie/", { email }); setEnvoye(true); }
    catch (err) { setErreur((err as ErreurApi).message); }
    finally { setEnvoi(false); }
  }
  if (envoye) return (
    <div className="text-center">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-succes-doux text-succes"><MailCheck className="h-6 w-6" /></span>
      <h1 className="mt-4 text-xl font-semibold tracking-tight">Vérifiez votre messagerie</h1>
      <p className="mt-2 text-sm text-discret">Si un compte correspond à {email}, un lien de réinitialisation vient d'y être envoyé. Il est valable 24 heures.</p>
    </div>
  );
  return (
    <form onSubmit={envoyer} className="space-y-5" noValidate>
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mot de passe oublié</h1>
        <p className="mt-1.5 text-sm text-discret">Indiquez l'adresse e-mail de votre compte : nous vous enverrons un lien pour en choisir un nouveau.</p>
      </div>
      {erreur && <p role="alert" className="rounded-xl bg-danger-doux px-4 py-3 text-sm font-medium text-danger">{erreur}</p>}
      <Champ libelle="Adresse e-mail" type="email" autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
      <Bouton type="submit" variante="primaire" className="w-full" chargement={envoi} disabled={!email.includes("@")}>Recevoir le lien</Bouton>
    </form>
  );
}

function Nouveau({ uid, jeton }: { uid: string; jeton: string }) {
  const naviguer = useNavigate();
  const [mdp, setMdp] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreurs, setErreurs] = useState<string[]>();
  const [erreur, setErreur] = useState<string>();
  const [envoi, setEnvoi] = useState(false);
  async function envoyer(e: FormEvent) {
    e.preventDefault();
    if (mdp !== confirmation) return setErreurs(["Les deux saisies ne correspondent pas."]);
    setEnvoi(true);
    setErreurs(undefined);
    setErreur(undefined);
    try {
      await api.post("/api/auth/nouveau-mot-de-passe/", { uid, jeton, mot_de_passe: mdp });
      naviguer("/connexion", { replace: true, state: { message: "Mot de passe enregistré : connectez-vous." } });
    } catch (err) {
      const x = err as ErreurApi;
      if (x.erreurs?.mot_de_passe) setErreurs(x.erreurs.mot_de_passe); else setErreur(x.message);
    } finally { setEnvoi(false); }
  }
  return (
    <form onSubmit={envoyer} className="space-y-5" noValidate>
      <div>
        <span className="grid h-11 w-11 place-items-center rounded-2xl bg-marque-doux text-marque"><KeyRound className="h-5 w-5" /></span>
        <h1 className="mt-4 text-xl font-semibold tracking-tight">Choisissez votre mot de passe</h1>
        <p className="mt-1.5 text-sm text-discret">12 caractères au moins, avec trois types parmi : minuscules, majuscules, chiffres, symboles.</p>
      </div>
      {erreur && <p role="alert" className="rounded-xl bg-danger-doux px-4 py-3 text-sm font-medium text-danger">{erreur} <Link to="/mot-de-passe-oublie" className="underline">Nouveau lien</Link></p>}
      <Champ libelle="Nouveau mot de passe" type="password" autoComplete="new-password" autoFocus value={mdp} onChange={(e) => setMdp(e.target.value)} erreurs={erreurs} />
      <Champ libelle="Confirmez le mot de passe" type="password" autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />
      <Bouton type="submit" variante="primaire" className="w-full" chargement={envoi} disabled={mdp.length < 12 || !confirmation}>Enregistrer le mot de passe</Bouton>
    </form>
  );
}
