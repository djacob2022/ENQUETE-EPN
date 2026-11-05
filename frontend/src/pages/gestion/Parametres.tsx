import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImageUp, Mail, Save, Server, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { Bouton, Carte, Champ, EnTeteCarte, Squelette, useToast, ZoneTexte } from "@/ui";
import { EnTetePage } from "./Gestion";

interface Parametres {
  pays: string; devise: string; ministere: string; institution: string; monnaie: string; email_contact: string;
  texte_invitation: string; texte_relance: string; signature: string; logo: string | null;
  smtp: { hote: string; port: number; expediteur: string; tls: boolean };
  defauts: { pays: string; devise: string; ministere: string; institution: string };
}
type Texte = Exclude<keyof Parametres, "logo" | "smtp" | "defauts">;

/** Paramétrage (F-48) : identité de l'institution, logo, textes des e-mails. */
export default function Parametres() {
  const client = useQueryClient();
  const toast = useToast();
  const fichier = useRef<HTMLInputElement>(null);
  const q = useQuery({ queryKey: ["parametres"], queryFn: () => api.get<Parametres>("/api/gestion/parametres/") });
  const [p, setP] = useState<Parametres | null>(null);
  useEffect(() => { if (q.data) setP(q.data); }, [q.data]);

  const envoyer = useMutation({
    mutationFn: (corps: FormData | Partial<Parametres> & { supprimer_logo?: boolean }) => api.post<Parametres>("/api/gestion/parametres/", corps),
    onSuccess: (d) => {
      client.setQueryData(["parametres"], d);
      client.invalidateQueries({ queryKey: ["config"] });
      toast("succes", "Paramètres enregistrés.");
    },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  if (!p) return <Squelette className="h-96 rounded-2xl" />;
  const maj = (c: Texte, v: string) => setP((x) => x && { ...x, [c]: v });
  const champ = (c: Texte, libelle: string, aide?: string) => (
    <Champ libelle={libelle} value={p[c]} onChange={(e) => maj(c, e.target.value)} aide={aide}
      placeholder={(p.defauts as Record<string, string>)[c] ?? ""} />
  );
  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    const { logo, smtp, defauts, ...textes } = p;
    envoyer.mutate(textes);
  };
  const deposerLogo = (f: File) => { const d = new FormData(); d.append("logo", f); envoyer.mutate(d); };

  return (
    <form onSubmit={soumettre}>
      <EnTetePage titre="Paramètres" sous="Identité affichée sur toutes les pages et dans les e-mails envoyés aux établissements."
        actions={<Bouton type="submit" variante="primaire" icone={<Save className="h-4 w-4" />} chargement={envoyer.isPending}>Enregistrer</Bouton>} />
      <div className="grid gap-6 xl:grid-cols-2">
        <Carte>
          <EnTeteCarte titre="Institution" sous="Champ vide : la valeur du fichier .env (en grisé) s'applique." />
          <div className="space-y-4 p-5">
            {champ("pays", "Pays (en-tête officiel)")}
            {champ("devise", "Devise nationale")}
            {champ("ministere", "Ministère commanditaire")}
            {champ("institution", "Institution (signature des e-mails)")}
            <div className="grid gap-4 sm:grid-cols-2">
              {champ("monnaie", "Monnaie des montants", "Ex. FCFA. Affichée à côté des montants.")}
              {champ("email_contact", "E-mail d'assistance", "Indiqué aux établissements en cas de difficulté.")}
            </div>
          </div>
        </Carte>
        <Carte>
          <EnTeteCarte titre="Logo" sous="PNG ou JPG, 1 Mo au plus. Remplace l'emblème provisoire." />
          <div className="flex flex-wrap items-center gap-5 p-5">
            <div className="grid h-24 w-24 place-items-center rounded-2xl border border-trait bg-relief/50">
              {p.logo ? <img src={`${p.logo}?v=${Date.now()}`} alt="Logo actuel" className="max-h-20 max-w-20 object-contain" /> : <ImageUp className="h-6 w-6 text-discret" />}
            </div>
            <input ref={fichier} type="file" accept=".png,.jpg,.jpeg" className="sr-only" tabIndex={-1} aria-hidden
              onChange={(e) => { const f = e.target.files?.[0]; if (f) deposerLogo(f); e.target.value = ""; }} />
            <div className="flex gap-2">
              <Bouton type="button" icone={<ImageUp className="h-4 w-4" />} onClick={() => fichier.current?.click()}>{p.logo ? "Remplacer" : "Choisir un logo"}</Bouton>
              {p.logo && <Bouton type="button" variante="fantome" icone={<Trash2 className="h-4 w-4" />} onClick={() => envoyer.mutate({ supprimer_logo: true })}>Retirer</Bouton>}
            </div>
          </div>
          <EnTeteCarte titre="Serveur d'envoi" sous="Réglé dans le fichier .env du serveur (le mot de passe n'est jamais stocké en base)." />
          <dl className="grid grid-cols-2 gap-3 p-5 text-sm">
            <div><dt className="flex items-center gap-1.5 text-xs text-discret"><Server className="h-3.5 w-3.5" /> Serveur SMTP</dt><dd className="font-medium">{p.smtp.hote}:{p.smtp.port}{p.smtp.tls ? " · TLS" : ""}</dd></div>
            <div><dt className="flex items-center gap-1.5 text-xs text-discret"><Mail className="h-3.5 w-3.5" /> Expéditeur</dt><dd className="font-medium">{p.smtp.expediteur}</dd></div>
          </dl>
        </Carte>
        <Carte className="xl:col-span-2">
          <EnTeteCarte titre="Modèles d'e-mails" sous="Paragraphes ajoutés aux e-mails automatiques. Le lien personnel et la date limite sont toujours insérés." />
          <div className="grid gap-4 p-5 lg:grid-cols-3">
            <ZoneTexte libelle="Message d'invitation" value={p.texte_invitation} onChange={(e) => maj("texte_invitation", e.target.value)} placeholder="Ex. Sur instruction du Ministre…" />
            <ZoneTexte libelle="Message de relance" value={p.texte_relance} onChange={(e) => maj("texte_relance", e.target.value)} />
            <ZoneTexte libelle="Signature" value={p.signature} onChange={(e) => maj("signature", e.target.value)} placeholder="Le Directeur général…" />
          </div>
        </Carte>
      </div>
    </form>
  );
}
