# ABOUTME: End-to-end tests for the team page's paired roster moves: Send down / Call up controls and the move page.
# ABOUTME: Uses one small road series, real players and the test client; no JavaScript is needed to make a move.

import re

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from ulmg import models, roster_moves
from tests.usage_fixtures import ULMG_SEASON, create_pitcher, create_series, create_teams

TEAM_URL = "/teams/atl/"
GAME_URL = "/teams/atl/game/"
MOVE_URL = "/teams/atl/moves/"
CHOICE_URL = "/teams/atl/moves/new/"
MOVE_FORM = f'<form method="post" action="{MOVE_URL}"'
NO_MOVES_LEFT = "No moves left this half (10 of 10 used)"


def create_owner(username, team):
    user = User.objects.create_user(username, f"{username}@example.com", "password")
    owner = models.Owner.objects.create(user=user, name=f"{username} owner", email=user.email)
    team.owner_obj = owner
    team.save()
    return user


def carded(name, team, mlb=False, aaa=False, **fields):
    """A pitcher with last season's MLB innings, so he passes the carded gate."""
    player = create_pitcher(name, team=team, g=30, gs=0, ip="60.0")
    models.Player.objects.filter(pk=player.pk).update(
        is_ulmg_mlb_roster=mlb, is_ulmg_aaa_roster=aaa, **fields
    )
    player.refresh_from_db()
    return player


def uncarded(name, team, mlb=False, aaa=False):
    return models.Player.objects.create(
        name=name, position="P", level="B", team=team, is_ulmg_mlb_roster=mlb, is_ulmg_aaa_roster=aaa
    )


def radio_ids(page):
    """The player ids the move page offers as radio choices."""
    return {int(value) for value in re.findall(r'type="radio" name="player_\w+" value="(\d+)"', page.content.decode())}


class OwnerClients:
    def setUp(self):
        self.clients = {}

    def client_for(self, user):
        # One client per user, so a message set by a post shows on the next page.
        if user not in self.clients:
            client = Client()
            if user is not None:
                client.force_login(user)
            self.clients[user] = client
        return self.clients[user]


