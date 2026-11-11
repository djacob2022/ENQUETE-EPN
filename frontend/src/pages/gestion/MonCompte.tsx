import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseBackup, Download, KeyRound, Printer, ShieldCheck, ShieldOff, Smartphone, TriangleAlert, Upload } from "lucide-react";
import { FormEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErreurApi } from "@/lib/api";
import { Badge, Bouton, Carte, Champ, cx, Dialogue, EnTeteCarte, Squelette, useToast } from "@/ui";
import { EnTetePage, useGestion } from "./Gestion";

type Etat = { active: boolean; codes_restants: number };
type Debut = { secret: string; uri: string; qr_svg: string };

/** Mon compte : double authentification (F-03) et, pour le super-administrateur, sauvegarde et restauration (F-49). */
export default function MonCompte() {
  const { moi } = useGestion();
  return (
    <>
      <EnTetePage titre="Mon compte" sous={`${moi.nom} · ${moi.role_libelle}${moi.email ? ` · ${moi.email}` : ""}`} />
      <div className="grid gap-6 xl:grid-cols-2">
        <DoubleAuthentification />
        {moi.superutilisateur && <Sauvegardes />}
      </div>
    </>
  );
}

function DoubleAuthentification() {
  const client = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["deux-facteurs"], queryFn: () => api.get<Etat>("/api/auth/deux-facteurs/") });
  const [debut, setDebut] = useState<Debut | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [desactiver, setDesactiver] = useState(false);
  const [mdp, setMdp] = useState("");
  const rafraichir = () => { client.invalidateQueries({ queryKey: ["deux-facteurs"] }); client.invalidateQueries({ queryKey: ["moi"] }); };

  const commencer = useMutation({ mutationFn: () => api.post<Debut>("/api/auth/deux-facteurs/"), onSuccess: setDebut,
    onError: (e: ErreurApi) => toast("erreur", e.message) });
  const activer = useMutation({
    mutationFn: () => api.post<Etat & { codes_secours: string[] }>("/api/auth/deux-facteurs/", { code }),
    onSuccess: (r) => { setCodes(r.codes_secours); setDebut(null); setCode(""); rafraichir(); toast("succes", "Double authentification activée."); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  const couper = useMutation({
    mutationFn: () => fetch("/api/auth/deux-facteurs/", { method: "DELETE", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] ?? "") },
      body: JSON.stringify({ mot_de_passe: mdp }) }).then(async (r) => { if (!r.ok) throw new ErreurApi(r.status, (await r.json()).erreur); }),
    onSuccess: () => { setDesactiver(false); setMdp(""); rafraichir(); toast("info", "Double authentification désactivée."); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  return (
    <Carte>
      <EnTeteCarte titre="Double authentification" sous="Un code à 6 chiffres, donné par une application de votre téléphone, s'ajoute au mot de passe."
        actions={q.data && (q.data.active ? <Badge ton="succes"><ShieldCheck className="h-3 w-3" /> Active</Badge> : <Badge ton="alerte">Désactivée</Badge>)} />
      <div className="p-5">
        {!q.data ? <Squelette className="h-24" /> : codes ? (
          <div>
            <p className="text-sm"><strong>Gardez ces codes de secours en lieu sûr</strong> (imprimés, ou dans un coffre-fort de mots de passe). Chacun permet
              une seule connexion si vous perdez votre téléphone. Ils ne seront plus affichés.</p>
            <ol className="chiffres mt-4 grid grid-cols-2 gap-2 font-mono text-[15px]">
              {codes.map((c) => <li key={c} className="rounded-lg bg-relief px-3 py-2 text-center">{c}</li>)}
            </ol>
            <div className="mt-4 flex gap-2">
              <Bouton taille="sm" icone={<Printer className="h-4 w-4" />} onClick={() => window.print()}>Imprimer</Bouton>
              <Bouton taille="sm" variante="primaire" onClick={() => setCodes(null)}>C'est noté</Bouton>
            </div>
          </div>
        ) : q.data.active ? (
          <div className="flex flex-wrap items-center gap-4">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-succes-doux text-succes"><ShieldCheck className="h-6 w-6" /></span>
            <div className="flex-1 text-sm">
              <p className="font-medium">Votre compte est protégé.</p>
              <p className="text-discret">{q.data.codes_restants} code{q.data.codes_restants > 1 ? "s" : ""} de secours restant{q.data.codes_restants > 1 ? "s" : ""}.</p>
            </div>
            <Bouton taille="sm" variante="fantome" icone={<ShieldOff className="h-4 w-4" />} onClick={() => setDesactiver(true)}>Désactiver</Bouton>
          </div>
        ) : debut ? (
          <form className="grid gap-5 sm:grid-cols-[200px_1fr]" onSubmit={(e: FormEvent) => { e.preventDefault(); activer.mutate(); }}>
            <div className="rounded-2xl border border-trait bg-white p-2 [&_svg]:h-auto [&_svg]:w-full" aria-label="QR code à scanner"
              dangerouslySetInnerHTML={{ __html: debut.qr_svg }} />
            <div className="space-y-3 text-sm">
              <ol className="list-decimal space-y-1.5 pl-5 text-discret">
                <li>Installez une application d'authentification : Google Authenticator, Microsoft Authenticator ou FreeOTP.</li>
                <li>Scannez ce QR code avec l'application.</li>
                <li>Saisissez le code à 6 chiffres qu'elle affiche.</li>
              </ol>
              <p className="text-xs text-discret">Impossible de scanner ? Clé à saisir : <span className="select-all break-all font-mono text-encre">{debut.secret}</span></p>
              <Champ libelle="Code affiché par l'application" inputMode="numeric" autoComplete="one-time-code" value={code}
                onChange={(e) => setCode(e.target.value)} placeholder="123456" />
              <Bouton type="submit" variante="primaire" chargement={activer.isPending} disabled={code.replace(/\D/g, "").length !== 6}>Activer</Bouton>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-alerte-doux text-alerte"><Smartphone className="h-6 w-6" /></span>
            <p className="flex-1 text-sm text-discret">Recommandée pour tous, indispensable pour les administrateurs : un mot de passe volé ne suffit plus pour entrer.</p>
            <Bouton variante="primaire" icone={<KeyRound className="h-4 w-4" />} chargement={commencer.isPending} onClick={() => commencer.mutate()}>Activer</Bouton>
          </div>
        )}
      </div>
      <Dialogue ouvert={desactiver} fermer={() => setDesactiver(false)} titre="Désactiver la double authentification ?"
        description="Votre compte ne sera plus protégé que par le mot de passe.">
        <form onSubmit={(e) => { e.preventDefault(); couper.mutate(); }} className="space-y-4">
          <Champ libelle="Votre mot de passe" type="password" autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Bouton type="button" variante="fantome" onClick={() => setDesactiver(false)}>Annuler</Bouton>
            <Bouton type="submit" variante="danger" chargement={couper.isPending} disabled={!mdp}>Désactiver</Bouton>
          </div>
        </form>
      </Dialogue>
    </Carte>
  );
}

function Sauvegardes() {
  const naviguer = useNavigate();
  const toast = useToast();
  const champ = useRef<HTMLInputElement>(null);
  const [fichier, setFichier] = useState<File | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const restaurer = useMutation({
    mutationFn: () => { const d = new FormData(); d.append("fichier", fichier!); d.append("confirmation", confirmation); return api.post<{ fichiers: number }>("/api/gestion/restauration/", d); },
    onSuccess: () => naviguer("/connexion", { replace: true, state: { message: "Données restaurées. Reconnectez-vous." } }),
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  return (
    <Carte>
      <EnTeteCarte titre="Sauvegarde et restauration" sous="Réservé au super-administrateur. En plus de la sauvegarde automatique quotidienne." />
      <div className="space-y-5 p-5">
        <div className="flex flex-wrap items-center gap-4">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-marque-doux text-marque"><DatabaseBackup className="h-6 w-6" /></span>
          <p className="flex-1 text-sm text-discret">Archive complète : comptes, répertoire, campagnes, réponses, journal et pièces jointes. À conserver hors du serveur.</p>
          <a href="/api/gestion/sauvegarde.zip" className="inline-flex h-11 items-center gap-2 rounded-[10px] bg-marque px-4 text-sm font-medium text-white shadow-sm hover:bg-marque-fonce dark:text-[#04140c]">
            <Download className="h-4 w-4" /> Télécharger une sauvegarde</a>
        </div>
        <div className="rounded-xl border border-danger/25 bg-danger-doux/40 p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-danger"><TriangleAlert className="h-4 w-4" /> Restaurer une sauvegarde</p>
          <p className="mt-1 text-sm text-discret">Remplace <strong>toutes</strong> les données actuelles par celles de l'archive. Tous les comptes devront se reconnecter.</p>
          <input ref={champ} type="file" accept=".zip" className="sr-only" tabIndex={-1} aria-hidden onChange={(e) => setFichier(e.target.files?.[0] ?? null)} />
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <Bouton taille="sm" icone={<Upload className="h-4 w-4" />} onClick={() => champ.current?.click()}>{fichier ? fichier.name : "Choisir l'archive .zip"}</Bouton>
            <Champ libelle="Tapez RESTAURER" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} className={cx("w-44", !fichier && "opacity-50")} disabled={!fichier} />
            <Bouton taille="sm" variante="danger" disabled={!fichier || confirmation !== "RESTAURER"} chargement={restaurer.isPending} onClick={() => restaurer.mutate()}>Restaurer</Bouton>
          </div>
        </div>
      </div>
    </Carte>
  );
}
