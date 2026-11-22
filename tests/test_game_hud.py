# ABOUTME: Tests the game HUD page against the real engine: the scoreboard, cards, field, calls, last play and substitution panel.
# ABOUTME: Each test opens a real game from the shared fixtures and reads the rendered page the way a manager would.

import json
import re

from django.db import transaction
from django.test import TestCase

from tests import game_fixtures as gf
from ulmg import cards, engine_client, game_field, models, sim_game

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

    def order(self, html, during=False):
        marker = 'id="hud-during-order"' if during else 'id="hud-order"'
        return self.section(html, marker, "</ol>")

    def order_row(self, hitter, position, number, mark, short, tone, throws):
        from ulmg import game_hud

        line = game_hud.hitter_line(models.Card.objects.get(player=hitter), throws)
        title = f"{hitter.name}, {position}, bats {hitter.bats}, {line['avg']}/{line['obp']}"
        if mark:
            title += f", {mark}"
        attrs = f' class="{tone}"' if tone else ""
        if tone in ("now", "due"):
            attrs += ' aria-current="true"'
        tail = f'<span class="mark">{short}</span>' if short else f'<span class="slash">{line["avg"]}</span>'
        return (
            f"<li{attrs}><span class=\"slot\">{number}</span>"
            f'<a href="/players/{hitter.id}/" title="{title}">{hitter.name}</a>'
            f'<span class="pos">{position} · {hitter.bats}</span>{tail}</li>'
        )

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

    def test_the_pitcher_card_shows_his_role_pitch_count_and_innings_left(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        card = self.section(self.page(), 'class="hud-card hud-pitcher"', 'class="hud-controls"')
        starter = self.home.starters[0]
        fatigue = self.log().state[HOME]["fatigue"][str(starter.id)]
        self.assertIn(starter.name, card)
        self.assertIn("Starter · throws right", card)
        self.assertIn(f"<b>{fatigue['pitches']}</b> pitches · tires near <b>{round(fatigue['ceiling'])}</b>", card)
        self.assertIn("IP left this outing: <b>", card)

    def test_the_plate_appearance_odds_sit_with_the_batter_when_the_manager_is_hitting(self):
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        strikeout = f'<span class="pct">{dict(sim_game.matchup(sim_game.Play(self.log())))["Strikeout"]:.1f}%</span>'
        mine = self.page()
        batter = self.section(mine, 'class="hud-card hud-batter"', 'id="hud-field"')
        pitcher = self.section(mine, 'id="hud-pitcher"', 'class="hud-controls"')
        self.assertIn("This plate appearance", batter)
        self.assertIn(strikeout, batter)
        self.assertNotIn("This plate appearance", pitcher)
        watching = self.page(self.manager)
        self.assertIn(strikeout, self.section(watching, 'id="hud-pitcher"', 'class="hud-controls"'))
        self.assertNotIn("This plate appearance", self.section(watching, 'class="hud-card hud-batter"', 'id="hud-field"'))

    def test_the_plate_appearance_odds_stay_with_the_pitcher_on_defense(self):
        self.post("open", seats="home")
        self.post("step", expected=self.expected())
        strikeout = f'<span class="pct">{dict(sim_game.matchup(sim_game.Play(self.log())))["Strikeout"]:.1f}%</span>'
        html = self.page()
        self.assertIn(strikeout, self.section(html, 'id="hud-pitcher"', 'class="hud-controls"'))
        self.assertNotIn("This plate appearance", self.section(html, 'class="hud-card hud-batter"', 'id="hud-field"'))

    def test_the_cards_color_the_platoon_edge_of_this_matchup(self):
        leadoff = self.road.hitters[0]
        vs_rhp = dict(gf.HITTER_RATES, single=0.24, bip_out=gf.HITTER_RATES["bip_out"] - 0.1)
        models.Card.objects.filter(player=leadoff).update(hitter_rates_vs_rhp=vs_rhp)
        starter = self.home.starters[0]
        vs_rhh = {"k": 0.25, "bb": 0.05, "hbp": 0.01, "h": 0.12, "hr": 0.02}
        models.Card.objects.filter(player=starter).update(pitcher_rates_vs_rhh=vs_rhh)
        self.post("open", seats="away,home")
        html = self.page()
        from ulmg import game_hud

        hitter_card = models.Card.objects.get(player=leadoff)
        pitcher_card = models.Card.objects.get(player=starter)
        hitter = game_hud.hitter_edge(hitter_card, "R")
        pitcher = game_hud.pitcher_edge(pitcher_card, leadoff.bats)
        self.assertGreater(hitter, 0)
        self.assertLess(pitcher, 0)
        batter = self.section(html, 'class="hud-card hud-batter"', "</ul>")
        self.assertIn(f'class="matchup-edge edge-good">vs RHP {game_hud.edge_text(hitter)} OPS', batter)
        mound = self.section(html, 'class="hud-card hud-pitcher"', "</ul>")
        self.assertIn(f'class="matchup-edge edge-good">vs RHH {game_hud.edge_text(pitcher)} OBP', mound)


# Batting-order slots the fixture files: catcher, the seven fielders, then the DH.
ORDER_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]


