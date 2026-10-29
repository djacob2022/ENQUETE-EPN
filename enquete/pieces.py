"""Contrôle des fichiers déposés : extension autorisée, taille maximale, contenu cohérent avec l'extension."""
import os

from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

TAILLE_MAX = 10 * 1024 * 1024  # 10 Mo par fichier

# Extension -> débuts de fichier acceptés (signature), pour refuser un exécutable renommé en .pdf.
SIGNATURES = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}
EXTENSIONS = tuple(SIGNATURES)
ACCEPT = ",".join(EXTENSIONS)
LIBELLE_FORMATS = "PDF, Word, Excel, JPG ou PNG"


def valider_piece(fichier):
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in SIGNATURES:
        raise ValidationError(f"Format non accepté. Formats autorisés : {LIBELLE_FORMATS}.")
    if fichier.size > TAILLE_MAX:
        raise ValidationError(
            f"Fichier trop volumineux ({filesizeformat(fichier.size)}). Maximum : {filesizeformat(TAILLE_MAX)}.")
    if fichier.size == 0:
        raise ValidationError("Le fichier est vide.")
    debut = fichier.read(8)
    fichier.seek(0)
    if not debut.startswith(SIGNATURES[extension]):
        raise ValidationError("Le contenu du fichier ne correspond pas à son extension.")
