# ABOUTME: The depth-chart page: managers file plate appearances, starts and bullpen innings, and read the gaps.
# ABOUTME: Anyone can read a chart. Only the owner and the commissioner can change one.

from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import Client, TestCase

from tests.test_depth import SEASON, make_player, make_team
from ulmg import models, utils


def make_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=username, email=user.email)
    team.owner_obj = owner
    team.save()
    return user


class DepthPageTest(TestCase):
    def setUp(self):
        self.atl = make_team("ATL")
        self.car = make_team("CAR")
        self.seager = make_player(self.atl, "Corey Seager", position="IF")
        self.greene = make_player(self.atl, "Riley Greene", position="OF", throws="L")
        self.strider = make_player(self.atl, "Spencer Strider", position="P")
        self.ohtani = make_player(self.atl, "Shohei Ohtani", position="IF-P")
        self.owner = make_owner("atl", self.atl)
        self.other = make_owner("car", self.car)
        self.commissioner = User.objects.create_superuser("commish", "commish@example.com", "password")
        self.client = Client()
        self.url = f"/teams/atl/depth/{SEASON}/"

    def sign_in(self, user):
        self.client.force_login(user)
        return self.client

    def add(self, player, bucket, amount="", unlimited=False):
        data = {"action": "add", "bucket": bucket, "player": player.id, "amount": amount}
        if unlimited:
            data["unlimited"] = "on"
        return self.client.post(self.url, data, follow=True)

    def test_a_missing_year_and_a_capitalized_abbreviation_redirect_to_the_canonical_path(self):
        year = utils.league_season()
        bounced = self.client.get("/teams/atl/depth/")
        self.assertRedirects(bounced, f"/teams/atl/depth/{year}/")
        upper = self.client.get(f"/teams/ATL/depth/{SEASON}/")
        self.assertRedirects(upper, self.url)
        self.assertEqual(self.client.get("/teams/nope/depth/").status_code, 404)

    def test_anyone_can_read_the_holes_and_the_tabs_put_depth_charts_with_the_game(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn("Nothing is filed yet.", body)
        self.assertIn("6,097", body)
        self.assertIn("1,437", body)
        self.assertNotIn('name="action"', body)
        self.assertIn(">Depth charts</span>", body)
        self.assertLess(body.index(">Schedule<"), body.index(">Lineups<"))
        self.assertLess(body.index(">Lineups<"), body.index(">Depth charts<"))
        self.assertLess(body.index(">Depth charts<"), body.index(">Rotation<"))
        self.assertLess(body.index(">Rotation<"), body.index(">Bullpen<"))
        tabs = render_to_string(
            "includes/game_tabs.html",
            {"team": self.atl, "game_section": "lineups", "schedule_season": SEASON, "season_half": "1h", "user": AnonymousUser()},
        )
        self.assertIn(f'href="/teams/atl/depth/{SEASON}/"', tabs)
        self.assertLess(tabs.index(">Lineups<"), tabs.index(">Depth charts<"))
        self.assertLess(tabs.index(">Depth charts<"), tabs.index(">Rotation<"))

    def test_the_owner_files_a_player_at_two_positions_and_sees_each_shortfall(self):
        self.sign_in(self.owner)
        first = self.add(self.seager, "SS", "200")
        self.assertContains(first, "477 PA short")
        self.assertContains(first, "SS is 477 plate appearances short.")
        second = self.add(self.seager, "2B", "236")
        self.assertContains(second, "441 PA short")
        self.assertContains(second, "2B is 441 plate appearances short.")
        row = second.content.decode().split(f'data-player="{self.seager.id}"', 1)[1].split("</tr>", 1)[0]
        self.assertIn("436", row)
        self.assertIn("200 PA at SS", row)
        self.assertIn("236 PA at 2B", row)
        self.assertEqual(models.DepthAssignment.objects.filter(chart__team=self.atl).count(), 2)

    def test_right_field_says_how_many_plate_appearances_are_still_open(self):
        self.sign_in(self.owner)
        page = self.add(self.seager, "RF", "477")
        self.assertContains(page, "200 PA short")
        self.assertContains(page, "RF is 200 plate appearances short.")
        section = page.content.decode().split('data-bucket="RF"', 1)[1].split('data-bucket="', 1)[0]
        self.assertIn("Counted: 477 PA", section)

    def test_an_unlimited_player_completes_a_spot_without_being_counted(self):
        self.sign_in(self.owner)
        self.add(self.seager, "RF", "200")
        page = self.add(self.greene, "LF", unlimited=True)
        body = page.content.decode()
        right = body.split('data-bucket="RF"', 1)[1].split('data-bucket="', 1)[0]
        left = body.split('data-bucket="LF"', 1)[1].split('data-bucket="', 1)[0]
        self.assertIn("Counted: 200 PA", right)
        self.assertIn('data-state="short"', right)
        self.assertIn('data-state="covered"', left)
        self.assertIn("Riley Greene takes the other 677 plate appearances.", left)
        self.assertIn("Unlimited — 677 PA", left)
        self.assertNotIn("LF is", body.split('id="depth-gaps"', 1)[1].split("</div>", 1)[0])

    def test_a_lefty_stays_off_shortstop_and_a_stranger_stays_off_the_team(self):
        self.sign_in(self.owner)
        blocked = self.add(self.greene, "SS", "100")
        self.assertContains(blocked, "throws left and cannot play SS")
        stranger = make_player(self.car, "Juan Soto", position="OF")
        refused = self.add(stranger, "RF", "100")
        self.assertContains(refused, "is not on ATL")
        self.assertEqual(models.DepthAssignment.objects.count(), 0)
        form = self.client.get(self.url).content.decode().split('data-bucket="SS"', 1)[1].split('data-bucket="', 1)[0]
        self.assertNotIn(f'value="{self.greene.id}"', form)
        first = self.client.get(self.url).content.decode().split('data-bucket="1B"', 1)[1].split('data-bucket="', 1)[0]
        self.assertIn(f'value="{self.greene.id}"', first)

    def test_the_owner_can_change_a_number_mark_it_unlimited_and_remove_it(self):
        self.sign_in(self.owner)
        self.add(self.seager, "SS", "200")
        row = models.DepthAssignment.objects.get()
        changed = self.client.post(
            self.url, {"action": "update", "assignment": row.id, "amount": "300"}, follow=True
        )
        self.assertContains(changed, "377 PA short")
        covered = self.client.post(
            self.url, {"action": "update", "assignment": row.id, "unlimited": "on"}, follow=True
        )
        section = covered.content.decode().split('data-bucket="SS"', 1)[1].split('data-bucket="', 1)[0]
        self.assertIn('data-state="covered"', section)
        self.assertIn("Counted: 0 PA", section)
        removed = self.client.post(self.url, {"action": "remove", "assignment": row.id}, follow=True)
        self.assertContains(removed, "Nothing is filed yet.")
        self.assertEqual(models.DepthAssignment.objects.count(), 0)

    def test_starts_and_bullpen_innings_show_their_own_gaps(self):
        self.sign_in(self.owner)
        starts = self.add(self.strider, "SP", "30")
        self.assertContains(starts, "132 starts short")
        self.assertContains(starts, "The rotation is 132 starts short.")
        pen = self.add(self.ohtani, "RP", "100")
        self.assertContains(pen, "495 IP short")
        self.assertContains(pen, "The bullpen is 495 innings short.")
        covered = self.add(self.ohtani, "SP", unlimited=True)
        rotation = covered.content.decode().split('data-bucket="SP"', 1)[1].split('data-bucket="', 1)[0]
        self.assertIn('data-state="covered"', rotation)
        self.assertIn("Counted: 30 starts", rotation)
        self.assertIn("Shohei Ohtani takes the other 132 starts.", rotation)

    def test_another_owner_and_a_logged_out_visitor_cannot_edit(self):
        self.sign_in(self.owner)
        self.add(self.seager, "RF", "477")
        self.client.logout()
        anonymous = self.client.post(self.url, {"action": "remove", "assignment": models.DepthAssignment.objects.get().id})
        self.assertEqual(anonymous.status_code, 403)
        self.sign_in(self.other)
        refused = self.client.post(self.url, {"action": "add", "bucket": "SS", "player": self.seager.id, "amount": "10"})
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(models.DepthAssignment.objects.count(), 1)
        page = self.client.get(self.url)
        self.assertContains(page, "200 PA short")
        self.assertNotContains(page, 'name="action"')

    def test_the_commissioner_can_file_a_chart_for_a_team(self):
        self.sign_in(self.commissioner)
        page = self.add(self.seager, "SS", "200")
        self.assertContains(page, "477 PA short")
        self.assertEqual(models.DepthAssignment.objects.get().player, self.seager)
