# ABOUTME: Playing time on the lineup, rotation and bullpen pages: managers split plate appearances by position, plan starts and bullpen innings, and read the gaps.
# ABOUTME: Anyone can read it. Only the owner and the commissioner can save a spot. The depth-chart address opens the lineups.

from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import Client, TestCase

from tests.test_depth import SEASON, make_player, make_team
from ulmg import models, plans, utils


def make_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=username, email=user.email)
    team.owner_obj = owner
    team.save()
    return user


def section(body, code):
    return body.split(f'data-bucket="{code}"', 1)[1].split('data-bucket="', 1)[0]


def player_row(body, player_id):
    """The playing-time summary row. The lineup cards above it use the same player id."""
    table = body.split('id="depth-players"', 1)[1]
    return table.split(f'data-player="{player_id}"', 1)[1].split("</tr>", 1)[0]


class PlayingTimePagesTest(TestCase):
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
        self.lineups = f"/teams/atl/plan/1/{SEASON}/"
        self.edit = f"/teams/atl/plan/1/{SEASON}/edit/"
        self.rotation = f"/teams/atl/plan/1/{SEASON}/rotation/"
        self.bullpen = f"/teams/atl/plan/1/{SEASON}/bullpen/"

    def sign_in(self, user):
        self.client.force_login(user)
        return self.client

    def save(self, url, bucket, rows=(), player=None, amount="", unlimited=False):
        """Post one spot. rows are (assignment, amount, unlimited, remove)."""
        data = {"action": "spot", "bucket": bucket, "assignment": []}
        for row, row_amount, row_unlimited, remove in rows:
            data["assignment"].append(row.id)
            data[f"amount_{row.id}"] = row_amount
            if row_unlimited:
                data[f"unlimited_{row.id}"] = "on"
            if remove:
                data[f"remove_{row.id}"] = "on"
        if player is not None:
            data["player"] = player.id
            data["amount"] = amount
            if unlimited:
                data["unlimited"] = "on"
        return self.client.post(url, data, follow=True)

    def test_the_depth_chart_address_opens_the_lineups_and_the_tab_is_gone(self):
        year = utils.league_season()
        self.assertRedirects(self.client.get("/teams/atl/depth/"), f"/teams/atl/depth/{year}/", fetch_redirect_response=False)
        self.assertRedirects(
            self.client.get(f"/teams/atl/depth/{SEASON}/"),
            f"/teams/atl/plan/{plans.current_half()}/{SEASON}/",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get("/teams/nope/depth/").status_code, 404)
        tabs = render_to_string(
            "includes/game_tabs.html",
            {"team": self.atl, "game_section": "lineups", "schedule_season": SEASON, "season_half": "1h", "user": AnonymousUser()},
        )
        self.assertNotIn("Depth charts", tabs)
        self.assertNotIn("/depth/", tabs)

    def test_anyone_reads_the_split_on_the_lineups_page_without_a_form(self):
        page = self.client.get(self.lineups)
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn('id="playing-time"', body)
        self.assertIn("Playing time by position", body)
        self.assertIn("Lineup card plays", section(body, "C"))
        self.assertIn("6,097", body)
        self.assertIn("The lineup card plays.", section(body, "SS"))
        self.assertNotIn('name="action"', body)
        self.assertNotIn('data-bucket="SP"', body)

    def test_the_owner_splits_seager_between_second_and_short_on_the_lineup_editor(self):
        self.sign_in(self.owner)
        first = self.save(self.edit, "2B", player=self.seager, amount="200")
        self.assertEqual(first.redirect_chain[-1][0], self.edit + "#playing-time")
        self.assertContains(first, "Saved the playing time.")
        second = self.save(self.edit, "SS", player=self.seager, amount="236")
        body = second.content.decode()
        self.assertIn("477 PA to the card", section(body, "2B"))
        self.assertIn("The lineup card&#x27;s starter at SS takes the other 441 plate appearances.", section(body, "SS"))
        row = player_row(body, self.seager.id)
        self.assertIn("436", row)
        self.assertIn("200 PA at 2B", row)
        self.assertIn("236 PA at SS", row)
        self.assertEqual(models.DepthAssignment.objects.filter(chart__team=self.atl).count(), 2)
        public = self.client.get(self.lineups).content.decode()
        self.assertIn("Corey Seager: 236 PA", section(public, "SS"))

    def test_a_player_down_for_more_than_his_cap_is_flagged(self):
        models.UsageCounter.objects.create(player=self.seager, season=SEASON, plate_appearances_cap=436)
        self.sign_in(self.owner)
        self.save(self.edit, "2B", player=self.seager, amount="300")
        page = self.save(self.edit, "SS", player=self.seager, amount="236")
        row = player_row(page.content.decode(), self.seager.id)
        self.assertIn("He is down for 536 PA and his cap is 436.", row)

    def test_one_save_changes_a_number_marks_the_rest_and_drops_a_row(self):
        self.sign_in(self.owner)
        self.save(self.edit, "1B", player=self.seager, amount="200")
        self.save(self.edit, "1B", player=self.greene, amount="100")
        seager = models.DepthAssignment.objects.get(player=self.seager)
        greene = models.DepthAssignment.objects.get(player=self.greene)
        page = self.save(self.edit, "1B", rows=[(seager, "", True, False), (greene, "100", False, True)])
        first = section(page.content.decode(), "1B")
        self.assertIn('data-state="covered"', first)
        self.assertIn("Corey Seager takes the other 677 plate appearances.", first)
        self.assertEqual(list(models.DepthAssignment.objects.values_list("player__name", "unlimited")), [("Corey Seager", True)])

    def test_a_bad_row_saves_nothing_in_the_spot(self):
        self.sign_in(self.owner)
        self.save(self.edit, "1B", player=self.seager, amount="200")
        seager = models.DepthAssignment.objects.get()
        page = self.save(self.edit, "1B", rows=[(seager, "250", False, False)], player=self.ohtani, amount="lots")
        self.assertEqual(page.status_code, 400)
        self.assertContains(page, "Shohei Ohtani: Plate appearances have to be a whole number.", status_code=400)
        self.assertEqual(models.DepthAssignment.objects.get().amount, 200)

    def test_a_lefty_stays_off_shortstop_and_a_stranger_stays_off_the_team(self):
        self.sign_in(self.owner)
        blocked = self.save(self.edit, "SS", player=self.greene, amount="100")
        self.assertContains(blocked, "throws left and cannot play SS", status_code=400)
        stranger = make_player(self.car, "Juan Soto", position="OF")
        refused = self.save(self.edit, "RF", player=stranger, amount="100")
        self.assertContains(refused, "is not on ATL", status_code=400)
        self.assertEqual(models.DepthAssignment.objects.count(), 0)
        body = self.client.get(self.edit).content.decode()
        self.assertNotIn(f'value="{self.greene.id}"', section(body, "SS"))
        self.assertIn(f'value="{self.greene.id}"', section(body, "1B"))

    def test_the_player_box_is_a_typeahead_of_the_mlb_roster(self):
        farm = make_player(self.atl, "Farm Bat", position="OF", mlb=False)
        self.sign_in(self.owner)
        page = self.client.get(self.edit)
        body = page.content.decode()
        first = section(body, "1B")
        self.assertIn("data-depth-select", first)
        self.assertIn('aria-label="Add a player at 1B"', first)
        self.assertIn(f'value="{self.seager.id}"', first)
        self.assertIn(">Corey Seager<", first)
        self.assertNotIn(f'value="{farm.id}"', first)
        self.assertNotIn("Farm Bat", first)
        self.assertIn('querySelectorAll("[data-depth-select]")', body)
        refused = self.save(self.edit, "RF", player=farm, amount="100")
        self.assertContains(refused, "Farm Bat is not on the MLB roster.", status_code=400)
        self.assertEqual(models.DepthAssignment.objects.count(), 0)

    def test_a_lineup_spot_names_the_bat_wrc_and_war(self):
        self.seager.bats = "L"
        self.seager.save(update_fields=["bats"])
        models.PlayerStatSeason.objects.create(
            player=self.seager, season=SEASON - 1, classification="1-mlb", hit_stats={"war": 5.4, "wrc_plus": 100}
        )
        models.Card.objects.create(player=self.seager, season=SEASON - 1, wrc_plus=142)
        self.sign_in(self.owner)
        body = self.client.get(self.edit).content.decode()
        self.assertIn("Corey Seager · L · 142 wRC+ · 5.4 WAR", section(body, "1B"))

    def test_a_pitching_spot_names_the_hand_and_the_card_xfip(self):
        models.PlayerStatSeason.objects.create(
            player=self.strider, season=SEASON - 1, classification="1-mlb", pitch_stats={"xfip": 2.85}
        )
        self.sign_in(self.owner)
        body = self.client.get(self.rotation).content.decode()
        self.assertIn("Spencer Strider · RHP · 2.85 xFIP", section(body, "SP"))
        self.assertIn("Shohei Ohtani · RHP", section(body, "SP"))

    def test_planned_starts_live_on_the_rotation_page(self):
        self.sign_in(self.owner)
        page = self.save(self.rotation, "SP", player=self.strider, amount="30")
        body = page.content.decode()
        self.assertIn("Planned starts", body)
        self.assertIn("132 starts in turn", section(body, "SP"))
        self.assertIn("Rotation starters with no number take the other 132 starts in turn.", section(body, "SP"))
        self.assertNotIn('data-bucket="SS"', body)
        self.assertNotIn('data-bucket="RP"', body)

    def test_planned_innings_live_on_the_bullpen_page(self):
        self.sign_in(self.owner)
        page = self.save(self.bullpen, "RP", player=self.ohtani, amount="100")
        body = page.content.decode()
        self.assertIn("Planned bullpen innings", body)
        self.assertIn("495 IP by role", section(body, "RP"))
        self.assertIn("Relievers with no number pitch the other 495 innings.", section(body, "RP"))
        self.assertNotIn('data-bucket="SP"', body)

    def test_another_owner_and_a_logged_out_visitor_cannot_save(self):
        data = {"action": "spot", "bucket": "SS", "player": self.seager.id, "amount": "10"}
        self.assertEqual(self.client.post(self.rotation, dict(data, bucket="SP", player=self.strider.id)).status_code, 403)
        self.assertEqual(self.client.post(self.bullpen, dict(data, bucket="RP", player=self.strider.id)).status_code, 403)
        self.sign_in(self.other)
        self.assertEqual(self.client.post(self.edit, data).status_code, 403)
        self.assertEqual(models.DepthAssignment.objects.count(), 0)

    def test_the_commissioner_can_split_a_teams_playing_time(self):
        self.sign_in(self.commissioner)
        page = self.save(self.edit, "SS", player=self.seager, amount="200")
        self.assertContains(page, "477 PA to the card")
        self.assertEqual(models.DepthAssignment.objects.get().player, self.seager)
