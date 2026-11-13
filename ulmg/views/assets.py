# ABOUTME: Serves the live-game field scripts and the service worker from this site.
# ABOUTME: The field modules ship with the app. A service worker has to come from this origin.

from pathlib import Path

from django.http import Http404, HttpResponse

STATIC = Path(__file__).resolve().parents[1] / "static"

ASSETS = {
    "game_field_js": (STATIC / "ulmg" / "game_field.js", "public, max-age=300"),
    "pixelkit_mjs": (STATIC / "ulmg" / "pixelkit.mjs", "public, max-age=300"),
    "service_worker": (STATIC / "sw.js", "no-cache"),
}


def _asset(request, key):
    path, cache_control = ASSETS[key]
    if not path.is_file():
        raise Http404(key)
    response = HttpResponse(path.read_bytes(), content_type="text/javascript; charset=utf-8")
    response["Cache-Control"] = cache_control
    return response


def game_field_js(request):
    return _asset(request, "game_field_js")


def pixelkit_mjs(request):
    return _asset(request, "pixelkit_mjs")


def service_worker(request):
    response = _asset(request, "service_worker")
    response["Service-Worker-Allowed"] = "/"
    return response
