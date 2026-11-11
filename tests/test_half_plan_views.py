# ABOUTME: End-to-end tests for the half plan pages: the public plan, the plan editor and the day editor.
# ABOUTME: Posts real forms over the test client as the owner, another owner, the commissioner and logged out.

import re

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import decision_cards, models, plans, usage
from ulmg.views.plan import by_last_name
from tests.plan_fixtures import SEASON, Roster, create_hitter, create_pitcher, create_season


def form_data(roster, rotation=None, vs_lhp=None, vs_rhp=None):
    data = {
        "rotation": [p.id for p in (rotation or roster.starters)],
        "closer": roster.relievers[0].id,
        "setup": [roster.relievers[1].id],
        "middle_long": [roster.swingman.id],
        "bench": [p.id for p in roster.bench],
    }
    for prefix, lineup in (("vs_lhp", vs_lhp), ("vs_rhp", vs_rhp)):
        for i, entry in enumerate(lineup or roster.lineup(), start=1):
            data[f"{prefix}_order_{i}"] = entry["order"]
            data[f"{prefix}_player_{i}"] = entry["player"].id
            data[f"{prefix}_position_{i}"] = entry["position"]
    return data


def day_data(starter=None, lineup=None):
    data = {"starter": starter.id if starter else ""}
    if lineup:
        data["override_lineup"] = "1"
        for i, entry in enumerate(lineup, start=1):
            data[f"day_order_{i}"] = entry["order"]
            data[f"day_player_{i}"] = entry["player"].id
            data[f"day_position_{i}"] = entry["position"]
    return data


def create_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=f"{username} owner", email=user.email)
    team.owner_obj = owner
    team.save()
    return user


PLAN_URL = f"/teams/atl/plan/1/{SEASON}/"
EDIT_URL = f"/teams/atl/plan/1/{SEASON}/edit/"
ROTATION_URL = f"/teams/atl/plan/1/{SEASON}/rotation/"
DESIGNATION_URL = f"/teams/atl/plan/1/{SEASON}/designation/"
SCHEDULE_URL = f"/teams/atl/schedule/{SEASON}/"


def articles(body, player_id):
    """Every decision card for one player, stack copies and slot copies."""
    return re.findall(
        rf'<article\b[^>]*\bdata-player="{player_id}"[^>]*>.*?</article>',
        body,
        re.S,
    )


def stack_html(body):
    """The first card list, before the editor form."""
    return body.split("data-stack", 1)[1].split("<form", 1)[0]


def day_url(day, half=1):
    return f"/teams/atl/plan/{half}/{SEASON}/day/{day}/"


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class PlanViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.car = models.Team.objects.get(abbreviation="CAR")
        cls.roster = Roster(cls.atl)
        cls.owner = create_owner("atl", cls.atl)
        cls.other_owner = create_owner("car", cls.car)
        cls.commissioner = User.objects.create_superuser("commish", "commish@example.com", "password")

    def setUp(self):
        self.client = Client()

    def as_user(self, user):
        self.client.force_login(user)
        return self.client

    def saved_plan(self):
        return models.HalfPlan.objects.filter(team=self.atl, season=SEASON, half=1).first()


