import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Download, ExternalLink, Link2, MailCheck, Search, Send, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { api, avecParams, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { ReponseResume } from "@/lib/types";
import { BadgeStatut, Bouton, Carte, cx, Dialogue, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, SansCampagne, useGestion } from "./Gestion";
import { Kpi } from "./TableauDeBord";

export default function Liens() {
  const { campagne } = useGestion();
  const client = useQueryClient();
  const toast = useToast();
  const [recherche, setRecherche] = useState("");
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [confirmer, setConfirmer] = useState(false);
  const [copie, setCopie] = useState<number | null>(null);
  const url = avecParams("/api/gestion/liens/", { campagne: campagne?.id });

  const q = useQuery({
    queryKey: ["liens", campagne?.id],
    queryFn: () => api.get<{ liens: ReponseResume[]; sans_lien: number; lien_public: string }>(url), enabled: !!campagne,
  });
  const rafraichir = () => ["liens", "reponses", "tableau"].forEach((k) => client.invalidateQueries({ queryKey: [k] }));
  const generer = useMutation({
    mutationFn: () => api.post<{ crees: number }>(url),
    onSuccess: (r) => { rafraichir(); toast("succes", r.crees ? `${r.crees} lien(s) personnel(s) généré(s).` : "Tous les établissements ont déjà un lien."); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  const envoyer = useMutation({
    mutationFn: (ids: number[]) => api.post<{ envoyees: number }>(url, { envoyer: true, epn: ids }),
    onSuccess: (r) => { setConfirmer(false); setSelection(new Set()); rafraichir(); toast("succes", `${r.envoyees} invitation(s) envoyée(s) par e-mail.`); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  const liens = q.data?.liens ?? [];
  const lignes = useMemo(() => {
    const t = recherche.toLowerCase().trim();
    return liens.filter((l) => !t || l.epn.nom.toLowerCase().includes(t) || l.epn.email_contact.toLowerCase().includes(t));
  }, [liens, recherche]);
  const nonInvites = liens.filter((l) => !l.date_invitation);
  const cibles = selection.size ? nonInvites.filter((l) => selection.has(l.epn.id)) : nonInvites;

  if (!campagne) return <SansCampagne />;

  async function copier(l: ReponseResume) {
    await navigator.clipboard.writeText(l.lien);
    setCopie(l.id);
    setTimeout(() => setCopie((c) => (c === l.id ? null : c)), 1600);
  }
  const basculer = (id: number) => setSelection((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  return (
    <>
      <EnTetePage titre="Liens et invitations" sous="Un lien unique pour tous, et un lien personnel par établissement."
        actions={<>
          <a href={avecParams("/api/gestion/liens.xlsx", { campagne: campagne.id })} className="inline-flex h-11 items-center gap-2 rounded-[10px] border border-trait bg-surface px-4 text-sm font-medium shadow-sm hover:bg-relief">
            <Download className="h-4 w-4" /> Exporter (Excel)</a>
          <Bouton icone={<Sparkles className="h-4 w-4" />} chargement={generer.isPending} disabled={!q.data?.sans_lien} onClick={() => generer.mutate()}>
            Générer les liens manquants{q.data?.sans_lien ? ` (${q.data.sans_lien})` : ""}</Bouton>
          <Bouton variante="primaire" icone={<Send className="h-4 w-4" />} disabled={!cibles.length} onClick={() => setConfirmer(true)}>
            Envoyer {selection.size ? "la sélection" : "les invitations"}{cibles.length ? ` (${cibles.length})` : ""}</Bouton>
        </>} />

      {q.data && (
        <section aria-label="Lien unique" className="motif-officiel relative mb-6 overflow-hidden rounded-2xl bg-institution p-6 text-white shadow-carte">
          <div className="tricolore absolute inset-x-0 top-0 h-1" aria-hidden />
          <div className="flex flex-wrap items-center gap-6">
            <div className="min-w-[260px] flex-1">
              <p className="text-xs font-bold uppercase tracking-[.12em] text-accent">Lien unique à diffuser</p>
              <p className="mt-1 text-lg font-bold">Le même lien pour tous les établissements</p>
              <p className="mt-1 text-sm text-white/75">Chaque entité y choisit son établissement ; son lien personnel part alors à l'adresse officielle de son point focal.</p>
            </div>
            <div className="flex min-w-[300px] flex-1 items-center gap-2 rounded-lg bg-white/10 p-1.5 pl-4 ring-1 ring-white/15">
              <code className="min-w-0 flex-1 truncate font-mono text-sm">{q.data.lien_public}</code>
              <button onClick={async () => { await navigator.clipboard.writeText(q.data.lien_public); setCopie(-1); setTimeout(() => setCopie(null), 1600); }}
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-white px-3 text-sm font-semibold text-institution transition hover:bg-white/90">
                {copie === -1 ? <><Check className="h-4 w-4" /> Copié</> : <><Copy className="h-4 w-4" /> Copier</>}
              </button>
            </div>
          </div>
        </section>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Kpi icone={Link2} libelle="Liens générés" valeur={String(liens.length)} note="un par établissement actif" />
        <Kpi icone={MailCheck} libelle="Invitations envoyées" valeur={String(liens.length - nonInvites.length)} note={`${nonInvites.length} lien(s) pas encore envoyé(s)`} />
        <Kpi icone={Sparkles} libelle="Sans lien" valeur={String(q.data?.sans_lien ?? "…")} note="établissements à ajouter à la campagne" />
      </div>

      <Carte className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-trait p-4">
          <label className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-discret" />
            <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher un établissement ou un e-mail" aria-label="Rechercher"
              className="h-10 w-full rounded-[10px] border border-trait bg-surface pl-9 pr-3 text-sm focus:border-marque focus:shadow-anneau focus:outline-none" />
          </label>
          <p className="text-xs text-discret">Un lien ne donne accès qu'au questionnaire de son établissement : transmettez-le à son seul point focal.</p>
        </div>
        <div className="defilement-fin overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-relief/50 text-left text-xs uppercase tracking-wider text-discret">
              <tr><th className="w-10 py-3 pl-6" /><th className="px-4 py-3 font-medium">Établissement</th><th className="px-4 py-3 font-medium">Lien personnel</th>
                <th className="px-4 py-3 font-medium">Invitation</th><th className="px-4 py-3 pr-6 font-medium">Statut</th></tr>
            </thead>
            <tbody className="divide-y divide-trait">
              {q.isLoading && Array.from({ length: 5 }, (_, i) => <tr key={i}><td colSpan={5} className="px-6 py-3"><Squelette className="h-9" /></td></tr>)}
              {lignes.map((l) => (
                <tr key={l.id} className={cx("transition hover:bg-relief/40", selection.has(l.epn.id) && "bg-marque-doux/40")}>
                  <td className="py-3 pl-6">
                    {!l.date_invitation && <input type="checkbox" checked={selection.has(l.epn.id)} onChange={() => basculer(l.epn.id)}
                      aria-label={`Sélectionner ${l.epn.nom}`} className="h-4 w-4 accent-[rgb(var(--marque))]" />}
                  </td>
                  <td className="px-4 py-3"><p className="font-medium">{l.epn.nom}</p><p className="text-xs text-discret">{l.epn.email_contact}</p></td>
                  <td className="px-4 py-3">
                    <div className="flex max-w-[420px] items-center gap-1 rounded-[10px] border border-trait bg-relief/50 py-1 pl-3 pr-1">
                      <code className="min-w-0 flex-1 truncate font-mono text-xs text-discret" title={l.lien}>{l.lien.replace(/^https?:\/\//, "")}</code>
                      <Bouton taille="sm" variante="fantome" className="h-7 px-2" onClick={() => copier(l)} aria-label={`Copier le lien de ${l.epn.nom}`}>
                        {copie === l.id ? <><Check className="h-3.5 w-3.5 text-succes" /><span className="text-succes">Copié</span></> : <><Copy className="h-3.5 w-3.5" />Copier</>}
                      </Bouton>
                      <a href={l.lien} target="_blank" rel="noopener" className="grid h-7 w-7 place-items-center rounded-md text-discret hover:bg-surface hover:text-encre" aria-label="Ouvrir"><ExternalLink className="h-3.5 w-3.5" /></a>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-discret">{l.date_invitation ? <span className="inline-flex items-center gap-1 text-succes"><MailCheck className="h-3.5 w-3.5" />{date(l.date_invitation)}</span> : "Pas encore envoyée"}</td>
                  <td className="px-4 py-3 pr-6"><BadgeStatut statut={l.statut} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!q.isLoading && !liens.length && (
            <Vide icone={<Link2 className="h-5 w-5" />} titre="Aucun lien pour cette campagne" texte="Générez un lien unique pour chaque établissement actif du répertoire."
              action={<Bouton variante="primaire" chargement={generer.isPending} onClick={() => generer.mutate()}>Générer les liens</Bouton>} />
          )}
        </div>
      </Carte>

      <Dialogue ouvert={confirmer} fermer={() => setConfirmer(false)} titre={`Envoyer ${cibles.length} invitation${cibles.length > 1 ? "s" : ""} ?`}
        description="Chaque point focal recevra un e-mail avec le lien personnel de son établissement et la date limite.">
        <ul className="defilement-fin max-h-48 space-y-1 overflow-y-auto rounded-xl border border-trait p-2 text-sm">
          {cibles.map((c) => <li key={c.id} className="flex justify-between gap-3 rounded-lg px-2 py-1.5"><span className="truncate">{c.epn.nom}</span><span className="shrink-0 text-xs text-discret">{c.epn.email_contact}</span></li>)}
        </ul>
        <div className="mt-5 flex justify-end gap-2">
          <Bouton variante="fantome" onClick={() => setConfirmer(false)}>Annuler</Bouton>
          <Bouton variante="primaire" chargement={envoyer.isPending} onClick={() => envoyer.mutate(cibles.map((c) => c.epn.id))}><Send className="h-4 w-4" /> Envoyer</Bouton>
        </div>
      </Dialogue>
    </>
  );
}
