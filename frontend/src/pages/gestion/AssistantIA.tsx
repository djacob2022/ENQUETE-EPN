import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, FileText, Info, RefreshCw, SendHorizontal, Sparkles, Trash2, UserRound } from "lucide-react";
import { FormEvent, Fragment, ReactNode, useEffect, useRef, useState } from "react";
import { api, avecParams, ErreurApi } from "@/lib/api";
import { ilYa } from "@/lib/format";
import { Badge, Bouton, Carte, cx, EnTeteCarte, Liste, Squelette, useToast } from "@/ui";
import { EnTetePage, peut, SansCampagne, useGestion } from "./Gestion";

type EtatAssistant = { disponible: boolean; nominatif: boolean; modele: string; suggestions: string[] };
type Message = { role: "user" | "assistant"; contenu: string; erreur?: boolean };
type ContenuSynthese = { synthese: string; points_forts: string[]; points_vigilance: string[]; besoins: string[]; recommandations: string[] };
type Synthese = { contenu: ContenuSynthese; date: string; auteur: string; modele: string; nombre_reponses: number };
const BASES: Record<string, string> = { validees: "Réponses validées", envoyees: "Réponses envoyées", toutes: "Toutes les réponses" };

/** Assistant IA (questions sur les résultats) et rapport annuel automatique. */
export default function AssistantIA() {
  const { campagne, moi } = useGestion();
  const [base, setBase] = useState("validees");
  const etat = useQuery({ queryKey: ["assistant"], queryFn: () => api.get<EtatAssistant>("/api/gestion/assistant/") });
  if (!campagne) return <SansCampagne />;
  return (
    <>
      <EnTetePage titre="Assistant IA et rapport annuel" sous={`${campagne.nom} · exercice ${campagne.exercice}`}
        actions={<Liste libelle="Base de calcul" value={base} onChange={(e) => setBase(e.target.value)} className="w-52">
          {Object.entries(BASES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Liste>} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <Conversation base={base} etat={etat.data} />
        <RapportAnnuel base={base} disponible={!!etat.data?.disponible} peutSynthetiser={peut(moi, "voir_nominatif")} />
      </div>
    </>
  );
}

function Conversation({ base, etat }: { base: string; etat?: EtatAssistant }) {
  const { campagne } = useGestion();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => { fin.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [messages]);

  const demander = useMutation({
    mutationFn: (q: string) => api.post<{ reponse: string; n: number }>(avecParams("/api/gestion/assistant/", { campagne: campagne?.id }), {
      question: q, base, historique: messages.filter((m) => !m.erreur).map(({ role, contenu }) => ({ role, contenu })) }),
    onMutate: (q) => { setMessages((m) => [...m, { role: "user", contenu: q }]); setQuestion(""); },
    onSuccess: (r) => setMessages((m) => [...m, { role: "assistant", contenu: r.reponse }]),
    onError: (e: ErreurApi) => setMessages((m) => [...m, { role: "assistant", contenu: e.message, erreur: true }]),
  });
  const envoyer = (e?: FormEvent) => { e?.preventDefault(); const q = question.trim(); if (q && !demander.isPending) demander.mutate(q); };

  return (
    <Carte className="flex min-h-[620px] flex-col">
      <EnTeteCarte titre={<span className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-marque" /> Posez vos questions sur les résultats</span>}
        sous={etat ? (etat.nominatif ? "L'assistant voit les chiffres de chaque EPN de votre périmètre et leurs réponses ouvertes, jamais les coordonnées des répondants."
          : "Votre rôle donne accès aux chiffres agrégés : l'assistant ne voit pas le détail par établissement.") : undefined}
        actions={messages.length > 0 && <Bouton taille="sm" variante="fantome" icone={<Trash2 className="h-4 w-4" />} onClick={() => setMessages([])}>Effacer</Bouton>} />
      <div className="defilement-fin flex-1 space-y-4 overflow-y-auto p-5" aria-live="polite">
        {!etat ? <Squelette className="h-40" /> : !etat.disponible ? (
          <div className="flex gap-3 rounded-xl border border-alerte/30 bg-alerte-doux/50 p-4 text-sm">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-alerte" />
            <div><p className="font-medium">L'assistant IA n'est pas encore activé sur ce serveur.</p>
              <p className="mt-1 text-discret">L'administrateur technique doit renseigner la clé <code className="font-mono">ANTHROPIC_API_KEY</code> dans le fichier
                .env, puis relancer l'application. Le rapport annuel reste disponible sans assistant.</p></div>
          </div>
        ) : messages.length === 0 ? (
          <div className="py-6 text-center">
            <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-marque-doux text-marque"><Bot className="h-7 w-7" /></span>
            <p className="mt-3 font-medium">Que voulez-vous savoir sur la campagne ?</p>
            <p className="mt-1 text-sm text-discret">Exemples de questions :</p>
            <div className="mx-auto mt-4 flex max-w-2xl flex-wrap justify-center gap-2">
              {etat.suggestions.map((s) => (
                <button key={s} onClick={() => demander.mutate(s)}
                  className="rounded-full border border-trait bg-surface px-3.5 py-1.5 text-left text-[13px] hover:border-marque hover:bg-marque-doux">{s}</button>
              ))}
            </div>
          </div>
        ) : messages.map((m, i) => <Bulle key={i} message={m} />)}
        {demander.isPending && (
          <div className="flex items-center gap-3 text-sm text-discret">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-marque-doux text-marque"><Bot className="h-4 w-4" /></span>
            <span className="flex gap-1">{[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-marque" style={{ animationDelay: `${i * 150}ms` }} />)}</span>
            Analyse des données en cours…
          </div>
        )}
        <div ref={fin} />
      </div>
      <form onSubmit={envoyer} className="flex items-end gap-2 border-t border-trait p-4">
        <label className="sr-only" htmlFor="question-ia">Votre question</label>
        <textarea id="question-ia" rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} disabled={!etat?.disponible}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); envoyer(); } }} maxLength={2000}
          placeholder={etat?.disponible ? "Ex. : quels EPN dépendent le plus de la subvention ? (Entrée pour envoyer)" : "Assistant non configuré"}
          className="min-h-[48px] flex-1 resize-none rounded-[10px] border border-trait bg-surface px-3.5 py-2.5 text-sm outline-none focus:border-marque focus:ring-2 focus:ring-marque/20 disabled:opacity-60" />
        <Bouton type="submit" variante="primaire" icone={<SendHorizontal className="h-4 w-4" />} chargement={demander.isPending}
          disabled={!etat?.disponible || !question.trim()} aria-label="Envoyer la question">Envoyer</Bouton>
      </form>
      <p className="px-4 pb-3 text-[11px] text-discret">Réponses générées par IA à partir des données de l'enquête : vérifiez les chiffres importants dans les statistiques avant diffusion.</p>
    </Carte>
  );
}

