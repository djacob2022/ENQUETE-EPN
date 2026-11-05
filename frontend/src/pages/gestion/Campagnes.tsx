import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CalendarRange, ClipboardList, Pencil, Plus, Target } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Campagne } from "@/lib/types";
import { Badge, Bouton, Carte, Champ, cx, Dialogue, Liste, Progression, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, peut, useGestion } from "./Gestion";

type Brouillon = {
  nom: string; exercice: string; date_ouverture: string; date_cloture: string; active: boolean;
  cible_tutelles: string; cible_categories: string; relances_auto: string; copier_de?: string;
};
const vide: Brouillon = { nom: "", exercice: String(new Date().getFullYear() - 1), date_ouverture: "", date_cloture: "", active: true,
  cible_tutelles: "", cible_categories: "", relances_auto: "-7,-2,1" };
const liste = (t: string) => t.split(",").map((x) => x.trim()).filter(Boolean);
const jours = (t: string) => liste(t).map((j) => (Number(j) < 0 ? `J${j}` : Number(j) === 0 ? "le jour J" : `J+${Number(j)}`)).join(", ");

export default function Campagnes() {
  const { choisirCampagne, moi, options } = useGestion();
  const naviguer = useNavigate();
  const admin = peut(moi, "gerer_campagnes");
  const client = useQueryClient();
  const toast = useToast();
  const [edition, setEdition] = useState<{ id?: number; valeurs: Brouillon } | null>(null);
  const [erreurs, setErreurs] = useState<Record<string, string[]>>({});
  const q = useQuery({ queryKey: ["campagnes"], queryFn: () => api.get<{ campagnes: Campagne[] }>("/api/gestion/campagnes/") });

  const enregistrer = useMutation({
    mutationFn: ({ id, valeurs }: { id?: number; valeurs: Brouillon }) => id
      ? api.put<Campagne>(`/api/gestion/campagnes/${id}/`, valeurs) : api.post<Campagne>("/api/gestion/campagnes/", valeurs),
    onSuccess: (c) => {
      setEdition(null);
      ["campagnes", "options"].forEach((k) => client.invalidateQueries({ queryKey: [k] }));
      if (c.active) choisirCampagne(c.id);
      toast("succes", `Campagne « ${c.nom} » enregistrée.`);
    },
    onError: (e: ErreurApi) => { setErreurs(e.erreurs ?? {}); if (!e.erreurs) toast("erreur", e.message); },
  });

  const ouvrir = (c?: Campagne) => {
    setErreurs({});
    setEdition(c ? { id: c.id, valeurs: { nom: c.nom, exercice: String(c.exercice), date_ouverture: c.date_ouverture, date_cloture: c.date_cloture,
      active: c.active, cible_tutelles: c.cible_tutelles, cible_categories: c.cible_categories, relances_auto: c.relances_auto } }
      : { valeurs: { ...vide, copier_de: String(q.data?.campagnes[0]?.id ?? "") } });
  };
  const maj = (cle: keyof Brouillon, v: string | boolean) => setEdition((e) => e && { ...e, valeurs: { ...e.valeurs, [cle]: v } });
  const basculer = (cle: "cible_tutelles" | "cible_categories", v: string) => {
    const l = liste(edition?.valeurs[cle] ?? "");
    maj(cle, (l.includes(v) ? l.filter((x) => x !== v) : [...l, v]).join(", "));
  };
  const soumettre = (e: FormEvent) => { e.preventDefault(); if (edition) enregistrer.mutate(edition); };

  return (
    <>
      <EnTetePage titre="Campagnes" sous="Une campagne = un exercice de référence et une période de collecte. Une seule est active à la fois."
        actions={admin && <Bouton variante="primaire" icone={<Plus className="h-4 w-4" />} onClick={() => ouvrir()}>Nouvelle campagne</Bouton>} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {q.isLoading && [0, 1, 2].map((i) => <Squelette key={i} className="h-44 rounded-2xl" />)}
        {q.data?.campagnes.map((c) => {
          const taux = c.total ? Math.round((100 * (c.soumis ?? 0)) / c.total) : 0;
          const cibles = [...liste(c.cible_tutelles), ...liste(c.cible_categories)];
          return (
            <Carte key={c.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div><p className="font-semibold tracking-tight">{c.nom}</p><p className="text-sm text-discret">Exercice {c.exercice}</p></div>
                {c.active ? <Badge ton="succes">Active</Badge> : <Badge>Archivée</Badge>}
              </div>
              <p className="mt-4 flex items-center gap-2 text-sm text-discret"><CalendarRange className="h-4 w-4" />{date(c.date_ouverture)} → {date(c.date_cloture)}</p>
              <p className="mt-1.5 flex items-center gap-2 text-sm text-discret"><Target className="h-4 w-4" />{cibles.length ? cibles.join(", ") : "Tous les EPN actifs"}</p>
              <p className="mt-1.5 flex items-center gap-2 text-sm text-discret"><BellRing className="h-4 w-4" />{c.relances_auto ? `Relances ${jours(c.relances_auto)}` : "Pas de relance automatique"}</p>
              <div className="mt-auto pt-5">
                <div className="mb-1.5 flex justify-between text-xs text-discret"><span>{c.soumis} / {c.total} envoyées · {c.validees ?? 0} validées</span><span className="chiffres font-medium text-encre">{taux} %</span></div>
                <Progression valeur={taux} ton={taux === 100 ? "succes" : "marque"} />
              </div>
              <div className="mt-4 flex flex-wrap gap-1">
                {admin && <Bouton taille="sm" variante="fantome" icone={<Pencil className="h-3.5 w-3.5" />} onClick={() => ouvrir(c)}>Modifier</Bouton>}
                <Bouton taille="sm" variante="fantome" icone={<ClipboardList className="h-3.5 w-3.5" />} onClick={() => { choisirCampagne(c.id); naviguer("/gestion/questionnaire"); }}>
                  Questionnaire v{c.version_questionnaire}</Bouton>
              </div>
            </Carte>
          );
        })}
      </div>
      {q.data && !q.data.campagnes.length && <Carte><Vide icone={<CalendarRange className="h-5 w-5" />} titre="Aucune campagne" texte="Créez la première campagne d'enquête." /></Carte>}

      <Dialogue ouvert={!!edition} fermer={() => setEdition(null)} titre={edition?.id ? "Modifier la campagne" : "Nouvelle campagne"}
        description="Les liens envoyés aux établissements ouvrent la campagne active, pendant sa période de collecte.">
        {edition && (
          <form onSubmit={soumettre} className="space-y-4" noValidate>
            <Champ libelle="Intitulé" required value={edition.valeurs.nom} erreurs={erreurs.nom} onChange={(e) => maj("nom", e.target.value)} placeholder="Enquête annuelle 2026" />
            <Champ libelle="Exercice de référence" required inputMode="numeric" value={edition.valeurs.exercice} erreurs={erreurs.exercice} onChange={(e) => maj("exercice", e.target.value)} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Champ libelle="Ouverture" type="date" required value={edition.valeurs.date_ouverture} erreurs={erreurs.date_ouverture} onChange={(e) => maj("date_ouverture", e.target.value)} />
              <Champ libelle="Clôture" type="date" required value={edition.valeurs.date_cloture} erreurs={erreurs.date_cloture} onChange={(e) => maj("date_cloture", e.target.value)} />
            </div>
            {!edition.id && (q.data?.campagnes.length ?? 0) > 0 && (
              <Liste libelle="Questionnaire de départ" value={edition.valeurs.copier_de} onChange={(e) => maj("copier_de", e.target.value)}>
                {q.data!.campagnes.map((c) => <option key={c.id} value={c.id}>Reprendre celui de « {c.nom} »</option>)}
              </Liste>
            )}
            <fieldset>
              <legend className="mb-2 text-[13px] font-medium text-discret">EPN ciblés (rien coché = tous les EPN actifs)</legend>
              <div className="flex flex-wrap gap-2">
                {options.categories.map((c) => <Puce key={c.valeur} coche={liste(edition.valeurs.cible_categories).includes(c.valeur)} onClick={() => basculer("cible_categories", c.valeur)}>{c.libelle}</Puce>)}
              </div>
              <div className="defilement-fin mt-2 flex max-h-32 flex-wrap gap-2 overflow-y-auto">
                {options.tutelles.map((t) => <Puce key={t} coche={liste(edition.valeurs.cible_tutelles).includes(t)} onClick={() => basculer("cible_tutelles", t)}>{t}</Puce>)}
              </div>
            </fieldset>
            <Champ libelle="Relances automatiques" value={edition.valeurs.relances_auto} erreurs={erreurs.relances_auto} onChange={(e) => maj("relances_auto", e.target.value)}
              aide={edition.valeurs.relances_auto ? `Jours par rapport à la clôture : ${jours(edition.valeurs.relances_auto)}. Vide = aucune.` : "Aucune relance automatique."} placeholder="-7,-2,1" />
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-trait p-3 text-sm">
              <input type="checkbox" checked={edition.valeurs.active} onChange={(e) => maj("active", e.target.checked)} className="h-4 w-4 accent-[rgb(var(--marque))]" />
              <span><strong>Campagne active</strong><span className="block text-xs text-discret">Désactive automatiquement l'ancienne campagne active.</span></span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Bouton type="button" variante="fantome" onClick={() => setEdition(null)}>Annuler</Bouton>
              <Bouton type="submit" variante="primaire" chargement={enregistrer.isPending}>Enregistrer</Bouton>
            </div>
          </form>
        )}
      </Dialogue>
    </>
  );
}

function Puce({ coche, onClick, children }: { coche: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={coche}
      className={cx("rounded-lg border px-3 py-1.5 text-sm transition", coche ? "border-marque bg-marque-doux font-medium" : "border-trait hover:bg-relief")}>{children}</button>
  );
}
