import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownUp, BellRing, Check, Copy, Download, ExternalLink, FileArchive, FileText, Inbox, Mail, Phone, RotateCcw, Search, Send,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, avecParams, ErreurApi } from "@/lib/api";
import { copier } from "@/lib/presse-papiers";
import { date, ilYa, taille } from "@/lib/format";
import { ReponseDetail, ReponseResume, Statut } from "@/lib/types";
import { BadgeStatut, Bouton, Carte, cx, Liste, Progression, Squelette, Tiroir, useToast, Vide } from "@/ui";
import { EnTetePage, SansCampagne, useGestion } from "./Gestion";

type Tri = "epn" | "tutelle" | "avancement" | "date";

export default function Reponses() {
  const { campagne, options } = useGestion();
  const [params, setParams] = useSearchParams();
  const [recherche, setRecherche] = useState("");
  const [tri, setTri] = useState<{ col: Tri; asc: boolean }>({ col: "epn", asc: true });
  const filtres = { statut: params.get("statut") ?? "", tutelle: params.get("tutelle") ?? "", categorie: params.get("categorie") ?? "" };
  const ouvert = Number(params.get("ouvrir")) || null;

  const q = useQuery({
    queryKey: ["reponses", campagne?.id, filtres],
    queryFn: () => api.get<{ reponses: ReponseResume[] }>(avecParams("/api/gestion/reponses/", { campagne: campagne?.id, ...filtres })),
    enabled: !!campagne,
  });

  const lignes = useMemo(() => {
    const t = recherche.trim().toLowerCase();
    const liste = (q.data?.reponses ?? []).filter((r) => !t || [r.epn.nom, r.epn.sigle, r.repondant, r.email].some((x) => x?.toLowerCase().includes(t)));
    const cle = (r: ReponseResume) => tri.col === "epn" ? r.epn.nom : tri.col === "tutelle" ? r.epn.tutelle
      : tri.col === "avancement" ? r.avancement : r.date_soumission ?? r.date_modification ?? "";
    return [...liste].sort((a, b) => (cle(a) > cle(b) ? 1 : cle(a) < cle(b) ? -1 : 0) * (tri.asc ? 1 : -1));
  }, [q.data, recherche, tri]);

  const changerFiltre = (cle: string, v: string) => {
    const p = new URLSearchParams(params);
    v ? p.set(cle, v) : p.delete(cle);
    setParams(p, { replace: true });
  };
  const ouvrir = (id: number | null) => changerFiltre("ouvrir", id ? String(id) : "");

  if (!campagne) return <SansCampagne />;
  const exporter = avecParams("/api/gestion/export.xlsx", { campagne: campagne.id, ...filtres, toutes: filtres.statut ? undefined : 1 });
  const nb = (s: Statut) => (q.data?.reponses ?? []).filter((r) => r.statut === s).length;

  const EnTeteTri = ({ col, children, className }: { col: Tri; children: React.ReactNode; className?: string }) => (
    <th className={cx("px-4 py-3 font-medium", className)}>
      <button onClick={() => setTri((t) => ({ col, asc: t.col === col ? !t.asc : col !== "avancement" && col !== "date" }))}
        className={cx("inline-flex items-center gap-1 hover:text-encre", tri.col === col && "text-encre")}>
        {children}<ArrowDownUp className={cx("h-3 w-3", tri.col !== col && "opacity-40")} />
      </button>
    </th>
  );

  return (
    <>
      <EnTetePage titre="Réponses" sous={`${q.data?.reponses.length ?? "…"} établissements invités · ${campagne.nom}`}
        actions={<a href={exporter} className="inline-flex h-11 items-center gap-2 rounded-[10px] border border-trait bg-surface px-4 text-sm font-medium shadow-sm transition hover:bg-relief">
          <Download className="h-4 w-4" /> Exporter la sélection</a>} />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {[{ v: "", l: "Tous" }, { v: "soumis", l: "Envoyés" }, { v: "en_cours", l: "En cours" }, { v: "invite", l: "Non commencés" }].map((s) => (
          <button key={s.v} onClick={() => changerFiltre("statut", s.v)}
            className={cx("inline-flex h-9 items-center gap-2 rounded-full border px-4 text-sm transition",
              filtres.statut === s.v ? "border-encre bg-encre text-fond" : "border-trait bg-surface text-discret hover:text-encre")}>
            {s.l}{s.v && q.data && !filtres.statut && <span className="chiffres text-xs opacity-70">{nb(s.v as Statut)}</span>}
          </button>
        ))}
      </div>

      <Carte className="overflow-hidden">
        <div className="flex flex-wrap items-end gap-3 border-b border-trait p-4">
          <label className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-discret" />
            <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher un EPN, un sigle, un répondant…" aria-label="Rechercher"
              className="h-10 w-full rounded-[10px] border border-trait bg-surface pl-9 pr-3 text-sm focus:border-marque focus:shadow-anneau focus:outline-none" />
          </label>
          <Liste value={filtres.tutelle} onChange={(e) => changerFiltre("tutelle", e.target.value)} aria-label="Tutelle" className="w-48">
            <option value="">Toutes les tutelles</option>{options.tutelles.map((t) => <option key={t}>{t}</option>)}
          </Liste>
          <Liste value={filtres.categorie} onChange={(e) => changerFiltre("categorie", e.target.value)} aria-label="Catégorie" className="w-44">
            <option value="">Toutes catégories</option>{options.categories.map((c) => <option key={c.valeur} value={c.valeur}>{c.libelle}</option>)}
          </Liste>
        </div>

        <div className="defilement-fin overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-relief/50 text-left text-xs uppercase tracking-wider text-discret">
              <tr>
                <EnTeteTri col="epn" className="pl-6">Établissement</EnTeteTri>
                <EnTeteTri col="tutelle">Tutelle</EnTeteTri>
                <th className="px-4 py-3 font-medium">Statut</th>
                <EnTeteTri col="avancement">Avancement</EnTeteTri>
                <th className="px-4 py-3 font-medium">Répondant</th>
                <EnTeteTri col="date" className="pr-6">Activité</EnTeteTri>
              </tr>
            </thead>
            <tbody className="divide-y divide-trait">
              {q.isLoading && Array.from({ length: 6 }, (_, i) => <tr key={i}><td colSpan={6} className="px-6 py-3"><Squelette className="h-8" /></td></tr>)}
              {lignes.map((r) => (
                <tr key={r.id} onClick={() => ouvrir(r.id)} className="cursor-pointer transition hover:bg-relief/50">
                  <td className="py-3 pl-6 pr-4">
                    <button className="text-left font-medium hover:text-marque" onClick={(e) => { e.stopPropagation(); ouvrir(r.id); }}>{r.epn.nom}</button>
                    <p className="text-xs text-discret">{[r.epn.sigle, r.epn.categorie].filter(Boolean).join(" · ")}</p>
                  </td>
                  <td className="px-4 py-3 text-discret">{r.epn.tutelle}</td>
                  <td className="px-4 py-3"><BadgeStatut statut={r.statut} /></td>
                  <td className="px-4 py-3"><div className="flex items-center gap-3"><Progression valeur={r.avancement} className="w-24" ton={r.avancement === 100 ? "succes" : "marque"} /><span className="chiffres w-10 text-xs text-discret">{r.avancement} %</span></div></td>
                  <td className="px-4 py-3">{r.repondant ? <><p>{r.repondant}</p><p className="text-xs text-discret">{r.telephone}</p></> : <span className="text-discret">—</span>}</td>
                  <td className="py-3 pl-4 pr-6 text-xs text-discret">{r.date_soumission ? `Envoyé ${ilYa(r.date_soumission)}` : r.date_modification ? `Modifié ${ilYa(r.date_modification)}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!q.isLoading && lignes.length === 0 && <Vide icone={<Inbox className="h-5 w-5" />} titre="Aucune réponse" texte="Aucun établissement ne correspond à ces critères." />}
        </div>
      </Carte>

      <Tiroir ouvert={!!ouvert} fermer={() => ouvrir(null)} titre={<span className="text-sm font-medium text-discret">Fiche de l'établissement</span>}>
        {ouvert && <DetailReponse id={ouvert} />}
      </Tiroir>
    </>
  );
}

function DetailReponse({ id }: { id: number }) {
  const client = useQueryClient();
  const toast = useToast();
  const [onglet, setOnglet] = useState<"reponses" | "pieces" | "historique">("reponses");
  const [copie, setCopie] = useState(false);
  const q = useQuery({ queryKey: ["reponse-detail", id], queryFn: () => api.get<ReponseDetail>(`/api/gestion/reponses/${id}/`) });
  const action = useMutation({
    mutationFn: (a: "relancer" | "inviter" | "rouvrir") => api.post<{ message: string; reponse: ReponseDetail }>(`/api/gestion/reponses/${id}/${a}/`),
    onSuccess: (r) => { client.setQueryData(["reponse-detail", id], r.reponse); client.invalidateQueries({ queryKey: ["reponses"] }); client.invalidateQueries({ queryKey: ["tableau"] }); toast("succes", r.message); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  const r = q.data;
  if (!r) return <div className="space-y-4 p-6"><Squelette className="h-10 w-2/3" /><Squelette className="h-24" /><Squelette className="h-72" /></div>;

  const copierLien = async () => {
    if (!(await copier(r.lien))) return toast("erreur", "Copie impossible dans ce navigateur : utilisez « Ouvrir le formulaire » puis copiez l'adresse.");
    setCopie(true);
    setTimeout(() => setCopie(false), 1500);
  };

  return (
    <div>
      <div className="border-b border-trait bg-surface px-6 pb-5 pt-4">
        <div className="flex flex-wrap items-center gap-2"><BadgeStatut statut={r.statut} /><span className="text-xs text-discret">{r.epn.categorie} · {r.epn.tutelle}</span></div>
        <h2 className="titre-display mt-2 text-3xl">{r.epn.nom}</h2>
        <div className="mt-4 flex items-center gap-3"><Progression valeur={r.avancement} className="flex-1" ton={r.avancement === 100 ? "succes" : "marque"} /><span className="chiffres text-sm font-medium">{r.avancement} %</span></div>
        <div className="mt-5 flex flex-wrap gap-2">
          {r.statut === "soumis"
            ? <Bouton taille="sm" icone={<RotateCcw className="h-3.5 w-3.5" />} chargement={action.isPending} onClick={() => action.mutate("rouvrir")}>Rouvrir pour correction</Bouton>
            : <>
                <Bouton taille="sm" variante="primaire" icone={<BellRing className="h-3.5 w-3.5" />} chargement={action.isPending && action.variables === "relancer"} onClick={() => action.mutate("relancer")}>Relancer</Bouton>
                <Bouton taille="sm" icone={<Send className="h-3.5 w-3.5" />} chargement={action.isPending && action.variables === "inviter"} onClick={() => action.mutate("inviter")}>{r.date_invitation ? "Renvoyer l'invitation" : "Envoyer l'invitation"}</Bouton>
              </>}
          <Bouton taille="sm" icone={copie ? <Check className="h-3.5 w-3.5 text-succes" /> : <Copy className="h-3.5 w-3.5" />} onClick={copierLien}>{copie ? "Lien copié" : "Copier le lien"}</Bouton>
          <a href={r.lien} target="_blank" rel="noopener" className="inline-flex h-9 items-center gap-2 rounded-[10px] px-3 text-[13px] font-medium text-discret hover:bg-relief hover:text-encre"><ExternalLink className="h-3.5 w-3.5" /> Ouvrir le formulaire</a>
        </div>
      </div>

      <div className="grid gap-3 border-b border-trait bg-surface px-6 py-4 text-sm sm:grid-cols-3">
        <div><p className="text-xs text-discret">Répondant</p><p className="font-medium">{r.repondant || "Pas encore identifié"}</p><p className="text-xs text-discret">{r.fonction}</p></div>
        <div className="space-y-1">
          <p className="text-xs text-discret">Contact</p>
          {r.email ? <a href={`mailto:${r.email}`} className="flex items-center gap-1.5 hover:text-marque"><Mail className="h-3.5 w-3.5" />{r.email}</a> : <p className="text-discret">—</p>}
          {r.telephone && <a href={`tel:${r.telephone}`} className="flex items-center gap-1.5 hover:text-marque"><Phone className="h-3.5 w-3.5" />{r.telephone}</a>}
        </div>
        <div><p className="text-xs text-discret">Envoyé le</p><p className="font-medium">{date(r.date_soumission, true)}</p><p className="text-xs text-discret">Point focal : {r.epn.email_contact}</p></div>
      </div>

      <div className="sticky top-0 z-10 flex gap-1 border-b border-trait bg-fond/90 px-6 backdrop-blur">
        {([["reponses", "Réponses"], ["pieces", `Pièces jointes (${r.pieces.length})`], ["historique", `Historique (${r.envois.length})`]] as const).map(([cle, l]) => (
          <button key={cle} onClick={() => setOnglet(cle)}
            className={cx("relative h-11 px-3 text-sm transition", onglet === cle ? "font-semibold text-encre" : "text-discret hover:text-encre")}>
            {l}{onglet === cle && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-marque" />}
          </button>
        ))}
      </div>

      <div className="space-y-4 p-6">
        {onglet === "reponses" && r.modules.map((m) => (
          <Carte key={m.code} className="overflow-hidden">
            <div className="flex items-center gap-3 border-b border-trait px-5 py-3">
              <span className="font-mono text-xs text-discret">{m.code}</span>
              <h3 className="flex-1 text-sm font-semibold">{m.titre}</h3>
              {!m.complet && <span className="text-xs font-medium text-alerte">Incomplet</span>}
            </div>
            <dl className="divide-y divide-trait">
              {m.lignes.map((l) => (
                <div key={l.code} className="grid gap-1 px-5 py-2.5 text-sm sm:grid-cols-[1fr_1fr] sm:gap-4">
                  <dt className="text-discret">{l.libelle}</dt>
                  <dd className={cx("font-medium", !l.valeur && "font-normal text-discret/60")}>
                    {l.piece ? <a href={l.piece.url} className="inline-flex items-center gap-1.5 text-marque hover:underline"><FileText className="h-3.5 w-3.5" />{l.piece.nom}</a> : l.valeur || "—"}
                  </dd>
                </div>
              ))}
            </dl>
          </Carte>
        ))}

        {onglet === "pieces" && (r.pieces.length === 0 ? <Vide icone={<FileText className="h-5 w-5" />} titre="Aucune pièce jointe" /> : (
          <>
            {r.zip_url && <a href={r.zip_url} className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-marque px-4 text-sm font-medium text-white dark:text-[#04140c]"><FileArchive className="h-4 w-4" /> Tout télécharger (ZIP)</a>}
            <Carte className="divide-y divide-trait">
              {r.pieces.map((p) => (
                <a key={p.code} href={p.url} className="flex items-center gap-4 px-5 py-4 transition hover:bg-relief/50">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-marque-doux text-marque"><FileText className="h-5 w-5" /></span>
                  <div className="min-w-0 flex-1"><p className="truncate font-medium">{p.nom}</p><p className="text-xs text-discret">{p.code} · {taille(p.taille)} · {date(p.date_depot, true)}</p></div>
                  <Download className="h-4 w-4 text-discret" />
                </a>
              ))}
            </Carte>
          </>
        ))}

        {onglet === "historique" && (r.envois.length === 0 ? <Vide icone={<Mail className="h-5 w-5" />} titre="Aucun e-mail envoyé" /> : (
          <ol className="relative space-y-4 border-l border-trait pl-6">
            {r.envois.map((e, i) => (
              <li key={i} className="relative">
                <span className={cx("absolute -left-[31px] top-1 h-3 w-3 rounded-full ring-4 ring-fond", e.succes ? "bg-marque" : "bg-danger")} />
                <p className="text-sm font-medium">{e.type}{!e.succes && <span className="ml-2 text-danger">échec</span>}</p>
                <p className="text-xs text-discret">{date(e.date, true)}{e.par && ` · par ${e.par}`}</p>
                <p className="text-xs text-discret">{e.destinataires}</p>
              </li>
            ))}
          </ol>
        ))}
      </div>
    </div>
  );
}