class PublicPlanTestCase(PlanViewsTestCase):
    def test_plan_is_public(self):
        self.roster.file()
        response = self.client.get(PLAN_URL)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('data-lineup="vs_rhp"', body)
        self.assertIn('data-lineup="vs_lhp"', body)
        self.assertIn("lg:grid-cols-2", body)
        self.assertIn(">vs Righty<", body)
        self.assertIn(">vs Lefty<", body)
        self.assertNotIn(">vR<", body)
        self.assertNotIn(">vL<", body)
        self.assertNotIn("Clear all", body)
        self.assertNotIn('aria-label="Remove from this spot"', body)
        self.assertIn("ATL Catcher", body)
        self.assertNotIn('class="plan-day ', body)
        self.assertIn("These lineups use the 2026 MLB cards", body)
        self.assertNotIn("Set lineups", body)
        rotation = self.client.get(ROTATION_URL).content.decode()
        self.assertIn("ATL Starter 1", rotation)
        self.assertNotIn("Push rotation to schedule", rotation)

    def test_plan_shows_cards_and_usage(self):
        self.roster.file()
        body = self.client.get(PLAN_URL).content.decode()
        self.assertIn("C +4.0", body)
        self.assertIn("PA unlimited", body)
        self.assertIn("Spd -", body)

    def test_plan_page_without_a_plan(self):
        response = self.client.get(PLAN_URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ATL has not filed lineups for this half", response.content.decode())

    def test_logged_out_editor_redirects_to_login(self):
        response = self.client.get(EDIT_URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_another_owner_can_read_but_not_edit(self):
        self.roster.file()
        client = self.as_user(self.other_owner)
        self.assertEqual(client.get(PLAN_URL).status_code, 200)
        self.assertNotIn("Set lineups", client.get(PLAN_URL).content.decode())
        self.assertEqual(client.get(EDIT_URL).status_code, 403)

        reversed_rotation = list(reversed(self.roster.starters))
        response = client.post(EDIT_URL, form_data(self.roster, rotation=reversed_rotation))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.saved_plan().rotation, [p.id for p in self.roster.starters])

        response = client.post(day_url(20), day_data(starter=self.roster.swingman))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.saved_plan().days.filter(manual_starter__isnull=False).exists())

    def test_capped_batter_is_flagged(self):
        self.roster.file()
        counter = usage.counter_for(self.roster.hitters[-1], SEASON)
        counter.plate_appearances_cap = 10
        counter.plate_appearances = 10
        counter.save()
        body = self.client.get(PLAN_URL).content.decode()
        self.assertIn("past his PA cap", body)


