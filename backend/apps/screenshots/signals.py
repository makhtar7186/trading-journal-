from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import TradeScreenshot
from .services import delete_stored_file


@receiver(post_delete, sender=TradeScreenshot)
def remove_file_after_delete(sender, instance: TradeScreenshot, **kwargs):
    """Couvre aussi les suppressions en cascade (trade ou utilisateur supprimé).

    Le fichier n'est effacé qu'après validation de la transaction : un rollback ne perd rien.
    """
    key = instance.storage_key
    transaction.on_commit(lambda: delete_stored_file(key))
