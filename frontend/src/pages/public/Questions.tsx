import { AnimatePresence, motion } from "framer-motion";
import { Check, Download, FileText, MessageSquareWarning, Plus, RefreshCw, Trash2, UploadCloud, X } from "lucide-react";
import { useId, useRef, useState } from "react";
import { api, envoyerFichier, ErreurApi } from "@/lib/api";
import { compacte, date, nombre, taille } from "@/lib/format";
import { langue, t } from "@/lib/langue";
import { LigneTableau, Module, Piece, Question, ReponsePublique, Valeur } from "@/lib/types";
import { Bouton, cx, Etiquette, MessageChamp, useToast } from "@/ui";
import { urlApi, useFormulaire } from "./Formulaire";

/* ---------- Conversion des saisies ---------- */

const numerique = (t: string) => ["entier", "montant", "pourcentage"].includes(t);
/** « 1 250 000,50 » (français) ou « 1,250,000.50 » (anglais) → « 1250000.50 ». */
export const nettoyerNombre = (v: string) => {
  const s = v.replace(/[\s\u00a0\u202f]/g, "");
  return langue() === "en" ? s.replace(/,/g, "") : s.replace(",", ".");
};

/** Vrai si la question est posée, compte tenu des réponses déjà données (condition d'affichage). */
export function estPosee(q: Question, valeurs: Record<string, Valeur>) {
  if (!q.si) return true;
  const v = valeurs[q.si.question];
  if (Array.isArray(v)) return v.some((x) => typeof x === "string" && q.si!.valeurs.includes(x));
  return typeof v === "string" && q.si.valeurs.includes(v);
}

/** Commentaire de la tutelle sur une question à corriger. */
export function CommentaireTutelle({ texte }: { texte?: string }) {
  if (!texte) return null;
  return (
    <div className="mb-3 flex gap-2.5 rounded-xl border border-danger/25 bg-danger-doux/60 px-4 py-3 text-sm">
      <MessageSquareWarning className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
      <p><span className="font-semibold text-danger">{t("Correction demandée : ")}</span>{texte}</p>
    </div>
  );
}

/** Nettoie les nombres saisis à la française (« 1 250 000,50 ») avant l'envoi au serveur. */
export function versEnvoi(module: Module, valeurs: Record<string, Valeur>) {
  const sortie: Record<string, Valeur> = {};
  module.questions.forEach((q) => {
    if (q.type === "fichier") return;
    const v = valeurs[q.code];
    sortie[q.code] = numerique(q.type) && typeof v === "string" ? nettoyerNombre(v) : v;
  });
  return sortie;
}

/** Valeur lisible pour le récapitulatif. */
export function lisible(q: Question, v: Valeur): string {
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return "";
  if (q.type === "tableau" && Array.isArray(v)) {
    return (v as LigneTableau[]).map((l) => (q.colonnes ?? []).map((c) => l[c.code] ?? "").join(" · ")).join(" ; ");
  }
  if (q.type === "date" && typeof v === "string") return date(v);
  if (q.type === "echelle") return `${v} / ${q.max ?? 5}`;
  if (q.choix) {
    const lib = (x: string) => q.choix!.find((c) => c.valeur === x)?.libelle ?? x;
    return Array.isArray(v) ? (v as string[]).map(lib).join(", ") : lib(String(v));
  }
  if (numerique(q.type) && !q.annee) {
    const n = Number(v);
    if (Number.isNaN(n)) return String(v);
    return q.type === "pourcentage" ? `${nombre(n)} %` : `${nombre(n)}${q.unite ? " " + q.unite : ""}`;
  }
  return String(v);
}

/* ---------- Champ ---------- */

