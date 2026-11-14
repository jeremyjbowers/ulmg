# ABOUTME: The service worker has to load from this site.
# ABOUTME: Anonymous requests must get JavaScript, not a redirect to the login page.

from pathlib import Path

from django.test import TestCase

ROOT = Path(__file__).resolve().parent.parent


class AppAssetTests(TestCase):
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
