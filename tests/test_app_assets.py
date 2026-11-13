# ABOUTME: The live field scripts and the service worker have to load from this site.
# ABOUTME: Anonymous requests must get JavaScript, not a redirect to the login page.

from pathlib import Path

from django.test import TestCase

ROOT = Path(__file__).resolve().parent.parent


class AppAssetTests(TestCase):
    def test_the_field_script_is_javascript_from_this_origin(self):
        response = self.client.get("/static/ulmg/game_field.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertEqual(response.content, (ROOT / "ulmg/static/ulmg/game_field.js").read_bytes())
        self.assertIn(b"./pixelkit.mjs", response.content)

    def test_the_pixel_kit_module_is_javascript(self):
        response = self.client.get("/static/ulmg/pixelkit.mjs")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertEqual(response.content, (ROOT / "ulmg/static/ulmg/pixelkit.mjs").read_bytes())

    def test_the_service_worker_is_javascript_from_this_origin(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertContains(response, "ulmg-static-v1")
        self.assertContains(response, "if (response.ok)")
        self.assertNotContains(response, "return cached || fetchPromise")
        self.assertNotContains(response, "<html")

    def test_the_login_page_registers_the_worker_on_this_origin(self):
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "navigator.serviceWorker.register('/sw.js')")
        self.assertNotContains(response, "digitaloceanspaces.com/public/sw.js")
