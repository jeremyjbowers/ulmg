# ABOUTME: End-to-end tests for the half plan pages: the public plan, the plan editor and the day editor.
# ABOUTME: Posts real forms over the test client as the owner, another owner, the commissioner and logged out.

import re
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import computer_manager, decision_cards, models, plans, schedule, usage, utils
from ulmg.views.plan import by_last_name
from tests.plan_fixtures import HITTER_RATES, SEASON, Roster, create_hitter, create_pitcher, create_season


def form_data(roster, rotation=None, vs_lhp=None, vs_rhp=None):
    data = {
        "rotation": [p.id for p in (rotation or roster.starters)],
        "closer": roster.relievers[0].id,
        "sirp": [roster.relievers[1].id],
        "mirp": [roster.swingman.id],
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
BULLPEN_URL = f"/teams/atl/plan/1/{SEASON}/bullpen/"
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


def slot_html(body, index):
    """The rotation slot numbered index, through the start of the next slot."""
    chunk = body.split(f'data-index="{index}"', 1)[1]
    if 'data-index="' in chunk:
        chunk = chunk.split('data-index="', 1)[0]
    return chunk


def order_group(body, name):
    """One pinch or defensive-replacement column, up to the next column."""
    chunk = body.split(f'data-lineup="{name}"', 1)[1]
    stops = [chunk.find(marker) for marker in ('data-lineup="', "<fieldset")]
    stops = [index for index in stops if index >= 0]
    if stops:
        chunk = chunk[: min(stops)]
    return chunk


HOOK_ON = "bg-gray-800 text-white"
HOOK_BUTTON = "border border-gray-400 px-1 leading-none"


def hook_button(value, label, selected):
    classes = HOOK_BUTTON + (f" {HOOK_ON}" if selected else "")
    return f'data-hook="{value}" class="{classes}">{label}'


@override_settings(CURRENT_SEASON=SEASON, CURRENT_SEASON_TYPE="midseason", TEAM_SEASON_HALF="1h")
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
        self.assertLess(body.index('data-lineup="vs_lhp"'), body.index('data-lineup="vs_rhp"'))
        self.assertIn("lg:grid-cols-2", body)
        self.assertIn(">vs Righty<", body)
        self.assertIn(">vs Lefty<", body)
        self.assertNotIn(">vR<", body)
        self.assertNotIn(">vL<", body)
        self.assertNotIn("Clear all", body)
        self.assertNotIn("Clear lineup", body)
        self.assertNotIn('aria-label="Remove from this spot"', body)
        self.assertNotIn("data-reorder", body)
        self.assertIn("ATL Catcher", body)
        self.assertNotIn("OPS R", body)
        self.assertNotIn('class="plan-day ', body)
        self.assertIn("These lineups use the 2026 MLB cards", body)
        self.assertNotIn("Set lineups", body)
        rotation = self.client.get(ROTATION_URL).content.decode()
        self.assertIn("ATL Starter 1", rotation)
        self.assertNotIn("Push rotation to schedule", rotation)
        self.assertNotIn('name="hook_1"', rotation)
        bullpen = self.client.get(BULLPEN_URL).content.decode()
        self.assertIn("ATL Reliever 1", bullpen)
        self.assertIn("ATL Swingman", bullpen)
        self.assertIn("Bullpen usage: Traditional closer", bullpen)
        self.assertIn("from the sixth", bullpen)
        self.assertNotIn("bullpen-choice", bullpen)
        self.assertIn(">SIRP<", bullpen)
        self.assertIn(">MIRP<", bullpen)
        self.assertNotIn("Bullpen logic", bullpen)
        self.assertNotIn("Save bullpen", bullpen)
        self.assertLess(bullpen.index(">Schedule<"), bullpen.index(">Lineups<"))
        self.assertLess(bullpen.index(">Lineups<"), bullpen.index(">Rotation<"))
        self.assertLess(bullpen.index(">Rotation<"), bullpen.index(">Bullpen<"))
        self.assertNotIn(">Results<", bullpen)
        self.assertNotIn(">Up next<", bullpen)

    def test_a_batting_order_offers_a_reorder_handle_and_names_an_empty_well(self):
        body = self.as_user(self.owner).get(EDIT_URL).content.decode()
        self.assertIn('data-reorder', body)
        self.assertIn(">Reorder<", body)
        self.assertIn("Drop a hitter here", body)

    def test_a_lineup_card_shows_vs_l_on_the_left_and_vs_r_on_the_right(self):
        self.roster.file()
        catcher = self.roster.catcher
        card = models.Card.objects.get(player=catcher)
        card.hitter_rates_vs_rhp = {"k": 0, "bb": 0, "hbp": 0, "single": 0.2, "double": 0, "triple": 0, "hr": 0.1}
        card.hitter_rates_vs_lhp = {"k": 0, "bb": 0.1, "hbp": 0, "single": 0.1, "double": 0, "triple": 0, "hr": 0}
        card.save()
        body = self.client.get(PLAN_URL).content.decode()
        shown = articles(body, catcher.id)[0]
        built = decision_cards.hitter_card(catcher, {"pa": 600}, card)
        self.assertLess(shown.index("vsL .111/.200/.111"), shown.index("vsR .300/.300/.600"))
        self.assertNotIn("linear-gradient", shown)
        self.assertLess(shown.index(f"background-color: {built['shade_vs_l']}"), shown.index("vsL"))
        self.assertLess(shown.index("vsL"), shown.index(f"background-color: {built['shade_vs_r']}"))
        self.assertLess(shown.index(f"background-color: {built['shade_vs_r']}"), shown.index("vsR"))

    def test_a_glove_of_minus_ten_or_worse_is_listed_as_emergency_only(self):
        shortstop = next(player for player in self.roster.fielders if player.name.endswith("SS"))
        card = models.Card.objects.get(player=shortstop)
        card.defense = {"SS": -10.0, "2B": -9.9}
        card.primary_position = "SS"
        card.save()
        self.roster.file()
        body = self.as_user(self.owner).get(EDIT_URL).content.decode()
        article = articles(body, shortstop.id)[0]
        self.assertIn('data-emergency="SS"', article)
        self.assertIn('title="Emergency only"', article)
        slot = re.search(
            rf'<li class="lineup-slot\b[^>]*>.*?data-player="{shortstop.id}".*?</li>',
            body,
            re.S,
        ).group(0)
        label = slot.index(">Emergency only:<")
        self.assertLess(slot.index('data-position="2B"'), label)
        self.assertLess(label, slot.index('data-position="SS" data-emergency'))
        self.assertNotIn("data-position-emergency", slot)

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
        self.assertLess(body.index('data-lineup="vs_lhp"'), body.index('data-lineup="vs_rhp"'))
        self.assertIn("lg:grid-cols-2", body)
        self.assertNotIn("<select", body.split("<main", 1)[1])
        self.assertIn('data-position-buttons', body)
        self.assertIn('data-positions="C,DH"', body)
        self.assertIn('data-positions="1B,2B,3B,SS,LF,CF,RF,DH"', body)
        self.assertIn('data-positions="1B,LF,CF,RF,DH"', body)
        self.assertNotIn('type="radio" name="vs_rhp_position_', body)
        self.assertIn('name="vs_rhp_position_1"', body)
        self.assertIn("slot-well", body)
        self.assertIn("background: #e5e7eb", body)
        self.assertIn(">vs Righty<", body)
        self.assertIn(">vs Lefty<", body)
        self.assertEqual(body.count(">Clear lineup<"), 2)
        self.assertIn('name="clear_lineup" value="vs_lhp"', body)
        self.assertIn('name="clear_lineup" value="vs_rhp"', body)
        self.assertNotIn(">Clear all<", body)
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

        response = client.post(
            BULLPEN_URL,
            {
                "closer": self.roster.relievers[0].id,
                "sirp": [self.roster.relievers[1].id],
                "mirp": [self.roster.swingman.id],
                "bullpen_logic": "leverage",
            },
            follow=True,
        )
        self.assertRedirects(response, BULLPEN_URL)
        self.assertIn("Saved the bullpen", response.content.decode())
        plan.refresh_from_db()
        self.assertEqual(plan.closer_id, self.roster.relievers[0].id)
        self.assertEqual(plan.sirp, [self.roster.relievers[1].id])
        self.assertEqual(plan.mirp, [self.roster.swingman.id])
        self.assertEqual(plan.bullpen_logic, models.HalfPlan.LEVERAGE_PEN)
        self.assertEqual(plan.rotation, [])
        self.assertFalse(plan.days.exists())
        self.assertIn("with a runner on", response.content.decode())
        self.assertIn("One inning from the 6th on", response.content.decode())
        self.assertIn("messy inning (1.1 or 1.2)", response.content.decode())
        self.assertIn("consecutive days", response.content.decode())
        self.assertNotIn("Name a closer", response.content.decode())
        saved = client.get(BULLPEN_URL).content.decode()
        self.assertIn('name="bullpen_logic" value="leverage"', saved)
        self.assertRegex(saved, r'data-bullpen-choice="leverage"[^>]*\bis-selected\b')

        response = client.post(ROTATION_URL, {"rotation": [p.id for p in self.roster.starters]}, follow=True)
        self.assertRedirects(response, SCHEDULE_URL)
        self.assertIn("Pushed the rotation onto the schedule", response.content.decode())
        plan.refresh_from_db()
        self.assertEqual(plans.starters(plan)[6], self.roster.starters[0])
        self.assertFalse(usage.counter_for(self.roster.starters[0], SEASON).confined_to_relief)

    def test_the_owner_clears_one_lineup_and_leaves_the_other(self):
        vs_lhp = self.roster.lineup(self.roster.hitters[:-1] + [self.roster.bench[1]])
        client = self.as_user(self.owner)
        client.post(EDIT_URL, form_data(self.roster, vs_lhp=vs_lhp))
        plan = self.saved_plan()
        rhp = list(plan.lineup_vs_rhp)
        hook = plan.starter_hook

        posted = form_data(self.roster)
        posted["clear_lineup"] = "vs_lhp"
        response = client.post(EDIT_URL, posted, follow=True)
        self.assertRedirects(response, EDIT_URL)
        self.assertIn("Cleared the vs Lefty lineup.", response.content.decode())
        plan.refresh_from_db()
        self.assertEqual(plan.lineup_vs_lhp, [])
        self.assertEqual(plan.lineup_vs_rhp, rhp)
        self.assertEqual(plan.starter_hook, hook)

        refused = self.as_user(self.other_owner).post(EDIT_URL, {"clear_lineup": "vs_rhp"})
        self.assertEqual(refused.status_code, 403)
        plan.refresh_from_db()
        self.assertEqual(plan.lineup_vs_rhp, rhp)

        bad = self.as_user(self.owner).post(EDIT_URL, {"clear_lineup": "bench"})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("Choose the lineup vs LHP or the lineup vs RHP.", bad.content.decode())
        plan.refresh_from_db()
        self.assertEqual(plan.lineup_vs_rhp, rhp)

    def test_a_day_page_exists_before_the_cards_are_filed(self):
        self.assertIsNone(self.saved_plan())
        response = self.as_user(self.owner).get(day_url(1))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This is a")
        self.assertIsNotNone(self.saved_plan())

    def test_the_editor_heading_names_the_half_and_the_lineups_follow(self):
        body = self.as_user(self.owner).get(EDIT_URL).content.decode()
        self.assertIn(">Set first half lineups<", body)
        self.assertIn("order-1", body)
        self.assertIn("order-2", body)
        self.assertIn("max-h-64", body)
        rotation = self.as_user(self.owner).get(ROTATION_URL).content.decode()
        self.assertIn("order-1", rotation)
        self.assertIn("max-h-64", rotation)
        self.assertLess(body.index(">Set first half lineups<"), body.index('data-lineup="vs_lhp"'))
        self.assertLess(body.index('data-lineup="vs_lhp"'), body.index('data-lineup="vs_rhp"'))
        self.assertNotIn("Drag a card into a slot", body)
        self.assertNotIn("These lineups use the", body)
        self.assertNotIn("A call-up plays road games only", body)
        self.assertNotIn("Games 82", body)
        self.assertNotIn("Back to the lineups", body)
        second = self.as_user(self.owner).get(EDIT_URL.replace("/plan/1/", "/plan/2/")).content.decode()
        self.assertIn(">Set second half lineups<", second)

    def test_owner_sets_the_starter_hook(self):
        client = self.as_user(self.owner)
        page = client.get(EDIT_URL).content.decode()
        self.assertIn('value="normal" checked', page)
        self.assertIn(">Default starter hook<", page)
        self.assertIn("no hook of his own", page)
        response = client.post(EDIT_URL, dict(form_data(self.roster), starter_hook="quick"), follow=True)
        self.assertRedirects(response, PLAN_URL)
        self.assertEqual(self.saved_plan().starter_hook, models.HalfPlan.QUICK_HOOK)
        self.assertIn("Starter hook: Quick", response.content.decode())
        page = client.get(EDIT_URL).content.decode()
        self.assertIn('value="quick" checked', page)

    def test_the_bullpen_page_offers_each_role_and_refuses_a_pitcher_in_two_of_them(self):
        client = self.as_user(self.owner)
        body = client.get(BULLPEN_URL).content.decode()
        self.assertIn("Save bullpen", body)
        self.assertIn('data-bullpen-group="closer"', body)
        self.assertIn('data-bullpen-group="sirp"', body)
        self.assertIn('data-bullpen-group="mirp"', body)
        self.assertIn(">SIRP<", body)
        self.assertIn(">MIRP<", body)
        self.assertIn('name="bullpen_logic"', body)
        self.assertIn('value="traditional"', body)
        self.assertRegex(body, r'data-bullpen-choice="traditional"[^>]*\bis-selected\b')
        self.assertIn(">Highest leverage<", body)
        self.assertIn(">Fireman<", body)
        self.assertIn(">Protect the lead<", body)
        self.assertIn(">Save the pen<", body)
        self.assertNotIn('type="radio"', body)
        self.assertIn("As soon as the starter is out", body)
        self.assertIn("at most 3 innings", body)
        self.assertIn("those innings are relief", body)
        self.assertIn("One inning from the 6th on, when the game is within three runs.", body)
        self.assertIn("The 9th or later, in a save.", body)
        self.assertIn("from the sixth", body)
        self.assertNotIn("Name a closer", body)
        self.assertLess(body.index(">Schedule<"), body.index(">Lineups<"))
        self.assertLess(body.index(">Lineups<"), body.index(">Rotation<"))
        self.assertLess(body.index(">Rotation<"), body.index(">Bullpen</span>"))
        self.assertNotIn(">Results<", body)
        self.assertNotIn(">Set lineups<", body)
        self.assertNotIn(">Set rotation<", body)

        response = client.post(
            BULLPEN_URL,
            {"closer": self.roster.relievers[0].id, "sirp": [self.roster.relievers[0].id], "bullpen_logic": "traditional"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("is in the bullpen twice", response.content.decode())
        self.assertIsNone(self.saved_plan())

    def test_advanced_bullpen_rules_are_optional_and_save_the_group_for_each_window(self):
        client = self.as_user(self.owner)
        body = client.get(BULLPEN_URL).content.decode()
        self.assertIn(">Advanced<", body)
        self.assertRegex(body, r'<button[^>]*data-bullpen-choice="traditional"[^>]*\bis-selected\b')
        self.assertNotRegex(body, r'<button[^>]*data-bullpen-choice="advanced"[^>]*\bis-selected\b')
        self.assertRegex(body, r'<div data-bullpen-advanced[^>]*\bhidden\b')
        self.assertIn("which group pitches the high-leverage innings", body)
        self.assertIn('data-rules=', body)
        self.assertIn("High-leverage relief uses", body)

        rules = dict(computer_manager.rules_for("fireman"), hold_role="mirp")
        posted = {
            "closer": self.roster.relievers[0].id,
            "sirp": [self.roster.relievers[1].id],
            "mirp": [self.roster.swingman.id],
            "bullpen_logic": "advanced",
        }
        posted.update(computer_manager.form_values(rules))
        response = client.post(BULLPEN_URL, posted, follow=True)
        self.assertRedirects(response, BULLPEN_URL)
        plan = self.saved_plan()
        self.assertEqual(plan.bullpen_logic, models.HalfPlan.ADVANCED_PEN)
        self.assertEqual(plan.bullpen_rules["hold_role"], "mirp")
        self.assertEqual(plan.bullpen_rules["closer_first"], 6)
        saved = client.get(BULLPEN_URL).content.decode()
        self.assertRegex(saved, r'<button[^>]*data-bullpen-choice="advanced"[^>]*\bis-selected\b')
        self.assertNotRegex(saved, r'<div data-bullpen-advanced[^>]*\bhidden\b')
        self.assertRegex(saved, r'<button[^>]*data-adv-choice="mirp"[^>]*\bis-selected\b')
        self.assertIn("Multi-inning relief pitches the seventh and eighth", saved)
        self.assertIn("Single-inning relief works the rest", saved)
        reader = self.as_user(self.other_owner).get(BULLPEN_URL).content.decode()
        self.assertIn("Bullpen usage: Advanced", reader)
        self.assertIn("Single-inning relief works the rest", reader)
        self.assertNotIn("data-bullpen-advanced", reader)
        self.assertNotIn("Save bullpen", reader)

        backwards = dict(posted, adv_hold_min_lead="3", adv_hold_max_lead="0")
        refused = self.as_user(self.owner).post(BULLPEN_URL, backwards)
        self.assertEqual(refused.status_code, 400)
        self.assertIn("smaller lead to a larger one", refused.content.decode())
        plan.refresh_from_db()
        self.assertEqual(plan.bullpen_rules["hold_min_lead"], 2)

        shortcut = dict(posted, bullpen_logic="fireman")
        response = client.post(BULLPEN_URL, shortcut, follow=True)
        self.assertRedirects(response, BULLPEN_URL)
        plan.refresh_from_db()
        self.assertEqual(plan.bullpen_logic, models.HalfPlan.FIREMAN_PEN)
        self.assertEqual(plan.bullpen_rules, {})

    def test_an_unknown_bullpen_logic_is_refused(self):
        self.roster.file(bullpen_logic=models.HalfPlan.SAVE_PEN)
        response = self.as_user(self.owner).post(
            BULLPEN_URL,
            {"closer": self.roster.relievers[0].id, "bullpen_logic": "wild"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "The bullpen logic must be traditional, leverage, fireman, protect, save or advanced.",
            response.content.decode(),
        )
        self.assertEqual(self.saved_plan().bullpen_logic, models.HalfPlan.SAVE_PEN)

    def test_another_owner_can_read_the_bullpen_but_not_set_it(self):
        self.roster.file()
        client = self.as_user(self.other_owner)
        self.assertEqual(client.get(BULLPEN_URL).status_code, 200)
        self.assertNotIn("Save bullpen", client.get(BULLPEN_URL).content.decode())
        response = client.post(
            BULLPEN_URL,
            {"closer": self.roster.swingman.id, "sirp": [self.roster.relievers[1].id], "bullpen_logic": "save"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.saved_plan().closer_id, self.roster.relievers[0].id)

    def test_the_lineup_page_saves_pinch_hitters_and_defensive_replacements(self):
        client = self.as_user(self.owner)
        page = client.get(EDIT_URL).content.decode()
        self.assertIn(">Pinch vs RHP<", page)
        self.assertIn(">Pinch vs LHP<", page)
        self.assertIn(">Defensive replacements<", page)
        self.assertLess(page.index(">Pinch vs RHP<"), page.index(">Pinch vs LHP<"))
        self.assertLess(page.index(">Pinch vs LHP<"), page.index(">Defensive replacements<"))
        self.assertIn('name="pinch_vs_rhp"', page)
        self.assertIn('name="pinch_vs_lhp"', page)
        self.assertIn('name="defensive_replacements"', page)
        self.assertIn("Empty uses the bench order.", page)
        for name in ("pinch_vs_rhp", "pinch_vs_lhp", "defensive_replacements"):
            group = order_group(page, name)
            self.assertEqual(group.count('class="lineup-slot'), 3, name)
            self.assertEqual(group.count(f'name="{name}"'), 3, name)
            self.assertEqual(group.count("data-add-slot"), 1, name)
            self.assertIn(">Add a slot<", group)
        self.assertIn("[data-add-slot]", page)

        bench = self.roster.bench
        data = form_data(self.roster)
        data["pinch_vs_rhp"] = [bench[1].id, bench[0].id]
        data["pinch_vs_lhp"] = [bench[0].id]
        data["defensive_replacements"] = [bench[1].id]
        response = client.post(EDIT_URL, data, follow=True)
        self.assertRedirects(response, PLAN_URL)
        plan = self.saved_plan()
        self.assertEqual(plan.pinch_vs_rhp, [bench[1].id, bench[0].id])
        self.assertEqual(plan.pinch_vs_lhp, [bench[0].id])
        self.assertEqual(plan.defensive_replacements, [bench[1].id])
        self.assertEqual(plan.lineup_vs_rhp[0], {"player": self.roster.catcher.id, "position": "C"})

        again = client.get(EDIT_URL).content.decode()
        self.assertLess(
            again.index(f'name="pinch_vs_rhp" value="{bench[1].id}"'),
            again.index(f'name="pinch_vs_rhp" value="{bench[0].id}"'),
        )
        self.assertIn(f'name="pinch_vs_lhp" value="{bench[0].id}"', again)
        self.assertIn(f'name="defensive_replacements" value="{bench[1].id}"', again)

    def test_an_empty_pinch_list_is_saved_and_clearing_a_lineup_leaves_the_lists(self):
        client = self.as_user(self.owner)
        data = form_data(self.roster)
        data["pinch_vs_rhp"] = [self.roster.bench[0].id]
        data["defensive_replacements"] = [self.roster.bench[1].id]
        client.post(EDIT_URL, data)
        plan = self.saved_plan()
        self.assertEqual(plan.pinch_vs_rhp, [self.roster.bench[0].id])

        cleared = client.post(EDIT_URL, {"clear_lineup": "vs_lhp"}, follow=True)
        self.assertRedirects(cleared, EDIT_URL)
        plan.refresh_from_db()
        self.assertEqual(plan.lineup_vs_lhp, [])
        self.assertEqual(plan.pinch_vs_rhp, [self.roster.bench[0].id])
        self.assertEqual(plan.defensive_replacements, [self.roster.bench[1].id])

        emptied = client.post(EDIT_URL, form_data(self.roster), follow=True)
        self.assertRedirects(emptied, PLAN_URL)
        plan.refresh_from_db()
        self.assertEqual(plan.pinch_vs_rhp, [])
        self.assertEqual(plan.pinch_vs_lhp, [])
        self.assertEqual(plan.defensive_replacements, [])
        self.assertEqual(len(plan.lineup_vs_rhp), 9)

    def test_a_pinch_list_refuses_a_pitcher_and_a_duplicate(self):
        self.roster.file(pinch_vs_lhp=[self.roster.bench[1]])
        data = form_data(self.roster)
        data["pinch_vs_rhp"] = [self.roster.relievers[0].id, self.roster.bench[0].id, self.roster.bench[0].id]
        data["defensive_replacements"] = [self.roster.relievers[1].id]
        response = self.as_user(self.owner).post(EDIT_URL, data)
        self.assertEqual(response.status_code, 400)
        body = response.content.decode()
        self.assertIn("pinch-hitter list vs RHP", body)
        self.assertIn("is a pitcher", body)
        self.assertIn("twice", body)
        self.assertIn("defensive-replacement list", body)
        plan = self.saved_plan()
        self.assertEqual(plan.pinch_vs_rhp, [])
        self.assertEqual(plan.pinch_vs_lhp, [self.roster.bench[1].id])
        self.assertEqual(plan.defensive_replacements, [])
        self.assertEqual(len(plan.lineup_vs_rhp), 9)

    def test_a_saved_list_longer_than_three_keeps_every_name_and_the_add_button(self):
        four = self.roster.bench + self.roster.fielders[:2]
        self.roster.file(pinch_vs_rhp=four, defensive_replacements=four[:1])
        page = self.as_user(self.owner).get(EDIT_URL).content.decode()
        rhp = order_group(page, "pinch_vs_rhp")
        defense = order_group(page, "defensive_replacements")
        left = order_group(page, "pinch_vs_lhp")
        self.assertEqual(rhp.count('class="lineup-slot'), 4)
        self.assertLess(rhp.index(f'value="{four[0].id}"'), rhp.index(f'value="{four[3].id}"'))
        self.assertEqual(defense.count('class="lineup-slot'), 3)
        self.assertIn(f'value="{four[0].id}"', defense)
        self.assertEqual(left.count('class="lineup-slot'), 3)
        self.assertIn(">Add a slot<", rhp)
        self.assertIn(">Add a slot<", defense)

    def test_an_unknown_starter_hook_is_refused(self):
        self.roster.file()
        response = self.as_user(self.owner).post(EDIT_URL, dict(form_data(self.roster), starter_hook="lazy"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("The starter hook must be quick, normal or slow.", response.content.decode())
        self.assertEqual(self.saved_plan().starter_hook, models.HalfPlan.NORMAL_HOOK)

    def test_the_owner_sets_a_hook_for_one_starter_and_leaves_another_on_the_default(self):
        self.roster.file(starter_hook=models.HalfPlan.SLOW_HOOK)
        client = self.as_user(self.owner)
        first, second = self.roster.starters[0], self.roster.starters[1]
        page = client.get(ROTATION_URL).content.decode()
        self.assertIn("Default uses the starter hook", page)
        self.assertNotIn('type="radio"', page)
        opened = slot_html(page, 1)
        self.assertIn('class="mt-1" data-starter-hook', opened)
        self.assertIn('name="hook_1" value=""', opened)
        self.assertIn(hook_button("", "Default", True), opened)
        self.assertIn(hook_button("quick", "Quick", False), opened)
        self.assertIn(hook_button("normal", "Normal", False), opened)
        self.assertIn(hook_button("slow", "Slow", False), opened)
        self.assertIn('class="mt-1 hidden" data-starter-hook', slot_html(page, 6))
        response = client.post(
            ROTATION_URL,
            {
                "rotation": [p.id for p in self.roster.starters],
                "hook_1": "quick",
                "hook_2": "",
            },
            follow=True,
        )
        self.assertRedirects(response, SCHEDULE_URL)
        plan = self.saved_plan()
        self.assertEqual(plan.starter_hook, models.HalfPlan.SLOW_HOOK)
        self.assertEqual(plan.starter_hooks, {str(first.id): models.HalfPlan.QUICK_HOOK})
        saved = client.get(ROTATION_URL).content.decode()
        chosen = slot_html(saved, 1)
        other = slot_html(saved, 2)
        self.assertIn('name="hook_1" value="quick"', chosen)
        self.assertIn(hook_button("quick", "Quick", True), chosen)
        self.assertIn(hook_button("", "Default", False), chosen)
        self.assertIn('name="hook_2" value=""', other)
        self.assertIn(hook_button("", "Default", True), other)
        self.assertIn(hook_button("quick", "Quick", False), other)
        summary = client.get(PLAN_URL).content.decode()
        self.assertIn("Starter hook: Slow", summary)
        self.assertIn(f"{first.name}: Quick hook", summary)
        self.assertNotIn(f"{second.name}:", summary)

    def test_the_plan_lists_a_starters_hook_only_when_it_differs_from_the_default(self):
        first, second = self.roster.starters[0], self.roster.starters[1]
        self.roster.file(
            starter_hook=models.HalfPlan.NORMAL_HOOK,
            starter_hooks={
                str(first.id): models.HalfPlan.QUICK_HOOK,
                str(second.id): models.HalfPlan.NORMAL_HOOK,
            },
        )
        body = self.client.get(PLAN_URL).content.decode()
        self.assertIn("Starter hook: Normal", body)
        self.assertIn(f"{first.name}: Quick hook", body)
        self.assertNotIn(f"{second.name}:", body)

    def test_an_unknown_hook_for_one_starter_is_refused(self):
        first = self.roster.starters[0]
        self.roster.file(starter_hooks={str(first.id): models.HalfPlan.SLOW_HOOK})
        response = self.as_user(self.owner).post(
            ROTATION_URL,
            {"rotation": [p.id for p in self.roster.starters], "hook_1": "lazy"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("The starter hook must be quick, normal or slow.", response.content.decode())
        self.assertEqual(self.saved_plan().starter_hooks, {str(first.id): models.HalfPlan.SLOW_HOOK})

    def test_the_rotation_page_counts_scheduled_and_completed_starts_against_remaining(self):
        self.roster.file()
        starter = self.roster.starters[0]
        counter = usage.counter_for(starter, SEASON)
        counter.starts = 4
        counter.save(update_fields=["starts"])
        counted = plans.start_usage(self.atl, SEASON, [starter])[starter.id]
        self.assertEqual(counted["made"], 4)
        self.assertGreater(counted["scheduled"], 0)
        self.assertEqual(
            counted["remaining"],
            counted["cap"] - counted["made"] - counted["scheduled"],
        )
        card = articles(
            stack_html(self.as_user(self.owner).get(ROTATION_URL).content.decode()),
            starter.id,
        )[0]
        self.assertIn(f"{counted['made']} completed", card)
        self.assertIn(f"{counted['scheduled']} scheduled", card)
        self.assertIn(f"{counted['remaining']} remaining", card)

    def test_rotation_starters_are_not_offered_for_the_bullpen(self):
        self.roster.file()
        body = self.as_user(self.owner).get(BULLPEN_URL).content.decode()
        stack = stack_html(body)
        for starter in self.roster.starters:
            self.assertNotIn(f'data-player="{starter.id}"', stack)
        for reliever in self.roster.relievers:
            self.assertIn(f'data-player="{reliever.id}"', stack)
        self.assertIn(f'data-player="{self.roster.swingman.id}"', stack)

    def test_a_rotation_starter_kept_in_a_bullpen_role_stays_in_that_role(self):
        starter = self.roster.starters[0]
        self.roster.file(closer=starter)
        body = self.as_user(self.owner).get(BULLPEN_URL).content.decode()
        self.assertNotIn(f'data-player="{starter.id}"', stack_html(body))
        role = body.split('data-bullpen-group="closer"', 1)[1].split('data-bullpen-group="sirp"', 1)[0]
        self.assertIn(starter.name, role)
        self.assertIn(f'data-player="{starter.id}"', role)

    def test_editor_shows_the_saved_plan(self):
        self.roster.file()
        body = self.as_user(self.owner).get(ROTATION_URL).content.decode()
        self.assertIn(f'name="rotation" value="{self.roster.starters[0].id}"', body)
        self.assertIn("34 starts", body)
        self.assertNotIn("32 GS", body)
        self.assertNotIn("Put one to six", body)
        self.assertIn("190.0 IP", body)

    def test_commissioner_can_edit_any_plan(self):
        response = self.as_user(self.commissioner).post(EDIT_URL, form_data(self.roster))
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.saved_plan())

    def test_a_two_way_player_is_offered_as_a_hitter_and_a_pitcher(self):
        two_way = create_pitcher(self.atl, "ATL Two Way")
        card = models.Card.objects.get(player=two_way, season=SEASON - 1)
        card.hitter_rates = dict(HITTER_RATES)
        card.plate_appearances = 600
        card.primary_position = "DH"
        card.save()
        utils.promote_two_way_pitchers()
        two_way.refresh_from_db()
        self.assertEqual(two_way.position, "DH-P")

        client = self.as_user(self.owner)
        hitters = stack_html(client.get(EDIT_URL).content.decode())
        pitchers = stack_html(client.get(ROTATION_URL).content.decode())
        self.assertIn('data-kind="h"', articles(hitters, two_way.id)[0])
        self.assertIn('data-kind="p"', articles(pitchers, two_way.id)[0])

        lineup = self.roster.lineup()
        lineup[8]["player"] = two_way
        response = client.post(EDIT_URL, form_data(self.roster, vs_lhp=lineup, vs_rhp=lineup))
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])

    def test_a_pitcher_with_a_few_plate_appearances_is_not_a_hitter(self):
        mop = create_pitcher(self.atl, "ATL Mop")
        card = models.Card.objects.get(player=mop, season=SEASON - 1)
        card.hitter_rates = dict(HITTER_RATES)
        card.plate_appearances = 12
        card.primary_position = "DH"
        card.save()
        utils.promote_two_way_pitchers()
        mop.refresh_from_db()
        self.assertEqual(mop.position, "P")
        hitters = stack_html(self.as_user(self.owner).get(EDIT_URL).content.decode())
        self.assertNotIn(f'data-player="{mop.id}"', hitters)

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
        self.assertRegex(response.content.decode(), r"No legal starter for home days [\d, ]+\.")

    def test_second_half_locked_until_2h(self):
        url = f"/teams/atl/plan/2/{SEASON}/edit/"
        client = self.as_user(self.owner)
        self.assertIn("opens after the trade break", client.get(url).content.decode())
        bullpen = f"/teams/atl/plan/2/{SEASON}/bullpen/"
        self.assertIn("opens after the trade break", client.get(bullpen).content.decode())
        self.assertEqual(client.post(bullpen, {"closer": self.roster.relievers[0].id}).status_code, 400)
        response = client.post(url, form_data(self.roster))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(models.HalfPlan.objects.filter(half=2).exists())
        public = self.client.get(f"/teams/atl/plan/2/{SEASON}/").content.decode()
        self.assertIn("opens after the trade break", public)
        self.assertIn("ATL has not filed lineups for this half", public)

        closed = client.post(
            f"/teams/atl/plan/2/{SEASON}/designation/",
            {"player": self.roster.swingman.id, "designation": "bullpen"},
        )
        self.assertEqual(closed.status_code, 400)
        self.assertTrue(closed["Content-Type"].startswith("text/plain"))
        self.assertIn("half 2", closed.content.decode())

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

    def test_cards_still_show_war_per_600_on_the_summary_line(self):
        self.set_war(self.roster.catcher, 4)
        self.set_war(self.roster.bench[0], 0)
        client = self.as_user(self.owner)
        body = client.get(EDIT_URL).content.decode()
        good = articles(body, self.roster.catcher.id)[0]
        bad = articles(body, self.roster.bench[0].id)[0]
        self.assertIn("4.0/600", good)
        self.assertIn("0.0/600", bad)
        plain = articles(body, self.roster.bench[1].id)[0]
        self.assertNotIn("/600", plain)

    def set_war(self, player, war):
        row = models.PlayerStatSeason.objects.get(player=player, season=SEASON - 1, classification="1-mlb")
        stats = dict(row.hit_stats)
        stats["war"] = war
        row.hit_stats = stats
        row.save()

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
        self.assertNotIn(">Clear lineup<", day_body)
        self.assertEqual(day_body.count('aria-label="Remove from this spot"'), 9)
        self.assertNotIn(">Rotation</button>", day_body)
        self.assertIn('aria-label="Remove from this start"', day_body)
        response = client.post(day_url(20), day_data(starter=self.roster.swingman, lineup=lineup), follow=True)
        self.assertRedirects(response, SCHEDULE_URL + "#day-20", fetch_redirect_response=False)
        body = response.content.decode()
        self.assertIn("ends his relief-only designation", body)
        row = self.plan.days.get(day=20)
        self.assertEqual(row.manual_starter, self.roster.swingman)
        self.assertEqual(row.manual_lineup[-1], {"player": self.roster.bench[1].id, "position": "DH"})
        self.assertRegex(body, r'(?s)data-day="20".*?ATL Swingman.*?\*')

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
        self.assertEqual(body.count('class="starter-slot '), 80)
        self.assertNotIn(f'href="/teams/atl/plan/1/{SEASON}/day/1/"', body)
        self.assertNotIn("day-lineup", body)
        self.assertIn(">Game 1<", body)

    def test_a_road_day_page_says_a_call_up_can_play_and_a_home_day_says_he_cannot(self):
        games = plans.half_games(self.atl, SEASON, 1)
        road = next(game for game in games.values() if game.series.road_team_id == self.atl.id)
        home = next(game for game in games.values() if game.series.home_team_id == self.atl.id)
        client = self.as_user(self.owner)
        road_body = client.get(day_url(road.day)).content.decode()
        home_body = client.get(day_url(home.day)).content.decode()
        self.assertIn("This is a road game.", road_body)
        self.assertIn("Check Set this day's lineup to file a call-up here.", road_body)
        self.assertIn("This is a home game.", home_body)
        self.assertIn("A call-up cannot be in this lineup.", home_body)

    def test_lineup_override_rule_errors(self):
        stranger = create_hitter(self.car, "CAR Hitter")
        lineup = self.roster.lineup()
        lineup[8]["player"] = stranger
        response = self.as_user(self.owner).post(day_url(10), day_data(lineup=lineup))
        self.assertEqual(response.status_code, 400)
        self.assertIn("CAR Hitter is not on ATL&#x27;s 30-man", response.content.decode())


class SchedulePlannedStartersTestCase(PlanViewsTestCase):
    def test_the_schedule_opens_with_what_is_still_unfiled(self):
        body = self.as_user(self.owner).get(SCHEDULE_URL).content.decode()
        self.assertIn('id="plan-gaps"', body)
        self.assertLess(body.index('id="plan-gaps"'), body.index("schedule-game"))
        gaps = body.split('id="plan-gaps"', 1)[1].split("</aside>", 1)[0]
        self.assertIn("Still to file", gaps)
        self.assertIn("Lineups are not filed.", gaps)
        self.assertIn("The rotation has not been pushed to the schedule.", gaps)
        self.assertIn("No closer is named.", gaps)
        self.assertIn("No one is in single-inning relief.", gaps)
        self.assertIn("No one is in multi-inning relief.", gaps)
        self.assertIn(f'href="/teams/atl/plan/1/{SEASON}/edit/"', gaps)
        self.assertIn(f'href="/teams/atl/plan/1/{SEASON}/rotation/"', gaps)
        self.assertIn(f'href="/teams/atl/plan/1/{SEASON}/bullpen/"', gaps)
        self.assertNotIn('id="plan-gaps"', self.as_user(self.other_owner).get(SCHEDULE_URL).content.decode())
        self.assertNotIn('id="plan-gaps"', Client().get(SCHEDULE_URL).content.decode())

        self.roster.file()
        plan = self.saved_plan()
        plan.lineup_vs_lhp = []
        plan.save(update_fields=["lineup_vs_lhp"])
        partial = self.as_user(self.owner).get(SCHEDULE_URL).content.decode()
        named = partial.split('id="plan-gaps"', 1)[1].split("</aside>", 1)[0]
        self.assertIn("The lineup vs LHP is not filed.", named)
        self.assertNotIn("Lineups are not filed.", named)
        self.assertNotIn("The rotation has not been pushed to the schedule.", named)
        self.assertNotIn("No closer is named.", named)

        plan.lineup_vs_lhp = self.roster.file().lineup_vs_lhp
        plan.save(update_fields=["lineup_vs_lhp"])
        self.assertNotIn('id="plan-gaps"', self.as_user(self.owner).get(SCHEDULE_URL).content.decode())

    def test_the_schedule_names_games_and_does_not_edit_lineups(self):
        self.roster.file()
        body = self.as_user(self.owner).get(SCHEDULE_URL).content.decode()
        games = list(plans.half_games(self.atl, SEASON, 1).values())
        self.assertNotIn("day-lineup", body)
        self.assertNotIn("Home lineup", body)
        self.assertNotIn("Road lineup", body)
        self.assertNotIn("Game numbers are league days", body)
        self.assertNotIn(">Rotation</button>", body)
        self.assertIn('aria-label="Remove from this start"', body)
        self.assertIn("pitcher-stack", body)
        self.assertIn("position: sticky", body)
        self.assertIn(">Home starter<", body)
        self.assertIn(">Away starter<", body)
        self.assertEqual(body.count('class="starter-slot '), len(games))
        for game in games[:2]:
            self.assertIn(f">Game {game.day}<", body)
            self.assertNotIn(f'href="/teams/atl/plan/1/{SEASON}/day/{game.day}/"', body)
        first = articles(stack_html(body), self.roster.starters[0].id)[0]
        self.assertIn("34 starts", first)
        self.assertIn("17 scheduled", first)
        self.assertIn("17 remaining", first)
        self.assertNotIn("34 remaining", first)
        self.assertIn('draggable="true"', first)
        self.assertIn('class="play-next" style="', body)
        self.assertIn("background:#f2c230", body)
        self.assertNotIn('class="play-next underline', body)
        self.assertNotIn("schedule-play", body)
        nxt = schedule.next_unplayed_road_game(self.atl, SEASON)
        self.assertIn(f'href="/games/{nxt.id}/" class="play-next', body)
        with patch("ulmg.utils.league_season", return_value=1999):
            dated = self.as_user(self.owner).get(SCHEDULE_URL).content.decode()
        self.assertIn(f'href="/games/{nxt.id}/" class="play-next', dated)
        public = Client().get(SCHEDULE_URL).content.decode()
        self.assertNotIn("day-lineup", public)
        self.assertNotIn("play-next", public)
        self.assertIn(">Game 1<", public)
        self.assertIn('id="day-1"', public)

    def test_a_pitcher_with_no_starts_left_cannot_be_added_to_the_schedule(self):
        capped = create_pitcher(self.atl, "ATL Capped", stats={"g": 2, "gs": 2, "ip": "10.0"})
        rotation = list(self.roster.starters[:4])
        rotation.insert(1, capped)
        self.roster.file(rotation=rotation)
        client = self.as_user(self.owner)
        page = client.get(SCHEDULE_URL).content.decode()
        card = articles(stack_html(page), capped.id)[0]
        self.assertIn("2 starts", card)
        self.assertIn("2 scheduled", card)
        self.assertIn("0 remaining", card)
        self.assertNotIn("2 remaining", card)
        self.assertNotIn("2 GS", card)
        self.assertIn('draggable="false"', card)
        response = client.post(SCHEDULE_URL, {"starter_30": capped.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("cap is 2 starts", response.content.decode())

    def test_team_schedule_shows_the_plans_starters(self):
        plan = self.roster.file()
        body = self.client.get(SCHEDULE_URL).content.decode()
        starters = plans.starters(plan)
        self.assertIn(">Home starter<", body)
        self.assertIn(">Away starter<", body)
        self.assertNotIn(">Played by<", body)
        for game in plans.half_games(self.atl, SEASON, 1).values():
            row = re.search(rf'(?s)<tr id="day-{game.day}".*?</tr>', body).group(0)
            is_home = game.series.home_team_id == self.atl.id
            home = re.search(r'class="home-starter[^"]*"[^>]*>(.*?)</td>', row, re.S).group(1).strip()
            away = re.search(r'class="away-starter[^"]*"[^>]*>(.*?)</td>', row, re.S).group(1).strip()
            name = starters[game.day].name
            self.assertEqual((home, away), (name, "-") if is_home else ("-", name))

    def test_the_owner_clears_every_open_starter(self):
        self.roster.file()
        client = self.as_user(self.owner)
        page = client.get(SCHEDULE_URL).content.decode()
        self.assertEqual(page.count(">Clear away starters<"), 1)
        self.assertIn('name="clear_starters"', page)
        self.assertNotIn(">Clear away starters<", Client().get(SCHEDULE_URL).content.decode())
        self.assertNotIn(
            ">Clear away starters<", self.as_user(self.other_owner).get(SCHEDULE_URL).content.decode()
        )

        refused = self.as_user(self.other_owner).post(SCHEDULE_URL, {"clear_starters": "1"})
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(
            Client().post(SCHEDULE_URL, {"clear_starters": "1"}).status_code, 403
        )
        self.assertIsNotNone(plans.starters(self.saved_plan())[1])

        client = self.as_user(self.owner)
        response = client.post(
            SCHEDULE_URL,
            {"clear_starters": "1", "starter_20": self.roster.swingman.id},
            follow=True,
        )
        self.assertRedirects(response, SCHEDULE_URL)
        body = response.content.decode()
        self.assertIn("Cleared the away starters.", body)
        self.assertNotIn("open home day", body)
        plan = self.saved_plan()
        games = plans.half_games(self.atl, SEASON, 1)
        starters = plans.starters(plan)
        self.assertEqual(plan.rotation, [p.id for p in self.roster.starters])
        self.assertTrue(any(
            starters[day] is None
            for day, game in games.items()
            if game.series.home_team_id != self.atl.id
        ))
        self.assertTrue(all(
            starters[day] is not None
            for day, game in games.items()
            if game.series.home_team_id == self.atl.id
        ))

        client.post(SCHEDULE_URL, {f"starter_{day}": "" for day in starters})
        starters = plans.starters(self.saved_plan())
        self.assertTrue(all(
            starters[day] is not None
            for day, game in games.items()
            if game.series.home_team_id == self.atl.id
        ))
        client.post(ROTATION_URL, {"rotation": [p.id for p in self.roster.starters]})
        self.assertTrue(all(plans.starters(self.saved_plan()).values()))

    def test_the_owner_drops_a_rotation_starter_on_his_side(self):
        self.roster.file()
        body = self.as_user(self.owner).get(SCHEDULE_URL).content.decode()
        stack = body.split("data-stack", 1)[1].split("data-starter-grid", 1)[0]
        for starter in self.roster.starters:
            self.assertIn(f'data-player="{starter.id}"', stack)
        for other in self.roster.relievers + [self.roster.swingman]:
            self.assertNotIn(f'data-player="{other.id}"', stack)
        self.assertIn(">Starters<", body)
        self.assertIn("w-60", body)
        games = list(plans.half_games(self.atl, SEASON, 1).values())
        road = [game for game in games if game.series.road_team_id == self.atl.id]
        self.assertEqual(body.count("schedule-away"), len(road))
        self.assertEqual(body.count("#fff8e4"), len(road))
        self.assertNotIn("#fff3c4", body)
        self.assertNotIn("unplayed", body)
        self.assertEqual(body.count("play-next"), 1)
        self.assertNotIn("schedule-play", body)
        for game in games:
            row = re.search(rf'(?s)<tr id="day-{game.day}".*?</tr>', body).group(0)
            is_home = game.series.home_team_id == self.atl.id
            home = re.search(r'class="home-starter[^"]*"[^>]*>(.*?)</td>', row, re.S).group(1)
            away = re.search(r'class="away-starter[^"]*"[^>]*>(.*?)</td>', row, re.S).group(1)
            self.assertEqual("starter-slot" in home, is_home)
            self.assertEqual("starter-slot" in away, not is_home)
            if is_home:
                self.assertNotIn("schedule-play", row)
                self.assertNotIn("schedule-away", row)
                result = re.search(r'class="schedule-result[^"]*"[^>]*>(.*?)</td>', row, re.S).group(1)
                self.assertEqual(result.strip(), "")