class OpponentLineupTest(GameHudTestCase):
    def test_a_pitching_manager_sees_his_opponents_whole_lineup(self):
        self.post("open", seats="home")
        throws = self.home.starters[0].throws
        order = self.order(self.page())
        self.assertIn(f"Opponent · {self.road.team.abbreviation} · vs RHP", order)
        self.assertNotIn(self.home.hitters[0].name, order)
        for number, (hitter, position) in enumerate(zip(self.road.hitters, ORDER_POSITIONS), start=1):
            mark, short, tone = {1: ("Now", "Now", "now"), 2: ("On deck", "Deck", "deck"), 3: ("In the hole", "Hole", "hole")}.get(number, ("", "", ""))
            self.assertIn(self.order_row(hitter, position, number, mark, short, tone, throws), order)

    def test_a_batting_manager_sees_who_his_opponent_has_due_up(self):
        self.post("open", seats="away")
        throws = self.road.starters[0].throws
        order = self.order(self.page())
        self.assertIn(f"Opponent · {self.home.team.abbreviation} · vs RHP", order)
        self.assertNotIn(">Now</span>", order)
        for number, (hitter, position) in enumerate(zip(self.home.hitters, ORDER_POSITIONS), start=1):
            mark, short, tone = {1: ("Due up", "Due", "due"), 2: ("On deck", "Deck", "deck"), 3: ("In the hole", "Hole", "hole")}.get(number, ("", "", ""))
            self.assertIn(self.order_row(hitter, position, number, mark, short, tone, throws), order)
        watching = self.order(self.page(self.other_manager))
        self.assertIn(f"Batting order · {self.road.team.abbreviation}", watching)
        self.assertIn(self.order_row(self.road.hitters[0], "C", 1, "Now", "Now", "now", self.home.starters[0].throws), watching)

    def test_the_highlight_follows_the_order_and_the_play_keeps_the_man_who_just_hit(self):
        gf.set_rates([self.road.hitters[0]], gf.STRIKEOUT_RATES)
        self.post("open", seats="home")
        html = self.post("step", expected=self.expected()).content.decode()
        throws = self.home.starters[0].throws
        live = self.order(html)
        prior = self.order(html, during=True)
        self.assertIn(self.order_row(self.road.hitters[1], "1B", 2, "Now", "Now", "now", throws), live)
        self.assertIn(self.order_row(self.road.hitters[2], "2B", 3, "On deck", "Deck", "deck", throws), live)
        self.assertIn(self.order_row(self.road.hitters[0], "C", 1, "Now", "Now", "now", throws), prior)
        self.assertIn(self.order_row(self.road.hitters[1], "1B", 2, "On deck", "Deck", "deck", throws), prior)


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
        self.assertIn('href="?confirm=bunt"', offense)
        self.assertNotIn('href="?confirm=intentional_walk"', defense)
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
        self.assertIn('href="?confirm=steal" class="hud-btn live"', offense)
        self.assertNotIn("Steal needs a runner", offense)
        self.assertIn('<a class="hud-btn" href="#sub-pr" data-open="pr">Pinch run</a>', offense)
        response = self.post("step", expected=self.expected(), call="steal")
        self.assertEqual(gf.events(self.log(), Event.CALL)[-1].payload["call"], "steal")
        self.assertContains(response, "calls steal")

    def test_batting_calls_wait_for_the_manager_who_is_batting(self):
        self.post("open", seats="home")
        html = self.page()
        self.assertIn("Play the next plate appearance", html)
        self.assertNotIn('confirm=bunt', html)
        self.assertNotIn('confirm=steal', html)
        self.assertIn('href="?confirm=intentional_walk"', html)

    def test_a_call_asks_before_it_is_sent_and_a_steal_names_the_runner(self):
        leadoff = self.road.hitters[0]
        models.Card.objects.filter(player=leadoff).update(steal_success=0.62)
        gf.set_rates([leadoff], SINGLE)
        self.post("open", seats="away,home")
        quiet = self.page()
        self.assertNotIn('href="?confirm=steal"', quiet)
        asked = self.client.get(self.url + "?confirm=bunt").content.decode()
        dialog = self.section(asked, 'class="hud-confirm"', "</form>")
        self.assertIn(leadoff.name, dialog)
        self.assertIn('name="call" value="bunt"', dialog)
        self.assertNotIn('class="hud-confirm"', self.client.get(self.url + "?confirm=steal").content.decode())
        self.post("step", expected=self.expected())
        html = self.client.get(self.url + "?confirm=steal").content.decode()
        dialog = self.section(html, 'class="hud-confirm"', "</form>")
        self.assertIn(f"{leadoff.name}, on first, steals second 62% of the time.", dialog)
        self.assertIn('name="call" value="steal"', dialog)
        self.assertIn(">Send him<", dialog)

    def test_a_steal_with_no_success_rate_shows_the_engine_default(self):
        leadoff = self.road.hitters[0]
        self.assertIsNone(models.Card.objects.get(player=leadoff).steal_success)
        gf.set_rates([leadoff], SINGLE)
        self.post("open", seats="away,home")
        self.post("step", expected=self.expected())
        html = self.client.get(self.url + "?confirm=steal").content.decode()
        self.assertIn(f"{leadoff.name}, on first, steals second 75% of the time.", self.section(html, 'class="hud-confirm"', "</form>"))


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
        self.assertEqual(play["ball"][1], list(game_field.HOME), "the hit leaves home plate")
        self.assertEqual([(r["name"], r["end"]) for r in play["runners"]], [("Catcher", "first")])
        self.assertEqual(play["runners"][0]["from"], [300.0, 492.0])
        self.assertEqual(play["runners"][0]["path"][0], play["runners"][0]["from"])
        self.assertEqual(play["runners"][0]["path"][-1], play["runners"][0]["to"])
        self.assertEqual(len(play["runners"][0]["path"]), 2, "first base is one base away")

    def test_the_field_keeps_the_defense_until_the_play_has_been_shown(self):
        gf.set_rates(self.road.hitters[:3], gf.STRIKEOUT_RATES)
        self.post("open", seats="away,home")
        for _ in range(2):
            self.post("step", expected=self.expected())
        html = self.post("step", expected=self.expected()).content.decode()
        live = self.section(html, 'id="hud-fielders"', '<g id="hud-runners">')
        during = self.section(html, 'id="hud-during-fielders"', 'id="hud-during-batter"')
        self.assertIn(f'data-player="{self.road.catcher.id}"', live, "the end state is the new half's defense")
        self.assertIn(f'data-player="{self.road.starters[0].id}"', live)
        self.assertIn(f'data-player="{self.home.catcher.id}"', during, "the play is shown with the defense that was on the field")
        self.assertIn(f'data-player="{self.home.starters[0].id}"', during)
        self.assertNotIn(f'data-player="{self.home.catcher.id}"', live)
        batter = self.section(html, 'id="hud-during-batter"', 'id="hud-during-pitcher"')
        self.assertIn(self.road.hitters[2].name, batter)
        live_batter = self.section(html, 'id="hud-batter"', 'id="hud-field"')
        self.assertIn(self.home.hitters[0].name, live_batter, "the end state has the next half's batter")
        self.assertNotIn(self.road.hitters[2].name, live_batter)
        self.assertIn(self.home.starters[0].name, self.section(html, 'id="hud-during-pitcher"', "</div>"))
        self.assertIn(self.road.starters[0].name, self.section(html, 'id="hud-pitcher"', 'id="hud-during'))
        play = self.last_play(html)
        self.assertEqual(play["situation"]["outs"], 2)
        self.assertIn("Top", play["situation"]["inning"])
        self.assertIn("Bottom", self.section(html, 'id="hud-inning"', "</p>"))

    def test_a_home_run_scores_the_batter_and_flashes_the_run(self):
        gf.set_rates([self.road.hitters[0]], gf.HOME_RUN_RATES)
        self.post("open", seats="away,home")
        play = self.last_play(self.post("step", expected=self.expected()).content.decode())
        self.assertEqual(play["runs"], 1)
        self.assertEqual(play["side"], AWAY)
        self.assertEqual(play["inning"], 1)
        self.assertEqual(play["runners"][0]["end"], "home")
        self.assertEqual(len(play["runners"][0]["path"]), 5, "a home run touches every base")
        self.assertEqual(play["runners"][0]["path"][0], play["runners"][0]["path"][-1])

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


