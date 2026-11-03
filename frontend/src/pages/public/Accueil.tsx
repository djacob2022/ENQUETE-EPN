import { motion } from "framer-motion";
import { ArrowRight, FileCheck2, Mail, ShieldCheck, Timer } from "lucide-react";
import { Link } from "react-router-dom";
import BoutonTheme from "@/composants/BoutonTheme";
import { Logo } from "@/ui";

const etapes = [
  { icone: Mail, titre: "Recevez votre lien", texte: "Le point focal de chaque établissement reçoit un lien personnel par e-mail." },
  { icone: Timer, titre: "Répondez à votre rythme", texte: "Les réponses sont enregistrées automatiquement : reprenez quand vous voulez." },
  { icone: FileCheck2, titre: "Joignez vos pièces", texte: "États financiers, rapport d'activités : déposez-les directement en ligne." },
  { icone: ShieldCheck, titre: "Envoyez en toute sécurité", texte: "Vous relisez, vous certifiez, vous recevez un accusé de réception." },
];

export default function Accueil() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="grille-fond pointer-events-none absolute inset-x-0 top-0 h-[620px]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-marque/10 blur-3xl" />

      <header className="relative mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <div className="flex items-center gap-2">
          <BoutonTheme />
          <Link to="/connexion" className="rounded-[10px] px-3 py-2 text-sm font-medium text-discret transition hover:bg-relief hover:text-encre">
            Espace administration
          </Link>
        </div>
      </header>

      <main className="relative mx-auto max-w-6xl px-6 pb-24 pt-16 sm:pt-24">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
          className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-trait bg-surface/80 px-3 py-1 text-xs font-medium text-discret shadow-sm backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-succes" /> Campagne d'enquête annuelle
          </span>
          <h1 className="titre-display mt-6 text-5xl leading-[1.05] sm:text-7xl">
            Les données des établissements publics,<span className="italic text-marque"> réunies.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg text-discret">
            Une plateforme unique pour recueillir, contrôler et analyser les informations de chaque Établissement Public National.
          </p>
          <div className="mx-auto mt-10 max-w-md rounded-2xl border border-trait bg-surface/90 p-5 text-left shadow-carte backdrop-blur">
            <p className="text-sm font-medium">Vous êtes le point focal d'un établissement ?</p>
            <p className="mt-1 text-sm text-discret">
              Ouvrez le lien personnel reçu par e-mail : il donne accès directement au questionnaire de votre établissement.
              Vous ne le retrouvez pas ? Contactez l'administration de tutelle.
            </p>
          </div>
        </motion.div>

        <div className="mt-24 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {etapes.map((e, i) => (
            <motion.div key={e.titre} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.08 }}
              className="rounded-2xl border border-trait bg-surface p-6 shadow-carte">
              <div className="flex items-center justify-between">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-marque-doux text-marque"><e.icone className="h-5 w-5" /></span>
                <span className="font-mono text-xs text-discret">0{i + 1}</span>
              </div>
              <h2 className="mt-5 font-semibold tracking-tight">{e.titre}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-discret">{e.texte}</p>
            </motion.div>
          ))}
        </div>

        <div className="mt-16 flex justify-center">
          <Link to="/connexion" className="group inline-flex items-center gap-2 text-sm font-medium text-marque">
            Accéder à l'espace administration <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </Link>
        </div>
      </main>
    </div>
  );
}
