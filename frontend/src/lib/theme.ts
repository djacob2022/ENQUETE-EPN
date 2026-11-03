import { useEffect, useState } from "react";

export function useTheme() {
  const [sombre, setSombre] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", sombre);
    try { localStorage.setItem("theme", sombre ? "sombre" : "clair"); } catch { /* stockage indisponible */ }
  }, [sombre]);
  return { sombre, basculer: () => setSombre((s) => !s) };
}
