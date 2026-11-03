import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, FileSpreadsheet, Search, UploadCloud } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { api, envoyerFichier, ErreurApi } from "@/lib/api";
import { EPN } from "@/lib/types";
import { Badge, Carte, cx, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, useGestion } from "./Gestion";

export default function Repertoire() {
  const client = useQueryClient();
  const { moi } = useGestion();
  const toast = useToast();
  const champ = useRef<HTMLInputElement>(null);
  const [recherche, setRecherche] = useState("");
  const [progres, setProgres] = useState<number | null>(null);
  const [erreurs, setErreurs] = useState<string[]>([]);
  const [survol, setSurvol] = useState(false);
  const q = useQuery({ queryKey: ["epn"], queryFn: () => api.get<{ epn: EPN[] }>("/api/gestion/epn/") });

  const lignes = useMemo(() => {
    const t = recherche.toLowerCase().trim();
    return (q.data?.epn ?? []).filter((e) => !t || [e.nom, e.sigle, e.tutelle, e.email_contact].some((x) => x.toLowerCase().includes(t)));
  }, [q.data, recherche]);

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
        : `${q.data?.epn.length ?? "…"} établissements · la liste qui reçoit les liens de chaque campagne`} />
      <div className={cx("grid gap-6", moi.administrateur && "xl:grid-cols-[1fr_340px]")}>
        <Carte className="overflow-hidden">
          <div className="border-b border-trait p-4">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-discret" />
              <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher par nom, sigle, tutelle ou e-mail" aria-label="Rechercher"
                className="h-10 w-full rounded-[10px] border border-trait bg-surface pl-9 pr-3 text-sm focus:border-marque focus:shadow-anneau focus:outline-none" />
            </label>
          </div>
          <div className="defilement-fin overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-relief/50 text-left text-xs uppercase tracking-wider text-discret">
                <tr>{["Établissement", "Catégorie", "Tutelle", "Région", "Point focal"].map((h, i) => <th key={h} className={cx("px-4 py-3 font-medium", i === 0 && "pl-6")}>{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-trait">
                {q.isLoading && Array.from({ length: 6 }, (_, i) => <tr key={i}><td colSpan={5} className="px-6 py-3"><Squelette className="h-8" /></td></tr>)}
                {lignes.map((e) => (
                  <tr key={e.id} className="hover:bg-relief/40">
                    <td className="py-3 pl-6 pr-4"><p className="font-medium">{e.nom}{!e.actif && <span className="ml-2"><Badge>inactif</Badge></span>}</p><p className="text-xs text-discret">{e.sigle}</p></td>
                    <td className="px-4"><Badge ton={e.categorie === "EPIC" ? "marque" : "neutre"}>{e.categorie}</Badge></td>
                    <td className="px-4 text-discret">{e.tutelle}</td>
                    <td className="px-4 text-discret">{e.region || "—"}</td>
                    <td className="px-4 pr-6 text-discret">{e.email_contact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!q.isLoading && !lignes.length && <Vide icone={<Building2 className="h-5 w-5" />} titre="Aucun établissement" texte="Importez la liste des EPN depuis un fichier Excel." />}
          </div>
        </Carte>

        {moi.administrateur && (
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
              {["Dénomination", "Sigle", "Catégorie (EPA, EPIC, AUTRE)", "Tutelle", "Région", "E-mail du point focal"].map((c, i) => (
                <li key={c} className="flex items-center gap-2"><span className="grid h-5 w-5 place-items-center rounded bg-relief font-mono text-[11px] text-discret">{String.fromCharCode(65 + i)}</span>{c}</li>
              ))}
            </ol>
          </Carte>
        </div>
        )}
      </div>
    </>
  );
}