@override_settings(CURRENT_SEASON=ULMG_SEASON, TEAM_SEASON_HALF="1h", TEAM_ROSTER_TAB=True)
class BeforeTheHalfTestCase(OwnerClients, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.home, cls.atl = create_teams()
        create_series(cls.home, cls.atl, length=3)
        cls.starter = carded("ATL Starter", cls.atl, mlb=True)
        cls.prospect = carded("ATL Prospect", cls.atl, aaa=True)
        cls.owner = create_owner("atl", cls.atl)

    def test_the_team_page_shows_the_single_mlb_and_aaa_buttons(self):
        page = self.client_for(self.owner).get(TEAM_URL)
        self.assertContains(page, f'data-playerid="{self.starter.id}" data-action="off_roster">MLB</a>', html=False)
        self.assertContains(page, f'data-playerid="{self.prospect.id}" data-action="to_mlb">MLB</a>', html=False)
        self.assertContains(page, f'data-playerid="{self.starter.id}" data-action="to_aaa">AAA</a>', html=False)
        self.assertNotContains(page, "Send down</a>")
        self.assertNotContains(page, "Call up</a>")
        game = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(game, "half-not-started")
        self.assertNotContains(game, "Send down</a>")


@override_settings(CURRENT_SEASON=ULMG_SEASON, TEAM_SEASON_HALF="1h", TEAM_ROSTER_TAB=True)
class PairedMovePagesTestCase(OwnerClients, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.home, cls.atl = create_teams()
        cls.games = create_series(cls.home, cls.atl, length=5)
        cls.owner = create_owner("atl", cls.atl)
        cls.other = create_owner("hch", cls.home)
        cls.commish = User.objects.create_superuser("commish", "c@example.com", "password")

        # The 30-man.
        cls.starter = carded("ATL Starter", cls.atl, mlb=True)
        cls.reliever = carded("ATL Reliever", cls.atl, mlb=True)
        cls.open_pick = carded("ATL Open Pick", cls.atl, mlb=True, is_ulmg_2h_draft=True)
        cls.stayer = carded("ATL Stayer", cls.atl, mlb=True)
        cls.appeared = carded("ATL Appeared", cls.atl, mlb=True)
        # AAA.
        cls.prospect = carded("ATL Prospect", cls.atl, aaa=True)
        cls.returner = carded("ATL Returner", cls.atl, aaa=True)
        cls.uncarded = uncarded("ATL Uncarded", cls.atl, aaa=True)
        # Elsewhere.
        cls.hch_aaa = carded("HCH Prospect", cls.home, aaa=True)
        cls.hch_mlb = carded("HCH Starter", cls.home, mlb=True)

        # An earlier move: the stayer's 15-road-game stay runs through all five road games.
        models.RosterMove.objects.create(
            season=ULMG_SEASON, half=1, team=cls.atl, player_up=cls.stayer, player_down=cls.returner,
            stay_games=5, stay_last_day=cls.games[-1].day,
        )
        # The first road game is in progress and one player has appeared in it.
        game = cls.games[0]
        game.opened_at = timezone.now()
        game.save()
        models.UsageAppearance.objects.create(player=cls.appeared, game=game, plate_appearances=1)

    def choice_page(self, user=None, **params):
        return self.client_for(user or self.owner).get(CHOICE_URL, params)

    def fill_to_cap(self):
        for _ in range(roster_moves.MOVES_PER_HALF - 1):
            models.RosterMove.objects.create(
                season=ULMG_SEASON, half=1, team=self.atl, player_up=self.prospect,
                player_down=self.starter, stay_games=0,
            )

    # Taking a player off his roster

    def test_an_aaa_player_keeps_his_off_roster_toggle_and_a_major_leaguer_has_none(self):
        page = self.client_for(self.owner).get(TEAM_URL).content.decode()
        self.assertIn(f'data-playerid="{self.prospect.id}" data-action="off_roster"', page)
        self.assertNotIn(f'data-playerid="{self.starter.id}" data-action="off_roster"', page)

    def test_an_owner_cannot_take_a_major_leaguer_off_his_roster_once_the_half_has_started(self):
        response = self.client_for(self.owner).get(f"/api/v1/player/{self.starter.id}/off_roster/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("roster move", response.json()["error"])
        self.starter.refresh_from_db()
        self.assertTrue(self.starter.is_ulmg_mlb_roster)

    def test_an_owner_can_still_take_an_aaa_player_off_his_roster(self):
        response = self.client_for(self.owner).get(f"/api/v1/player/{self.prospect.id}/off_roster/")
        self.assertEqual(response.content, b"ok")
        self.prospect.refresh_from_db()
        self.assertFalse(self.prospect.is_ulmg_aaa_roster)

    def test_the_commissioner_can_still_take_a_major_leaguer_off_his_roster(self):
        response = self.client_for(self.commish).get(f"/api/v1/player/{self.starter.id}/off_roster/")
        self.assertEqual(response.content, b"ok")

    # The team page

    def test_the_roster_page_keeps_the_opening_roster_once_the_half_has_started(self):
        page = self.client_for(self.owner).get(TEAM_URL)
        self.assertContains(page, "opening-roster-note")
        self.assertContains(page, 'class="opening-roster-player', count=5)
        self.assertNotContains(page, "Send down</a>")
        self.assertNotContains(page, "Call up</a>")
        self.assertNotContains(page, 'data-action="to_mlb">MLB</a>')
        self.assertNotContains(page, 'data-action="to_aaa">AAA</a>')
        self.assertNotContains(page, f'data-playerid="{self.starter.id}" data-action="off_roster"')
        # Midseason Open picks stay up, as before.
        self.assertContains(page, 'class="2h-draft-locked-mlb ', count=1)
        self.assertNotContains(page, f"?down={self.open_pick.id}")

    def test_the_game_page_shows_paired_controls_once_the_half_has_started(self):
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, f'href="{CHOICE_URL}?down={self.starter.id}"', count=1)
        self.assertContains(page, f'href="{CHOICE_URL}?up={self.prospect.id}"', count=1)
        self.assertContains(page, "Send down</a>", count=4)
        self.assertContains(page, "Call up</a>", count=3)
        self.assertNotContains(page, f"?down={self.open_pick.id}")
        home = page.content.decode().split('id="home-roster"', 1)[1].split('id="away-roster"', 1)[0]
        self.assertNotIn("/moves/new/", home)
        self.assertIn(self.returner.name, home)
        self.assertNotIn(self.prospect.name, home)

    def test_the_commissioner_sees_the_paired_controls(self):
        page = self.client_for(self.commish).get(GAME_URL)
        self.assertContains(page, f'href="{CHOICE_URL}?down={self.starter.id}"')

    # The move page lists exactly the legal choices

    def test_a_send_down_offers_the_carded_aaa_players(self):
        page = self.choice_page(down=self.starter.id)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(radio_ids(page), {self.prospect.id, self.returner.id})
        self.assertContains(page, "Send down ATL Starter")

    def test_a_send_down_leaves_out_an_uncarded_player_and_says_why(self):
        page = self.choice_page(down=self.starter.id)
        self.assertNotIn(self.uncarded.id, radio_ids(page))
        self.assertContains(page, "ATL Uncarded: Only carded players (MLB experience last season)")

    def test_a_call_up_offers_the_30_man_players_who_can_go_down(self):
        page = self.choice_page(up=self.prospect.id)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(radio_ids(page), {self.starter.id, self.reliever.id})
        self.assertContains(page, "Call up ATL Prospect")

    def test_a_call_up_leaves_out_a_midseason_open_pick(self):
        page = self.choice_page(up=self.prospect.id)
        self.assertNotIn(self.open_pick.id, radio_ids(page))
        self.assertContains(page, "ATL Open Pick: Midseason Open picks must stay on the MLB roster")

    def test_a_call_up_leaves_out_a_player_inside_his_stay(self):
        page = self.choice_page(up=self.prospect.id)
        self.assertNotIn(self.stayer.id, radio_ids(page))
        self.assertContains(page, "ATL Stayer: ATL Stayer was called up and stays on the 30-man")

    def test_a_call_up_leaves_out_a_player_in_the_road_game_in_progress(self):
        page = self.choice_page(up=self.prospect.id)
        self.assertNotIn(self.appeared.id, radio_ids(page))
        self.assertContains(page, "ATL Appeared: ATL Appeared has appeared in the game in progress (day 1)")

    def test_a_player_who_cant_go_down_gets_a_reason_not_a_list(self):
        for player, reason in [
            (self.stayer, "road games left on his stay"),
            (self.open_pick, "Midseason Open picks must stay on the MLB roster"),
            (self.appeared, "has appeared in the game in progress"),
        ]:
            with self.subTest(player=player.name):
                page = self.choice_page(down=player.id)
                self.assertEqual(radio_ids(page), set())
                self.assertContains(page, reason)
                self.assertNotContains(page, MOVE_FORM)

    def test_a_player_who_cant_come_up_gets_a_reason_not_a_list(self):
        page = self.choice_page(up=self.uncarded.id)
        self.assertEqual(radio_ids(page), set())
        self.assertContains(page, "Only carded players (MLB experience last season)")
        self.assertNotContains(page, MOVE_FORM)

    def test_no_legal_partner_says_why_for_each_player(self):
        models.Player.objects.filter(pk__in=[self.prospect.pk, self.returner.pk]).update(team=self.home)
        page = self.choice_page(down=self.starter.id)
        self.assertEqual(radio_ids(page), set())
        self.assertContains(page, "No AAA player can be called up for ATL Starter.")
        self.assertContains(page, "ATL Uncarded: Only carded players")
        self.assertNotContains(page, MOVE_FORM)

    def test_another_teams_player_is_not_offered(self):
        page = self.choice_page(down=self.starter.id)
        self.assertNotIn(self.hch_aaa.id, radio_ids(page))
        self.assertNotContains(page, "HCH Prospect")
        page = self.choice_page(down=self.hch_mlb.id)
        self.assertContains(page, "HCH Starter is not on ATL&#x27;s 30-man.")

    # Confirming

    def test_confirming_makes_one_move_and_counts_once(self):
        page = self.choice_page(down=self.starter.id)
        form = page.content.decode()
        self.assertIn(f'<form method="post" action="{MOVE_URL}"', form)
        self.assertIn(f'<input type="hidden" name="player_down" value="{self.starter.id}">', form)

        before = roster_moves.moves_left(self.atl, ULMG_SEASON, 1)
        response = self.client_for(self.owner).post(
            MOVE_URL, {"player_down": self.starter.id, "player_up": self.prospect.id}
        )
        self.assertRedirects(response, GAME_URL + "#roster-moves", fetch_redirect_response=False)
        self.assertEqual(models.RosterMove.objects.filter(team=self.atl).count(), 2)
        self.assertEqual(roster_moves.moves_left(self.atl, ULMG_SEASON, 1), before - 1)

        self.prospect.refresh_from_db()
        self.starter.refresh_from_db()
        self.assertTrue(self.prospect.is_ulmg_mlb_roster)
        self.assertTrue(self.starter.is_ulmg_aaa_roster)

        game_page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(game_page, "Called up ATL Prospect and sent down ATL Starter.")
        self.assertContains(game_page, '<span id="moves-left">8</span> of 10', html=False)
        self.assertContains(game_page, f'href="{CHOICE_URL}?down={self.prospect.id}"')
        self.assertContains(game_page, f'href="{CHOICE_URL}?up={self.starter.id}"')
        self.assertContains(game_page, "ATL Prospect</a>: 5 road games left")

    def test_a_refused_move_goes_back_with_the_reason(self):
        response = self.client_for(self.owner).post(
            MOVE_URL, {"player_down": self.stayer.id, "player_up": self.prospect.id}
        )
        self.assertRedirects(response, GAME_URL + "#roster-moves", fetch_redirect_response=False)
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, "road games left on his stay")
        self.assertEqual(models.RosterMove.objects.filter(team=self.atl).count(), 1)

    # The cap

    def test_at_the_cap_the_controls_give_way_to_the_cap_message(self):
        self.fill_to_cap()
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, NO_MOVES_LEFT, count=1)
        self.assertNotContains(page, "Send down</a>")
        self.assertNotContains(page, "Call up</a>")
        roster = self.client_for(self.owner).get(TEAM_URL)
        self.assertNotContains(roster, 'data-action="to_mlb">MLB</a>')

        choice = self.choice_page(down=self.starter.id)
        self.assertContains(choice, "ATL has made its 10 moves for half 1.")
        self.assertNotContains(choice, MOVE_FORM)

    def test_the_eleventh_move_is_refused_with_the_cap_message(self):
        self.fill_to_cap()
        self.client_for(self.owner).post(MOVE_URL, {"player_down": self.reliever.id, "player_up": self.prospect.id})
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, "ATL has made its 10 moves for half 1.")
        self.assertEqual(models.RosterMove.objects.filter(team=self.atl).count(), 10)
        self.reliever.refresh_from_db()
        self.assertTrue(self.reliever.is_ulmg_mlb_roster)

    # Who can move

    def test_another_owner_sees_no_controls_and_is_refused_the_move_page(self):
        page = self.client_for(self.other).get(GAME_URL)
        self.assertNotContains(page, "Send down</a>")
        self.assertNotContains(page, "Call up</a>")
        roster = self.client_for(self.other).get(TEAM_URL)
        self.assertNotContains(roster, "Send down</a>")
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.choice_page(self.other, down=self.starter.id)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden: /teams/atl/moves/new/", logs.output[0])

    def test_logged_out_goes_to_login_from_the_move_page(self):
        response = self.client_for(None).get(CHOICE_URL, {"down": self.starter.id})
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_the_move_page_needs_one_player(self):
        for params in ({}, {"down": "x"}, {"down": self.starter.id, "up": self.prospect.id}):
            with self.subTest(params=params):
                response = self.choice_page(**params)
                self.assertRedirects(response, GAME_URL + "#roster-moves", fetch_redirect_response=False)
        page = self.client_for(self.owner).get(GAME_URL)
        self.assertContains(page, "Start a move from a player on the game page.")

    # Without JavaScript

    def test_the_controls_and_the_move_page_work_without_javascript(self):
        team_page = self.client_for(self.owner).get(GAME_URL).content.decode()
        send_down = re.search(r'<a [^>]*href="/teams/atl/moves/new/\?down=\d+"[^>]*>', team_page).group(0)
        self.assertNotIn("player-action", send_down)
        self.assertNotIn("data-action", send_down)

        page = self.choice_page(up=self.prospect.id).content.decode()
        body = page.split('id="paired-move"', 1)[1].split("</main>", 1)[0]
        self.assertNotIn("<script", body)
        self.assertNotIn("onclick", body)
        self.assertIn('<form method="post"', body)
        self.assertIn('<button type="submit"', body)
        self.assertIn('name="csrfmiddlewaretoken"', body)

        # A plain form post, with only the fields the page holds, makes the move.
        fields = dict(re.findall(r'<input type="hidden" name="(player_\w+)" value="(\d+)">', body))
        fields["player_down"] = str(self.reliever.id)
        self.client_for(self.owner).post(MOVE_URL, fields)
        self.reliever.refresh_from_db()
        self.assertTrue(self.reliever.is_ulmg_aaa_roster)