export function ChampQuestion({ question: q, valeur, erreurs, changer }: {
  question: Question; valeur: Valeur; erreurs?: string[]; changer: (v: Valeur) => void;
}) {
  const id = useId();
  const enErreur = !!erreurs?.length;
  const bordure = cx("w-full rounded-[10px] border bg-surface px-3.5 text-[15px] text-encre transition-shadow placeholder:text-discret/60",
    "focus:border-marque focus:shadow-anneau focus:outline-none", enErreur ? "border-danger" : "border-trait");

  if (q.type === "echelle") {
    const min = q.min ?? 1, max = q.max ?? 5;
    const crans = Array.from({ length: max - min + 1 }, (_, i) => min + i);
    return (
      <fieldset aria-describedby={`${id}-m`}>
        <legend className="mb-3"><Etiquette code={q.code} obligatoire={q.obligatoire}>{q.libelle}</Etiquette></legend>
        <div className="flex max-w-lg gap-2" role="radiogroup">
          {crans.map((n) => {
            const actif = String(valeur ?? "") === String(n);
            return (
              <label key={n} className={cx("grid h-12 flex-1 cursor-pointer place-items-center rounded-xl border text-sm font-semibold transition chiffres",
                actif ? "border-marque bg-marque text-white shadow-[0_0_0_1px_rgb(var(--marque))] dark:text-[#04140c]" : "border-trait bg-surface hover:bg-relief/60",
                enErreur && !actif && "border-danger/40")}>
                <input type="radio" name={q.code} value={n} checked={actif} onChange={() => changer(String(n))} className="sr-only" />{n}
              </label>
            );
          })}
        </div>
        {(q.libelle_min || q.libelle_max) && (
          <div className="mt-1.5 flex max-w-lg justify-between text-xs text-discret"><span>{q.libelle_min}</span><span>{q.libelle_max}</span></div>
        )}
        <div className="mt-2"><MessageChamp id={`${id}-m`} erreurs={erreurs} aide={q.aide} /></div>
      </fieldset>
    );
  }

  if (q.type === "tableau") return <ChampTableau question={q} valeur={valeur} erreurs={erreurs} changer={changer} />;

  if (q.type === "choix" || q.type === "oui_non" || q.type === "choix_multiple") {
    const multiple = q.type === "choix_multiple";
    const choisis = multiple ? (valeur as string[]) ?? [] : [valeur as string];
    const basculer = (c: string) => multiple
      ? changer(choisis.includes(c) ? choisis.filter((x) => x !== c) : [...choisis, c])
      : changer(c);
    return (
      <fieldset aria-describedby={`${id}-m`}>
        <legend className="mb-3"><Etiquette code={q.code} obligatoire={q.obligatoire}>{q.libelle}</Etiquette></legend>
        {multiple && <p className="-mt-1.5 mb-3 text-[13px] text-discret">{t("Plusieurs réponses possibles.")}</p>}
        <div className={cx("grid gap-2", q.type === "oui_non" ? "max-w-sm grid-cols-2" : "sm:grid-cols-2")}>
          {q.choix!.map((c) => {
            const actif = choisis.includes(c.valeur);
            return (
              <label key={c.valeur}
                className={cx("group flex min-h-[48px] cursor-pointer items-center gap-3 rounded-xl border px-4 py-2.5 text-sm transition-all",
                  actif ? "border-marque bg-marque-doux/60 font-medium text-encre shadow-[0_0_0_1px_rgb(var(--marque))]"
                    : "border-trait bg-surface hover:border-discret/40 hover:bg-relief/60",
                  enErreur && !actif && "border-danger/40")}>
                <input type={multiple ? "checkbox" : "radio"} name={q.code} value={c.valeur} checked={actif}
                  onChange={() => basculer(c.valeur)} className="peer sr-only" />
                <span className={cx("grid h-5 w-5 shrink-0 place-items-center border-2 transition peer-focus-visible:ring-2 peer-focus-visible:ring-marque/40",
                  multiple ? "rounded-md" : "rounded-full", actif ? "border-marque bg-marque text-white dark:text-[#04140c]" : "border-trait bg-surface")}>
                  {actif && (multiple ? <Check className="h-3 w-3" strokeWidth={3.5} /> : <span className="h-2 w-2 rounded-full bg-white dark:bg-[#04140c]" />)}
                </span>
                <span className="leading-snug">{c.libelle}</span>
              </label>
            );
          })}
        </div>
        <div className="mt-2"><MessageChamp id={`${id}-m`} erreurs={erreurs} aide={q.aide} /></div>
      </fieldset>
    );
  }

  const texte = (valeur as string) ?? "";
  if (q.type === "texte_long") {
    return (
      <div className="flex flex-col gap-2">
        <Etiquette htmlFor={id} code={q.code} obligatoire={q.obligatoire}>{q.libelle}</Etiquette>
        <textarea id={id} value={texte} onChange={(e) => changer(e.target.value)} rows={4} maxLength={5000}
          aria-invalid={enErreur} className={cx(bordure, "min-h-[120px] resize-y py-3 leading-relaxed")} />
        <div className="flex justify-between gap-4"><MessageChamp erreurs={erreurs} aide={q.aide} />
          <span className="ml-auto shrink-0 text-xs text-discret chiffres">{texte.length} / 5 000</span></div>
      </div>
    );
  }

  const estNombre = numerique(q.type);
  const brut = estNombre ? Number(nettoyerNombre(texte)) : NaN;
  const apercu = q.type === "montant" && texte && !Number.isNaN(brut) && brut >= 10000 ? `≈ ${compacte(brut)}` : null;
  const suffixe = q.type === "pourcentage" ? "%" : q.unite ?? (q.type === "montant" ? t("monnaie locale") : undefined);

  return (
    <div className="flex flex-col gap-2">
      <Etiquette htmlFor={id} code={q.code} obligatoire={q.obligatoire}>{q.libelle}</Etiquette>
      <div className={cx("relative", estNombre && "max-w-sm")}>
        <input id={id} value={texte} onChange={(e) => changer(e.target.value)} aria-invalid={enErreur}
          type={q.type === "url" ? "url" : "text"} inputMode={q.type === "entier" ? "numeric" : estNombre ? "decimal" : undefined}
          placeholder={q.type === "url" ? "https://" : q.annee ? t("AAAA") : ""}
          className={cx(bordure, "h-12", estNombre && "chiffres text-right")} style={suffixe ? { paddingRight: `${suffixe.length * 7.5 + 28}px` } : undefined} />
        {suffixe && <span className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-[13px] text-discret">{suffixe}</span>}
      </div>
      <div className="flex gap-3">
        <MessageChamp erreurs={erreurs} aide={q.aide ?? (q.min !== undefined && q.max !== undefined && !q.annee ? t("Entre {min} et {max}.", { min: nombre(q.min), max: nombre(q.max) }) : undefined)} />
        {apercu && !erreurs?.length && <span className="text-[13px] font-medium text-marque">{apercu}</span>}
      </div>
    </div>
  );
}

/* ---------- Tableau à lignes répétables ---------- */

function ChampTableau({ question: q, valeur, erreurs, changer }: {
  question: Question; valeur: Valeur; erreurs?: string[]; changer: (v: Valeur) => void;
}) {
  const colonnes = q.colonnes ?? [];
  const lignes = (Array.isArray(valeur) ? valeur : []) as LigneTableau[];
  const vide = () => Object.fromEntries(colonnes.map((c) => [c.code, ""])) as LigneTableau;
  const affichees = lignes.length ? lignes : [vide()];
  const maj = (i: number, code: string, v: string) =>
    changer(affichees.map((l, j) => (j === i ? { ...l, [code]: v } : l)));
  return (
    <div className="flex flex-col gap-3">
      <Etiquette code={q.code} obligatoire={q.obligatoire}>{q.libelle}</Etiquette>
      <div className="overflow-x-auto rounded-xl border border-trait">
        <table className="w-full min-w-[520px] text-sm">
          <thead className="bg-relief/60 text-left text-xs text-discret">
            <tr>{colonnes.map((c) => <th key={c.code} className="px-3 py-2 font-medium">{c.libelle}</th>)}<th className="w-10" /></tr>
          </thead>
          <tbody className="divide-y divide-trait">
            {affichees.map((l, i) => (
              <tr key={i}>
                {colonnes.map((c) => (
                  <td key={c.code} className="p-1.5">
                    <input value={String(l[c.code] ?? "")} onChange={(e) => maj(i, c.code, e.target.value)}
                      aria-label={t("{colonne}, ligne {n}", { colonne: c.libelle, n: i + 1 })} inputMode={c.type === "nombre" ? "decimal" : undefined}
                      className={cx("h-10 w-full rounded-lg border border-transparent bg-transparent px-2.5 focus:border-marque focus:bg-surface focus:outline-none",
                        c.type === "nombre" && "chiffres text-right")} />
                  </td>
                ))}
                <td className="p-1.5">
                  <button type="button" onClick={() => changer(affichees.filter((_, j) => j !== i))} aria-label={t("Supprimer la ligne {n}", { n: i + 1 })}
                    className="grid h-9 w-9 place-items-center rounded-lg text-discret hover:bg-danger-doux hover:text-danger"><X className="h-4 w-4" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3">
        <Bouton taille="sm" variante="secondaire" disabled={affichees.length >= 20} onClick={() => changer([...affichees, vide()])}>
          <Plus className="h-4 w-4" /> {t("Ajouter une ligne")}
        </Bouton>
        <span className="text-xs text-discret">{affichees.length} / 20</span>
      </div>
      <MessageChamp erreurs={erreurs} aide={q.aide} />
    </div>
  );
}

/* ---------- Pièce jointe ---------- */

const extensions = (accept: string) => accept.split(",").map((e) => e.trim().toLowerCase());

export function DepotFichier({ question: q, piece, erreurs, effacerErreur }: {
  question: Question; piece?: Piece; erreurs?: string[]; effacerErreur: () => void;
}) {
  const { jeton, questionnaire, mettreAJour, setSauvegarde } = useFormulaire();
  const toast = useToast();
  const champ = useRef<HTMLInputElement>(null);
  const [survol, setSurvol] = useState(false);
  const [progres, setProgres] = useState<number | null>(null);
  const [erreurLocale, setErreurLocale] = useState<string>();
  const { accept, taille_max } = questionnaire.fichiers;
  const url = urlApi(jeton, `pieces/${q.code}/`);

  async function deposer(f: File) {
    const ext = "." + (f.name.split(".").pop() ?? "").toLowerCase();
    if (!extensions(accept).includes(ext)) return setErreurLocale(t("Format non accepté : PDF, Word, Excel, JPG ou PNG."));
    if (f.size > taille_max) return setErreurLocale(t("Fichier trop volumineux ({taille}). Maximum : {max}.", { taille: taille(f.size), max: taille(taille_max) }));
    setErreurLocale(undefined);
    effacerErreur();
    setProgres(0);
    setSauvegarde("enregistrement");
    try {
      mettreAJour(await envoyerFichier<ReponsePublique>(url, f, setProgres));
      setSauvegarde("enregistre");
      toast("succes", t("« {nom} » déposé.", { nom: f.name }));
    } catch (e) {
      setSauvegarde("erreur");
      setErreurLocale((e as ErreurApi).message);
    } finally {
      setProgres(null);
    }
  }

  async function supprimer() {
    try {
      mettreAJour(await api.delete<ReponsePublique>(url));
      toast("info", t("Fichier supprimé."));
    } catch (e) {
      toast("erreur", (e as ErreurApi).message);
    }
  }

  const messages = erreurLocale ? [erreurLocale] : erreurs;

  return (
    <div className="flex flex-col gap-3">
      <Etiquette code={q.code} obligatoire={q.obligatoire}>{q.libelle}</Etiquette>
      <input ref={champ} type="file" accept={accept} className="sr-only" tabIndex={-1} aria-hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) deposer(f); e.target.value = ""; }} />

      <AnimatePresence mode="wait" initial={false}>
        {piece && progres === null ? (
          <motion.div key="piece" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex flex-wrap items-center gap-4 rounded-xl border border-succes/30 bg-succes-doux/50 p-4">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-surface text-succes shadow-sm"><FileText className="h-5 w-5" /></span>
            <div className="min-w-0 flex-1">
              <a href={piece.url} className="block truncate font-medium text-encre hover:underline">{piece.nom}</a>
              <p className="text-xs text-discret">{taille(piece.taille)} · {t("déposé le {date}", { date: date(piece.date_depot, true) })}</p>
            </div>
            <div className="flex gap-1">
              <a href={piece.url} className="grid h-9 w-9 place-items-center rounded-lg text-discret hover:bg-surface hover:text-encre" aria-label={t("Télécharger")}><Download className="h-4 w-4" /></a>
              <Bouton variante="fantome" taille="sm" onClick={() => champ.current?.click()} aria-label={t("Remplacer")}><RefreshCw className="h-4 w-4" /></Bouton>
              <Bouton variante="fantome" taille="sm" onClick={supprimer} aria-label={t("Supprimer")} className="hover:text-danger"><Trash2 className="h-4 w-4" /></Bouton>
            </div>
          </motion.div>
        ) : (
          <motion.button key="zone" type="button" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => champ.current?.click()} disabled={progres !== null}
            onDragOver={(e) => { e.preventDefault(); setSurvol(true); }} onDragLeave={() => setSurvol(false)}
            onDrop={(e) => { e.preventDefault(); setSurvol(false); const f = e.dataTransfer.files?.[0]; if (f) deposer(f); }}
            className={cx("relative flex w-full flex-col items-center gap-2 overflow-hidden rounded-xl border-2 border-dashed px-6 py-8 text-center transition",
              survol ? "border-marque bg-marque-doux/60" : messages?.length ? "border-danger/50 bg-danger-doux/30" : "border-trait bg-relief/40 hover:border-marque/50 hover:bg-marque-doux/30")}>
            {progres !== null ? (
              <>
                <span className="text-sm font-medium">{t("Envoi en cours… {n} %", { n: Math.round(progres * 100) })}</span>
                <div className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-trait">
                  <motion.div className="h-full bg-marque" animate={{ width: `${progres * 100}%` }} />
                </div>
              </>
            ) : (
              <>
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface text-marque shadow-sm"><UploadCloud className="h-5 w-5" /></span>
                <span className="text-sm"><span className="font-semibold text-marque">{t("Choisissez un fichier")}</span> {t("ou glissez-le ici")}</span>
                <span className="text-xs text-discret">{t("PDF, Word, Excel, JPG ou PNG · {max} maximum", { max: taille(taille_max) })}</span>
              </>
            )}
          </motion.button>
        )}
      </AnimatePresence>
      <MessageChamp erreurs={messages} />
    </div>
  );
}
