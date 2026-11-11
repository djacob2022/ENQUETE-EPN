"""Mots de passe à usage unique (TOTP, RFC 6238) pour la double authentification (F-03).

Compatible avec Google Authenticator, Microsoft Authenticator, FreeOTP… : code à 6 chiffres renouvelé toutes les
30 secondes, dérivé d'un secret partagé une seule fois au moyen d'un QR code.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

PERIODE = 30
CHIFFRES = 6


def nouveau_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def _code(secret, pas):
    cle = base64.b32decode(secret, casefold=True)
    empreinte = hmac.new(cle, struct.pack(">Q", pas), hashlib.sha1).digest()
    decalage = empreinte[-1] & 0x0F
    valeur = struct.unpack(">I", empreinte[decalage:decalage + 4])[0] & 0x7FFFFFFF
    return str(valeur % 10 ** CHIFFRES).zfill(CHIFFRES)


def pas_courant(instant=None):
    return int((instant if instant is not None else time.time()) // PERIODE)


def verifier(secret, code, dernier_pas=None, instant=None, tolerance=1):
    """Renvoie le pas de temps accepté, ou None. Un code déjà utilisé (pas <= dernier_pas) est refusé."""
    code = "".join(c for c in str(code) if c.isdigit())
    if len(code) != CHIFFRES or not secret:
        return None
    courant = pas_courant(instant)
    for pas in range(courant - tolerance, courant + tolerance + 1):
        if dernier_pas is not None and pas <= dernier_pas:
            continue
        if hmac.compare_digest(_code(secret, pas), code):
            return pas
    return None


def uri(secret, compte, emetteur="ENQUETE-EPN"):
    """Adresse otpauth:// lue par les applications d'authentification (contenu du QR code)."""
    libelle = quote(f"{emetteur}:{compte}")
    return f"otpauth://totp/{libelle}?secret={secret}&issuer={quote(emetteur)}&digits={CHIFFRES}&period={PERIODE}"


def qr_svg(contenu):
    import io

    import segno

    tampon = io.BytesIO()
    segno.make(contenu, error="m").save(tampon, kind="svg", scale=5, border=2, dark="#073625", xmldecl=False)
    return tampon.getvalue().decode("utf-8")


def codes_de_secours(n=8):
    """Codes à usage unique, à imprimer et garder en lieu sûr (perte du téléphone)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2)) for _ in range(n)]
