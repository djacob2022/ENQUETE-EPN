const nf = new Intl.NumberFormat("fr-FR");
const nf1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 });

export const nombre = (n: number | null | undefined) => (n === null || n === undefined ? "—" : nf.format(n));
export const decimal = (n: number | null | undefined) => (n === null || n === undefined ? "—" : nf1.format(n));
export const compacte = (n: number | null | undefined) => (n === null || n === undefined ? "—" : compact.format(n));
export const pourcent = (n: number | null | undefined) => (n === null || n === undefined ? "—" : `${nf1.format(n)} %`);

export function date(iso: string | null | undefined, avecHeure = false) {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  return d.toLocaleDateString("fr-FR", avecHeure
    ? { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "long", year: "numeric" });
}

export function ilYa(iso: string | null | undefined) {
  if (!iso) return "—";
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "à l'instant";
  const rtf = new Intl.RelativeTimeFormat("fr", { numeric: "auto" });
  if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
  if (s < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  return rtf.format(-Math.round(s / 86400), "day");
}

export function joursRestants(iso: string) {
  const fin = new Date(iso + "T23:59:59").getTime();
  return Math.ceil((fin - Date.now()) / 86400000);
}

export const taille = (o: number) =>
  o < 1024 ? `${o} o` : o < 1048576 ? `${nf1.format(o / 1024)} Ko` : `${nf1.format(o / 1048576)} Mo`;

export const initiales = (texte: string) =>
  texte.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]?.toUpperCase()).join("") || "?";
