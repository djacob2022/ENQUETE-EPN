from django.conf import settings


def institution(request):
    return {"NOM_INSTITUTION": settings.NOM_INSTITUTION}