class DiceCardTest(GameHudTestCase):
    def dice(self, html):
        return self.section(html, 'id="hud-dice"', "</section>")

    def test_a_swing_shows_the_dice_and_lights_the_card_cell_that_reads_the_result(self):
        gf.set_rates([self.road.hitters[0]], SINGLE)
        self.post("open", seats="away,home")
        self.assertNotIn('id="hud-dice"', self.page(), "no dice before the first pitch")
        html = self.post("step", expected=self.expected()).content.decode()
        event = gf.events(self.log(), Event.PLATE_APPEARANCE)[-1]
        self.assertEqual(set(event.payload["card"]), {key for key, _ in sim_game.MATCHUP_LABELS})
        self.assertAlmostEqual(sum(event.payload["card"].values()), 1.0, places=6)
        dice = self.dice(html)
        self.assertIn(f'data-sequence="{event.sequence}"', html)
        self.assertIn("<b>SINGLE</b>", dice)
        self.assertIn(f"{self.road.hitters[0].name}</span> <i>vs</i> <span>{self.home.starters[0].name}", dice)
        self.assertEqual(dice.count('<td class="'), 100)
        lit = re.findall(r'<span class="part[^"]* hit"[^>]*><span class="long">([^<]+)</span>', dice)
        self.assertEqual(lit, ["SINGLE"])
        read = sim_game.dice_for(sim_game.Play(self.log()), event)
        self.assertIn(f'data-face="{read["dice"]["column"]}"', dice)
        self.assertIn(f'data-face="{read["dice"]["row"]}"', dice)

    def test_the_card_is_the_engines_matchup_for_the_plate_appearance(self):
        self.post("open", seats="away,home")
        play = sim_game.Play(self.log())
        _, _, inputs = sim_game.plate_appearance_inputs(play, None)
        before = engine_client.matchup(sim_game.with_rates(play.state, inputs["hitter_rates"], inputs["pitcher_rates"]))
        self.post("step", expected=self.expected())
        event = gf.events(self.log(), Event.PLATE_APPEARANCE)[-1]
        for key, _ in sim_game.MATCHUP_LABELS:
            self.assertEqual(event.payload["card"][key], before["probabilities"][key], key)

    def test_a_reload_shows_the_same_roll(self):
        self.post("open", seats="away,home")
        first = self.dice(self.post("step", expected=self.expected()).content.decode())
        self.assertEqual(self.dice(self.page()), first)

    def test_a_bunt_reads_no_card(self):
        gf.set_rates([self.road.hitters[0]], SINGLE)
        self.post("open", seats="away,home")
        html = self.post("step", expected=self.expected(), call="bunt").content.decode()
        event = gf.events(self.log(), Event.PLATE_APPEARANCE)[-1]
        self.assertTrue(event.payload["result"]["outcome"].startswith("bunt"))
        self.assertNotIn('id="hud-dice"', html)


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
        for starter in self.home.starters:
            self.assertNotIn(f'value="{starter.id}"', drawer)
        self.assertIn(f'value="{self.home.swingman.id}"', drawer)

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


