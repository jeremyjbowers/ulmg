# ABOUTME: Unit, integration, and API tests for cached constitution access.
# ABOUTME: Covers HTML extraction, search, refresh command, and MCP JSON routes.
import os
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase

from ulmg import models
from ulmg.constitution import (
    CONSTITUTION_PUB_URL,
    extract_constitution_text,
    search_constitution_text,
)


SAMPLE_HTML = """
<html><body>
<div id="contents">
<p>The ULMG Constitution</p>
<p>Article I. Rosters</p>
<p>Each team shall maintain a 30-man Major League roster and may protect
up to 40 players for the Open Draft.</p>
<p>Article II. Drafts</p>
<p>The Open Draft covers unprotected players. The AA Draft is for B-level
prospects.</p>
<p>Article III. Trades</p>
<p>Trades may include players and draft picks. All trades must be approved
by both owners.</p>
</div>
</body></html>
"""


class ExtractConstitutionTextTestCase(TestCase):
    """Unit: parse Google Docs pub HTML into plain text."""

    def test_extracts_contents_div(self):
        text = extract_constitution_text(SAMPLE_HTML)
        self.assertIn("The ULMG Constitution", text)
        self.assertIn("30-man Major League roster", text)
        self.assertIn("Article III. Trades", text)
        self.assertNotIn("<p>", text)
        self.assertNotIn("id=\"contents\"", text)

    def test_missing_contents_raises(self):
        with self.assertRaises(ValueError):
            extract_constitution_text("<html><body><p>nope</p></body></html>")


class SearchConstitutionTextTestCase(TestCase):
    """Unit: case-insensitive excerpt search over constitution text."""

    def setUp(self):
        self.text = extract_constitution_text(SAMPLE_HTML)

    def test_finds_matches_with_context(self):
        hits = search_constitution_text(self.text, "open draft")
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(
            any("Open Draft" in h["excerpt"] for h in hits)
        )
        for hit in hits:
            self.assertIn("query", hit)
            self.assertIn("excerpt", hit)
            self.assertIn("offset", hit)

    def test_no_matches_returns_empty(self):
        self.assertEqual(
            search_constitution_text(self.text, "waiver wire claim"),
            [],
        )

    def test_empty_query_returns_empty(self):
        self.assertEqual(search_constitution_text(self.text, "  "), [])


class ConstitutionCacheModelTestCase(TestCase):
    """Unit: singleton-style cache row helpers."""

    def test_store_and_current(self):
        doc = models.ConstitutionCache.store(
            text="Hello constitution",
            source_url=CONSTITUTION_PUB_URL,
            title="The ULMG Constitution",
        )
        self.assertEqual(doc.text, "Hello constitution")
        self.assertIsNotNone(doc.fetched_at)
        self.assertEqual(models.ConstitutionCache.current().pk, doc.pk)

    def test_store_replaces_previous(self):
        models.ConstitutionCache.store(text="old", source_url=CONSTITUTION_PUB_URL)
        models.ConstitutionCache.store(text="new", source_url=CONSTITUTION_PUB_URL)
        self.assertEqual(models.ConstitutionCache.objects.count(), 1)
        self.assertEqual(models.ConstitutionCache.current().text, "new")

    def test_current_none_when_empty(self):
        models.ConstitutionCache.objects.all().delete()
        self.assertIsNone(models.ConstitutionCache.current())


class RefreshConstitutionCommandTestCase(TestCase):
    """Integration: management command fetches/parses and writes the cache."""

    def test_refresh_from_html_bytes(self):
        mock_resp = mock.Mock()
        mock_resp.content = SAMPLE_HTML.encode("utf-8")
        mock_resp.raise_for_status = mock.Mock()
        with mock.patch(
            "ulmg.constitution.requests.get", return_value=mock_resp
        ) as get:
            out = StringIO()
            call_command("refresh_constitution", stdout=out)
            get.assert_called_once()
            args, kwargs = get.call_args
            self.assertEqual(args[0], CONSTITUTION_PUB_URL)
        doc = models.ConstitutionCache.current()
        self.assertIsNotNone(doc)
        self.assertIn("The ULMG Constitution", doc.text)
        self.assertIn("refreshed", out.getvalue().lower())

    def test_refresh_from_file(self):
        path = os.path.join(os.path.dirname(__file__), "_constitution_fixture.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_HTML)
        try:
            call_command("refresh_constitution", from_file=path, stdout=StringIO())
        finally:
            os.remove(path)
        doc = models.ConstitutionCache.current()
        self.assertIn("30-man Major League roster", doc.text)

    def test_refresh_from_text_file(self):
        path = os.path.join(os.path.dirname(__file__), "_constitution_plain.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Plain constitution text about the AA Draft.\n")
        try:
            call_command("refresh_constitution", from_file=path, stdout=StringIO())
        finally:
            os.remove(path)
        self.assertEqual(
            models.ConstitutionCache.current().text.strip(),
            "Plain constitution text about the AA Draft.",
        )


class ConstitutionAPITestCase(TestCase):
    """End-to-end: authenticated MCP JSON endpoints for constitution."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="const_owner", email="const@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Const Owner", email="const@example.com"
        )
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="tests")
        models.ConstitutionCache.store(
            text=extract_constitution_text(SAMPLE_HTML),
            source_url=CONSTITUTION_PUB_URL,
            title="The ULMG Constitution",
        )

    def _get(self, path, **params):
        return self.client.get(
            path,
            data=params,
            HTTP_AUTHORIZATION=f"Bearer {self.raw}",
        )

    def test_get_constitution_requires_auth(self):
        resp = self.client.get("/api/mcp/v1/constitution/")
        self.assertEqual(resp.status_code, 401)

    def test_get_constitution(self):
        resp = self._get("/api/mcp/v1/constitution/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("The ULMG Constitution", data["text"])
        self.assertEqual(data["source_url"], CONSTITUTION_PUB_URL)
        self.assertIn("fetched_at", data)
        self.assertGreater(data["char_count"], 100)

    def test_search_constitution(self):
        resp = self._get("/api/mcp/v1/constitution/search/", q="30-man")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["query"], "30-man")
        self.assertGreaterEqual(data["match_count"], 1)
        self.assertTrue(
            any("30-man" in m["excerpt"] for m in data["matches"])
        )

    def test_search_requires_query(self):
        resp = self._get("/api/mcp/v1/constitution/search/")
        self.assertEqual(resp.status_code, 400)

    def test_get_constitution_404_when_uncached(self):
        models.ConstitutionCache.objects.all().delete()
        resp = self._get("/api/mcp/v1/constitution/")
        self.assertEqual(resp.status_code, 404)


class ConstitutionServicesTestCase(TestCase):
    """Integration: service helpers used by MCP tools."""

    def setUp(self):
        models.ConstitutionCache.store(
            text=extract_constitution_text(SAMPLE_HTML),
            source_url=CONSTITUTION_PUB_URL,
        )

    def test_get_constitution_payload(self):
        from ulmg.mcp import services

        data = services.get_constitution()
        self.assertIn("text", data)
        self.assertIn("Open Draft", data["text"])

    def test_search_constitution_payload(self):
        from ulmg.mcp import services

        data = services.search_constitution("AA Draft")
        self.assertEqual(data["match_count"], len(data["matches"]))
        self.assertGreaterEqual(data["match_count"], 1)
