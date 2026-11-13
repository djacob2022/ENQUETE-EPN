import { langue } from "./langue";

// Formats suivant la langue choisie par le répondant (F-16) ; l'équipe d'enquête travaille en français.
const locale = () => (langue() === "en" ? "en-GB" : "fr-FR");
const cache = new Map<string, Intl.NumberFormat>();
function formateur(cle: string, options: Intl.NumberFormatOptions) {
  const k = `${locale()}|${cle}`;
  if (!cache.has(k)) cache.set(k, new Intl.NumberFormat(locale(), options));
  return cache.get(k)!;
}
const nf = () => formateur("n", {});
const nf1 = () => formateur("1", { maximumFractionDigits: 1 });
const compact = () => formateur("c", { notation: "compact", maximumFractionDigits: 1 });

export const nombre = (n: number | null | undefined) => (n === null || n === undefined ? "—" : nf().format(n));
export const decimal = (n: number | null | undefined) => (n === null || n === undefined ? "—" : nf1().format(n));
export const compacte = (n: number | null | undefined) => (n === null || n === undefined ? "—" : compact().format(n));
export const pourcent = (n: number | null | undefined) => (n === null || n === undefined ? "—" : `${nf1().format(n)} %`);

export function date(iso: string | null | undefined, avecHeure = false) {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  return d.toLocaleDateString(locale(), avecHeure
    ? { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "long", year: "numeric" });
}

export function ilYa(iso: string | null | undefined) {
  if (!iso) return "—";
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  const en = langue() === "en";
  if (s < 45) return en ? "just now" : "à l'instant";
  const rtf = new Intl.RelativeTimeFormat(en ? "en" : "fr", { numeric: "auto" });
  if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
  if (s < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  return rtf.format(-Math.round(s / 86400), "day");
}

export function joursRestants(iso: string) {
  const fin = new Date(iso + "T23:59:59").getTime();
  return Math.ceil((fin - Date.now()) / 86400000);
}

export function taille(o: number) {
  const [oc, ko, mo] = langue() === "en" ? ["B", "KB", "MB"] : ["o", "Ko", "Mo"];
  return o < 1024 ? `${o} ${oc}` : o < 1048576 ? `${nf1().format(o / 1024)} ${ko}` : `${nf1().format(o / 1048576)} ${mo}`;
}

export const initiales = (texte: string) =>
  texte.split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]?.toUpperCase()).join("") || "?";
