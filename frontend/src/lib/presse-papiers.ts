/** Copie un texte. Renvoie false si le navigateur refuse (ex. page en http:// hors localhost). */
export async function copier(texte: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(texte);
      return true;
    }
  } catch {
    /* on tente le repli ci-dessous */
  }
  const zone = document.createElement("textarea");
  zone.value = texte;
  zone.setAttribute("readonly", "");
  zone.style.position = "fixed";
  zone.style.opacity = "0";
  document.body.appendChild(zone);
  zone.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    zone.remove();
  }
}
