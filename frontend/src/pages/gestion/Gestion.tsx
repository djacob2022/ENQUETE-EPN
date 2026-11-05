import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3, Bell, Building2, CalendarRange, CircleHelp, ClipboardList, CornerDownLeft, History, Inbox, LayoutDashboard, Link2,
  LogOut, Menu, Search, Settings, UsersRound, X,
} from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import BoutonTheme from "@/composants/BoutonTheme";
import { api, avecParams, ErreurApi } from "@/lib/api";
import { ilYa, initiales } from "@/lib/format";
import { Campagne, Moi, Notification, Options, Permission, ReponseResume } from "@/lib/types";
import { Avatar, Bouton, cx, Kbd, Logo, Squelette } from "@/ui";
import Campagnes from "./Campagnes";
import Comptes from "./Comptes";
import Journal from "./Journal";
import Parametres from "./Parametres";
import Liens from "./Liens";
import QuestionnaireApercu from "./QuestionnaireApercu";
import Repertoire from "./Repertoire";
import Reponses from "./Reponses";
import Statistiques from "./Statistiques";
import TableauDeBord from "./TableauDeBord";

interface ContexteGestion {
  moi: Moi;
  options: Options;
  campagne: Campagne | null;
  choisirCampagne: (id: number) => void;
}
const Ctx = createContext<ContexteGestion | null>(null);
export const useGestion = () => useContext(Ctx)!;

type Lien = { to: string; libelle: string; icone: typeof Inbox; fin?: boolean; droit?: Permission; section?: string };
const NAVIGATION: Lien[] = [
  { to: "/gestion", libelle: "Tableau de bord", icone: LayoutDashboard, fin: true },
  { to: "/gestion/reponses", libelle: "Réponses", icone: Inbox, droit: "voir_nominatif" },
  { to: "/gestion/liens", libelle: "Liens et invitations", icone: Link2, droit: "gerer_liens" },
  { to: "/gestion/statistiques", libelle: "Statistiques", icone: BarChart3 },
  { to: "/gestion/epn", libelle: "Répertoire des EPN", icone: Building2, droit: "voir_nominatif" },
  { to: "/gestion/campagnes", libelle: "Campagnes", icone: CalendarRange, section: "Paramétrage" },
  { to: "/gestion/questionnaire", libelle: "Questionnaire", icone: ClipboardList },
  { to: "/gestion/comptes", libelle: "Comptes et rôles", icone: UsersRound, droit: "gerer_comptes", section: "Administration" },
  { to: "/gestion/journal", libelle: "Journal d'audit", icone: History, droit: "voir_journal" },
  { to: "/gestion/parametres", libelle: "Paramètres", icone: Settings, droit: "parametrer" },
];
const navigationDe = (moi: Moi) => NAVIGATION.filter((n) => !n.droit || moi.permissions.includes(n.droit));
export const peut = (moi: Moi, droit: Permission) => moi.permissions.includes(droit);

export default function Gestion() {
  const { pathname } = useLocation();
  const moi = useQuery({ queryKey: ["moi"], queryFn: () => api.get<Moi>("/api/auth/moi/"), retry: false, staleTime: 60_000 });
  const options = useQuery({ queryKey: ["options"], queryFn: () => api.get<Options>("/api/gestion/options/"), enabled: !!moi.data });
  const [campagneId, setCampagneId] = useState<number | null>(() => Number(localStorage.getItem("campagne")) || null);

  const campagne = useMemo(() => {
    const liste = options.data?.campagnes ?? [];
    return liste.find((c) => c.id === campagneId) ?? options.data?.courante ?? liste[0] ?? null;
  }, [options.data, campagneId]);

  if (moi.error) {
    return (moi.error as ErreurApi).statut === 401 || (moi.error as ErreurApi).statut === 403
      ? <Navigate to="/connexion" replace state={{ depuis: pathname }} />
      : <div className="p-10 text-danger">{(moi.error as Error).message}</div>;
  }
  if (!moi.data || !options.data) {
    return (
      <div className="flex min-h-screen">
        <div className="hidden w-64 border-r border-trait bg-surface p-5 lg:block"><Squelette className="h-9 w-40" /></div>
        <div className="flex-1 space-y-6 p-10"><Squelette className="h-10 w-72" /><div className="grid grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <Squelette key={i} className="h-32" />)}</div><Squelette className="h-80" /></div>
      </div>
    );
  }

  const valeur: ContexteGestion = {
    moi: moi.data, options: options.data, campagne,
    choisirCampagne: (id) => { setCampagneId(id); localStorage.setItem("campagne", String(id)); },
  };

  return (
    <Ctx.Provider value={valeur}>
      <Coque>
        <Routes>
          <Route index element={<TableauDeBord />} />
          <Route path="reponses" element={<Reponses />} />
          <Route path="liens" element={<Liens />} />
          <Route path="statistiques" element={<Statistiques />} />
          <Route path="epn" element={<Repertoire />} />
          <Route path="campagnes" element={<Campagnes />} />
          <Route path="questionnaire" element={<QuestionnaireApercu />} />
          <Route path="comptes" element={<Comptes />} />
          <Route path="journal" element={<Journal />} />
          <Route path="parametres" element={<Parametres />} />
          <Route path="*" element={<Navigate to="/gestion" replace />} />
        </Routes>
      </Coque>
    </Ctx.Provider>
  );
}

