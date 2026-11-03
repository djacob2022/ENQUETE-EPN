import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { api } from "@/lib/api";
import { Questionnaire, TypeQuestion } from "@/lib/types";
import { Badge, Bouton, Carte, Squelette } from "@/ui";
import { EnTetePage } from "./Gestion";

const TYPES: Record<TypeQuestion, string> = {
  texte: "Texte", texte_long: "Texte libre", url: "Adresse web", entier: "Nombre", montant: "Montant", pourcentage: "Pourcentage",
  choix: "Un choix", choix_multiple: "Plusieurs choix", oui_non: "Oui / non", fichier: "Fichier joint",
};

export default function QuestionnaireApercu() {
  const q = useQuery({ queryKey: ["questionnaire"], queryFn: () => api.get<Questionnaire>("/api/questionnaire/"), staleTime: Infinity });
  const nb = q.data?.modules.reduce((n, m) => n + m.questions.length, 0);
  return (
    <>
      <EnTetePage titre="Questionnaire" sous={q.data ? `${q.data.modules.length} rubriques · ${nb} questions — le formulaire adressé aux établissements` : "…"}
        actions={<Bouton icone={<Printer className="h-4 w-4" />} onClick={() => window.print()} className="pas-imprimer">Imprimer / PDF</Bouton>} />
      {!q.data ? <Squelette className="h-96 rounded-2xl" /> : (
        <div className="space-y-5">
          {q.data.modules.map((m) => (
            <Carte key={m.code} className="overflow-hidden break-inside-avoid">
              <div className="border-b border-trait px-6 py-4">
                <h2 className="flex items-baseline gap-3 font-semibold tracking-tight"><span className="font-mono text-sm text-discret">{m.code}</span>{m.titre}</h2>
                {m.intro && <p className="mt-1 text-sm text-discret">{m.intro}</p>}
              </div>
              <ol className="divide-y divide-trait">
                {m.questions.map((x) => (
                  <li key={x.code} className="flex flex-wrap items-start gap-x-4 gap-y-2 px-6 py-3 text-sm">
                    <span className="w-10 shrink-0 font-mono text-xs text-discret">{x.code}</span>
                    <div className="min-w-[240px] flex-1">
                      <p className="font-medium">{x.libelle}{x.obligatoire && <span className="ml-0.5 text-danger">*</span>}</p>
                      {x.choix && <p className="mt-1 text-xs text-discret">{x.choix.map((c) => c.libelle).join(" · ")}</p>}
                    </div>
                    <Badge>{TYPES[x.type]}{x.unite ? ` (${x.unite})` : ""}</Badge>
                  </li>
                ))}
              </ol>
            </Carte>
          ))}
        </div>
      )}
    </>
  );
}
