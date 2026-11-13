/** Appels à l'API Django (même origine). Le jeton CSRF est lu dans le cookie posé par le serveur. */
import { langue, t } from "./langue";

export class ErreurApi extends Error {
  constructor(public statut: number, message: string, public erreurs?: Record<string, string[]>) {
    super(message);
  }
}

function cookie(nom: string) {
  return document.cookie.split("; ").find((c) => c.startsWith(nom + "="))?.split("=")[1] ?? "";
}

let csrfPret: Promise<unknown> | null = null;
async function assurerCsrf() {
  if (cookie("csrftoken")) return;
  csrfPret ??= fetch("/api/csrf/", { credentials: "same-origin" });
  await csrfPret;
}

async function requete<T>(methode: string, url: string, corps?: unknown): Promise<T> {
  // Langue du répondant (F-16) : le serveur ne la prend en compte que sur les adresses publiques du questionnaire.
  const enTetes: Record<string, string> = { Accept: "application/json", "X-Langue": langue() };
  let body: BodyInit | undefined;
  if (methode !== "GET") {
    await assurerCsrf();
    enTetes["X-CSRFToken"] = decodeURIComponent(cookie("csrftoken"));
  }
  if (corps instanceof FormData) body = corps;
  else if (corps !== undefined) {
    enTetes["Content-Type"] = "application/json";
    body = JSON.stringify(corps);
  }
  let reponse: Response;
  try {
    reponse = await fetch(url, { method: methode, headers: enTetes, body, credentials: "same-origin" });
  } catch {
    throw new ErreurApi(0, t("Connexion impossible. Vérifiez votre réseau puis réessayez."));
  }
  const type = reponse.headers.get("content-type") ?? "";
  const donnees = type.includes("application/json") ? await reponse.json() : null;
  if (!reponse.ok && !(reponse.status === 422 && donnees?.reponse)) {
    const message = donnees?.erreur ?? (donnees?.erreurs ? t("Certaines réponses sont à corriger.") : `Erreur ${reponse.status}`);
    throw new ErreurApi(reponse.status, message, donnees?.erreurs);
  }
  return donnees as T;
}

export const api = {
  get: <T,>(url: string) => requete<T>("GET", url),
  post: <T,>(url: string, corps?: unknown) => requete<T>("POST", url, corps ?? {}),
  put: <T,>(url: string, corps?: unknown) => requete<T>("PUT", url, corps ?? {}),
  delete: <T,>(url: string) => requete<T>("DELETE", url),
};

/** Envoi de fichier avec suivi de progression (fetch ne le permet pas encore). */
export function envoyerFichier<T>(url: string, fichier: File, progression: (p: number) => void): Promise<T> {
  return new Promise(async (resoudre, rejeter) => {
    await assurerCsrf();
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.setRequestHeader("X-CSRFToken", decodeURIComponent(cookie("csrftoken")));
    xhr.setRequestHeader("X-Langue", langue());
    xhr.upload.onprogress = (e) => e.lengthComputable && progression(e.loaded / e.total);
    xhr.onload = () => {
      let donnees: any = null;
      try { donnees = JSON.parse(xhr.responseText); } catch { /* réponse non JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resoudre(donnees as T);
      else rejeter(new ErreurApi(xhr.status, donnees?.erreur ?? `Erreur ${xhr.status}`));
    };
    xhr.onerror = () => rejeter(new ErreurApi(0, t("Connexion impossible.")));
    const corps = new FormData();
    corps.append("fichier", fichier);
    xhr.send(corps);
  });
}

export function avecParams(url: string, params: Record<string, string | number | undefined | null>) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && q.set(k, String(v)));
  const s = q.toString();
  return s ? `${url}?${s}` : url;
}
