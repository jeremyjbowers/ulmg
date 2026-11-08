# ABOUTME: Proves the usage ledger locks a player's counter so two live games cannot both use the last of a cap.
# ABOUTME: Runs two real database transactions on separate connections in separate threads.

import threading
import time

from django.db import connection, transaction
from django.test import TransactionTestCase

from ulmg import models, usage
from tests.usage_fixtures import (
    ULMG_SEASON,
    create_hitter,
    create_pitcher,
    create_series,
    create_teams,
)


class ConcurrentGamesTestCase(TransactionTestCase):
    def setUp(self):
        home, road = create_teams()
        other_road = models.Team.objects.create(
            abbreviation="PIT", city="Pittsburgh", nickname="Pirates", division="Rickey"
        )
        self.first_game = create_series(home, road, length=3)[0]
        self.second_game = create_series(other_road, home, length=3, slot_number=2, first_day=4)[0]
        self.batter = create_hitter("Last Plate Appearance", ab=1, pa=1)
        self.first_pitcher = create_pitcher("First Pitcher", ip=80, g=60, gs=0, relief_minusip=80)
        self.second_pitcher = create_pitcher("Second Pitcher", ip=80, g=60, gs=0, relief_minusip=80)

    def race(self, create_counter_first):
        if create_counter_first:
            usage.counter_for(self.batter, ULMG_SEASON)

        first_recorded = threading.Event()
        results = {}

        def first_game():
            try:
                with transaction.atomic():
                    usage.record_plate_appearance(
                        self.first_game, self.batter, self.first_pitcher, at_bat=False, outs=0
                    )
                    first_recorded.set()
                    # Hold the lock while the second game tries to use the same plate appearance.
                    time.sleep(0.5)
                results["first"] = "recorded"
            except usage.UsageViolation as violation:
                results["first"] = violation
            finally:
                first_recorded.set()
                connection.close()

        def second_game():
            first_recorded.wait()
            try:
                with transaction.atomic():
                    usage.record_plate_appearance(
                        self.second_game, self.batter, self.second_pitcher, at_bat=False, outs=0
                    )
                results["second"] = "recorded"
            except usage.UsageViolation as violation:
                results["second"] = violation
            finally:
                connection.close()

        threads = [threading.Thread(target=first_game), threading.Thread(target=second_game)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(results["first"], "recorded")
        self.assertIsInstance(results["second"], usage.UsageViolation)
        self.assertIn("plate appearances", str(results["second"]))
        counter = models.UsageCounter.objects.get(player=self.batter, season=ULMG_SEASON)
        self.assertEqual(counter.plate_appearances, 1)
        self.assertEqual(models.UsageAppearance.objects.filter(player=self.batter).count(), 1)

    def test_two_games_race_for_the_last_plate_appearance(self):
        self.race(create_counter_first=True)

    def test_two_games_race_while_creating_the_counter(self):
        self.race(create_counter_first=False)
