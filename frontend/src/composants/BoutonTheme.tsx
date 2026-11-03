import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { Bouton } from "@/ui";

export default function BoutonTheme() {
  const { sombre, basculer } = useTheme();
  return (
    <Bouton variante="fantome" taille="sm" onClick={basculer} aria-label={sombre ? "Passer en thème clair" : "Passer en thème sombre"}>
      {sombre ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Bouton>
  );
}
