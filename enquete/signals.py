from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PieceJointe


@receiver(post_delete, sender=PieceJointe)
def supprimer_fichier(sender, instance, **kwargs):
    """Supprime le fichier du disque quand la pièce disparaît (y compris par cascade)."""
    if instance.fichier:
        instance.fichier.delete(save=False)
