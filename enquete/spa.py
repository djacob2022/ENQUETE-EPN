"""Sert l'application React (frontend/dist/index.html) pour toutes les pages de l'interface."""
from functools import lru_cache

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie

INDEX = settings.BASE_DIR / "frontend" / "dist" / "index.html"

MESSAGE_SANS_BUILD = """<!doctype html><meta charset="utf-8"><title>ENQUÊTE-EPN</title>
<p style="font-family:system-ui;padding:40px">L'interface n'est pas construite.
Lancez <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>,
ou utilisez le serveur de développement : <code>npm run dev</code> puis http://localhost:5173.</p>"""


@lru_cache(maxsize=1)
def _index_production():
    return INDEX.read_text(encoding="utf-8")


@ensure_csrf_cookie
def application(request, **kwargs):
    if not INDEX.exists():
        return HttpResponse(MESSAGE_SANS_BUILD, status=503)
    contenu = INDEX.read_text(encoding="utf-8") if settings.DEBUG else _index_production()
    return HttpResponse(contenu)