@override_settings(CURRENT_SEASON=ULMG_SEASON)
class MoveChoicesAgreeWithMakeMoveTestCase(TestCase):
    """
    move_choices and make_move run the same checks: every AAA or 30-man player
    move_choices lists is one make_move accepts for that pair, and no other.
    """

    @classmethod
    def setUpTestData(cls):
        cls.home, cls.atl = create_teams()
        cls.games = create_series(cls.home, cls.atl, length=5)
        cls.players = [
            carded("ATL Starter", cls.atl, mlb=True),
            carded("ATL Open Pick", cls.atl, mlb=True, is_ulmg_2h_draft=True),
            carded("ATL Stayer", cls.atl, mlb=True),
            uncarded("ATL Uncarded Regular", cls.atl, mlb=True),
            carded("ATL Prospect", cls.atl, aaa=True),
            carded("ATL Returner", cls.atl, aaa=True),
            uncarded("ATL Uncarded", cls.atl, aaa=True),
        ]
        models.RosterMove.objects.create(
            season=ULMG_SEASON, half=1, team=cls.atl, player_up=cls.players[2], player_down=cls.players[5],
            stay_games=5, stay_last_day=cls.games[-1].day,
        )

    def test_every_listed_pair_is_one_make_move_accepts(self):
        thirty_man = [p for p in self.players if p.is_ulmg_mlb_roster]
        aaa = [p for p in self.players if p.is_ulmg_aaa_roster]
        for direction, starters, partners in [(roster_moves.DOWN, thirty_man, aaa), (roster_moves.UP, aaa, thirty_man)]:
            for player in starters:
                choices = roster_moves.move_choices(self.atl, player, direction, ULMG_SEASON, 1)
                listed = {p.id for p in choices.legal}
                for other in partners:
                    up, down = (other, player) if direction == roster_moves.DOWN else (player, other)
                    with self.subTest(up=up.name, down=down.name):
                        error = roster_moves._move_errors(self.atl, up, down, ULMG_SEASON, 1)
                        self.assertEqual(other.id in listed, error is None, error)