function Coque({ children }: { children: React.ReactNode }) {
  const { moi, options, campagne, choisirCampagne } = useGestion();
  const client = useQueryClient();
  const naviguer = useNavigate();
  const { pathname } = useLocation();
  const [menuMobile, setMenuMobile] = useState(false);
  const [palette, setPalette] = useState(false);

  useEffect(() => setMenuMobile(false), [pathname]);
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, []);

  async function deconnecter() {
    await api.post("/api/auth/deconnexion/").catch(() => {});
    client.clear();
    naviguer("/connexion");
  }

  const menu = (
    <div className="flex h-full flex-col">
      <div className="tricolore h-1" aria-hidden />
      <div className="px-5 pb-4 pt-5"><Logo /></div>
      <div className="px-3">
        <label className="mb-1.5 block px-2 text-[11px] font-medium uppercase tracking-wider text-discret" htmlFor="campagne">Campagne</label>
        <select id="campagne" value={campagne?.id ?? ""} onChange={(e) => choisirCampagne(Number(e.target.value))}
          className="h-10 w-full cursor-pointer rounded-[10px] border border-trait bg-relief/60 px-3 text-sm font-medium focus:border-marque focus:outline-none">
          {options.campagnes.map((c) => <option key={c.id} value={c.id}>{c.nom}{c.active ? " · active" : ""}</option>)}
        </select>
        {moi.perimetre && (
          <p className="mt-2 rounded-lg bg-accent-doux px-3 py-2 text-xs text-accent-fonce">
            <strong className="block font-semibold">Votre périmètre</strong>{moi.perimetre.join(", ")}
          </p>
        )}
      </div>
      <button onClick={() => setPalette(true)}
        className="mx-3 mt-3 flex h-10 items-center gap-2 rounded-[10px] border border-trait px-3 text-sm text-discret transition hover:bg-relief">
        <Search className="h-4 w-4" /> <span className="flex-1 text-left">Rechercher…</span> <Kbd>Ctrl K</Kbd>
      </button>
      <nav className="defilement-fin mt-5 flex-1 space-y-0.5 overflow-y-auto px-3" aria-label="Navigation principale">
        {navigationDe(moi).map((n) => (<div key={n.to}>
          {n.section && <p className="mb-1 mt-4 px-3 text-[11px] font-medium uppercase tracking-wider text-discret">{n.section}</p>}
          <NavLink to={n.to} end={n.fin}
            className={({ isActive }) => cx("group relative flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm transition",
              isActive ? "bg-marque-doux font-semibold text-marque" : "text-discret hover:bg-relief hover:text-encre")}>
            {({ isActive }) => (<>
              {isActive && <motion.span layoutId="nav-actif" className="absolute inset-y-2 left-0 w-[3px] rounded-full bg-marque" />}
              <n.icone className="h-[18px] w-[18px]" />{n.libelle}
            </>)}
          </NavLink>
        </div>))}
        <a href="/aide" target="_blank" rel="noopener" className="mt-3 flex h-10 items-center gap-3 rounded-[10px] px-3 text-sm text-discret hover:bg-relief hover:text-encre">
          <CircleHelp className="h-[18px] w-[18px]" />Aide et guide
        </a>
      </nav>
      <div className="m-3 rounded-xl border border-trait p-3">
        <div className="flex items-center gap-3">
          <Avatar texte={initiales(moi.nom)} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{moi.nom}</p>
            <p className="truncate text-xs text-discret" title={moi.perimetre?.join(", ")}>
              {moi.role_libelle}{moi.perimetre ? ` · ${moi.perimetre.join(", ")}` : ""}
            </p>
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between border-t border-trait pt-2">
          <Cloche />
          <BoutonTheme />
          <Bouton variante="fantome" taille="sm" onClick={deconnecter} aria-label="Se déconnecter"><LogOut className="h-4 w-4" /></Bouton>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-trait bg-surface lg:block">{menu}</aside>
      <AnimatePresence>
        {menuMobile && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div className="absolute inset-0 bg-black/30" onClick={() => setMenuMobile(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.aside className="absolute inset-y-0 left-0 w-72 bg-surface shadow-flottant" initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }}>{menu}</motion.aside>
          </div>
        )}
      </AnimatePresence>
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-trait bg-surface/85 px-4 backdrop-blur lg:hidden">
        <Bouton variante="fantome" taille="sm" onClick={() => setMenuMobile(true)} aria-label="Menu"><Menu className="h-5 w-5" /></Bouton>
        <Logo compact />
        <span className="truncate text-sm font-medium">{campagne?.nom}</span>
      </header>
      <main className="mx-auto max-w-[1400px] px-4 py-8 sm:px-8 lg:py-10">{children}</main>
      <Palette ouverte={palette} fermer={() => setPalette(false)} />
    </div>
  );
}

