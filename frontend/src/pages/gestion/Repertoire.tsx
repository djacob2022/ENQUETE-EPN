import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, FileSpreadsheet, History, ListTree, Plus, Search, Trash2, UploadCloud } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, envoyerFichier, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { EPN } from "@/lib/types";
import { Badge, Bouton, Carte, Champ, cx, Dialogue, Liste, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, peut, useGestion } from "./Gestion";

type Fiche = Omit<EPN, "id" | "actif" | "etat_libelle"> & { id?: number };
const FICHE_VIDE: Fiche = { nom: "", sigle: "", categorie: "EPA", tutelle: "", region: "", secteur: "", email_contact: "", etat: "actif" };
interface Reference { id: number; type: string; libelle: string; utilisations: number }

export default function Repertoire() {
  const client = useQueryClient();
  const { moi } = useGestion();
  const gerer = peut(moi, "gerer_repertoire");
  const [fiche, setFiche] = useState<Fiche | null>(null);
  const [etat, setEtat] = useState("");
  const toast = useToast();
  const champ = useRef<HTMLInputElement>(null);
  const [recherche, setRecherche] = useState("");
  const [progres, setProgres] = useState<number | null>(null);
  const [erreurs, setErreurs] = useState<string[]>([]);
  const [survol, setSurvol] = useState(false);
  const q = useQuery({ queryKey: ["epn"], queryFn: () => api.get<{ epn: EPN[] }>("/api/gestion/epn/") });

  const lignes = useMemo(() => {
    const t = recherche.toLowerCase().trim();
    return (q.data?.epn ?? []).filter((e) => (!etat || e.etat === etat)
      && (!t || [e.nom, e.sigle, e.tutelle, e.email_contact, e.secteur].some((x) => x.toLowerCase().includes(t))));
  }, [q.data, recherche, etat]);

  async function importer(f: File) {
    if (!f.name.toLowerCase().endsWith(".xlsx")) return toast("erreur", "Choisissez un fichier Excel (.xlsx).");
    setProgres(0);
    try {
      const r = await envoyerFichier<{ crees: number; mis_a_jour: number; erreurs: string[] }>("/api/gestion/epn/", f, setProgres);
      setErreurs(r.erreurs);
      toast("succes", `Import terminé : ${r.crees} créé(s), ${r.mis_a_jour} mis à jour.`);
      ["epn", "options", "liens", "tableau"].forEach((k) => client.invalidateQueries({ queryKey: [k] }));
    } catch (e) {
      toast("erreur", (e as ErreurApi).message);
    } finally {
      setProgres(null);
    }
  }

  return (
    <>
      <EnTetePage titre="Répertoire des EPN" sous={moi.perimetre
        ? `${q.data?.epn.length ?? "…"} établissements de votre périmètre : ${moi.perimetre.join(", ")}`
        : `${q.data?.epn.length ?? "…"} établissements · la liste qui reçoit les liens de chaque campagne`}
        actions={gerer && <Bouton variante="primaire" icone={<Plus className="h-4 w-4" />} onClick={() => setFiche(FICHE_VIDE)}>Nouvel établissement</Bouton>} />
      <div className={cx("grid gap-6", gerer && "xl:grid-cols-[1fr_340px]")}>
        <Carte className="overflow-hidden">
          <div className="flex flex-wrap gap-3 border-b border-trait p-4">
            <Liste value={etat} onChange={(e) => setEtat(e.target.value)} aria-label="Statut" className="w-44">
              <option value="">Tous les statuts</option>
              <option value="actif">Actifs</option><option value="liquidation">En liquidation</option><option value="dissous">Dissous</option>
            </Liste>
            <label className="relative block min-w-[240px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-discret" />
              <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher par nom, sigle, tutelle ou e-mail" aria-label="Rechercher"
                className="h-10 w-full rounded-[10px] border border-trait bg-surface pl-9 pr-3 text-sm focus:border-marque focus:shadow-anneau focus:outline-none" />
            </label>
          </div>
          <div className="defilement-fin overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-relief/50 text-left text-xs uppercase tracking-wider text-discret">
                <tr>{["Établissement", "Catégorie", "Tutelle", "Région · secteur", "Point focal"].map((h, i) => <th key={h} className={cx("px-4 py-3 font-medium", i === 0 && "pl-6")}>{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-trait">
                {q.isLoading && Array.from({ length: 6 }, (_, i) => <tr key={i}><td colSpan={5} className="px-6 py-3"><Squelette className="h-8" /></td></tr>)}
                {lignes.map((e) => (
                  <tr key={e.id} className="cursor-pointer hover:bg-relief/40" onClick={() => setFiche({ ...e })}>
                    <td className="py-3 pl-6 pr-4"><p className="font-medium">{e.nom}{e.etat !== "actif" && <span className="ml-2"><Badge ton="alerte">{e.etat_libelle}</Badge></span>}</p><p className="text-xs text-discret">{e.sigle}</p></td>
                    <td className="px-4"><Badge ton={e.categorie === "EPIC" ? "marque" : "neutre"}>{e.categorie}</Badge></td>
                    <td className="px-4 text-discret">{e.tutelle}</td>
                    <td className="px-4 text-discret">{e.region || "—"}{e.secteur && <span className="block text-xs">{e.secteur}</span>}</td>
                    <td className="px-4 pr-6 text-discret">{e.email_contact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!q.isLoading && !lignes.length && <Vide icone={<Building2 className="h-5 w-5" />} titre="Aucun établissement" texte="Importez la liste des EPN depuis un fichier Excel." />}
          </div>
        </Carte>

        {gerer && (
        <div className="space-y-4">
          <Carte className="p-5">
            <h2 className="font-semibold tracking-tight">Importer depuis Excel</h2>
            <p className="mt-1 text-sm text-discret">Un établissement déjà présent (même dénomination) est mis à jour.</p>
            <input ref={champ} type="file" accept=".xlsx" className="sr-only" tabIndex={-1} aria-hidden
              onChange={(e) => { const f = e.target.files?.[0]; if (f) importer(f); e.target.value = ""; }} />
            <button type="button" onClick={() => champ.current?.click()} disabled={progres !== null}
              onDragOver={(e) => { e.preventDefault(); setSurvol(true); }} onDragLeave={() => setSurvol(false)}
              onDrop={(e) => { e.preventDefault(); setSurvol(false); const f = e.dataTransfer.files?.[0]; if (f) importer(f); }}
              className={cx("mt-4 flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition",
                survol ? "border-marque bg-marque-doux/60" : "border-trait bg-relief/40 hover:border-marque/50")}>
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-surface text-marque shadow-sm"><UploadCloud className="h-5 w-5" /></span>
              <span className="text-sm">{progres !== null ? `Import… ${Math.round(progres * 100)} %` : <><span className="font-semibold text-marque">Choisissez</span> ou glissez un .xlsx</>}</span>
            </button>
            {erreurs.length > 0 && (
              <div className="mt-4 rounded-xl border border-alerte/30 bg-alerte-doux p-3 text-xs text-alerte">
                <p className="font-semibold">{erreurs.length} ligne(s) ignorée(s)</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-4">{erreurs.slice(0, 6).map((e) => <li key={e}>{e}</li>)}</ul>
              </div>
            )}
          </Carte>
          <Carte className="p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet className="h-4 w-4 text-succes" /> Format attendu</h3>
            <p className="mt-1 text-xs text-discret">Première ligne = en-têtes, puis une ligne par établissement :</p>
            <ol className="mt-3 space-y-1.5 text-sm">
              {["Dénomination", "Sigle", "Catégorie (EPA, EPIC, AUTRE)", "Tutelle", "Région", "E-mail du point focal", "Secteur (facultatif)", "Statut : Actif, En liquidation, Dissous (facultatif)"].map((c, i) => (
                <li key={c} className="flex items-center gap-2"><span className="grid h-5 w-5 place-items-center rounded bg-relief font-mono text-[11px] text-discret">{String.fromCharCode(65 + i)}</span>{c}</li>
              ))}
            </ol>
          </Carte>
          <ListesReference />
        </div>
        )}
      </div>
      <FicheEPN fiche={fiche} fermer={() => setFiche(null)} modifiable={gerer} />
    </>
  );
}

/* ---------- Fiche d'un établissement et historique (F-07, F-09) ---------- */

function FicheEPN({ fiche, fermer, modifiable }: { fiche: Fiche | null; fermer: () => void; modifiable: boolean }) {
  const { options } = useGestion();
  const client = useQueryClient();
  const toast = useToast();
  const [f, setF] = useState<Fiche | null>(null);
  const [erreurs, setErreurs] = useState<Record<string, string[]>>({});
  useEffect(() => { setF(fiche); setErreurs({}); }, [fiche]);
  const detail = useQuery({
    queryKey: ["epn-fiche", fiche?.id],
    queryFn: () => api.get<EPN & { historique: { date: string; auteur: string; creation: boolean; changements?: Record<string, [string, string]> }[] }>(`/api/gestion/epn/${fiche!.id}/`),
    enabled: !!fiche?.id,
  });
  const enregistrer = useMutation({
    mutationFn: (x: Fiche) => x.id ? api.put<EPN>(`/api/gestion/epn/${x.id}/`, x) : api.post<EPN>("/api/gestion/epn/", x),
    onSuccess: (e) => { ["epn", "options", "epn-fiche"].forEach((k) => client.invalidateQueries({ queryKey: [k] })); toast("succes", `Fiche de ${e.nom} enregistrée.`); fermer(); },
    onError: (e: ErreurApi) => { setErreurs(e.erreurs ?? {}); if (!e.erreurs) toast("erreur", e.message); },
  });
  if (!f) return <Dialogue ouvert={false} fermer={fermer} titre=""><div /></Dialogue>;
  const maj = (p: Partial<Fiche>) => setF((x) => x && { ...x, ...p });
  const soumettre = (e: FormEvent) => { e.preventDefault(); enregistrer.mutate(f); };
  const lecture = !modifiable;
  return (
    <Dialogue ouvert fermer={fermer} titre={f.id ? f.nom || "Fiche" : "Nouvel établissement"}>
      <form onSubmit={soumettre} className="space-y-4" noValidate>
        <Champ libelle="Dénomination" required disabled={lecture} value={f.nom} erreurs={erreurs.nom} onChange={(e) => maj({ nom: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Champ libelle="Sigle" disabled={lecture} value={f.sigle} onChange={(e) => maj({ sigle: e.target.value })} />
          <Liste libelle="Catégorie" disabled={lecture} value={f.categorie} onChange={(e) => maj({ categorie: e.target.value })}>
            {options.categories.map((c) => <option key={c.valeur} value={c.valeur}>{c.libelle}</option>)}
          </Liste>
          <Champ libelle="Tutelle technique" required disabled={lecture} list="tutelles" value={f.tutelle} erreurs={erreurs.tutelle} onChange={(e) => maj({ tutelle: e.target.value })} />
          <Champ libelle="Région" disabled={lecture} list="regions" value={f.region} onChange={(e) => maj({ region: e.target.value })} />
          <Champ libelle="Secteur d'activité" disabled={lecture} list="secteurs" value={f.secteur} onChange={(e) => maj({ secteur: e.target.value })} />
          <Liste libelle="Statut" disabled={lecture} value={f.etat} onChange={(e) => maj({ etat: e.target.value as Fiche["etat"] })}>
            {options.etats.map((c) => <option key={c.valeur} value={c.valeur}>{c.libelle}</option>)}
          </Liste>
        </div>
        <Champ libelle="E-mail du point focal" type="email" required disabled={lecture} value={f.email_contact} erreurs={erreurs.email_contact} onChange={(e) => maj({ email_contact: e.target.value })}
          aide="Les liens personnels sont envoyés à cette adresse." />
        <datalist id="tutelles">{options.tutelles.map((t) => <option key={t} value={t} />)}</datalist>
        <datalist id="regions">{options.regions.map((t) => <option key={t} value={t} />)}</datalist>
        <datalist id="secteurs">{options.secteurs.map((t) => <option key={t} value={t} />)}</datalist>
        {f.id && detail.data && detail.data.historique.length > 0 && (
          <div className="rounded-xl border border-trait p-3">
            <p className="flex items-center gap-2 text-sm font-semibold"><History className="h-4 w-4 text-discret" /> Historique des modifications</p>
            <ul className="mt-2 space-y-1.5 text-xs text-discret">
              {detail.data.historique.map((h, i) => (
                <li key={i}><span className="font-medium text-encre">{date(h.date, true)} · {h.auteur}</span> — {h.creation ? "création" :
                  Object.entries(h.changements ?? {}).map(([k, [a, b]]) => `${k} : ${a || "∅"} → ${b || "∅"}`).join(" ; ") || "import"}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Bouton type="button" variante="fantome" onClick={fermer}>{lecture ? "Fermer" : "Annuler"}</Bouton>
          {!lecture && <Bouton type="submit" variante="primaire" chargement={enregistrer.isPending}>Enregistrer</Bouton>}
        </div>
      </form>
    </Dialogue>
  );
}

/* ---------- Listes de référence (F-08) ---------- */

function ListesReference() {
  const client = useQueryClient();
  const toast = useToast();
  const [type, setType] = useState("tutelle");
  const [libelle, setLibelle] = useState("");
  const q = useQuery({ queryKey: ["references"], queryFn: () => api.get<{ listes: { valeur: string; libelle: string }[]; references: Reference[] }>("/api/gestion/references/") });
  const rafraichir = () => ["references", "options"].forEach((k) => client.invalidateQueries({ queryKey: [k] }));
  const ajouter = useMutation({
    mutationFn: () => api.post("/api/gestion/references/", { type, libelle }),
    onSuccess: () => { setLibelle(""); rafraichir(); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  const retirer = useMutation({ mutationFn: (id: number) => api.delete(`/api/gestion/references/${id}/`), onSuccess: rafraichir });
  const liste = (q.data?.references ?? []).filter((r) => r.type === type);
  return (
    <Carte className="p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold"><ListTree className="h-4 w-4 text-marque" /> Listes de référence</h3>
      <p className="mt-1 text-xs text-discret">Proposées à la saisie des fiches et dans les filtres.</p>
      <div className="mt-3 flex gap-1">
        {q.data?.listes.map((l) => (
          <button key={l.valeur} onClick={() => setType(l.valeur)} className={cx("rounded-lg px-2.5 py-1 text-xs font-medium", type === l.valeur ? "bg-marque text-white dark:text-[#04140c]" : "bg-relief text-discret")}>{l.libelle}</button>
        ))}
      </div>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (libelle.trim()) ajouter.mutate(); }}>
        <input value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ajouter un libellé" aria-label="Nouveau libellé"
          className="h-9 min-w-0 flex-1 rounded-lg border border-trait bg-surface px-3 text-sm focus:border-marque focus:outline-none" />
        <Bouton type="submit" taille="sm" chargement={ajouter.isPending} aria-label="Ajouter"><Plus className="h-4 w-4" /></Bouton>
      </form>
      <ul className="defilement-fin mt-3 max-h-56 space-y-1 overflow-y-auto">
        {liste.map((r) => (
          <li key={r.id} className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm hover:bg-relief">
            <span className="flex-1">{r.libelle}</span><span className="text-xs text-discret">{r.utilisations} EPN</span>
            <button onClick={() => retirer.mutate(r.id)} aria-label={`Retirer ${r.libelle}`} className="text-discret hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button>
          </li>
        ))}
        {!liste.length && <li className="px-2 py-2 text-xs text-discret">Liste vide : les valeurs déjà utilisées dans le répertoire restent proposées.</li>}
      </ul>
    </Carte>
  );
}
