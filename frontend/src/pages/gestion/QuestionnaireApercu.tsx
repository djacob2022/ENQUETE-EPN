import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown, ArrowUp, Eye, EyeOff, GitBranch, GripVertical, ListChecks, Pencil, Plus, Printer, Save, Sigma, Trash2, Undo2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Choix, Module, Question, QuestionnaireEditeur, Regle, TypeQuestion, Valeur } from "@/lib/types";
import { Badge, Bouton, Carte, Champ, cx, Dialogue, Liste, Squelette, Tiroir, useToast, ZoneTexte } from "@/ui";
import { ChampQuestion, estPosee } from "../public/Questions";
import { EnTetePage, SansCampagne, useGestion } from "./Gestion";

const NUMERIQUES: TypeQuestion[] = ["entier", "montant", "pourcentage"];
const A_CHOIX: TypeQuestion[] = ["choix", "choix_multiple"];

function deplacer<T>(liste: T[], de: number, vers: number) {
  const copie = [...liste];
  const [x] = copie.splice(de, 1);
  copie.splice(vers, 0, x);
  return copie;
}

/** Éditeur de questionnaire sans code (F-10 à F-15) : rubriques, questions, conditions et règles de contrôle. */
export default function QuestionnaireApercu() {
  const { campagne, moi } = useGestion();
  const client = useQueryClient();
  const toast = useToast();
  const modifiable = moi.permissions.includes("gerer_questionnaire");
  const url = `/api/gestion/campagnes/${campagne?.id}/questionnaire/`;
  const q = useQuery({ queryKey: ["editeur", campagne?.id], queryFn: () => api.get<QuestionnaireEditeur>(url), enabled: !!campagne });
  const [def, setDef] = useState<{ modules: Module[]; regles: Regle[] } | null>(null);
  const [actif, setActif] = useState(0);
  const [edition, setEdition] = useState<{ m: number; i: number | null; q: Question } | null>(null);
  const [apercu, setApercu] = useState(false);
  const [regle, setRegle] = useState<Regle | null>(null);
  const [glisse, setGlisse] = useState<{ type: "m" | "q"; i: number } | null>(null);

  useEffect(() => { if (q.data) setDef({ modules: structuredClone(q.data.modules), regles: structuredClone(q.data.regles) }); }, [q.data]);
  const modifie = useMemo(() => !!q.data && !!def && JSON.stringify({ modules: q.data.modules, regles: q.data.regles }) !== JSON.stringify(def), [q.data, def]);

  const enregistrer = useMutation({
    mutationFn: () => api.put<QuestionnaireEditeur>(url, def),
    onSuccess: (d) => {
      client.setQueryData(["editeur", campagne?.id], d);
      client.invalidateQueries({ queryKey: ["questionnaire"] });
      toast("succes", `Questionnaire enregistré (version ${d.version}).`);
    },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  if (!campagne) return <SansCampagne />;
  if (!q.data || !def) return <Squelette className="h-[480px] rounded-2xl" />;

  const toutes = def.modules.flatMap((m) => m.questions);
  const nb = toutes.length;
  const module = def.modules[Math.min(actif, def.modules.length - 1)];
  const majModules = (f: (m: Module[]) => Module[]) => setDef((d) => d && { ...d, modules: f(d.modules) });
  const majModule = (i: number, f: (m: Module) => Module) => majModules((ms) => ms.map((m, j) => (j === i ? f(m) : m)));

  function ajouterModule() {
    const pris = new Set(def!.modules.map((m) => m.code));
    const code = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").find((l) => !pris.has(l)) ?? "Z";
    majModules((ms) => [...ms, { code, titre: "Nouvelle rubrique", intro: "", actif: true, questions: [] }]);
    setActif(def!.modules.length);
  }

  function enregistrerQuestion(question: Question) {
    if (!edition) return;
    majModule(edition.m, (m) => ({
      ...m, questions: edition.i === null ? [...m.questions, question] : m.questions.map((x, j) => (j === edition.i ? question : x)),
    }));
    setEdition(null);
  }

  const lecture = !modifiable;

  return (
    <>
      <EnTetePage titre="Questionnaire"
        sous={<>Campagne « {campagne.nom} » · version {q.data.version} · {def.modules.filter((m) => m.actif !== false).length} rubriques actives · {nb} questions
          {q.data.modifie_le && <> · modifié le {date(q.data.modifie_le, true)}{q.data.modifie_par && ` par ${q.data.modifie_par}`}</>}</>}
        actions={<>
          <Bouton icone={<Eye className="h-4 w-4" />} onClick={() => setApercu(true)}>Aperçu répondant</Bouton>
          <Bouton icone={<Printer className="h-4 w-4" />} onClick={() => window.print()} className="pas-imprimer">Imprimer</Bouton>
          {modifiable && <>
            {modifie && <Bouton variante="fantome" icone={<Undo2 className="h-4 w-4" />} onClick={() => setDef({ modules: structuredClone(q.data!.modules), regles: structuredClone(q.data!.regles) })}>Annuler</Bouton>}
            <Bouton variante="primaire" icone={<Save className="h-4 w-4" />} disabled={!modifie} chargement={enregistrer.isPending} onClick={() => enregistrer.mutate()}>
              Enregistrer{modifie ? " *" : ""}
            </Bouton>
          </>}
        </>} />

      {q.data.avec_reponses > 0 && modifiable && (
        <p className="mb-5 rounded-xl border border-alerte/30 bg-alerte-doux px-4 py-3 text-sm text-alerte">
          {q.data.avec_reponses} établissement{q.data.avec_reponses > 1 ? "s ont" : " a"} déjà commencé à répondre : une question renseignée ne peut plus être supprimée ni changer de type.
          Les codes restent stables d'une version à l'autre.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Rubriques */}
        <Carte className="h-fit p-2">
          <p className="px-3 pb-2 pt-2 text-xs font-medium uppercase tracking-wider text-discret">Rubriques</p>
          <ol className="space-y-0.5">
            {def.modules.map((m, i) => (
              <li key={m.code} draggable={!lecture}
                onDragStart={() => setGlisse({ type: "m", i })} onDragOver={(e) => glisse?.type === "m" && e.preventDefault()}
                onDrop={() => { if (glisse?.type === "m" && glisse.i !== i) { majModules((ms) => deplacer(ms, glisse.i, i)); setActif(i); } setGlisse(null); }}
                className={cx("group flex items-center gap-2 rounded-xl px-2 py-2 text-sm transition",
                  i === actif ? "bg-marque-doux font-semibold text-marque" : "hover:bg-relief", m.actif === false && "opacity-55")}>
                {!lecture && <GripVertical className="h-4 w-4 shrink-0 cursor-grab text-discret" aria-hidden />}
                <button className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => setActif(i)}>
                  <span className="w-5 font-mono text-xs text-discret">{m.code}</span>
                  <span className="truncate">{m.titre}</span>
                </button>
                <span className="chiffres text-xs text-discret">{m.questions.length}</span>
              </li>
            ))}
          </ol>
          {!lecture && <Bouton taille="sm" variante="fantome" className="mt-2 w-full" icone={<Plus className="h-4 w-4" />} onClick={ajouterModule}>Ajouter une rubrique</Bouton>}
        </Carte>

        {/* Questions de la rubrique */}
        <div className="space-y-6">
          <Carte className="overflow-hidden">
            <div className="space-y-3 border-b border-trait p-5">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-sm text-discret">{module.code}</span>
                <input value={module.titre} disabled={lecture} aria-label="Titre de la rubrique"
                  onChange={(e) => majModule(actif, (m) => ({ ...m, titre: e.target.value }))}
                  className="min-w-[200px] flex-1 rounded-lg border border-transparent bg-transparent px-2 py-1 text-lg font-semibold tracking-tight hover:border-trait focus:border-marque focus:outline-none" />
                {module.actif === false ? <Badge ton="alerte">Désactivée</Badge> : <Badge ton="succes">Active</Badge>}
                {!lecture && <>
                  <Bouton taille="sm" variante="fantome" icone={module.actif === false ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                    onClick={() => majModule(actif, (m) => ({ ...m, actif: m.actif === false }))}>
                    {module.actif === false ? "Activer" : "Désactiver"}
                  </Bouton>
                  {module.questions.length === 0 && (
                    <Bouton taille="sm" variante="fantome" aria-label="Supprimer la rubrique" icone={<Trash2 className="h-4 w-4" />}
                      onClick={() => { majModules((ms) => ms.filter((_, j) => j !== actif)); setActif(0); }} />
                  )}
                </>}
              </div>
              <textarea value={module.intro} disabled={lecture} rows={2} placeholder="Texte d'introduction affiché en tête de rubrique (facultatif)"
                onChange={(e) => majModule(actif, (m) => ({ ...m, intro: e.target.value }))}
                className="w-full resize-y rounded-lg border border-trait bg-surface px-3 py-2 text-sm focus:border-marque focus:outline-none disabled:border-transparent" />
            </div>
            <ol className="divide-y divide-trait">
              {module.questions.map((x, i) => (
                <li key={x.code || `n${i}`} draggable={!lecture}
                  onDragStart={() => setGlisse({ type: "q", i })} onDragOver={(e) => glisse?.type === "q" && e.preventDefault()}
                  onDrop={() => { if (glisse?.type === "q" && glisse.i !== i) majModule(actif, (m) => ({ ...m, questions: deplacer(m.questions, glisse.i, i) })); setGlisse(null); }}
                  className="group flex items-start gap-3 px-5 py-3.5 text-sm">
                  {!lecture && <GripVertical className="mt-0.5 h-4 w-4 shrink-0 cursor-grab text-discret" aria-hidden />}
                  <span className="w-11 shrink-0 font-mono text-xs leading-5 text-discret">{x.code || "nouv."}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{x.libelle}{x.obligatoire && <span className="ml-0.5 text-danger">*</span>}</p>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      <Badge>{q.data!.types.find((t) => t.valeur === x.type)?.libelle ?? x.type}{x.unite ? ` · ${x.unite}` : ""}</Badge>
                      {x.si && <Badge ton="marque"><GitBranch className="h-3 w-3" /> si {x.si.question} = {x.si.valeurs.join(" ou ")}</Badge>}
                      {x.choix && <span className="text-xs text-discret">{x.choix.map((c) => c.libelle).join(" · ")}</span>}
                    </div>
                  </div>
                  {!lecture && (
                    <div className="flex shrink-0 gap-0.5 opacity-70 group-hover:opacity-100">
                      <Bouton taille="sm" variante="fantome" aria-label="Monter" disabled={i === 0}
                        onClick={() => majModule(actif, (m) => ({ ...m, questions: deplacer(m.questions, i, i - 1) }))}><ArrowUp className="h-4 w-4" /></Bouton>
                      <Bouton taille="sm" variante="fantome" aria-label="Descendre" disabled={i === module.questions.length - 1}
                        onClick={() => majModule(actif, (m) => ({ ...m, questions: deplacer(m.questions, i, i + 1) }))}><ArrowDown className="h-4 w-4" /></Bouton>
                      <Bouton taille="sm" variante="fantome" aria-label={`Modifier ${x.code}`} onClick={() => setEdition({ m: actif, i, q: structuredClone(x) })}><Pencil className="h-4 w-4" /></Bouton>
                      <Bouton taille="sm" variante="fantome" aria-label={`Supprimer ${x.code}`} className="hover:text-danger"
                        onClick={() => majModule(actif, (m) => ({ ...m, questions: m.questions.filter((_, j) => j !== i) }))}><Trash2 className="h-4 w-4" /></Bouton>
                    </div>
                  )}
                </li>
              ))}
              {module.questions.length === 0 && <li className="px-5 py-10 text-center text-sm text-discret">Aucune question dans cette rubrique.</li>}
            </ol>
            {!lecture && (
              <div className="border-t border-trait p-3">
                <Bouton taille="sm" icone={<Plus className="h-4 w-4" />}
                  onClick={() => setEdition({ m: actif, i: null, q: { code: "", libelle: "", type: "texte", obligatoire: true } })}>Ajouter une question</Bouton>
              </div>
            )}
          </Carte>

          {/* Règles de contrôle */}
          <Carte className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-trait px-5 py-4">
              <div><h2 className="flex items-center gap-2 font-semibold tracking-tight"><Sigma className="h-4 w-4 text-marque" /> Règles de cohérence</h2>
                <p className="text-[13px] text-discret">Contrôles entre questions, vérifiés avant l'envoi (ex. femmes + hommes = effectif total).</p></div>
              {!lecture && <Bouton taille="sm" icone={<Plus className="h-4 w-4" />} onClick={() => setRegle({ type: "somme", total: "", parties: ["", ""] })}>Ajouter une règle</Bouton>}
            </div>
            <ul className="divide-y divide-trait">
              {def.regles.map((r, i) => (
                <li key={i} className="flex items-center gap-3 px-5 py-3 text-sm">
                  <ListChecks className="h-4 w-4 shrink-0 text-discret" />
                  <span className="flex-1 font-mono text-[13px]">
                    {r.type === "somme" ? `${(r.parties ?? []).join(" + ")} = ${r.total}` : `${r.petit} ≤ ${r.grand}`}
                  </span>
                  {!lecture && <Bouton taille="sm" variante="fantome" aria-label="Supprimer la règle" className="hover:text-danger"
                    onClick={() => setDef((d) => d && { ...d, regles: d.regles.filter((_, j) => j !== i) })}><Trash2 className="h-4 w-4" /></Bouton>}
                </li>
              ))}
              {def.regles.length === 0 && <li className="px-5 py-6 text-center text-sm text-discret">Aucune règle.</li>}
            </ul>
          </Carte>
        </div>
      </div>

      <EditeurQuestion edition={edition} toutes={toutes} types={q.data.types} fermer={() => setEdition(null)} valider={enregistrerQuestion} />
      <DialogueRegle regle={regle} numeriques={toutes.filter((x) => NUMERIQUES.includes(x.type) && x.code)} fermer={() => setRegle(null)}
        valider={(r) => { setDef((d) => d && { ...d, regles: [...d.regles, r] }); setRegle(null); }} />
      <Apercu ouvert={apercu} fermer={() => setApercu(false)} modules={def.modules.filter((m) => m.actif !== false)} />
    </>
  );
}

/* ---------- Édition d'une question ---------- */

function EditeurQuestion({ edition, toutes, types, fermer, valider }: {
  edition: { m: number; i: number | null; q: Question } | null; toutes: Question[]; types: Choix[];
  fermer: () => void; valider: (q: Question) => void;
}) {
  const [q, setQ] = useState<Question | null>(null);
  useEffect(() => setQ(edition ? structuredClone(edition.q) : null), [edition]);
  if (!edition || !q) return <Tiroir ouvert={false} fermer={fermer} titre=""><div /></Tiroir>;
  const maj = (p: Partial<Question>) => setQ((x) => x && { ...x, ...p });
  const declencheurs = toutes.filter((x) => x.code && x.code !== q.code && ["oui_non", "choix", "choix_multiple"].includes(x.type));
  const cible = declencheurs.find((x) => x.code === q.si?.question);
  const choixCible = cible?.type === "oui_non" ? [{ valeur: "oui", libelle: "Oui" }, { valeur: "non", libelle: "Non" }] : cible?.choix ?? [];
  const nombre = (v: string) => (v === "" ? undefined : Number(v.replace(",", ".")));

  return (
    <Tiroir ouvert fermer={fermer} titre={edition.i === null ? "Nouvelle question" : `Question ${q.code}`} largeur={620}>
      <div className="space-y-5 p-6">
        <ZoneTexte libelle="Libellé de la question" required rows={2} value={q.libelle} onChange={(e) => maj({ libelle: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Liste libelle="Type de réponse" value={q.type} onChange={(e) => {
            const type = e.target.value as TypeQuestion;
            maj({ type, choix: A_CHOIX.includes(type) ? q.choix ?? [{ valeur: "", libelle: "" }, { valeur: "", libelle: "" }] : undefined,
              colonnes: type === "tableau" ? q.colonnes ?? [{ code: "", libelle: "Libellé", type: "texte" }] : undefined });
          }}>
            {types.map((t) => <option key={t.valeur} value={t.valeur}>{t.libelle}</option>)}
          </Liste>
          <label className="flex cursor-pointer items-center gap-3 self-end rounded-xl border border-trait p-3 text-sm">
            <input type="checkbox" checked={q.obligatoire} onChange={(e) => maj({ obligatoire: e.target.checked })} className="h-4 w-4 accent-[rgb(var(--marque))]" />
            Réponse obligatoire
          </label>
        </div>
        <Champ libelle="Aide en ligne (facultatif)" value={q.aide ?? ""} onChange={(e) => maj({ aide: e.target.value })} aide="Affichée sous la question." />

        {(NUMERIQUES.includes(q.type) || q.type === "echelle") && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Champ libelle="Minimum" inputMode="decimal" value={q.min ?? ""} onChange={(e) => maj({ min: nombre(e.target.value) })} />
            <Champ libelle="Maximum" inputMode="decimal" value={q.max ?? ""} onChange={(e) => maj({ max: nombre(e.target.value) })} />
            {q.type !== "echelle" && <Champ libelle="Unité" value={q.unite ?? ""} onChange={(e) => maj({ unite: e.target.value })} placeholder="agents" />}
          </div>
        )}
        {q.type === "echelle" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Champ libelle="Libellé du minimum" value={q.libelle_min ?? ""} onChange={(e) => maj({ libelle_min: e.target.value })} placeholder="Très faible" />
            <Champ libelle="Libellé du maximum" value={q.libelle_max ?? ""} onChange={(e) => maj({ libelle_max: e.target.value })} placeholder="Très forte" />
          </div>
        )}

        {A_CHOIX.includes(q.type) && (
          <ListeEditable titre="Choix proposés" elements={q.choix ?? []} vide={{ valeur: "", libelle: "" }}
            changer={(choix) => maj({ choix })} rendu={(c, m) => (
              <input value={c.libelle} onChange={(e) => m({ ...c, libelle: e.target.value })} placeholder="Libellé du choix" aria-label="Libellé du choix"
                className="h-10 flex-1 rounded-lg border border-trait bg-surface px-3 text-sm focus:border-marque focus:outline-none" />
            )} />
        )}
        {q.type === "tableau" && (
          <ListeEditable titre="Colonnes du tableau" elements={q.colonnes ?? []} vide={{ code: "", libelle: "", type: "texte" as const }}
            changer={(colonnes) => maj({ colonnes })} rendu={(c, m) => (<>
              <input value={c.libelle} onChange={(e) => m({ ...c, libelle: e.target.value })} placeholder="Intitulé de colonne" aria-label="Intitulé de colonne"
                className="h-10 flex-1 rounded-lg border border-trait bg-surface px-3 text-sm focus:border-marque focus:outline-none" />
              <select value={c.type} onChange={(e) => m({ ...c, type: e.target.value as "texte" | "nombre" })} aria-label="Type de colonne"
                className="h-10 rounded-lg border border-trait bg-surface px-2 text-sm"><option value="texte">Texte</option><option value="nombre">Nombre</option></select>
            </>)} />
        )}

        <div className="rounded-xl border border-trait p-4">
          <p className="flex items-center gap-2 text-sm font-semibold"><GitBranch className="h-4 w-4 text-marque" /> Condition d'affichage</p>
          <p className="mt-0.5 text-[13px] text-discret">La question n'est posée que si une réponse précédente a l'une des valeurs choisies.</p>
          <Liste libelle="Afficher seulement si…" className="mt-3" value={q.si?.question ?? ""}
            onChange={(e) => maj({ si: e.target.value ? { question: e.target.value, valeurs: [] } : undefined })}>
            <option value="">Toujours afficher</option>
            {declencheurs.map((x) => <option key={x.code} value={x.code}>{x.code} · {x.libelle}</option>)}
          </Liste>
          {cible && (
            <div className="mt-3 flex flex-wrap gap-2">
              {choixCible.map((c) => {
                const coche = q.si!.valeurs.includes(c.valeur);
                return (
                  <label key={c.valeur} className={cx("flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm", coche ? "border-marque bg-marque-doux" : "border-trait")}>
                    <input type="checkbox" checked={coche} className="accent-[rgb(var(--marque))]"
                      onChange={() => maj({ si: { question: cible.code, valeurs: coche ? q.si!.valeurs.filter((v) => v !== c.valeur) : [...q.si!.valeurs, c.valeur] } })} />
                    {c.libelle}
                  </label>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-trait pt-4">
          <Bouton variante="fantome" onClick={fermer}>Annuler</Bouton>
          <Bouton variante="primaire" disabled={!q.libelle.trim()} onClick={() => valider(q)}>Valider la question</Bouton>
        </div>
        <p className="text-xs text-discret">Pensez à cliquer sur « Enregistrer » en haut de page pour publier les modifications.</p>
      </div>
    </Tiroir>
  );
}

function ListeEditable<T>({ titre, elements, vide, changer, rendu }: {
  titre: string; elements: T[]; vide: T; changer: (l: T[]) => void; rendu: (e: T, maj: (e: T) => void) => React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium">{titre}</p>
      <ul className="space-y-2">
        {elements.map((e, i) => (
          <li key={i} className="flex items-center gap-2">
            {rendu(e, (n) => changer(elements.map((x, j) => (j === i ? n : x))))}
            <Bouton taille="sm" variante="fantome" aria-label="Retirer" onClick={() => changer(elements.filter((_, j) => j !== i))}><Trash2 className="h-4 w-4" /></Bouton>
          </li>
        ))}
      </ul>
      <Bouton taille="sm" variante="fantome" className="mt-2" icone={<Plus className="h-4 w-4" />} onClick={() => changer([...elements, structuredClone(vide)])}>Ajouter</Bouton>
    </div>
  );
}

/* ---------- Règle de cohérence ---------- */

function DialogueRegle({ regle, numeriques, fermer, valider }: { regle: Regle | null; numeriques: Question[]; fermer: () => void; valider: (r: Regle) => void }) {
  const [r, setR] = useState<Regle | null>(null);
  useEffect(() => setR(regle && structuredClone(regle)), [regle]);
  const choix = (valeur: string, changer: (v: string) => void, libelle: string) => (
    <Liste libelle={libelle} value={valeur} onChange={(e) => changer(e.target.value)}>
      <option value="">Choisir…</option>
      {numeriques.map((q) => <option key={q.code} value={q.code}>{q.code} · {q.libelle}</option>)}
    </Liste>
  );
  const complet = r && (r.type === "somme" ? r.total && (r.parties ?? []).filter(Boolean).length >= 2 : r.petit && r.grand);
  return (
    <Dialogue ouvert={!!r} fermer={fermer} titre="Nouvelle règle de cohérence" description="Vérifiée à la validation de la rubrique et avant l'envoi.">
      {r && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">
            {(["somme", "inferieur"] as const).map((t) => (
              <button key={t} onClick={() => setR(t === "somme" ? { type: t, total: "", parties: ["", ""] } : { type: t, petit: "", grand: "" })}
                className={cx("rounded-xl border p-3 text-left text-sm", r.type === t ? "border-marque bg-marque-doux font-semibold" : "border-trait")}>
                {t === "somme" ? "Somme : A + B = Total" : "Comparaison : A ≤ B"}
              </button>
            ))}
          </div>
          {r.type === "somme" ? (<>
            {choix(r.total ?? "", (v) => setR({ ...r, total: v }), "Total")}
            {(r.parties ?? []).map((p, i) => <div key={i}>{choix(p, (v) => setR({ ...r, parties: r.parties!.map((x, j) => (j === i ? v : x)) }), `Partie ${i + 1}`)}</div>)}
            <Bouton taille="sm" variante="fantome" icone={<Plus className="h-4 w-4" />} onClick={() => setR({ ...r, parties: [...(r.parties ?? []), ""] })}>Ajouter une partie</Bouton>
          </>) : (<>
            {choix(r.petit ?? "", (v) => setR({ ...r, petit: v }), "Valeur qui ne doit pas dépasser…")}
            {choix(r.grand ?? "", (v) => setR({ ...r, grand: v }), "…cette valeur")}
          </>)}
          <div className="flex justify-end gap-2 pt-2">
            <Bouton variante="fantome" onClick={fermer}>Annuler</Bouton>
            <Bouton variante="primaire" disabled={!complet} onClick={() => valider({ ...r, parties: r.parties?.filter(Boolean) })}>Ajouter la règle</Bouton>
          </div>
        </div>
      )}
    </Dialogue>
  );
}

/* ---------- Aperçu tel que le verra le répondant (F-15) ---------- */

function Apercu({ ouvert, fermer, modules }: { ouvert: boolean; fermer: () => void; modules: Module[] }) {
  const [valeurs, setValeurs] = useState<Record<string, Valeur>>({});
  const [i, setI] = useState(0);
  const m = modules[Math.min(i, modules.length - 1)];
  return (
    <Tiroir ouvert={ouvert} fermer={fermer} titre="Aperçu du questionnaire" largeur={820}>
      {m && (
        <div className="p-6">
          <div className="mb-5 flex flex-wrap gap-1.5">
            {modules.map((x, j) => (
              <button key={x.code} onClick={() => setI(j)} className={cx("rounded-lg px-2.5 py-1 text-xs font-medium", j === i ? "bg-marque text-white dark:text-[#04140c]" : "bg-relief text-discret")}>{x.code}</button>
            ))}
          </div>
          <p className="text-sm font-medium text-marque">Rubrique {m.code} · {i + 1} sur {modules.length}</p>
          <h2 className="titre-display mt-1 text-3xl">{m.titre}</h2>
          {m.intro && <p className="mt-2 text-discret">{m.intro}</p>}
          <Carte className="mt-5 divide-y divide-trait">
            {m.questions.filter((q) => estPosee(q, valeurs)).map((q) => (
              <div key={q.code} className="px-6 py-5">
                {q.type === "fichier"
                  ? <div><p className="text-sm font-medium">{q.libelle}</p><p className="mt-2 rounded-xl border-2 border-dashed border-trait p-5 text-center text-sm text-discret">Zone de dépôt de fichier</p></div>
                  : <ChampQuestion question={{ ...q, choix: q.type === "oui_non" ? [{ valeur: "oui", libelle: "Oui" }, { valeur: "non", libelle: "Non" }] : q.choix }}
                    valeur={valeurs[q.code]} changer={(v) => setValeurs((x) => ({ ...x, [q.code]: v }))} />}
              </div>
            ))}
          </Carte>
          <p className="mt-4 text-xs text-discret">Aperçu interactif : les conditions d'affichage réagissent à vos choix. Rien n'est enregistré.</p>
        </div>
      )}
    </Tiroir>
  );
}
