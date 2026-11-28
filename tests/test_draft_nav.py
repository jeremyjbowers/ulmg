# ABOUTME: Tests that the draft nav and /draft/ index come from DraftPick rows.
# ABOUTME: The nav keeps the three newest draft events plus any that sit after the current season.

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import drafts, models


def _pick(year, season, draft_type, draft_round=1):
    return models.DraftPick.objects.create(
        year=str(year),
        season=season,
        draft_type=draft_type,
        draft_round=draft_round,
    )


@override_settings(CURRENT_SEASON=2027, CURRENT_SEASON_TYPE="offseason")
class DraftBoardQueryTest(TestCase):
    def setUp(self):
        _pick(2028, "offseason", "aa")
        _pick(2027, "midseason", "open")
        _pick(2027, "offseason", "aa", draft_round=1)
        _pick(2027, "offseason", "aa", draft_round=2)
        _pick(2027, "offseason", "open")
        _pick(2026, "midseason", "aa")
        _pick(2026, "midseason", "open")
        _pick(2026, "offseason", "aa")
        _pick(2025, "midseason", "open")

    def test_boards_are_distinct_and_newest_first(self):
        self.assertEqual(
            [(board["title"], board["url"]) for board in drafts.all_boards()],
            [
                ("2028 Offseason AA", "/draft/2028/offseason/aa/"),
                ("2027 Midseason Open", "/draft/2027/midseason/open/"),
                ("2027 Offseason AA", "/draft/2027/offseason/aa/"),
                ("2027 Offseason Open", "/draft/2027/offseason/open/"),
                ("2026 Midseason AA", "/draft/2026/midseason/aa/"),
                ("2026 Midseason Open", "/draft/2026/midseason/open/"),
                ("2026 Offseason AA", "/draft/2026/offseason/aa/"),
                ("2025 Midseason Open", "/draft/2025/midseason/open/"),
            ],
        )

    def test_the_settings_file_does_not_list_drafts(self):
        self.assertFalse(hasattr(settings, "DRAFTS"))

    def test_nav_keeps_three_recent_events_and_every_future_event(self):
        self.assertEqual(
            [board["title"] for board in drafts.nav_boards()],
            [
                "2028 Offseason AA",
                "2027 Midseason Open",
                "2027 Offseason AA",
                "2027 Offseason Open",
                "2026 Midseason AA",
                "2026 Midseason Open",
                "2026 Offseason AA",
            ],
        )


@override_settings(CURRENT_SEASON=2027, CURRENT_SEASON_TYPE="offseason")
class DraftIndexPageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("manager", password="secret")
        self.client = Client()
        self.client.force_login(self.user)
        _pick(2027, "offseason", "aa")
        _pick(2027, "offseason", "open")
        _pick(2026, "midseason", "aa")
        _pick(2026, "midseason", "open")
        _pick(2026, "offseason", "open")
        _pick(2025, "offseason", "aa")

    def test_index_lists_every_draft_in_the_database(self):
        response = self.client.get("/draft/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/draft/2027/offseason/aa/")
        self.assertContains(response, "/draft/2026/midseason/open/")
        self.assertContains(response, "/draft/2025/offseason/aa/")

    def test_index_groups_drafts_by_year(self):
        body = self.client.get("/draft/").content.decode()

        year_2027 = body.index('<h2 class="text-lg font-bold mt-6 mb-1">2027</h2>')
        aa = body.index('href="/draft/2027/offseason/aa/"', year_2027)
        open_draft = body.index('href="/draft/2027/offseason/open/"', aa)
        year_2026 = body.index('<h2 class="text-lg font-bold mt-6 mb-1">2026</h2>', open_draft)
        mid_aa = body.index('href="/draft/2026/midseason/aa/"', year_2026)
        mid_open = body.index('href="/draft/2026/midseason/open/"', mid_aa)
        off_open = body.index('href="/draft/2026/offseason/open/"', mid_open)
        year_2025 = body.index('<h2 class="text-lg font-bold mt-6 mb-1">2025</h2>', off_open)
        body.index('href="/draft/2025/offseason/aa/"', year_2025)

        aa_text = body[body.index(">", aa) + 1:body.index("</a>", aa)]
        self.assertEqual(aa_text, "Offseason AA")

    def test_empty_index_says_there_are_no_drafts(self):
        models.DraftPick.objects.all().delete()

        response = self.client.get("/draft/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No drafts available.")

    def test_nav_omits_drafts_older_than_the_three_most_recent(self):
        body = self.client.get("/draft/").content.decode()

        # Recent boards are linked from the nav and from the index.
        # Older boards are linked from the index only.
        self.assertGreaterEqual(body.count('href="/draft/2027/offseason/aa/"'), 2)
        self.assertGreaterEqual(body.count('href="/draft/2026/offseason/open/"'), 2)
        self.assertEqual(body.count('href="/draft/2025/offseason/aa/"'), 1)
        self.assertIn('href="/draft/"', body)

    def test_old_drafts_path_redirects_to_the_index(self):
        response = self.client.get("/drafts/")

        self.assertRedirects(response, "/draft/", fetch_redirect_response=False)

    def test_nav_does_not_link_to_the_wordpress_archive(self):
        response = self.client.get("/draft/")

        self.assertContains(response, 'href="/draft/"')
        self.assertNotContains(response, "ulmg.wordpress.com")
        self.assertNotContains(response, "Archived drafts")
