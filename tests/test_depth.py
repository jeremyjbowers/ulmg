# ABOUTME: Depth-chart totals: plate appearances by position, the 162 starts, and bullpen innings.
# ABOUTME: An unlimited player covers a shortfall and is left out of the number that gets added up.

from django.test import SimpleTestCase, TestCase

from ulmg import depth, models


SEASON = 2027


def make_team(abbreviation="ATL"):
    return models.Team.objects.create(
        abbreviation=abbreviation, city=abbreviation, nickname=abbreviation, division="Rickey"
    )


def make_player(team, name, position="OF", throws="R"):
    return models.Player.objects.create(
        name=name, position=position, throws=throws, team=team, level="V"
    )


def spot(chart, code):
    spots = [*chart.hitting, chart.rotation, chart.bullpen]
    return next(item for item in spots if item.code == code)


class EstimateTest(SimpleTestCase):
    def test_a_season_asks_for_162_starts_and_the_recent_rate_of_batting_and_innings(self):
        self.assertEqual(depth.season_plate_appearances(), 6097)
        self.assertEqual(depth.position_plate_appearances(), 677)
        self.assertEqual(depth.season_innings(), 1437)
        self.assertEqual(depth.starter_innings(), 842)
        self.assertEqual(depth.bullpen_innings(), 595)
        self.assertEqual(depth.bucket_target("RF"), 677)
        self.assertEqual(depth.bucket_target(depth.STARTS), 162)
        self.assertEqual(depth.bucket_target(depth.BULLPEN), 595)
        self.assertEqual(depth.position_plate_appearances() * 9 + 4, depth.season_plate_appearances())

    def test_the_page_note_names_those_totals(self):
        note = depth.estimate_note()
        for number in ("6,097", "677", "162", "1,437", "842", "595"):
            self.assertIn(number, note)
        self.assertIn("677", depth.empty_note())
        self.assertIn("162", depth.empty_note())
        self.assertIn("595", depth.empty_note())


