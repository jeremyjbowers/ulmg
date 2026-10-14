# ABOUTME: Tests for owner self-service API keys (read and read-write).
# ABOUTME: Covers token scope, the logged-in page, and Bearer use after revoke.
import json

from django.contrib.auth.models import User
from django.core.management import call_command
from django.http import JsonResponse
from django.test import Client, RequestFactory, TestCase
from io import StringIO

from ulmg import models
from ulmg.mcp_app.auth import require_owner_api_token


class OwnerAPITokenScopeUnitTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="key_owner", email="keys@example.com", password="secret"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Key Owner", email="keys@example.com"
        )

    def test_default_scope_is_read_and_secret_is_stored(self):
        raw, token = models.OwnerAPIToken.create_token(self.owner, label="laptop")
        self.assertEqual(token.scope, models.OwnerAPIToken.SCOPE_READ)
        self.assertEqual(token.token_secret, raw)
        self.assertTrue(raw.startswith("ulmg_"))
        self.assertFalse(token.allows_write)

    def test_read_write_scope_allows_write(self):
        raw, token = models.OwnerAPIToken.create_token(
            self.owner, label="agent", scope=models.OwnerAPIToken.SCOPE_READ_WRITE
        )
        self.assertEqual(token.scope, models.OwnerAPIToken.SCOPE_READ_WRITE)
        self.assertEqual(token.token_secret, raw)
        self.assertTrue(token.allows_write)
        found = models.OwnerAPIToken.authenticate(raw)
        self.assertEqual(found.pk, token.pk)

    def test_unknown_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            models.OwnerAPIToken.create_token(self.owner, scope="admin")

    def test_revoked_token_does_not_allow_write(self):
        _, token = models.OwnerAPIToken.create_token(
            self.owner, scope=models.OwnerAPIToken.SCOPE_READ_WRITE
        )
        token.revoke()
        token.refresh_from_db()
        self.assertFalse(token.allows_write)


class OwnerAPITokenWriteScopeIntegrationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="scope_owner", email="scope@example.com", password="secret"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Scope Owner", email="scope@example.com"
        )
        self.factory = RequestFactory()

    def _write_view(self):
        @require_owner_api_token(write=True)
        def write_view(request):
            return JsonResponse({"ok": True, "owner": request.mcp_owner.pk})

        return write_view

    def test_read_token_is_forbidden_on_write_view(self):
        raw, _ = models.OwnerAPIToken.create_token(
            self.owner, scope=models.OwnerAPIToken.SCOPE_READ
        )
        request = self.factory.post(
            "/unused/", HTTP_AUTHORIZATION=f"Bearer {raw}"
        )
        response = self._write_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_read_write_token_is_allowed_on_write_view(self):
        raw, _ = models.OwnerAPIToken.create_token(
            self.owner, scope=models.OwnerAPIToken.SCOPE_READ_WRITE
        )
        request = self.factory.post(
            "/unused/", HTTP_AUTHORIZATION=f"Bearer {raw}"
        )
        response = self._write_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["owner"], self.owner.pk)

    def test_read_token_still_calls_read_views(self):
        @require_owner_api_token
        def read_view(request):
            return JsonResponse({"owner": request.mcp_owner.pk})

        raw, _ = models.OwnerAPIToken.create_token(
            self.owner, scope=models.OwnerAPIToken.SCOPE_READ
        )
        request = self.factory.get(
            "/unused/", HTTP_AUTHORIZATION=f"Bearer {raw}"
        )
        response = read_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["owner"], self.owner.pk)

    def test_command_mints_requested_scope(self):
        out = StringIO()
        call_command(
            "create_owner_api_token",
            "--email",
            "scope@example.com",
            "--label",
            "cli",
            "--scope",
            "read_write",
            stdout=out,
        )
        token = models.OwnerAPIToken.objects.get(owner=self.owner, label="cli")
        self.assertEqual(token.scope, models.OwnerAPIToken.SCOPE_READ_WRITE)
        self.assertIn(token.token_secret, out.getvalue())


class OwnerAPIKeyPageIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="page_owner", email="page@example.com", password="secret"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Page Owner", email="page@example.com"
        )
        self.other_user = User.objects.create_user(
            username="other_owner", email="other@example.com", password="secret"
        )
        self.other_owner = models.Owner.objects.create(
            user=self.other_user, name="Other Owner", email="other@example.com"
        )
        self.other_raw, self.other_token = models.OwnerAPIToken.create_token(
            self.other_owner, label="theirs", scope=models.OwnerAPIToken.SCOPE_READ
        )

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get("/my/api-keys/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_owner_page_lists_only_their_key_text(self):
        raw, _ = models.OwnerAPIToken.create_token(
            self.owner, label="mine", scope=models.OwnerAPIToken.SCOPE_READ_WRITE
        )
        self.client.login(username="page_owner", password="secret")
        response = self.client.get("/my/api-keys/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, raw)
        self.assertNotContains(response, self.other_raw)
        self.assertContains(response, "Read and write")
        self.assertNotContains(response, "theirs")

    def test_invalid_scope_does_not_create_a_key(self):
        self.client.login(username="page_owner", password="secret")
        response = self.client.post(
            "/my/api-keys/",
            {"action": "create", "scope": "admin", "label": "nope"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            models.OwnerAPIToken.objects.filter(owner=self.owner).count(), 0
        )
        self.assertContains(response, "Pick a read or read-write key.")

    def test_user_without_owner_cannot_mint_a_key(self):
        spectator = User.objects.create_user(
            username="spectator", email="spectator@example.com", password="secret"
        )
        self.client.login(username="spectator", password="secret")
        page = self.client.get("/my/api-keys/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "not linked to an owner")
        denied = self.client.post(
            "/my/api-keys/",
            {"action": "create", "scope": "read", "label": "nope"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(
            models.OwnerAPIToken.objects.filter(label="nope").exists()
        )
        self.assertFalse(models.Owner.objects.filter(user=spectator).exists())


class OwnerAPIKeyPageE2ETestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="e2e_owner", email="e2e@example.com", password="secret"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="E2E Owner", email="e2e@example.com"
        )
        self.other_user = User.objects.create_user(
            username="e2e_other", email="e2e-other@example.com", password="secret"
        )
        self.other_owner = models.Owner.objects.create(
            user=self.other_user, name="E2E Other", email="e2e-other@example.com"
        )

    def test_owner_generates_uses_and_revokes_keys_without_leaking_them(self):
        self.client.login(username="e2e_owner", password="secret")

        read_page = self.client.post(
            "/my/api-keys/",
            {"action": "create", "scope": "read", "label": "lookup"},
            follow=True,
        )
        self.assertEqual(read_page.status_code, 200)
        read_token = models.OwnerAPIToken.objects.get(owner=self.owner, label="lookup")
        self.assertEqual(read_token.scope, models.OwnerAPIToken.SCOPE_READ)
        self.assertContains(read_page, read_token.token_secret)
        self.assertNotContains(read_page, 'type="password"')

        read_api = self.client.get(
            "/api/mcp/v1/season/",
            HTTP_AUTHORIZATION=f"Bearer {read_token.token_secret}",
        )
        self.assertEqual(read_api.status_code, 200)
        self.assertEqual(read_api.json()["my_owner"]["email"], "e2e@example.com")

        write_page = self.client.post(
            "/my/api-keys/",
            {"action": "create", "scope": "read_write", "label": "agent"},
            follow=True,
        )
        write_token = models.OwnerAPIToken.objects.get(owner=self.owner, label="agent")
        self.assertEqual(write_token.scope, models.OwnerAPIToken.SCOPE_READ_WRITE)
        self.assertContains(write_page, write_token.token_secret)
        self.assertContains(write_page, read_token.token_secret)

        write_api = self.client.get(
            "/api/mcp/v1/season/",
            HTTP_AUTHORIZATION=f"Bearer {write_token.token_secret}",
        )
        self.assertEqual(write_api.status_code, 200)

        self.client.logout()
        self.client.login(username="e2e_other", password="secret")
        other_page = self.client.get("/my/api-keys/")
        self.assertNotContains(other_page, read_token.token_secret)
        self.assertNotContains(other_page, write_token.token_secret)
        stolen = self.client.post(
            "/my/api-keys/",
            {"action": "revoke", "token_id": read_token.pk},
        )
        self.assertEqual(stolen.status_code, 404)
        read_token.refresh_from_db()
        self.assertIsNone(read_token.revoked_at)

        self.client.logout()
        self.client.login(username="e2e_owner", password="secret")
        revoked_page = self.client.post(
            "/my/api-keys/",
            {"action": "revoke", "token_id": read_token.pk},
            follow=True,
        )
        self.assertEqual(revoked_page.status_code, 200)
        self.assertContains(revoked_page, read_token.token_secret)
        self.assertContains(revoked_page, "Revoked")
        read_token.refresh_from_db()
        self.assertIsNotNone(read_token.revoked_at)
        self.assertIsNone(models.OwnerAPIToken.authenticate(read_token.token_secret))

        rejected = self.client.get(
            "/api/mcp/v1/season/",
            HTTP_AUTHORIZATION=f"Bearer {read_token.token_secret}",
        )
        self.assertEqual(rejected.status_code, 401)

        still_live = self.client.get(
            "/api/mcp/v1/season/",
            HTTP_AUTHORIZATION=f"Bearer {write_token.token_secret}",
        )
        self.assertEqual(still_live.status_code, 200)

    def test_csrf_is_required_to_mint_a_key(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="e2e_owner", password="secret")
        blocked = client.post(
            "/my/api-keys/",
            {"action": "create", "scope": "read", "label": "csrf"},
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertFalse(models.OwnerAPIToken.objects.filter(label="csrf").exists())

        page = client.get("/my/api-keys/")
        csrf = client.cookies["csrftoken"].value
        created = client.post(
            "/my/api-keys/",
            {
                "action": "create",
                "scope": "read",
                "label": "csrf",
                "csrfmiddlewaretoken": csrf,
            },
            follow=True,
        )
        self.assertEqual(created.status_code, 200)
        token = models.OwnerAPIToken.objects.get(owner=self.owner, label="csrf")
        self.assertContains(created, token.token_secret)
        self.assertContains(page, "API keys")