class EditPlanTestCase(PlanViewsTestCase):
    def test_owner_saves_a_plan(self):
        client = self.as_user(self.owner)
        page = client.get(EDIT_URL)
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn("Save lineups", body)
        self.assertIn('data-lineup="vs_rhp"', body)
        self.assertIn('data-lineup="vs_lhp"', body)
        self.assertIn("lg:grid-cols-2", body)
        self.assertNotIn("<select", body.split("<main", 1)[1])
        self.assertIn('data-position-buttons', body)
        self.assertIn('data-positions="C,1B,DH"', body)
        self.assertIn('data-positions="1B,2B,3B,SS,LF,CF,RF,DH"', body)
        self.assertIn('data-positions="1B,LF,CF,RF,DH"', body)
        self.assertNotIn('type="radio" name="vs_rhp_position_', body)
        self.assertIn('name="vs_rhp_position_1"', body)
        self.assertIn("slot-well", body)
        self.assertIn("background: #e5e7eb", body)
        self.assertIn(">vs Righty<", body)
        self.assertIn(">vs Lefty<", body)
        self.assertEqual(body.count(">Clear all<"), 2)
        self.assertEqual(body.count('aria-label="Remove from this spot"'), 18)
        self.assertNotIn(">Clear<", body)
        self.assertNotIn("slot-remove", stack_html(body))
        self.assertIn("slot-frame:not(:has(.decision-card)) .slot-remove", body)

        response = client.post(EDIT_URL, form_data(self.roster), follow=True)
        self.assertRedirects(response, PLAN_URL)
        self.assertIn("Saved the half 1 lineups", response.content.decode())
        plan = self.saved_plan()
        self.assertEqual(plan.lineup_vs_rhp[0], {"player": self.roster.catcher.id, "position": "C"})
        self.assertEqual(plan.rotation, [])
        self.assertFalse(plan.days.exists())

        response = client.post(ROTATION_URL, {"rotation": [p.id for p in self.roster.starters]}, follow=True)
        self.assertRedirects(response, SCHEDULE_URL)
        self.assertIn("Pushed the rotation onto the schedule", response.content.decode())
        plan.refresh_from_db()
        self.assertEqual(plans.starters(plan)[6], self.roster.starters[0])
        self.assertFalse(usage.counter_for(self.roster.starters[0], SEASON).confined_to_relief)

    def test_owner_sets_the_starter_hook(self):
        client = self.as_user(self.owner)
        page = client.get(EDIT_URL).content.decode()
        self.assertIn('value="normal" checked', page)
        response = client.post(EDIT_URL, dict(form_data(self.roster), starter_hook="quick"), follow=True)
        self.assertRedirects(response, PLAN_URL)
        self.assertEqual(self.saved_plan().starter_hook, models.HalfPlan.QUICK_HOOK)
        self.assertIn("Starter hook: Quick", response.content.decode())
        page = client.get(EDIT_URL).content.decode()
        self.assertIn('value="quick" checked', page)

    def test_an_unknown_starter_hook_is_refused(self):
        self.roster.file()
        response = self.as_user(self.owner).post(EDIT_URL, dict(form_data(self.roster), starter_hook="lazy"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("The starter hook must be quick, normal or slow.", response.content.decode())
        self.assertEqual(self.saved_plan().starter_hook, models.HalfPlan.NORMAL_HOOK)

    def test_editor_shows_the_saved_plan(self):
        self.roster.file()
        body = self.as_user(self.owner).get(ROTATION_URL).content.decode()
        self.assertIn(f'name="rotation" value="{self.roster.starters[0].id}"', body)
        self.assertIn("32 GS (max 34)", body)
        self.assertIn("190.0 IP", body)

    def test_commissioner_can_edit_any_plan(self):
        response = self.as_user(self.commissioner).post(EDIT_URL, form_data(self.roster))
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.saved_plan())

    def test_rule_errors_are_shown_and_nothing_is_saved(self):
        lineup = self.roster.lineup()
        lineup[8]["player"] = self.roster.starters[0]
        response = self.as_user(self.owner).post(EDIT_URL, form_data(self.roster, vs_rhp=lineup))
        self.assertEqual(response.status_code, 400)
        body = response.content.decode()
        self.assertIn("ATL Starter 1 is a pitcher; pitchers do not hit.", body)
        # The posted selections are kept on the form.
        self.assertIn(f'data-player="{self.roster.starters[0].id}"', body)
        plan = self.saved_plan()
        self.assertTrue(plan is None or not plan.days.exists())

    def test_save_rejected_listing_days_without_a_starter(self):
        self.roster.file()
        response = self.as_user(self.owner).post(
            ROTATION_URL, {"rotation": [p.id for p in self.roster.starters[:3]]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertRegex(response.content.decode(), r"No legal starter for days 4, ")

    def test_second_half_locked_until_2h(self):
        url = f"/teams/atl/plan/2/{SEASON}/edit/"
        client = self.as_user(self.owner)
        self.assertIn("opens after the trade break", client.get(url).content.decode())
        response = client.post(url, form_data(self.roster))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.HalfPlan.objects.filter(half=2).exists())
        public = self.client.get(f"/teams/atl/plan/2/{SEASON}/").content.decode()
        self.assertIn("opens after the trade break", public)
        self.assertIn("ATL has not filed lineups for this half", public)

        with self.settings(TEAM_SEASON_HALF="2h"):
            response = client.post(ROTATION_URL.replace("/plan/1/", "/plan/2/"), {"rotation": [p.id for p in self.roster.starters]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(models.HalfPlanDay.objects.filter(plan__half=2).count(), 81)

    def test_unknown_half_is_not_found(self):
        self.assertEqual(self.client.get(f"/teams/atl/plan/3/{SEASON}/").status_code, 404)

    def test_card_lists_are_sorted_by_last_name(self):
        aaron = models.Player(name="Zack Aaron", first_name="Zack", last_name="Aaron", pk=2)
        zulu = models.Player(name="Adam Zulu", first_name="Adam", last_name="Zulu", pk=1)
        bare = models.Player(name="Moe Only", pk=3)
        self.assertEqual(
            [player.name for player in by_last_name([zulu, bare, aaron])],
            ["Zack Aaron", "Moe Only", "Adam Zulu"],
        )
        create_hitter(self.atl, "Zack Aaron")
        create_hitter(self.atl, "Adam Zulu")
        create_pitcher(self.atl, "Zack Aaron")
        create_pitcher(self.atl, "Adam Zulu")
        client = self.as_user(self.owner)
        hitters = stack_html(client.get(EDIT_URL).content.decode())
        self.assertLess(hitters.index("Zack Aaron"), hitters.index("Adam Zulu"))
        pitchers = stack_html(client.get(ROTATION_URL).content.decode())
        self.assertLess(pitchers.index("Zack Aaron"), pitchers.index("Adam Zulu"))

    def test_cards_wash_green_above_average_and_pink_below(self):
        models.Card.objects.filter(player=self.roster.catcher).update(wrc_plus=150)
        models.Card.objects.filter(player=self.roster.bench[0]).update(wrc_plus=50)
        client = self.as_user(self.owner)
        body = client.get(EDIT_URL).content.decode()
        good = articles(body, self.roster.catcher.id)[0]
        bad = articles(body, self.roster.bench[0].id)[0]
        self.assertIn(f"background-color: {decision_cards.hitter_shade(150)}", good)
        self.assertIn(f"background-color: {decision_cards.hitter_shade(50)}", bad)
        plain = articles(body, self.roster.bench[1].id)[0]
        self.assertNotIn("background-color", plain)

    def test_a_pitcher_who_never_started_shows_as_a_reliever(self):
        client = self.as_user(self.owner)
        body = client.get(ROTATION_URL).content.decode()
        reliever = articles(body, self.roster.relievers[0].id)[0]
        starter = articles(body, self.roster.starters[0].id)[0]
        swingman = articles(body, self.roster.swingman.id)[0]
        self.assertIn('data-designation="bullpen"', reliever)
        self.assertIn('data-designation="bullpen" class="border border-gray-400 px-1 leading-none bg-gray-800 text-white"', reliever)
        self.assertIn('data-designation="rotation"', starter)
        self.assertIn('data-designation="rotation"', swingman)
        self.assertFalse(models.UsageCounter.objects.filter(player=self.roster.relievers[0]).exists())
        self.assertIn("reliever innings bonus", body)

    def test_owner_designates_a_swingman_reliever_and_it_sticks(self):
        client = self.as_user(self.owner)
        response = client.post(
            DESIGNATION_URL,
            {"player": self.roster.swingman.id, "designation": "bullpen"},
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 204)
        counter = usage.counter_for(self.roster.swingman, SEASON)
        self.assertTrue(counter.confined_to_relief)
        self.assertEqual(usage.season_innings_cap(counter), counter.confined_innings_cap_outs)
        self.assertGreater(counter.confined_innings_cap_outs, counter.innings_cap_outs)
        body = client.get(ROTATION_URL).content.decode()
        for card in articles(body, self.roster.swingman.id):
            self.assertIn('data-designation="bullpen"', card)

        response = client.post(
            ROTATION_URL, {"rotation": [p.id for p in self.roster.starters]}, follow=True
        )
        self.assertRedirects(response, SCHEDULE_URL)
        counter.refresh_from_db()
        self.assertTrue(counter.confined_to_relief)

        response = client.post(
            DESIGNATION_URL,
            {"player": self.roster.swingman.id, "designation": "rotation"},
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 204)
        counter.refresh_from_db()
        self.assertFalse(counter.confined_to_relief)

    def test_only_the_owner_can_designate_a_roster_pitcher(self):
        self.roster.file()
        other = self.as_user(self.other_owner)
        response = other.post(
            DESIGNATION_URL, {"player": self.roster.swingman.id, "designation": "rotation"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(usage.counter_for(self.roster.swingman, SEASON).confined_to_relief)

        owner = self.as_user(self.owner)
        response = owner.post(DESIGNATION_URL, {"player": self.roster.catcher.id, "designation": "bullpen"})
        self.assertEqual(response.status_code, 400)
        response = owner.post(DESIGNATION_URL, {"player": self.roster.swingman.id, "designation": "closer"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(usage.counter_for(self.roster.swingman, SEASON).confined_to_relief)

        logged_out = Client().post(
            DESIGNATION_URL, {"player": self.roster.swingman.id, "designation": "rotation"}
        )
        self.assertEqual(logged_out.status_code, 302)
        self.assertIn("/accounts/login/", logged_out["Location"])
        public = Client().get(ROTATION_URL).content.decode()
        card = articles(public, self.roster.swingman.id)[0]
        self.assertNotIn("<button", card)
        self.assertIn("Reliever", card)


class EditDayTestCase(PlanViewsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plan = cls.roster.file()

    def test_owner_sets_a_spot_start_and_a_lineup(self):
        lineup = self.roster.lineup(self.roster.hitters[:-1] + [self.roster.bench[1]])
        client = self.as_user(self.owner)
        page = client.get(day_url(20))
        self.assertEqual(page.status_code, 200)
        day_body = page.content.decode()
        self.assertEqual(day_body.count(">Clear all<"), 1)
        self.assertEqual(day_body.count('aria-label="Remove from this spot"'), 9)
        self.assertIn(">Rotation<", day_body)
        response = client.post(day_url(20), day_data(starter=self.roster.swingman, lineup=lineup), follow=True)
        self.assertRedirects(response, SCHEDULE_URL + "#day-20", fetch_redirect_response=False)
        body = response.content.decode()
        self.assertIn("ends his relief-only designation", body)
        row = self.plan.days.get(day=20)
        self.assertEqual(row.manual_starter, self.roster.swingman)
        self.assertEqual(row.manual_lineup[-1], {"player": self.roster.bench[1].id, "position": "DH"})
        self.assertRegex(body, r'(?s)data-day="20".*?ATL Swingman\*')

    def test_spot_start_breaking_rest_is_rejected(self):
        response = self.as_user(self.owner).post(day_url(3), day_data(starter=self.roster.starters[0]))
        self.assertEqual(response.status_code, 400)
        self.assertIn("has not had rest", response.content.decode())
        self.assertIsNone(self.plan.days.get(day=3).manual_starter)

    def test_clearing_a_day_returns_it_to_auto_fill(self):
        client = self.as_user(self.owner)
        client.post(day_url(20), day_data(starter=self.roster.swingman))
        client.post(day_url(20), day_data())
        self.assertIsNone(self.plan.days.get(day=20).manual_starter)

    def test_an_opened_day_cannot_be_edited(self):
        game = next(g for g in plans.half_games(self.atl, SEASON, 1).values() if g.day == 1)
        plans.open_game(game)
        client = self.as_user(self.owner)
        self.assertIn("has opened", client.get(day_url(1)).content.decode())
        response = client.post(day_url(1), day_data(starter=self.roster.swingman))
        self.assertEqual(response.status_code, 400)
        body = client.get(SCHEDULE_URL).content.decode()
        self.assertRegex(body, r'(?s)data-day="1".*?Opened')
        self.assertEqual(body.count("starter-slot"), 80)

    def test_lineup_override_rule_errors(self):
        stranger = create_hitter(self.car, "CAR Hitter")
        lineup = self.roster.lineup()
        lineup[8]["player"] = stranger
        response = self.as_user(self.owner).post(day_url(10), day_data(lineup=lineup))
        self.assertEqual(response.status_code, 400)
        self.assertIn("CAR Hitter is not on ATL&#x27;s 30-man", response.content.decode())


class SchedulePlannedStartersTestCase(PlanViewsTestCase):
    def test_team_schedule_shows_the_plans_starters(self):
        self.roster.file()
        body = self.client.get(SCHEDULE_URL).content.decode()
        self.assertRegex(body, r'(?s)data-day="1">.*?class="schedule-starters[^"]*">ATL Starter 1 vs -</td>')
        self.assertRegex(body, r'(?s)data-day="6">.*?class="schedule-starters[^"]*">ATL Starter 1 vs -</td>')
        self.assertEqual(body.count("ATL Starter 1 vs"), 17)
