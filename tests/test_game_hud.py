# ABOUTME: Tests the game HUD page against the real engine: the scoreboard, cards, field, calls, last play and substitution panel.
# ABOUTME: Each test opens a real game from the shared fixtures and reads the rendered page the way a manager would.

import json
import re

from django.test import TestCase

from tests import game_fixtures as gf
from ulmg import cards, engine_client, models, sim_game

Event = models.GameEvent
AWAY, HOME = sim_game.AWAY, sim_game.HOME
SINGLE = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 1.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}


class GameHudTestCase(gf.EngineMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        gf.create_game_season(cls)

    def setUp(self):
        self.next_seed = gf.seeds()
        self.url = f"/games/{self.game.id}/"

    def post(self, action, user=None, **data):
        self.client.force_login(user or self.tester)
        return self.client.post(f"{self.url}{action}/", data, follow=True)

    def log(self):
        return models.GameLog.objects.get(game=self.game)

    def expected(self):
        return sim_game.Play(self.log()).sequence

    def page(self, user=None):
        self.client.force_login(user or self.tester)
        return self.client.get(self.url).content.decode()

    def section(self, html, start, end):
        return html.split(start, 1)[1].split(end, 1)[0]

    def group(self, html, name):
        return self.section(html, f'class="hud-group hud-{name}"', "</div>")

    def drawer(self, html, tab):
        return self.section(html, f'id="sub-{tab}"', "</aside>")

    def last_play(self, html):
        blob = self.section(html, 'id="hud-last-play"', "</script>").split(">", 1)[1]
        return json.loads(blob)


class ScoreboardTest(GameHudTestCase):
    def test_the_line_score_lights_the_inning_and_shows_runs_hits_errors_and_outs(self):
        self.post("open", seats="away,home")
        gf.set_rates([self.road.hitters[0]], gf.HOME_RUN_RATES)
        html = self.post("step", expected=self.expected()).content.decode()
        board = self.section(html, 'class="hud-board"', "</section>")
        self.assertIn('<th scope="col" class="now">1</th>', board)
        road = self.section(board, 'id="line-away"', "</tr>")
        self.assertIn(f'<td class="team">{self.road.team.abbreviation}</td>', road)
        self.assertIn('<td class="now" data-inning="1">1</td>', road)
        self.assertIn('<td class="tot runs" data-total="r">1</td><td>1</td><td>0</td>', road)
        home = self.section(board, 'id="line-home"', "</tr>")
        self.assertIn('data-inning="1">·</td>', home)
        self.assertIn("▲ Top 1st", board)
        self.assertIn("0 outs", board)
        self.assertEqual(board.count('class="out-light"'), 3)
        self.assertLess(html.find('class="hud-board"'), html.find('id="hud-field"'))
        self.assertLess(html.find('id="hud-field"'), html.find('id="hud-play"'))
        self.assertLess(html.find('id="hud-play"'), html.find("Play-by-play"))


class CardTest(GameHudTestCase):
    def test_the_batter_card_shows_his_slot_platoon_lines_speed_steals_and_who_follows(self):
        leadoff = self.road.hitters[0]
        models.Card.objects.filter(player=leadoff).update(
            spd=6.1, steal_success=0.78, hitter_rates_vs_lhp=dict(gf.HITTER_RATES, single=0.24, bip_out=gf.HITTER_RATES["bip_out"] - 0.1)
        )
        self.post("open", seats="away,home")
        card = self.section(self.page(), 'class="hud-card hud-batter"', "</ul>")
        self.assertIn(f"At bat · {self.road.team.abbreviation} · 1st", card)
        self.assertIn(leadoff.name, card)
        self.assertIn("C · bats right · first time up today", card)
        self.assertIn('<tr class="hot"><td>vs RHP</td><td>.241</td><td>.309</td><td>.398</td><td>3.0</td></tr>', card)
        self.assertIn('<tr class=""><td>vs LHP</td><td>.351</td>', card, "the split he does not face today, not highlighted")
        self.assertIn("Speed <b>6.1</b> · steals <b>78%</b> · PA left: unlimited", card)
        self.assertIn(f"On deck: <b>{self.road.hitters[1].name}</b>", card)
        self.assertIn(f"In the hole: <b>{self.road.hitters[2].name}</b>", card)

    def test_the_pitcher_card_shows_his_role_pitch_count_innings_left_and_the_odds(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        card = self.section(self.page(), 'class="hud-card hud-pitcher"', "</ul>")
        starter = self.home.starters[0]
        fatigue = self.log().state[HOME]["fatigue"][str(starter.id)]
        self.assertIn(starter.name, card)
        self.assertIn("Starter · throws right", card)
        self.assertIn(f"<b>{fatigue['pitches']}</b> pitches · tires near <b>{round(fatigue['ceiling'])}</b>", card)
        self.assertIn("IP left this outing: <b>", card)
        self.assertIn("This plate appearance", card)
        odds = dict(sim_game.matchup(sim_game.Play(self.log())))
        self.assertIn(f'<span class="pct">{odds["Strikeout"]:.1f}%</span>', card)


class FieldTest(GameHudTestCase):
    def test_fielders_are_tagged_with_their_slotted_rating_in_runs(self):
        models.Card.objects.filter(player=self.home.fielders[3]).update(defense={"SS": -2.0})
        self.post("open", seats="away,home")
        field = self.section(self.page(), 'id="hud-fielders"', '<g id="hud-runners">')
        self.assertIn(">C +4.0<", field)
        self.assertIn(">1B +1.5<", field)
        self.assertIn('class="tag low"', field)
        self.assertIn(">SS −2.0<", field)
        self.assertIn(">P<", field)
        self.assertIn(">Catcher<", field, "the name sits beside the tag")

    def test_runners_are_drawn_on_their_base_with_their_speed(self):
        leadoff = self.road.hitters[0]
        models.Card.objects.filter(player=leadoff).update(spd=7.4)
        gf.set_rates([leadoff], SINGLE)
        self.post("open", seats="away,home")
        html = self.post("step", expected=self.expected()).content.decode()
        runners = self.section(html, 'id="hud-runners"', "</g>\n        </g>")
        self.assertIn('data-base="first"', runners)
        self.assertIn(">Speed 7.4<", runners)
        text = self.section(html, 'id="hud-field-text"', "</p>")
        self.assertIn(f"{leadoff.name} on first (speed 7.4)", text)
        self.assertIn(f"{self.home.team.abbreviation} in the field: P {self.home.starters[0].name}", text)
        self.assertIn(f"C {self.home.catcher.name} +4.0", text)

    def test_the_home_park_is_drawn_from_its_dimensions_with_its_scores(self):
        venue = models.Venue.objects.create(
            name="Fenway Park", mlb_team="Red Sox", mlb_venue_id="3", mlb_venue_url="u", pf_hr=97, pf_2b=122,
            rules={"distances_ft": {"lf_line": 310, "rf_line": 302}, "wall_ft": {"lf_line": 37, "left_center": 37}},
        )
        self.home.team.home_field = venue
        self.home.team.save()
        self.post("open", seats="away,home")
        field = self.section(self.page(), 'id="hud-field"', "</svg>")
        self.assertIn("<span>Fenway Park</span><small>HR 97 · 2B 122 · grass</small>", field)
        self.assertIn(">310 · 37′ wall<", field)
        self.assertIn(">302<", field)
        self.assertIn('class="tall-wall"', field)


class ControlsTest(GameHudTestCase):
    def test_a_side_the_computer_holds_is_labelled_and_its_buttons_are_off(self):
        self.post("open", user=self.manager, seats="away")
        html = self.page(self.manager)
        offense = self.group(html, "offense")
        defense = self.group(html, "defense")
        self.assertIn(f"<b>{self.road.team.abbreviation} (you)</b>", offense)
        self.assertIn(f"<b>{self.home.team.abbreviation} computer</b>", defense)
        self.assertIn('value="bunt"', offense)
        self.assertNotIn('value="intentional_walk"', defense)
        self.assertIn('class="hud-btn" disabled data-key="I">Intentional walk', defense)
        self.assertIn("is the computer&#x27;s side", defense)
        self.assertIn("Play the next plate appearance", html)

    def test_steal_and_hit_and_run_stay_visible_disabled_with_the_reason(self):
        self.post("open", seats="away,home")
        offense = self.group(self.page(), "offense")
        self.assertIn('class="hud-btn" disabled data-key="S">Steal', offense)
        self.assertIn('class="hud-btn" disabled data-key="H">Hit &amp; run', offense)
        self.assertIn("Steal needs a runner with the next base open.", offense)
        self.assertIn("Hit &amp; run needs a runner on first.", offense)

    def test_a_runner_on_first_lights_steal_and_the_call_still_posts(self):
        gf.set_rates([self.road.hitters[0]], SINGLE)
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        offense = self.group(self.page(), "offense")
        self.assertIn('value="steal" class="hud-btn live"', offense)
        self.assertNotIn("Steal needs a runner", offense)
        self.assertIn('<a class="hud-btn" href="#sub-pr" data-open="pr">Pinch run</a>', offense)
        response = self.post("step", expected=self.expected(), call="steal")
        self.assertEqual(gf.events(self.log(), Event.CALL)[-1].payload["call"], "steal")
        self.assertContains(response, "calls steal")

    def test_batting_calls_wait_for_the_manager_who_is_batting(self):
        self.post("open", seats="home")
        html = self.page()
        self.assertIn("Play the next plate appearance", html)
        self.assertNotIn('value="bunt"', html)
        self.assertNotIn('value="steal"', html)
        self.assertIn('value="intentional_walk"', html)


class LastPlayTest(GameHudTestCase):
    def test_a_step_leaves_the_play_to_animate_from_its_before_state(self):
        gf.set_rates([self.road.hitters[0]], SINGLE)
        self.post("open", seats="away,home")
        html = self.page()
        self.assertNotIn('id="hud-last-play"', html, "nothing to animate before the first pitch")
        html = self.post("step", expected=self.expected()).content.decode()
        play = self.last_play(html)
        event = gf.events(self.log(), Event.PLATE_APPEARANCE)[-1]
        self.assertEqual(play["sequence"], event.sequence)
        self.assertEqual(play["banner"], "SINGLE")
        self.assertTrue(event.text.endswith(play["text"]))
        self.assertNotIn("Top 1,", play["text"], "the half inning and count are on the scoreboard, not the banner")
        self.assertEqual(len(play["ball"]), 3, "mound, plate and where it was hit")
        self.assertEqual([(r["name"], r["end"]) for r in play["runners"]], [("Catcher", "first")])
        self.assertEqual(play["runners"][0]["from"], [300.0, 492.0])

    def test_a_home_run_scores_the_batter_and_flashes_the_run(self):
        gf.set_rates([self.road.hitters[0]], gf.HOME_RUN_RATES)
        self.post("open", seats="away,home")
        play = self.last_play(self.post("step", expected=self.expected()).content.decode())
        self.assertEqual(play["runs"], 1)
        self.assertEqual(play["side"], AWAY)
        self.assertEqual(play["inning"], 1)
        self.assertEqual(play["runners"][0]["end"], "home")

    def test_a_change_made_after_the_play_leaves_nothing_to_animate(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        self.post("pitcher", expected=self.expected(), side=HOME, player=self.home.relievers[0].id)
        self.assertNotIn('id="hud-last-play"', self.page())

    def test_the_last_plays_list_holds_four_newest_first(self):
        self.post("open", seats="away,home")
        for _ in range(5):
            self.post("step", expected=self.expected())
        recent = self.section(self.page(), 'class="hud-recent"', "</section>")
        texts = [e.text.split(": ", 1)[1] for e in reversed(gf.events(self.log(), Event.PLATE_APPEARANCE))][:4]
        self.assertEqual(recent.count('<span class="when">'), 4)
        self.assertRegex(recent, r'<span class="when">(Top|Bot) \d · \d-\d</span>')
        self.assertLess(recent.find(texts[0]), recent.find(texts[1]))


class PanelTest(GameHudTestCase):
    def test_the_pinch_hit_table_has_legal_rows_with_reach_odds_and_greyed_illegal_rows(self):
        capped = self.road.bench[0]
        gf.counter(capped, plate_appearances_cap=3, plate_appearances=3)
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        html = self.page()
        drawer = self.drawer(html, "ph")
        self.assertIn(f'action="/games/{self.game.id}/pinch_hit/"', drawer)
        self.assertIn(f'<input type="radio" name="player" value="{capped.id}" id="ph-{capped.id}" disabled>', drawer)
        self.assertIn(f"has used all 3 of his plate appearances", drawer)
        legal = self.road.bench[1]
        self.assertIn(f'<input type="radio" name="player" value="{legal.id}" id="ph-{legal.id}">', drawer)
        row = self.section(drawer, f'value="{legal.id}"', "</tr>")
        self.assertRegex(row, r'class="reach[^"]*">\d+% \([+−±]\d+\)<')
        self.assertIn("Send him up", drawer)

    def test_the_chance_to_reach_base_is_the_engine_matchup_with_his_platoon_rates(self):
        bench = self.road.bench[1]
        models.Card.objects.filter(player=bench).update(
            hitter_rates_vs_rhp={"k": 0.1, "bb": 0.15, "hbp": 0.01, "single": 0.2, "double": 0.06, "triple": 0.01, "hr": 0.05, "bip_out": 0.42}
        )
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        drawer = self.drawer(self.page(), "ph")
        shown = float(re.search(rf'data-compare="[^"]*" data-reach="([0-9.]+)">\s*<td class="pickcell"><input type="radio" name="player" value="{bench.id}"', drawer).group(1))

        play = sim_game.Play(self.log())
        state = play.state
        club = state[AWAY]
        index = club["batter_index"]
        card = play.card(bench)
        club["lineup"][index] = sim_game.batter_card(bench, card, club["lineup"][index]["position"])
        pitcher = play.player(sim_game.current_pitcher_id(state))
        rates = cards.plate_appearance_rates(card, play.card(pitcher), bench.bats, pitcher.throws)
        odds = engine_client.matchup(sim_game.with_rates(state, rates["hitter_rates"], rates["pitcher_rates"]))["probabilities"]
        expected = sum(odds[key] for key in ("bb", "hbp", "single", "double", "triple", "hr"))
        self.assertAlmostEqual(shown, expected, places=6)
        self.assertIn(f"chance to reach base", drawer)

    def test_the_pinch_run_table_is_sorted_by_speed_with_steal_success(self):
        models.Card.objects.filter(player=self.road.bench[0]).update(spd=3.0, steal_success=0.5)
        models.Card.objects.filter(player=self.road.bench[1]).update(spd=8.0, steal_success=0.9)
        gf.set_rates([self.road.hitters[0]], SINGLE)
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        drawer = self.drawer(self.page(), "pr")
        self.assertIn(f'action="/games/{self.game.id}/pinch_run/"', drawer)
        self.assertIn('name="base" value="first" checked', drawer)
        self.assertLess(drawer.find(self.road.bench[1].name), drawer.find(self.road.bench[0].name))
        self.assertIn("<td>8.0</td><td>90%</td>", drawer)

    def test_the_pitcher_table_shows_role_rates_rest_and_innings_he_can_go(self):
        tired = self.home.relievers[1]
        gf.counter(tired, innings_cap_outs=3, outs=3)
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        drawer = self.drawer(self.page(), "pit")
        self.assertIn(f'action="/games/{self.game.id}/pitcher/"', drawer)
        closer = self.section(drawer, f'value="{self.home.relievers[0].id}"', "</tr>")
        self.assertIn('<td class="wide">Closer</td>', closer)
        self.assertIn("<td>25%</td><td>7%</td>", closer)
        self.assertIn('<td class="wide">rested</td>', closer)
        self.assertRegex(closer, r"<td class=\"wide\">rested</td><td>\d+\.\d</td>\s*$")
        self.assertIn(f'value="{tired.id}" id="pit-{tired.id}" disabled', drawer)
        self.assertIn("no innings left this season", drawer)

    def test_the_defense_tab_lists_slots_with_ratings_and_the_bench(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        drawer = self.drawer(self.page(), "def")
        self.assertIn(f'action="/games/{self.game.id}/defense/"', drawer)
        self.assertIn(f'action="/games/{self.game.id}/positions/"', drawer)
        self.assertIn(f"1. {self.home.catcher.name} C +4.0", drawer)
        self.assertIn(f'value="{self.home.bench[0].id}"', drawer)

    def test_a_computer_side_tab_says_so_instead_of_a_table(self):
        self.post("open", user=self.manager, seats="away")
        self.post("step", user=self.manager, expected=self.expected())
        drawer = self.drawer(self.page(self.manager), "pit")
        self.assertIn(f"{self.home.team.abbreviation} is the computer&#x27;s side.", drawer)
        self.assertNotIn("<table", drawer)

    def test_a_forced_replacement_opens_its_tab_by_itself(self):
        second = self.road.hitters[1]
        gf.counter(second, plate_appearances_cap=1)
        gf.set_rates(self.road.hitters + self.home.hitters, gf.STRIKEOUT_RATES)
        self.post("open", seats="away,home")
        for _ in range(40):
            if sim_game.Play(self.log()).need() is not None:
                break
            self.post("step", expected=self.expected())
        html = self.page()
        self.assertIn('<aside id="sub-ph" class="hud-drawer open"', html)
        drawer = self.drawer(html, "ph")
        self.assertIn(f'action="/games/{self.game.id}/replace/"', drawer)
        self.assertIn(f"Replace {second.name}", drawer)
        self.assertIn('id="hud-play" disabled', html)
        self.assertNotIn("Play the next plate appearance", html)
