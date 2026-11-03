import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, BarChart3, FileSpreadsheet, MailCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import BoutonTheme from "@/composants/BoutonTheme";
import { api, ErreurApi } from "@/lib/api";
import { Moi } from "@/lib/types";
import { Bouton, Champ, Logo } from "@/ui";

export default function Connexion() {
  const naviguer = useNavigate();
  const { state } = useLocation() as { state?: { depuis?: string } };
  const client = useQueryClient();
  const [identifiant, setIdentifiant] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string>();
  const [envoi, setEnvoi] = useState(false);

  async function connecter(e: FormEvent) {
    e.preventDefault();
    setEnvoi(true);
    setErreur(undefined);
    try {
      const moi = await api.post<Moi>("/api/auth/connexion/", { identifiant, mot_de_passe: motDePasse });
      client.setQueryData(["moi"], moi);
      naviguer(state?.depuis ?? "/gestion", { replace: true });
    } catch (err) {
      setErreur((err as ErreurApi).message);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-[#0b1b33] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -left-40 top-20 h-[480px] w-[480px] rounded-full bg-[#2563eb]/35 blur-[110px]" />
        <div className="pointer-events-none absolute -bottom-40 right-0 h-[420px] w-[420px] rounded-full bg-[#10b981]/20 blur-[110px]" />
        <div className="pointer-events-none absolute inset-0 opacity-[.07]" style={{ backgroundImage: "radial-gradient(white 1px, transparent 1px)", backgroundSize: "22px 22px" }} />
        <div className="relative"><Logo clair /></div>
        <div className="relative max-w-lg">
          <h1 className="titre-display text-6xl leading-[1.02]">Pilotez l'enquête,<br /><span className="italic text-[#93c5fd]">sans tableur.</span></h1>
          <p className="mt-6 text-lg text-white/70">Suivi en temps réel des réponses des établissements, relances, exports et statistiques.</p>
          <div className="mt-10 space-y-3">
            {[{ i: BarChart3, t: "Tableau de bord et statistiques en direct" }, { i: MailCheck, t: "Liens personnels et relances automatiques" },
              { i: FileSpreadsheet, t: "Exports Excel prêts à analyser" }].map(({ i: I, t }, n) => (
              <motion.div key={t} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + n * 0.1 }}
                className="flex items-center gap-3 text-white/85">
                <span className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5"><I className="h-4 w-4" /></span>{t}
              </motion.div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-white/40">Accès réservé aux agents habilités · toutes les actions sont journalisées.</p>
      </section>

      <section className="relative flex flex-col px-6 py-6 sm:px-12">
        <div className="flex items-center justify-between lg:justify-end"><span className="lg:hidden"><Logo /></span><BoutonTheme /></div>
        <div className="flex flex-1 items-center justify-center">
          <motion.form initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} onSubmit={connecter} className="w-full max-w-sm space-y-5">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">Espace administration</h2>
              <p className="mt-1.5 text-sm text-discret">Les établissements n'ont pas de compte : ils répondent avec le lien reçu par e-mail.</p>
            </div>
            {erreur && <div role="alert" className="rounded-xl border border-danger/30 bg-danger-doux px-4 py-3 text-sm font-medium text-danger">{erreur}</div>}
            <Champ libelle="Identifiant" autoComplete="username" autoFocus value={identifiant} onChange={(e) => setIdentifiant(e.target.value)} />
            <Champ libelle="Mot de passe" type="password" autoComplete="current-password" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />
            <Bouton type="submit" variante="primaire" taille="lg" className="w-full" chargement={envoi} disabled={!identifiant || !motDePasse}>
              Se connecter <ArrowRight className="h-4 w-4" />
            </Bouton>
          </motion.form>
        </div>
      </section>
    </div>
  );
}