/* ---------- Palette de commandes : pages et EPN ---------- */

function Palette({ ouverte, fermer }: { ouverte: boolean; fermer: () => void }) {
  const { campagne, moi: useGestionMoi } = useGestion();
  const naviguer = useNavigate();
  const [q, setQ] = useState("");
  const [index, setIndex] = useState(0);
  const reponses = useQuery({
    queryKey: ["reponses", campagne?.id, {}],
    queryFn: () => api.get<{ reponses: ReponseResume[] }>(avecParams("/api/gestion/reponses/", { campagne: campagne?.id })),
    enabled: ouverte && !!campagne && peut(useGestionMoi, "voir_nominatif"),
  });

  const resultats = useMemo(() => {
    const t = q.trim().toLowerCase();
    const pages = navigationDe(useGestionMoi).filter((n) => !t || n.libelle.toLowerCase().includes(t))
      .map((n) => ({ cle: n.to, titre: n.libelle, sous: "Page", icone: n.icone, aller: () => naviguer(n.to) }));
    const epn = (reponses.data?.reponses ?? []).filter((r) => t && (r.epn.nom.toLowerCase().includes(t) || r.epn.sigle.toLowerCase().includes(t)))
      .slice(0, 8).map((r) => ({ cle: `r${r.id}`, titre: r.epn.nom, sous: `${r.epn.tutelle} · ${r.statut_libelle}`, icone: Building2,
        aller: () => naviguer(`/gestion/reponses?ouvrir=${r.id}`) }));
    return [...epn, ...pages];
  }, [q, reponses.data, naviguer, useGestionMoi]);

  useEffect(() => { setIndex(0); }, [q]);
  useEffect(() => { if (!ouverte) setQ(""); }, [ouverte]);

  const choisir = (i: number) => { resultats[i]?.aller(); fermer(); };

  return (
    <AnimatePresence>
      {ouverte && (
        <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Recherche">
          <motion.div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={fermer} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div initial={{ opacity: 0, scale: 0.97, y: -8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }} transition={{ duration: 0.15 }}
            className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-trait bg-surface shadow-flottant">
            <div className="flex items-center gap-3 border-b border-trait px-4">
              <Search className="h-4 w-4 text-discret" />
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un EPN ou une page…"
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") { e.preventDefault(); setIndex((i) => Math.min(i + 1, resultats.length - 1)); }
                  if (e.key === "ArrowUp") { e.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
                  if (e.key === "Enter") choisir(index);
                  if (e.key === "Escape") fermer();
                }}
                className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-discret/70" />
              <Bouton variante="fantome" taille="sm" onClick={fermer} aria-label="Fermer"><X className="h-4 w-4" /></Bouton>
            </div>
            <ul className="defilement-fin max-h-[50vh] overflow-y-auto p-2">
              {resultats.length === 0 && <li className="px-3 py-8 text-center text-sm text-discret">Aucun résultat.</li>}
              {resultats.map((r, i) => (
                <li key={r.cle}>
                  <button onMouseEnter={() => setIndex(i)} onClick={() => choisir(i)}
                    className={cx("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm", i === index ? "bg-relief" : "")}>
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-trait bg-surface text-discret"><r.icone className="h-4 w-4" /></span>
                    <span className="min-w-0 flex-1"><span className="block truncate font-medium">{r.titre}</span><span className="block truncate text-xs text-discret">{r.sous}</span></span>
                    {i === index && <CornerDownLeft className="h-4 w-4 text-discret" />}
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

/* ---------- Notifications (F-47) ---------- */

function Cloche() {
  const { moi } = useGestion();
  const naviguer = useNavigate();
  const [ouvert, setOuvert] = useState(false);
  const cle = `notifications-vues-${moi.identifiant}`;
  const [vu, setVu] = useState(() => { try { return localStorage.getItem(cle) ?? ""; } catch { return ""; } });
  const q = useQuery({ queryKey: ["notifications"], queryFn: () => api.get<{ notifications: Notification[] }>("/api/gestion/notifications/"),
    refetchInterval: 60_000 });
  const liste = q.data?.notifications ?? [];
  const nouvelles = liste.filter((n) => n.date > vu).length;
  function basculer() {
    setOuvert((o) => !o);
    if (liste[0]) { setVu(liste[0].date); try { localStorage.setItem(cle, liste[0].date); } catch { /* stockage indisponible */ } }
  }
  return (
    <div className="relative">
      <Bouton variante="fantome" taille="sm" onClick={basculer} aria-label={`Notifications${nouvelles ? ` (${nouvelles} nouvelles)` : ""}`} aria-expanded={ouvert}>
        <Bell className="h-4 w-4" />
        {nouvelles > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-danger" />}
      </Bouton>
      <AnimatePresence>
        {ouvert && (<>
          <div className="fixed inset-0 z-40" onClick={() => setOuvert(false)} />
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="absolute bottom-11 left-0 z-50 w-80 overflow-hidden rounded-2xl border border-trait bg-surface shadow-flottant">
            <p className="border-b border-trait px-4 py-3 text-sm font-semibold">Activité récente</p>
            <ul className="defilement-fin max-h-80 divide-y divide-trait overflow-y-auto">
              {liste.length === 0 && <li className="px-4 py-6 text-center text-sm text-discret">Rien de nouveau.</li>}
              {liste.map((n) => (
                <li key={n.id}>
                  <button className="w-full px-4 py-3 text-left text-sm hover:bg-relief" disabled={!n.reponse || !peut(moi, "voir_nominatif")}
                    onClick={() => { setOuvert(false); naviguer(`/gestion/reponses?ouvrir=${n.reponse}`); }}>
                    <span className="block font-medium">{n.libelle}</span>
                    <span className="block truncate text-discret">{n.objet}</span>
                    <span className="text-xs text-discret">{ilYa(n.date)} · {n.auteur}</span>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        </>)}
      </AnimatePresence>
    </div>
  );
}

/* ---------- Éléments partagés par les pages ---------- */

export function EnTetePage({ titre, sous, actions }: { titre: string; sous?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="titre-display text-4xl sm:text-[42px]">{titre}</h1>
        {sous && <p className="mt-1.5 text-[15px] text-discret">{sous}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SansCampagne() {
  const naviguer = useNavigate();
  return (
    <div className="rounded-2xl border border-dashed border-trait p-12 text-center">
      <p className="font-medium">Aucune campagne pour l'instant</p>
      <p className="mt-1 text-sm text-discret">Créez une campagne pour inviter les établissements.</p>
      <Bouton variante="primaire" className="mt-4" onClick={() => naviguer("/gestion/campagnes")}>Créer une campagne</Bouton>
    </div>
  );
}
