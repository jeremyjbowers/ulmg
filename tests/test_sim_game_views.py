# ABOUTME: Tests the sim game pages over the test client against the real engine: open, step, refusals, seats and the box score.
# ABOUTME: Also covers the schedule's Play next and box score links, the public box score page and refusals shown as messages.

from django.test import TestCase, override_settings

from tests import game_fixtures as gf
from ulmg import models, plans, schedule, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME


class GamePageTestCase(gf.EngineMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        gf.create_game_season(cls)

    def setUp(self):
        self.next_seed = gf.seeds()
        self.url = f"/games/{self.game.id}/"

    def post(self, action, user=None, **data):
        self.client.force_login(user or self.manager)
        return self.client.post(f"{self.url}{action}/", data, follow=True)

    def log(self):
        return models.GameLog.objects.get(game=self.game)

    def expected(self):
        return sim_game.Play(self.log()).sequence

    def _lineup_post(self, prefix, entries):
        data = {}
        for entry in entries:
            data[f"{prefix}player-{entry['order']}"] = entry["player"].id
            data[f"{prefix}position-{entry['order']}"] = entry["position"]
        return data

    def test_the_page_before_the_game_starts_is_the_lineup_for_today(self):
        capped = self.road.hitters[3]
        gf.counter(capped, plate_appearances_cap=10, plate_appearances=10)
        self.client.force_login(self.manager)
        page = self.client.get(self.url)
        self.assertContains(page, "Proceed with this lineup")
        self.assertContains(page, "unlimited PA left")
        self.assertContains(page, f"{capped.name} — no PA left")
        self.assertContains(page, 'name="away-player-1"')
        self.assertNotContains(page, 'name="home-player-1"')
        self.assertContains(page, 'action="/games/%d/open/"' % self.game.id)
        self.assertContains(page, self.home.starters[0].name)
        self.client.force_login(self.tester)
        self.assertContains(self.client.get(self.url), 'name="home-player-1"')

    def test_the_hud_drops_the_play_bar_the_lineup_page_keeps(self):
        self.client.force_login(self.manager)
        lineup = self.client.get(self.url)
        self.assertContains(lineup, 'id="play-bar"')
        self.assertContains(lineup, "Play next:")
        hud = self.post("open", seats="away")
        self.assertContains(hud, 'id="hud"')
        self.assertNotContains(hud, 'id="play-bar"')
        self.assertNotContains(hud, "Play next:")

    def test_a_day_lineup_saved_without_the_checkbox_is_what_play_next_shows(self):
        bench = self.road.bench[1]
        entries = self.road.lineup()
        entries[-1] = {"order": 9, "player": bench, "position": "DH"}
        data = {"starter": ""}
        for entry in entries:
            data[f"day_order_{entry['order']}"] = entry["order"]
            data[f"day_player_{entry['order']}"] = entry["player"].id
            data[f"day_position_{entry['order']}"] = entry["position"]
        self.client.force_login(self.manager)
        team = self.road.team.abbreviation.lower()
        saved = self.client.post(f"/teams/{team}/plan/1/{gf.SEASON}/day/{self.game.day}/", data)
        self.assertEqual(saved.status_code, 302)
        page = self.client.get(self.url).content.decode()
        slot = page.split('name="away-player-9"', 1)[1].split("</select>", 1)[0]
        self.assertIn(f'value="{bench.id}" selected', slot)

    def test_proceeding_with_an_edited_lineup_opens_on_that_lineup(self):
        bench = self.road.bench[1]
        entries = self.road.lineup()
        entries[3] = {"order": 4, "player": bench, "position": "3B"}
        response = self.post("open", seats="away", **self._lineup_post("away-", entries))
        self.assertContains(response, "Play the next plate appearance")
        self.assertEqual(self.log().state[AWAY]["lineup"][3]["id"], str(bench.id))
        plan = plans.find_plan(self.road.team, gf.SEASON, 1)
        self.assertNotIn(bench.id, [e["player"] for e in plan.lineup_vs_rhp])

    def test_an_opened_game_cannot_be_played_until_the_lineup_is_accepted(self):
        sim_game.open_game(self.game, self.manager, (AWAY,), seeds=self.next_seed)
        self.client.force_login(self.manager)
        page = self.client.get(self.url)
        self.assertContains(page, "Proceed with this lineup before the first pitch.")
        self.assertContains(page, 'id="hud-play" disabled')
        self.assertNotContains(page, "Play the next plate appearance")
        data = {"expected": self.expected(), "side": AWAY}
        for order, entry in enumerate(sim_game.Play(self.log()).state[AWAY]["lineup"], start=1):
            data[f"player-{order}"] = entry["id"]
            data[f"position-{order}"] = entry["position"]
        response = self.post("proceed", **data)
        self.assertContains(response, "Play the next plate appearance")
        self.post("step", expected=self.expected())
        self.assertEqual(len(self.log().state["results"]), 1)

    def test_the_page_before_opening_shows_both_plans_and_the_seat_choice(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertContains(response, self.road.starters[0].name)
        self.assertContains(response, self.home.starters[0].name)
        self.assertContains(response, 'action="/games/%d/open/"' % self.game.id)
        self.assertContains(response, '<option value="away">Away</option>', html=True)
        self.assertNotContains(response, '<option value="home">Home</option>', html=True)
        self.assertContains(response, f"/plan/1/{gf.SEASON}/day/{self.game.day}/")

    def test_a_logged_out_visitor_is_sent_to_log_in(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_the_pregame_lineup_list_is_the_current_mlb_roster(self):
        self.post("open", user=self.tester, seats="away,home")
        removed = self.home.bench[0]
        kept = self.home.bench[1]
        removed.is_ulmg_mlb_roster = False
        removed.save()
        response = self.client.get(self.url)
        heading = f"{self.home.team.abbreviation} lineup for this game"
        form = response.content.decode().split(heading, 1)[1].split("</form>", 1)[0]
        self.assertNotIn(f'value="{removed.id}"', form)
        self.assertIn(f'value="{kept.id}"', form)

    def test_opening_and_stepping_through_the_page(self):
        response = self.post("open", seats="away")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Play the next plate appearance")
        self.assertContains(response, self.road.hitters[0].name)
        self.assertContains(response, self.home.starters[0].name)
        self.assertContains(response, "Strikeout")
        self.assertContains(response, "PA left: unlimited")
        self.assertContains(response, "IP left this outing")
        self.assertContains(response, "Top 1")
        self.assertContains(response, 'id="in-game-box"')
        self.assertContains(response, ">Box score</summary>")
        self.assertContains(response, "box-batting")

        response = self.post("step", expected=self.expected(), call="bunt")
        self.assertEqual(len(self.log().state["results"]), 1)
        self.assertContains(response, "calls bunt")
        call = gf.events(self.log(), Event.CALL)[0]
        self.assertEqual(call.user, self.manager)

    def test_a_stale_step_from_the_page_plays_nothing_and_says_so(self):
        self.post("open", seats="away")
        position = self.expected()
        self.post("step", expected=position)
        response = self.post("step", expected=position)
        self.assertContains(response, "moved on")
        self.assertEqual(len(self.log().state["results"]), 1)

    def test_the_browser_cannot_supply_a_seed(self):
        self.post("open", seats="away")
        self.post("step", expected=self.expected(), seed="12345")
        pa = gf.events(self.log(), Event.PLATE_APPEARANCE)[0]
        self.assertNotEqual(pa.seed, 12345)

    def test_a_refused_pitching_change_shows_why(self):
        self.post("open", seats="away")
        self.post("pitcher", expected=self.expected(), side=AWAY, player=self.road.relievers[0].id)
        response = self.post("pitcher", expected=self.expected(), side=HOME, player=self.home.relievers[0].id)
        self.assertContains(response, "You don&#x27;t hold the")
        self.assertEqual(gf.events(self.log(), Event.PITCHING_CHANGE), [])

    def test_a_manager_cannot_open_the_home_seat_from_the_page(self):
        response = self.post("open", seats="home")
        self.assertContains(response, "visiting side")
        self.assertFalse(models.GameLog.objects.exists())
        response = self.post("open", user=self.other_manager, seats="away")
        self.assertContains(response, "manager can play this game")
        self.assertFalse(models.GameLog.objects.exists())

    def test_a_tester_opens_both_seats_and_the_page_offers_both_sides_calls(self):
        self.client.force_login(self.tester)
        response = self.client.get(self.url)
        self.assertContains(response, '<option value="away,home">Both</option>', html=True)
        response = self.post("open", user=self.tester, seats="away,home")
        self.assertContains(response, "Pitch around")
        self.assertContains(response, "Steal")
        self.assertContains(response, "sim-tester")
        seats = {e.side: e.user for e in gf.events(self.log(), Event.SEAT)}
        self.assertEqual(seats, {AWAY: self.tester, HOME: self.tester})

    def test_a_final_stays_in_the_hud_and_the_box_score_is_a_choice(self):
        self.post("open", seats="away")
        gf.play_out(self.log(), self.manager, self.next_seed)
        waiting = self.client.get(self.url)
        self.assertContains(waiting, 'id="hud"')
        self.assertContains(waiting, 'id="hud-field"')
        self.assertContains(waiting, 'id="hud-box"')
        self.assertContains(waiting, f'href="/games/{self.game.id}/box/"')
        self.assertContains(waiting, "The game is over")
        self.assertNotContains(waiting, "Play the next plate appearance")
        self.assertNotContains(waiting, 'id="game-finish"')
        self.game.refresh_from_db()
        for team in (self.road.team, self.home.team):
            schedule_page = self.client.get(f"/teams/{team.abbreviation.lower()}/schedule/{gf.SEASON}/")
            self.assertContains(schedule_page, f'href="/games/{self.game.id}/box/"')
        self.client.logout()
        box = self.client.get(f"/games/{self.game.id}/box/")
        self.assertEqual(box.status_code, 200, "the box score is public")
        html = box.content.decode()
        self.assertIn("box-batting", html)
        self.assertIn("box-pitching", html)
        self.assertIn("(W)", html)
        self.assertIn("(L)", html)
        self.assertIn("box-notes", html)
        self.assertLess(html.find("box-notes"), html.find("Play-by-play") if "Play-by-play" in html else len(html))
        self.assertIn(">LOB</span>:", html)

    def test_the_box_score_choice_waits_until_the_game_is_over(self):
        self.post("open", seats="away")
        response = self.client.get(self.url)
        self.assertNotContains(response, 'id="hud-box"')
        self.assertContains(response, "Play the next plate appearance")

    @override_settings(TEAM_SEASON_HALF="2h")
    def test_the_schedule_offers_play_next_for_the_managers_next_road_game_only(self):
        self.client.force_login(self.manager)
        page = self.client.get(f"/teams/{self.road.team.abbreviation.lower()}/schedule/{gf.SEASON}/")
        self.assertContains(page, f'href="/games/{self.game.id}/" class="play-next', count=1)
        self.assertContains(page, "play-next", count=1)
        self.assertContains(page, f"Play next: Game {self.game.day} at {self.home.team.abbreviation}")
        self.assertContains(page, 'id="play-bar"')
        self.assertContains(page, "Home 0% complete")
        self.assertContains(page, "Away 0% complete")
        self.assertNotContains(page, "schedule-play")
        home_schedule = self.client.get(f"/teams/{self.home.team.abbreviation.lower()}/schedule/{gf.SEASON}/")
        self.assertContains(home_schedule, f'href="/games/{self.game.id}/" class="play-next', count=1)
        self.client.force_login(self.other_manager)
        page = self.client.get(f"/teams/{self.road.team.abbreviation.lower()}/schedule/{gf.SEASON}/")
        self.assertNotContains(page, f'href="/games/{self.game.id}/" class="play-next')
        own = schedule.next_unplayed_road_game(self.home.team, gf.SEASON)
        self.assertContains(page, f'href="/games/{own.id}/" class="play-next', count=1)
        self.assertContains(page, f"Play next: Game {own.day} at {own.series.home_team.abbreviation}")
        self.client.force_login(self.tester)
        page = self.client.get(f"/teams/{self.road.team.abbreviation.lower()}/schedule/{gf.SEASON}/")
        self.assertContains(page, f'href="/games/{self.game.id}/" class="play-next', count=1)
        self.assertContains(page, "play-next", count=1)
        self.assertNotContains(page, "schedule-play")
        home_page = self.client.get(f"/teams/{self.home.team.abbreviation.lower()}/schedule/{gf.SEASON}/")
        self.assertNotContains(home_page, f'href="/games/{self.game.id}/" class="play-next')
        self.assertNotContains(home_page, "schedule-play")

    def test_seat_changes_through_the_page_are_logged_with_the_user(self):
        self.post("open", user=self.tester, seats="home")
        self.post("take", user=self.manager, expected=self.expected(), side=AWAY)
        response = self.post("take", user=self.manager, expected=self.expected(), side=HOME)
        self.assertContains(response, "visiting side")
        self.post("leave", user=self.tester, expected=self.expected(), side=HOME)
        seats = [(e.side, e.user) for e in gf.events(self.log(), Event.SEAT)]
        self.assertEqual(seats[-2:], [(AWAY, self.manager), (HOME, None)])

    def test_the_page_names_a_forced_replacement_and_offers_only_legal_choices(self):
        second = self.road.hitters[1]
        gf.counter(second, plate_appearances_cap=1)
        gf.counter(self.road.bench[0], plate_appearances_cap=3, plate_appearances=3)
        self.post("open", seats="away")
        log = self.log()
        for _ in range(200):
            play = sim_game.Play(gf.refresh(log))
            need = play.need()
            if need is not None and need.side == AWAY and need.kind == sim_game.BATTER_NEED:
                break
            if need is not None and need.side == AWAY:
                option = gf.first_legal(play.options_for(need))
                sim_game.change_pitcher(log, self.manager, AWAY, option, play.sequence, seeds=self.next_seed)
                continue
            sim_game.step(log, self.manager, play.sequence, seeds=self.next_seed)
        response = self.client.get(self.url)
        self.assertContains(response, f"{second.name} must be replaced")
        self.assertContains(response, f'name="player" value="{self.road.bench[0].id}" id="ph-{self.road.bench[0].id}" disabled>', count=1)
        self.assertContains(response, f'name="player" value="{self.road.bench[1].id}" id="ph-{self.road.bench[1].id}">')
        self.assertNotContains(response, "Play the next plate appearance")
        self.post("replace", expected=self.expected(), side=AWAY, player=self.road.bench[1].id)
        self.assertEqual(gf.events(self.log(), Event.SUBSTITUTION)[-1].payload["player"], self.road.bench[1].id)
