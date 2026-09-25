# ABOUTME: Tests for OwnerAPIToken minting, hashing, and Bearer auth.
# ABOUTME: Covers management command output and MCP API 401 behavior.
import hashlib

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from io import StringIO

from ulmg import models


class OwnerAPITokenUnitTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner1", email="owner1@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Owner One", email="owner1@example.com"
        )

    def test_create_token_stores_hash_not_plaintext(self):
        raw, token = models.OwnerAPIToken.create_token(self.owner, label="laptop")
        self.assertTrue(raw.startswith("ulmg_"))
        self.assertNotEqual(token.token_hash, raw)
        self.assertEqual(
            token.token_hash, hashlib.sha256(raw.encode("utf-8")).hexdigest()
        )
        self.assertTrue(token.token_prefix)
        self.assertTrue(raw.startswith(token.token_prefix))

    def test_authenticate_valid_token(self):
        raw, _ = models.OwnerAPIToken.create_token(self.owner, label="laptop")
        found = models.OwnerAPIToken.authenticate(raw)
        self.assertIsNotNone(found)
        self.assertEqual(found.owner_id, self.owner.pk)
        found.refresh_from_db()
        self.assertIsNotNone(found.last_used_at)

    def test_authenticate_rejects_revoked_token(self):
        raw, token = models.OwnerAPIToken.create_token(self.owner, label="old")
        token.revoke()
        self.assertIsNone(models.OwnerAPIToken.authenticate(raw))

    def test_authenticate_rejects_garbage(self):
        self.assertIsNone(models.OwnerAPIToken.authenticate("ulmg_notreal"))
        self.assertIsNone(models.OwnerAPIToken.authenticate(""))
        self.assertIsNone(models.OwnerAPIToken.authenticate(None))


class CreateOwnerAPITokenCommandTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner2", email="owner2@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Owner Two", email="owner2@example.com"
        )

    def test_command_prints_token_once(self):
        out = StringIO()
        call_command(
            "create_owner_api_token",
            "--email",
            "owner2@example.com",
            "--label",
            "cursor",
            stdout=out,
        )
        text = out.getvalue()
        self.assertIn("ulmg_", text)
        self.assertEqual(models.OwnerAPIToken.objects.filter(owner=self.owner).count(), 1)
        raw = [line.strip() for line in text.splitlines() if line.strip().startswith("ulmg_")][0]
        self.assertIsNotNone(models.OwnerAPIToken.authenticate(raw))


class MCPAuthE2ETestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="owner3", email="owner3@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Owner Three", email="owner3@example.com"
        )
        self.team = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans", owner_obj=self.owner
        )
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="test")

    def test_mcp_endpoint_requires_token(self):
        resp = self.client.get("/api/mcp/v1/season/")
        self.assertEqual(resp.status_code, 401)

    def test_mcp_endpoint_accepts_bearer_token(self):
        resp = self.client.get(
            "/api/mcp/v1/season/",
            HTTP_AUTHORIZATION=f"Bearer {self.raw}",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("season", data)
        self.assertIn("season_type", data)
        self.assertEqual(data["my_team"]["abbreviation"], "BOS")
