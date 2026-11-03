import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Pencil, Plus } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { date } from "@/lib/format";
import { Campagne } from "@/lib/types";
import { Badge, Bouton, Carte, Champ, Dialogue, Progression, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, useGestion } from "./Gestion";

type Brouillon = { nom: string; exercice: string; date_ouverture: string; date_cloture: string; active: boolean };
const vide: Brouillon = { nom: "", exercice: String(new Date().getFullYear() - 1), date_ouverture: "", date_cloture: "", active: true };

export default function Campagnes() {
  const { choisirCampagne, moi } = useGestion();
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
    setEdition(c ? { id: c.id, valeurs: { nom: c.nom, exercice: String(c.exercice), date_ouverture: c.date_ouverture, date_cloture: c.date_cloture, active: c.active } } : { valeurs: vide });
  };
  const maj = (cle: keyof Brouillon, v: string | boolean) => setEdition((e) => e && { ...e, valeurs: { ...e.valeurs, [cle]: v } });
  const soumettre = (e: FormEvent) => { e.preventDefault(); if (edition) enregistrer.mutate(edition); };

  return (
    <>
      <EnTetePage titre="Campagnes" sous="Une campagne = un exercice de référence et une période de collecte. Une seule est active à la fois."
        actions={moi.administrateur && <Bouton variante="primaire" icone={<Plus className="h-4 w-4" />} onClick={() => ouvrir()}>Nouvelle campagne</Bouton>} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {q.isLoading && [0, 1, 2].map((i) => <Squelette key={i} className="h-44 rounded-2xl" />)}
        {q.data?.campagnes.map((c) => {
          const taux = c.total ? Math.round((100 * (c.soumis ?? 0)) / c.total) : 0;
          return (
            <Carte key={c.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <div><p className="font-semibold tracking-tight">{c.nom}</p><p className="text-sm text-discret">Exercice {c.exercice}</p></div>
                {c.active ? <Badge ton="succes">Active</Badge> : <Badge>Archivée</Badge>}
              </div>
              <p className="mt-4 flex items-center gap-2 text-sm text-discret"><CalendarRange className="h-4 w-4" />{date(c.date_ouverture)} → {date(c.date_cloture)}</p>
              <div className="mt-auto pt-5">
                <div className="mb-1.5 flex justify-between text-xs text-discret"><span>{c.soumis} / {c.total} réponses</span><span className="chiffres font-medium text-encre">{taux} %</span></div>
                <Progression valeur={taux} ton={taux === 100 ? "succes" : "marque"} />
              </div>
              {moi.administrateur && <Bouton taille="sm" variante="fantome" className="mt-4 self-start" icone={<Pencil className="h-3.5 w-3.5" />} onClick={() => ouvrir(c)}>Modifier</Bouton>}
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
