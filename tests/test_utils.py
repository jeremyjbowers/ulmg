from django.db.models import Prefetch
from django.test import TestCase, override_settings

from ulmg import models, utils


class UtilsTestCase(TestCase):
    """Test utility functions"""
    
    def test_normalized_pos(self):
        for p in ["1B", "2B", "3B", "SS"]:
            self.assertEqual(utils.normalize_pos(p), "IF")
            self.assertEqual(utils.normalize_pos(p.lower()), "IF")

        for p in ["RF", "CF", "LF"]:
            self.assertEqual(utils.normalize_pos(p), "OF")
            self.assertEqual(utils.normalize_pos(p.lower()), "OF")

    def test_str_to_bool(self):
        for b in ["y", "yes", "t", "true"]:
            self.assertEqual(utils.str_to_bool(b), True)
            self.assertEqual(utils.str_to_bool(b.upper()), True)

        for b in ["n", "no", "f", "false"]:
            self.assertEqual(utils.str_to_bool(b), False)
            self.assertEqual(utils.str_to_bool(b.upper()), False)

        for b in ["nope", "yup", "yessir", 12345, True]:
            self.assertEqual(utils.str_to_bool(b), None)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    def test_get_current_season_offseason_is_prior_year_for_stats(self):
        self.assertEqual(utils.get_current_season(), 2025)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_get_current_season_midseason_matches_current_season(self):
        self.assertEqual(utils.get_current_season(), 2026)

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_get_stats_display_season_cap_defaults_to_current_when_unset(self):
        self.assertEqual(utils.get_stats_display_season_cap(), 2026)

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=2025,
    )
    def test_get_stats_display_season_cap_can_pin_prior_year_in_midseason(self):
        self.assertEqual(utils.get_stats_display_season_cap(), 2025)

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="offseason",
        STATS_DISPLAY_SEASON_CAP=2026,
    )
    def test_get_stats_display_season_cap_respects_offseason_natural_max(self):
        self.assertEqual(utils.get_current_season(), 2025)
        self.assertEqual(utils.get_stats_display_season_cap(), 2025)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_get_midseason_open_carded_season(self):
        self.assertEqual(utils.get_midseason_open_carded_season(), 2025)
        self.assertEqual(utils.get_midseason_open_carded_season(2026), 2025)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_get_draft_prep_year_season_midseason_active_drafts(self):
        self.assertEqual(utils.get_draft_prep_year_season("aa"), (2026, "midseason"))
        self.assertEqual(utils.get_draft_prep_year_season("open"), (2026, "midseason"))

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_get_draft_prep_year_season_midseason_open_explicit(self):
        self.assertEqual(
            utils.get_draft_prep_year_season("open", list_type="midseason"),
            (2026, "midseason"),
        )

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_get_draft_prep_year_season_midseason_offseason_open_is_next_year(self):
        self.assertEqual(
            utils.get_draft_prep_year_season("open", list_type="offseason"),
            (2027, "offseason"),
        )

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    def test_get_draft_prep_year_season_offseason_active_drafts(self):
        self.assertEqual(utils.get_draft_prep_year_season("aa"), (2026, "offseason"))
        self.assertEqual(utils.get_draft_prep_year_season("open"), (2026, "offseason"))

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
    def test_get_draft_prep_year_season_offseason_open_explicit(self):
        self.assertEqual(
            utils.get_draft_prep_year_season("open", list_type="offseason"),
            (2026, "offseason"),
        )


class PlayerBestStatSeasonCapTestCase(TestCase):
    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=2025,
    )
    def test_get_best_stat_season_respects_display_cap(self):
        p = models.Player.objects.create(name="Cap Test", position="IF", level="A")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2025,
            classification="1-mlb",
            hit_stats={"pa": 100},
        )
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            hit_stats={"pa": 200},
        )
        best = p.get_best_stat_season()
        self.assertIsNotNone(best)
        self.assertEqual(best.season, 2025)


class PlayerUlmgActiveMlbRosterTestCase(TestCase):
    def test_active_mlb_roster_excludes_aaa_and_reserve(self):
        p = models.Player.objects.create(name="Roster Test", position="IF", level="A")
        p.is_ulmg_mlb_roster = True
        p.is_ulmg_aaa_roster = False
        p.is_ulmg_reserve = False
        p.save()
        self.assertTrue(p.is_ulmg_active_mlb_roster)

        p.is_ulmg_aaa_roster = True
        p.save()
        self.assertFalse(p.is_ulmg_active_mlb_roster)

        p.is_ulmg_aaa_roster = False
        p.is_ulmg_reserve = True
        p.save()
        self.assertFalse(p.is_ulmg_active_mlb_roster)


class PlayerStatSeasonDisplayRowTestCase(TestCase):
    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_stat_season_roster_resource_status_uses_roster_status_when_no_role(self):
        p = models.Player.objects.create(name="Status Test", position="IF", level="A")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            roster_status="MINORS",
            is_career=False,
        )
        self.assertEqual(p.stat_season_roster_resource_status, "MINORS")

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_stat_season_roster_resource_status_prefers_role_over_roster_status(self):
        p = models.Player.objects.create(name="Role Test", position="IF", level="A")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            role="Bench",
            roster_status="MLB",
            is_career=False,
        )
        self.assertEqual(p.stat_season_roster_resource_status, "Bench")

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_stat_season_display_uses_prefetch_when_present(self):
        p = models.Player.objects.create(name="Prefetch", position="IF", level="A")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            roster_status="MLB",
            level="MLB",
            is_career=False,
        )
        p2 = models.Player.objects.prefetch_related(
            Prefetch(
                "playerstatseason_set",
                queryset=models.PlayerStatSeason.objects.filter(
                    season=2026, is_career=False
                ).order_by("classification"),
                to_attr="current_season_stats",
            ),
        ).get(pk=p.pk)
        self.assertEqual(p2.stat_season_roster_resource_status, "MLB")
        self.assertEqual(p2.stat_season_level, "MLB")

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_stat_season_roster_resource_status_falls_back_to_current_mlb_roster_status(self):
        p = models.Player.objects.create(name="Alt Field", position="IF", level="A")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            roster_status=None,
            current_mlb_roster_status="IL-7",
            is_career=False,
        )
        self.assertEqual(p.stat_season_roster_resource_status, "IL-7")

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_stat_season_level_falls_back_to_player_level(self):
        p = models.Player.objects.create(name="No PSS Level", position="IF", level="B")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            level=None,
            roster_status="MLB",
            is_career=False,
        )
        self.assertEqual(p.stat_season_level, "B")

    @override_settings(
        CURRENT_SEASON=2026,
        CURRENT_SEASON_TYPE="midseason",
        STATS_DISPLAY_SEASON_CAP=None,
    )
    def test_stat_season_level_from_stat_row(self):
        p = models.Player.objects.create(name="AAA Guy", position="IF", level="B")
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="2-milb",
            level="AAA",
            roster_status="MINORS",
            is_career=False,
        )
        self.assertEqual(p.stat_season_level, "AAA")