class ChartTest(TestCase):
    def setUp(self):
        self.team = make_team()
        self.other = make_team("CAR")
        self.seager = make_player(self.team, "Corey Seager", position="IF")
        self.greene = make_player(self.team, "Riley Greene", position="OF", throws="L")
        self.abbott = make_player(self.team, "Aaron Abbott", position="IF")
        self.zimmer = make_player(self.team, "Zack Zimmer", position="OF")
        self.pitcher = make_player(self.team, "Spencer Strider", position="P")
        self.two_way = make_player(self.team, "Shohei Ohtani", position="IF-P")
        self.stranger = make_player(self.other, "Juan Soto", position="OF")
        self.chart = depth.ensure(self.team, SEASON)

    def file(self, player, bucket, amount=None, unlimited=False):
        return depth.add_player(self.chart, player, bucket, amount, unlimited)

    def described(self):
        return depth.describe(self.team, SEASON)

    def test_an_empty_chart_is_short_everywhere(self):
        chart = self.described()
        self.assertTrue(chart.empty)
        rf = spot(chart, "RF")
        self.assertEqual((rf.counted, rf.gap, rf.state, rf.headline), (0, 677, "short", "677 PA short"))
        self.assertEqual(
            chart.gaps,
            [
                "No one is filed at any position (677 plate appearances each).",
                "The rotation has no one filed (162 starts).",
                "The bullpen has no one filed (595 innings).",
            ],
        )

    def test_a_player_can_be_numbered_at_two_positions_and_the_gap_is_what_is_left(self):
        self.file(self.seager, "SS", 200)
        self.file(self.seager, "2B", 236)
        chart = self.described()
        shortstop = spot(chart, "SS")
        second = spot(chart, "2B")
        self.assertEqual(shortstop.counted, 200)
        self.assertEqual(shortstop.headline, "477 PA short")
        self.assertEqual(second.headline, "441 PA short")
        self.assertIn("SS is 477 plate appearances short.", chart.gaps)
        self.assertIn("2B is 441 plate appearances short.", chart.gaps)
        grouped = next(line for line in chart.gaps if "have no one filed" in line)
        self.assertIn("C, 1B, 3B, LF, CF, RF and DH", grouped)
        self.assertNotIn("SS", grouped)
        self.assertNotIn("2B", grouped)
        line = chart.players[0]
        self.assertEqual(line.player, self.seager)
        self.assertEqual(line.plate_appearances, 436)
        self.assertIn("200 PA at SS", line.detail)
        self.assertIn("236 PA at 2B", line.detail)

    def test_right_field_shows_the_shortfall_against_the_position(self):
        self.file(self.abbott, "RF", 477)
        chart = self.described()
        self.assertEqual(spot(chart, "RF").headline, "200 PA short")
        self.assertIn("RF is 200 plate appearances short.", chart.gaps)

    def test_one_plate_appearance_is_singular(self):
        self.file(self.abbott, "RF", 676)
        chart = self.described()
        self.assertEqual(spot(chart, "RF").headline, "1 PA short")
        self.assertIn("RF is 1 plate appearance short.", chart.gaps)
        self.file(self.zimmer, "LF", 678)
        chart = self.described()
        self.assertEqual(spot(chart, "LF").headline, "1 PA over")
        self.assertIn("LF is 1 plate appearance over.", chart.gaps)

    def test_an_unlimited_player_covers_the_spot_and_is_not_added_in(self):
        self.file(self.abbott, "RF", 200)
        self.file(self.zimmer, "RF", unlimited=True)
        right = spot(self.described(), "RF")
        self.assertEqual(right.counted, 200)
        self.assertEqual(right.state, "covered")
        self.assertEqual(right.gap, 0)
        self.assertEqual(right.headline, "Covered")
        self.assertIn("Zack Zimmer takes the other 477 plate appearances.", right.note)
        by_player = {row.player: row.projected for row in right.rows}
        self.assertEqual(by_player[self.zimmer], 477)
        self.assertEqual(by_player[self.abbott], 200)
        self.assertNotIn("RF is", " ".join(self.described().gaps))

    def test_unlimited_does_not_hide_numbered_players_who_are_already_over(self):
        self.file(self.abbott, "RF", 700)
        self.file(self.zimmer, "RF", unlimited=True)
        right = spot(self.described(), "RF")
        self.assertEqual(right.counted, 700)
        self.assertEqual(right.headline, "23 PA over")
        by_player = {row.player: row.projected for row in right.rows}
        self.assertEqual(by_player[self.zimmer], 0)
        self.assertEqual(by_player[self.abbott], 700)
        self.assertIn("nothing left here", right.note)

    def test_a_stored_amount_on_an_unlimited_row_is_still_left_out_of_the_total(self):
        models.DepthAssignment.objects.create(
            chart=self.chart, player=self.abbott, bucket="RF", amount=50, unlimited=True
        )
        right = spot(self.described(), "RF")
        self.assertEqual(right.counted, 0)
        self.assertEqual(right.state, "covered")
        self.assertEqual(right.rows[0].projected, 677)

    def test_two_unlimited_players_split_the_remainder_and_complete_the_spot(self):
        self.file(self.zimmer, "SS", unlimited=True)
        self.file(self.abbott, "SS", unlimited=True)
        shortstop = spot(self.described(), "SS")
        self.assertEqual(shortstop.counted, 0)
        self.assertEqual(shortstop.state, "covered")
        by_player = {row.player: row.projected for row in shortstop.rows}
        self.assertEqual(by_player[self.abbott], 339)
        self.assertEqual(by_player[self.zimmer], 338)
        self.assertIn("Aaron Abbott and Zack Zimmer split the other 677 plate appearances.", shortstop.note)

    def test_unlimited_at_two_spots_shows_how_many_plate_appearances_that_asks_for(self):
        self.file(self.seager, "SS", unlimited=True)
        self.file(self.seager, "2B", unlimited=True)
        line = self.described().players[0]
        self.assertEqual(line.plate_appearances, 1354)
        self.assertIn("1354 plate appearances is more than one player gets in a season.", line.warning)

    def test_the_rotation_counts_numbered_starts_and_an_unlimited_arm_covers_the_rest(self):
        self.file(self.pitcher, depth.STARTS, 30)
        rotation = spot(self.described(), depth.STARTS)
        self.assertEqual(rotation.headline, "132 starts short")
        self.assertIn("The rotation is 132 starts short.", self.described().gaps)
        self.file(self.two_way, depth.STARTS, unlimited=True)
        rotation = spot(self.described(), depth.STARTS)
        self.assertEqual(rotation.counted, 30)
        self.assertEqual(rotation.state, "covered")
        covered = next(row for row in rotation.rows if row.unlimited)
        self.assertEqual(covered.projected, 132)

    def test_starts_past_a_season_stay_over_and_say_so_on_the_pitcher(self):
        self.file(self.pitcher, depth.STARTS, 200)
        chart = self.described()
        self.assertEqual(spot(chart, depth.STARTS).headline, "38 starts over")
        self.assertIn("The rotation is 38 starts over.", chart.gaps)
        self.assertIn("200 starts is more than the 162 in a season.", chart.players[0].warning)

    def test_bullpen_innings_use_what_the_starters_leave(self):
        self.file(self.pitcher, depth.BULLPEN, 100)
        pen = spot(self.described(), depth.BULLPEN)
        self.assertEqual(pen.headline, "495 IP short")
        self.assertIn("The bullpen is 495 innings short.", self.described().gaps)
        self.file(self.two_way, depth.BULLPEN, unlimited=True)
        pen = spot(self.described(), depth.BULLPEN)
        self.assertEqual(pen.counted, 100)
        self.assertEqual(pen.state, "covered")
        self.assertIn("Shohei Ohtani takes the other 495 innings.", pen.note)

    def test_a_bullpen_past_its_innings_is_over(self):
        self.file(self.pitcher, depth.BULLPEN, 600)
        chart = self.described()
        self.assertEqual(spot(chart, depth.BULLPEN).headline, "5 IP over")
        self.assertIn("The bullpen is 5 innings over.", chart.gaps)
        self.assertIn("600 bullpen innings is more than the pen throws.", chart.players[0].warning)

    def test_a_two_way_player_can_hit_and_pitch(self):
        self.file(self.two_way, "DH", 400)
        self.file(self.two_way, depth.STARTS, 20)
        self.file(self.two_way, depth.BULLPEN, 40)
        line = self.described().players[0]
        self.assertEqual((line.plate_appearances, line.starts, line.innings), (400, 20, 40))

    def test_a_pitcher_does_not_hit_and_a_hitter_does_not_pitch(self):
        with self.assertRaises(depth.DepthError) as hit:
            self.file(self.pitcher, "DH", 10)
        self.assertIn("does not hit", hit.exception.errors[0])
        with self.assertRaises(depth.DepthError) as pitch:
            self.file(self.seager, depth.STARTS, 10)
        self.assertIn("does not pitch", pitch.exception.errors[0])
        self.assertEqual(models.DepthAssignment.objects.count(), 0)

    def test_a_lefty_cannot_play_the_lefty_blocked_positions(self):
        with self.assertRaises(depth.DepthError) as blocked:
            self.file(self.greene, "SS", 100)
        self.assertIn("throws left and cannot play SS", blocked.exception.errors[0])
        self.file(self.greene, "RF", 100)
        self.file(self.greene, "1B", 100)
        chart = self.described()
        self.assertNotIn(self.greene, spot(chart, "SS").options)
        self.assertIn(self.greene, spot(chart, "LF").options)
        self.assertNotIn(self.greene, spot(chart, "RF").options)

    def test_a_player_from_another_team_or_a_duplicate_row_is_refused(self):
        with self.assertRaises(depth.DepthError) as refused:
            self.file(self.stranger, "RF", 10)
        self.assertIn("is not on ATL", refused.exception.errors[0])
        self.file(self.seager, "SS", 200)
        with self.assertRaises(depth.DepthError) as duplicate:
            self.file(self.seager, "SS", 50)
        self.assertIn("already filed at SS", duplicate.exception.errors[0])
        self.assertEqual(models.DepthAssignment.objects.get().amount, 200)

    def test_a_blank_or_zero_number_has_to_be_unlimited_instead(self):
        with self.assertRaises(depth.DepthError) as blank:
            self.file(self.seager, "SS", None)
        self.assertIn("Enter plate appearances", blank.exception.errors[0])
        with self.assertRaises(depth.DepthError) as zero:
            self.file(self.seager, "SS", 0)
        self.assertIn("Enter plate appearances", zero.exception.errors[0])
        with self.assertRaises(depth.DepthError) as bad:
            self.file(self.seager, "SS", "bad")
        self.assertIn("whole number", bad.exception.errors[0])
        with self.assertRaises(depth.DepthError) as missing:
            self.file(None, "SS", 10)
        self.assertIn("Pick a player.", missing.exception.errors)
        self.assertEqual(models.DepthAssignment.objects.count(), 0)

    def test_changing_and_removing_a_row_changes_the_gap(self):
        row = self.file(self.seager, "SS", 200)
        depth.change_player(row, 300, False)
        self.assertEqual(spot(self.described(), "SS").counted, 300)
        depth.change_player(row, None, True)
        shortstop = spot(self.described(), "SS")
        self.assertEqual(shortstop.counted, 0)
        self.assertEqual(shortstop.state, "covered")
        depth.remove_player(models.DepthAssignment.objects.get())
        self.assertEqual(spot(self.described(), "SS").state, "short")
        self.assertTrue(self.described().empty)

    def test_an_unknown_spot_is_refused(self):
        with self.assertRaises(depth.DepthError) as refused:
            self.file(self.seager, "P", 10)
        self.assertIn("P is not a depth-chart spot.", refused.exception.errors)