function Bulle({ message }: { message: Message }) {
  const moi = message.role === "user";
  return (
    <div className={cx("flex gap-3", moi && "flex-row-reverse")}>
      <span className={cx("grid h-8 w-8 shrink-0 place-items-center rounded-full", moi ? "bg-relief text-discret" : "bg-marque-doux text-marque")}>
        {moi ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={cx("max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
        moi ? "rounded-tr-sm bg-marque text-white dark:text-[#04140c]" : message.erreur ? "rounded-tl-sm border border-danger/30 bg-danger-doux/50 text-danger" : "rounded-tl-sm bg-relief/70")}>
        {moi || message.erreur ? <p className="whitespace-pre-wrap">{message.contenu}</p> : <Markdown texte={message.contenu} />}
      </div>
    </div>
  );
}

/** Rendu Markdown minimal et sûr (aucun HTML injecté) : titres, listes, tableaux, gras, italique, code. */
function Markdown({ texte }: { texte: string }) {
  const lignes = texte.replace(/\r/g, "").split("\n");
  const blocs: ReactNode[] = [];
  for (let i = 0; i < lignes.length;) {
    const l = lignes[i];
    if (!l.trim()) { i++; continue; }
    if (/^\s*\|/.test(l) && i + 1 < lignes.length && /^\s*\|?\s*:?-{3,}/.test(lignes[i + 1])) {
      const cellules = (x: string) => x.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const entete = cellules(l);
      const corps: string[][] = [];
      i += 2;
      while (i < lignes.length && /^\s*\|/.test(lignes[i])) corps.push(cellules(lignes[i++]));
      blocs.push(
        <div key={i} className="defilement-fin my-2 overflow-x-auto"><table className="w-full text-[13px]">
          <thead><tr>{entete.map((c, j) => <th key={j} className="border-b border-trait px-2 py-1.5 text-left font-semibold">{enLigne(c)}</th>)}</tr></thead>
          <tbody>{corps.map((r, k) => <tr key={k} className="border-b border-trait/60">{r.map((c, j) => <td key={j} className="chiffres px-2 py-1.5">{enLigne(c)}</td>)}</tr>)}</tbody>
        </table></div>);
      continue;
    }
    const titre = l.match(/^(#{1,4})\s+(.*)/);
    if (titre) { blocs.push(<p key={i} className="mb-1 mt-3 font-semibold first:mt-0">{enLigne(titre[2])}</p>); i++; continue; }
    if (/^\s*([-*•]|\d+[.)])\s+/.test(l)) {
      const ordonnee = /^\s*\d/.test(l);
      const items: string[] = [];
      while (i < lignes.length && /^\s*([-*•]|\d+[.)])\s+/.test(lignes[i])) items.push(lignes[i++].replace(/^\s*([-*•]|\d+[.)])\s+/, ""));
      const L = ordonnee ? "ol" : "ul";
      blocs.push(<L key={i} className={cx("my-1.5 space-y-1 pl-5", ordonnee ? "list-decimal" : "list-disc")}>{items.map((x, k) => <li key={k}>{enLigne(x)}</li>)}</L>);
      continue;
    }
    const para: string[] = [];
    while (i < lignes.length && lignes[i].trim() && !/^(#{1,4}\s|\s*([-*•]|\d+[.)])\s|\s*\|)/.test(lignes[i])) para.push(lignes[i++]);
    if (!para.length) para.push(lignes[i++]);
    blocs.push(<p key={i} className="my-1.5">{para.map((x, k) => <Fragment key={k}>{k > 0 && <br />}{enLigne(x)}</Fragment>)}</p>);
  }
  return <div>{blocs}</div>;
}

function enLigne(texte: string): ReactNode[] {
  return texte.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).filter(Boolean).map((m, i) =>
    m.startsWith("**") ? <strong key={i}>{m.slice(2, -2)}</strong>
      : m.startsWith("`") ? <code key={i} className="rounded bg-relief px-1 font-mono text-[12px]">{m.slice(1, -1)}</code>
        : m.length > 2 && m.startsWith("*") && m.endsWith("*") ? <em key={i}>{m.slice(1, -1)}</em> : <Fragment key={i}>{m}</Fragment>);
}

function RapportAnnuel({ base, disponible, peutSynthetiser }: { base: string; disponible: boolean; peutSynthetiser: boolean }) {
  const { campagne } = useGestion();
  const client = useQueryClient();
  const toast = useToast();
  const cle = ["synthese-ia", campagne?.id, base];
  const q = useQuery({ queryKey: cle, queryFn: () => api.get<{ disponible: boolean; synthese: Synthese | null }>(
    avecParams("/api/gestion/synthese-ia/", { campagne: campagne?.id, base })) });
  const generer = useMutation({
    mutationFn: () => api.post<{ synthese: Synthese }>(avecParams("/api/gestion/synthese-ia/", { campagne: campagne?.id }), { base }),
    onSuccess: (r) => { client.setQueryData(cle, { disponible: true, synthese: r.synthese }); toast("succes", "Synthèse rédigée : elle figure désormais dans le rapport annuel."); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  const s = q.data?.synthese;
  const pdf = avecParams("/api/gestion/rapport-annuel.pdf", { campagne: campagne?.id, base });

  return (
    <Carte className="self-start">
      <EnTeteCarte titre="Rapport annuel" sous="Généré automatiquement à partir des données de votre périmètre : participation, indicateurs comparés à N-1, résultats par rubrique, contrôle qualité." />
      <div className="space-y-4 p-5">
        <a href={pdf} className="flex items-center gap-3 rounded-xl border border-trait p-3 hover:border-marque hover:bg-marque-doux">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-danger-doux text-danger"><FileText className="h-5 w-5" /></span>
          <span className="flex-1"><span className="block text-sm font-medium">Télécharger le rapport PDF</span>
            <span className="block text-xs text-discret">{BASES[base]}{s ? " · avec la synthèse IA" : " · constats chiffrés automatiques"}</span></span>
        </a>
        <p className="text-xs text-discret">Il est aussi envoyé automatiquement par e-mail aux administrateurs quelques jours après la clôture de la campagne.</p>

        <div className="border-t border-trait pt-4">
          <div className="flex items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-marque" /> Synthèse rédigée par l'IA</p>
            {s && <Badge ton="succes">Intégrée au PDF</Badge>}
          </div>
          {q.isLoading ? <Squelette className="mt-3 h-24" /> : s ? (
            <div className="mt-3 space-y-3 text-sm">
              {s.contenu.synthese.split("\n").filter(Boolean).map((p, i) => <p key={i} className="leading-relaxed">{p}</p>)}
              {([["Points forts", "points_forts", "text-succes"], ["Points de vigilance", "points_vigilance", "text-alerte"], ["Besoins exprimés", "besoins", "text-marque"],
                ["Recommandations", "recommandations", "text-encre"]] as const).map(([titre, k, ton]) => s.contenu[k].length > 0 && (
                <div key={k}><p className={cx("text-xs font-semibold uppercase tracking-wider", ton)}>{titre}</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px]">{s.contenu[k].map((x, i) => <li key={i}>{x}</li>)}</ul></div>
              ))}
              <p className="text-[11px] text-discret">Rédigée {ilYa(s.date)} par {s.auteur} sur {s.nombre_reponses} réponse{s.nombre_reponses > 1 ? "s" : ""}. Relisez-la avant diffusion.</p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-discret">{disponible ? "Ajoutez au rapport une analyse rédigée : synthèse, points forts, points de vigilance, besoins des EPN et recommandations."
              : "Disponible quand l'assistant IA est activé sur le serveur."}</p>
          )}
          {disponible && peutSynthetiser && (
            <Bouton className="mt-3 w-full" variante={s ? "secondaire" : "primaire"} icone={s ? <RefreshCw className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
              chargement={generer.isPending} onClick={() => generer.mutate()}>
              {generer.isPending ? "Rédaction en cours (jusqu'à une minute)…" : s ? "Rédiger à nouveau" : "Rédiger la synthèse"}</Bouton>
          )}
        </div>
      </div>
    </Carte>
  );
}
