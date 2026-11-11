import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Pencil, Plus, ShieldCheck, ShieldOff, UserRound, UsersRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, ErreurApi } from "@/lib/api";
import { copier } from "@/lib/presse-papiers";
import { ilYa, initiales } from "@/lib/format";
import { Compte } from "@/lib/types";
import { Avatar, Badge, Bouton, Carte, Champ, cx, Dialogue, Liste, Squelette, useToast, Vide } from "@/ui";
import { EnTetePage, useGestion } from "./Gestion";

const DESCRIPTION_ROLES: Record<string, string> = {
  administrateur: "Crée les campagnes et le questionnaire, gère le répertoire, les comptes et valide les réponses.",
  superviseur: "Consulte, valide ou renvoie pour correction les réponses des EPN de sa tutelle, relance.",
  analyste: "Consulte tous les résultats, exporte, produit des statistiques. Ne modifie rien.",
  lecteur: "Consulte les tableaux de bord et statistiques agrégés, sans données nominatives.",
};

type Brouillon = { id?: number; email: string; prenom: string; nom: string; role: string; tutelles: string[]; actif: boolean };

/** Création des comptes, attribution des rôles et rattachement à une tutelle (F-04, F-06). */
export default function Comptes() {
  const { options, moi } = useGestion();
  const client = useQueryClient();
  const toast = useToast();
  const [edition, setEdition] = useState<Brouillon | null>(null);
  const q = useQuery({ queryKey: ["comptes"], queryFn: () => api.get<{ comptes: Compte[] }>("/api/gestion/comptes/") });
  const libelleRole = (r: string) => r === "super_administrateur" ? "Super-administrateur" : options.roles.find((x) => x.valeur === r)?.libelle ?? r;

  const signalerLien = async (lien: string | null, ok: boolean) => {
    if (ok || !lien) return;
    const copie = await copier(lien);
    toast("info", copie ? "L'e-mail n'a pas pu partir : le lien d'activation a été copié, transmettez-le à la personne." : `L'e-mail n'a pas pu partir. Lien : ${lien}`);
  };

  const enregistrer = useMutation({
    mutationFn: (b: Brouillon) => b.id ? api.put<Compte>(`/api/gestion/comptes/${b.id}/`, b)
      : api.post<Compte & { email_envoye: boolean; lien: string | null }>("/api/gestion/comptes/", b),
    onSuccess: async (c: Compte & { email_envoye?: boolean; lien?: string | null }, b) => {
      setEdition(null);
      client.invalidateQueries({ queryKey: ["comptes"] });
      toast("succes", b.id ? `Compte de ${c.email} mis à jour.` : `Compte créé : un lien d'activation a été envoyé à ${c.email}.`);
      if (!b.id) await signalerLien(c.lien ?? null, !!c.email_envoye);
    },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });
  const relancer = useMutation({
    mutationFn: (c: Compte) => api.post<{ email_envoye: boolean; lien: string | null }>(`/api/gestion/comptes/${c.id}/`),
    onSuccess: async (r, c) => { if (r.email_envoye) toast("succes", `Lien envoyé à ${c.email}.`); await signalerLien(r.lien, r.email_envoye); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  const reinit = useMutation({
    mutationFn: (id: number) => api.post<Compte>(`/api/gestion/comptes/${id}/`, { action: "reinitialiser_2fa" }),
    onSuccess: (c) => { client.invalidateQueries({ queryKey: ["comptes"] }); toast("succes", `Double authentification de ${c.email} réinitialisée.`); },
    onError: (e: ErreurApi) => toast("erreur", e.message),
  });

  const soumettre = (e: FormEvent) => { e.preventDefault(); if (edition) enregistrer.mutate(edition); };
  const maj = (p: Partial<Brouillon>) => setEdition((b) => b && { ...b, ...p });

  return (
    <>
      <EnTetePage titre="Comptes et rôles" sous="Chaque personne de l'équipe a son compte. Le rôle fixe ce qu'elle voit et ce qu'elle peut faire."
        actions={<Bouton variante="primaire" icone={<Plus className="h-4 w-4" />}
          onClick={() => setEdition({ email: "", prenom: "", nom: "", role: "superviseur", tutelles: [], actif: true })}>Nouveau compte</Bouton>} />

      <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {options.roles.map((r) => (
          <Carte key={r.valeur} className="p-4">
            <p className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="h-4 w-4 text-marque" />{r.libelle}</p>
            <p className="mt-1 text-[13px] text-discret">{DESCRIPTION_ROLES[r.valeur]}</p>
          </Carte>
        ))}
      </div>

      <Carte className="overflow-hidden">
        <div className="defilement-fin overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-relief/50 text-left text-xs uppercase tracking-wider text-discret">
              <tr><th className="px-6 py-3 font-medium">Personne</th><th className="px-4 py-3 font-medium">Rôle</th><th className="px-4 py-3 font-medium">Périmètre</th>
                <th className="px-4 py-3 font-medium">Dernière connexion</th><th className="px-4 py-3 pr-6" /></tr>
            </thead>
            <tbody className="divide-y divide-trait">
              {q.isLoading && <tr><td colSpan={5} className="p-6"><Squelette className="h-24" /></td></tr>}
              {q.data?.comptes.map((c) => (
                <tr key={c.id} className={cx(!c.actif && "opacity-55")}>
                  <td className="px-6 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar texte={initiales(`${c.prenom} ${c.nom}`.trim() || c.identifiant)} />
                      <div><p className="font-medium">{`${c.prenom} ${c.nom}`.trim() || c.identifiant}</p><p className="text-xs text-discret">{c.email || c.identifiant}</p></div>
                    </div>
                  </td>
                  <td className="px-4 py-3"><Badge ton={c.role === "lecteur" ? "neutre" : "marque"}>{libelleRole(c.role)}</Badge>
                    {!c.actif && <Badge ton="danger">Désactivé</Badge>}{!c.mot_de_passe_defini && c.actif && <Badge ton="alerte">À activer</Badge>}
                    {c.deux_facteurs && <Badge ton="succes"><ShieldCheck className="h-3 w-3" /> 2FA</Badge>}</td>
                  <td className="px-4 py-3 text-discret">{c.tutelles.length ? c.tutelles.join(", ") : "Tous les EPN"}</td>
                  <td className="px-4 py-3 text-discret">{c.derniere_connexion ? ilYa(c.derniere_connexion) : "Jamais"}</td>
                  <td className="px-4 py-3 pr-6 text-right">
                    {(!c.superutilisateur || moi.superutilisateur) && <div className="flex justify-end gap-1">
                      <Bouton taille="sm" variante="fantome" icone={<KeyRound className="h-3.5 w-3.5" />} chargement={relancer.isPending && relancer.variables?.id === c.id}
                        onClick={() => relancer.mutate(c)} disabled={!c.email || !c.actif}>{c.mot_de_passe_defini ? "Réinitialiser" : "Renvoyer l'activation"}</Bouton>
                      {c.deux_facteurs && <Bouton taille="sm" variante="fantome" icone={<ShieldOff className="h-3.5 w-3.5" />} chargement={reinit.isPending && reinit.variables === c.id}
                        onClick={() => reinit.mutate(c.id)} title="Téléphone perdu : la personne pourra réactiver la double authentification">Réinitialiser la 2FA</Bouton>}
                      <Bouton taille="sm" variante="fantome" aria-label={`Modifier ${c.email}`} onClick={() => setEdition({ id: c.id, email: c.email, prenom: c.prenom, nom: c.nom,
                        role: c.role === "super_administrateur" ? "administrateur" : c.role, tutelles: c.tutelles, actif: c.actif })}><Pencil className="h-4 w-4" /></Bouton>
                    </div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {q.data && !q.data.comptes.length && <Vide icone={<UsersRound className="h-5 w-5" />} titre="Aucun compte" />}
        </div>
      </Carte>

      <Dialogue ouvert={!!edition} fermer={() => setEdition(null)} titre={edition?.id ? "Modifier le compte" : "Nouveau compte"}
        description={edition?.id ? undefined : "La personne reçoit un lien pour choisir son mot de passe (valable 24 heures)."}>
        {edition && (
          <form onSubmit={soumettre} className="space-y-4" noValidate>
            <Champ libelle="Adresse e-mail" type="email" required disabled={!!edition.id} value={edition.email} onChange={(e) => maj({ email: e.target.value })} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Champ libelle="Prénom" value={edition.prenom} onChange={(e) => maj({ prenom: e.target.value })} />
              <Champ libelle="Nom" value={edition.nom} onChange={(e) => maj({ nom: e.target.value })} />
            </div>
            <Liste libelle="Rôle" value={edition.role} onChange={(e) => maj({ role: e.target.value })}>
              {options.roles.map((r) => <option key={r.valeur} value={r.valeur}>{r.libelle}</option>)}
            </Liste>
            <p className="-mt-2 text-xs text-discret">{DESCRIPTION_ROLES[edition.role]}</p>
            <fieldset>
              <legend className="mb-2 text-[13px] font-medium text-discret">Tutelles visibles {edition.role === "superviseur" ? "(au moins une)" : "(aucune = tous les EPN)"}</legend>
              <div className="defilement-fin flex max-h-44 flex-wrap gap-2 overflow-y-auto">
                {options.tutelles.map((t) => {
                  const coche = edition.tutelles.includes(t);
                  return (
                    <label key={t} className={cx("flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm", coche ? "border-marque bg-marque-doux" : "border-trait")}>
                      <input type="checkbox" checked={coche} className="accent-[rgb(var(--marque))]"
                        onChange={() => maj({ tutelles: coche ? edition.tutelles.filter((x) => x !== t) : [...edition.tutelles, t] })} />{t}
                    </label>
                  );
                })}
              </div>
            </fieldset>
            {edition.id && (
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-trait p-3 text-sm">
                <input type="checkbox" checked={edition.actif} onChange={(e) => maj({ actif: e.target.checked })} className="h-4 w-4 accent-[rgb(var(--marque))]" />
                <span><strong>Compte actif</strong><span className="block text-xs text-discret">Un compte désactivé ne peut plus se connecter ; son historique est conservé.</span></span>
              </label>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Bouton type="button" variante="fantome" onClick={() => setEdition(null)}>Annuler</Bouton>
              <Bouton type="submit" variante="primaire" icone={<UserRound className="h-4 w-4" />} chargement={enregistrer.isPending}>{edition.id ? "Enregistrer" : "Créer et envoyer le lien"}</Bouton>
            </div>
          </form>
        )}
      </Dialogue>
    </>
  );
}