OUT = {"k": 0.0, "bb": 0.0, "hbp": 0.0, "single": 0.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 1.0}
WALK = {"k": 0.0, "bb": 1.0, "hbp": 0.0, "single": 0.0, "double": 0.0, "triple": 0.0, "hr": 0.0, "bip_out": 0.0}


class CallTextTest(GameHudTestCase):
    """A steal or a hit-and-run has to say so in the play the owner reads."""

    def _open_and_single(self):
        self.post("open", seats="away,home")
        gf.set_rates([self.road.hitters[0]], SINGLE)
        self.post("step", expected=self.expected())

    def _play(self, html):
        return self.last_play(html)["text"]

    def _book(self, html):
        return self.section(html, 'class="game-play-by-play', "</ol>")

    def test_a_steal_and_a_single_names_the_stolen_base(self):
        runner = self.road.hitters[0]
        batter = self.road.hitters[1]
        models.Card.objects.filter(player=runner).update(steal_success=1.0)
        self._open_and_single()
        gf.set_rates([batter], SINGLE)
        html = self.post("step", expected=self.expected(), call="steal").content.decode()
        text = self._play(html)
        stole = f"{runner.name} stole second."
        singled = f"{batter.name} singled."
        self.assertIn(stole, text)
        self.assertIn(singled, text)
        self.assertLess(text.find(stole), text.find(singled))
        self.assertIn(stole, self._book(html))

    def test_a_caught_stealing_names_the_runner(self):
        runner = self.road.hitters[0]
        batter = self.road.hitters[1]
        models.Card.objects.filter(player=runner).update(steal_success=0.0)
        self._open_and_single()
        gf.set_rates([batter], gf.STRIKEOUT_RATES)
        html = self.post("step", expected=self.expected(), call="steal").content.decode()
        text = self._play(html)
        self.assertIn(f"{runner.name} was caught stealing.", text)
        self.assertIn(f"{batter.name} struck out.", text)
        self.assertNotIn(f"{batter.name} was caught stealing", text)
        self.assertIn(f"{runner.name} was caught stealing.", self._book(html))

    def test_a_steal_with_the_bases_loaded_says_the_runner_held(self):
        self.post("open", seats="away,home")
        gf.set_rates(self.road.hitters[:4], WALK)
        for _ in range(3):
            self.post("step", expected=self.expected())
        html = self.post("step", expected=self.expected(), call="steal").content.decode()
        text = self._play(html)
        self.assertIn("Steal not attempted (held).", text)
        self.assertIn("walked.", text)
        self.assertLess(text.find("Steal not attempted (held)."), text.find("walked."))
        self.assertIn("Steal not attempted (held).", self._book(html))

    def test_a_hit_and_run_single_says_it_succeeded(self):
        batter = self.road.hitters[1]
        self._open_and_single()
        gf.set_rates([batter], SINGLE)
        html = self.post("step", expected=self.expected(), call="hit_and_run").content.decode()
        text = self._play(html)
        self.assertIn(f"{batter.name} singled.", text)
        self.assertIn("Hit-and-run succeeded.", text)
        self.assertLess(text.find(f"{batter.name} singled."), text.find("Hit-and-run succeeded."))
        self.assertIn("Hit-and-run succeeded.", self._book(html))

    def test_a_hit_and_run_strikeout_says_it_failed(self):
        batter = self.road.hitters[1]
        self._open_and_single()
        gf.set_rates([batter], gf.STRIKEOUT_RATES)
        # A hit-and-run keeps half the strikeouts, so the pure strikeout card is not a certain strikeout.
        log = self.log()
        for seed in range(40):
            mark = transaction.savepoint()
            sim_game.step(
                gf.refresh(log),
                self.tester,
                sim_game.Play(gf.refresh(log)).sequence,
                call="hit_and_run",
                seeds=lambda s=seed: s,
            )
            event = gf.events(gf.refresh(log), Event.PLATE_APPEARANCE)[-1]
            if event.payload["result"]["outcome"] == "strikeout":
                break
            transaction.savepoint_rollback(mark)
        else:
            self.fail("a hit-and-run still strikes out sometimes")
        html = self.page()
        text = self._play(html)
        self.assertIn(f"{batter.name} struck out.", text)
        self.assertIn("Hit-and-run failed.", text)
        self.assertLess(text.find(f"{batter.name} struck out."), text.find("Hit-and-run failed."))
        self.assertIn("Hit-and-run failed.", self._book(html))

    def test_a_hit_and_run_out_says_the_call_was_on(self):
        self._open_and_single()
        gf.set_rates([self.road.hitters[1]], OUT)
        html = self.post("step", expected=self.expected(), call="hit_and_run").content.decode()
        text = self._play(html)
        self.assertIn("Hit-and-run.", text)
        self.assertNotIn("Hit-and-run succeeded", text)
        self.assertNotIn("Hit-and-run failed", text)
        self.assertIn("Hit-and-run.", self._book(html))
