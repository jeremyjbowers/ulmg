# ABOUTME: Serves the service worker from this site.
# ABOUTME: A service worker has to come from this origin, not the static files CDN.

from pathlib import Path

from django.http import Http404, HttpResponse

STATIC = Path(__file__).resolve().parents[1] / "static"

ASSETS = {
    "service_worker": (STATIC / "sw.js", "no-cache"),
}


def _asset(request, key):
    path, cache_control = ASSETS[key]
    if not path.is_file():
        raise Http404(key)
    response = HttpResponse(path.read_bytes(), content_type="text/javascript; charset=utf-8")
    response["Cache-Control"] = cache_control
    return response


def service_worker(request):
    response = _asset(request, "service_worker")
    response["Service-Worker-Allowed"] = "/"
    return response
