# ABOUTME: Tests for users who are logged in but not linked to an Owner or Team.
# ABOUTME: Ensures site navigation and context building tolerate missing team assignments.

from django.contrib.auth.models import AnonymousUser, User
from django.test import Client, TestCase

from ulmg import models, utils


class NoTeamUserTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="spectator",
            email="spectator@example.com",
        )
        self.team = models.Team.objects.create(
            city="Test",
            abbreviation="TST",
            nickname="Testers",
            division="Test Division",
        )

    def test_get_owner_for_user_returns_none_when_unauthenticated(self):
        self.assertIsNone(utils.get_owner_for_user(AnonymousUser()))

    def test_get_owner_for_user_returns_none_without_owner_record(self):
        self.assertIsNone(utils.get_owner_for_user(self.user))

    def test_get_owner_for_user_returns_owner_when_linked(self):
        owner = models.Owner.objects.create(
            user=self.user,
            name="Spectator Owner",
            email="spectator@example.com",
        )
        self.assertEqual(utils.get_owner_for_user(self.user), owner)

    def test_get_team_for_owner_returns_none_without_team(self):
        owner = models.Owner.objects.create(
            user=self.user,
            name="No Team Owner",
            email="spectator@example.com",
        )
        self.assertIsNone(utils.get_team_for_owner(owner))
        self.assertIsNone(owner.team())

    def test_get_team_for_owner_returns_team_when_assigned(self):
        owner = models.Owner.objects.create(
            user=self.user,
            name="Team Owner",
            email="spectator@example.com",
        )
        self.team.owner_obj = owner
        self.team.save()
        self.assertEqual(utils.get_team_for_owner(owner), self.team)
        self.assertEqual(owner.team(), self.team)

    def test_build_context_without_owner_or_team(self):
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        context = utils.build_context(request)
        self.assertIsNone(context["owner"])
        self.assertIsNone(context["my_team"])

    def test_build_context_with_owner_but_no_team(self):
        models.Owner.objects.create(
            user=self.user,
            name="Owner Without Team",
            email="spectator@example.com",
        )
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        context = utils.build_context(request)
        self.assertIsNotNone(context["owner"])
        self.assertIsNone(context["my_team"])

    def test_home_page_renders_for_user_without_team(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/teams//"')
        self.assertNotContains(response, ">My Team</a>")

    def test_team_page_renders_for_user_without_team(self):
        self.client.force_login(self.user)
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, ">My Team</a>")

    def test_wishlist_api_returns_empty_for_user_without_owner(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/wishlist/players/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"players": []})
