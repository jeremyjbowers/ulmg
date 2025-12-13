import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ulmg import models
from ulmg import utils


class Command(BaseCommand):
    help = 'Load defensive ratings from CSV files to PlayerStatSeason records (MLB seasons only)'

    def is_batter(self, batter_dict):
        """Check if the row represents a batter."""
        possible_batter = ["B", "BAT"]
        if batter_dict.get("B/P", None):
            for b in possible_batter:
                if batter_dict["B/P"].strip().lower() == b.lower():
                    return True
        return False

    def parse_defense_ratings(self, player_row):
        """
        Parse defense ratings from CSV row and return as list of defense strings.
        Format: ["C-2-3", "1B-3-4", "2B-4-5", etc.]
        Where the format is: POSITION_CODE-RATING
        Position codes: C-2, 1B-3, 2B-4, 3B-5, SS-6, LF-7, CF-8, RF-9
        """
        defense = set()
        
        # Map position abbreviations to position-number format
        position_map = [
            ("C", "C-2"),
            ("1B", "1B-3"),
            ("2B", "2B-4"),
            ("3B", "3B-5"),
            ("SS", "SS-6"),
            ("LF", "LF-7"),
            ("CF", "CF-8"),
            ("RF", "RF-9"),
        ]
        
        for pos_abbrev, pos_format in position_map:
            rating = player_row.get(pos_abbrev, "").strip()
            if rating:
                # Remove parenthetical notes like "(B2)" from ratings
                if "(" in rating:
                    rating = rating.split("(")[0].strip()
                if rating:  # Make sure we still have a rating after cleaning
                    defense.add(f"{pos_format}-{rating}")
        
        return list(defense)

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Load defense for a specific year (2018-2025)',
        )
        parser.add_argument(
            '--all-years',
            action='store_true',
            help='Load defense for all years (2018-2025)',
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Write failures to a CSV file (optional)',
        )

    def handle(self, *args, **options):
        year = options.get('year')
        all_years = options.get('all_years', False)

        if not year and not all_years:
            raise CommandError('You must provide either --year or --all-years')

        if year and all_years:
            raise CommandError('You cannot provide both --year and --all-years')

        years_to_process = []
        if all_years:
            years_to_process = list(range(2018, 2026))  # 2018-2025
        else:
            if year < 2018 or year > 2025:
                raise CommandError('Year must be between 2018 and 2025')
            years_to_process = [year]

        # Track failures for reporting
        failures = []

        for year in years_to_process:
            csv_path = f"data/defense/{year}-som-range.csv"
            
            if not os.path.exists(csv_path):
                self.stdout.write(
                    self.style.WARNING(f"CSV file not found: {csv_path}, skipping year {year}")
                )
                continue

            self.stdout.write(f"Processing {year}...")
            
            with open(csv_path, "r") as readfile:
                players = [
                    dict(c) for c in csv.DictReader(readfile) if self.is_batter(c)
                ]

            year_successes = 0
            year_failures = []

            for player_row in players:
                # Extract name from CSV
                last = player_row["LAST"].split("-")[0].strip()
                first = player_row["FIRST"].strip()
                name_string = f"{first} {last}"

                # First, try to find player by strat_name (exact match)
                player = None
                strat_name_matches = models.Player.objects.filter(strat_name__iexact=name_string)
                
                if strat_name_matches.exists():
                    # Use strat_name match if found
                    player = strat_name_matches.first()
                else:
                    # Fall back to fuzzy matching
                    fuzzy_players = utils.fuzzy_find_player(name_string)
                    
                    if len(fuzzy_players) == 0:
                        year_failures.append({
                            'year': year,
                            'name': name_string,
                            'csv_row': player_row,
                            'reason': 'No player found'
                        })
                        continue

                    if len(fuzzy_players) > 1:
                        # Try to narrow down by team if available
                        team_abbrev = player_row.get("TM", "").strip()
                        if team_abbrev:
                            # Note: This would require a team lookup mapping
                            # For now, just use the first match
                            player = fuzzy_players[0]
                        else:
                            player = fuzzy_players[0]
                    else:
                        player = fuzzy_players[0]

                # Find the PlayerStatSeason for this year and MLB classification
                try:
                    stat_season = models.PlayerStatSeason.objects.get(
                        player=player,
                        season=year,
                        classification="1-mlb"
                    )
                except models.PlayerStatSeason.DoesNotExist:
                    year_failures.append({
                        'year': year,
                        'name': name_string,
                        'player_id': player.id,
                        'player_name': player.name,
                        'csv_row': player_row,
                        'reason': f'No MLB PlayerStatSeason found for {year}'
                    })
                    continue
                except models.PlayerStatSeason.MultipleObjectsReturned:
                    # If multiple, use the first one (shouldn't happen due to unique_together)
                    stat_season = models.PlayerStatSeason.objects.filter(
                        player=player,
                        season=year,
                        classification="1-mlb"
                    ).first()

                # Parse defense ratings from CSV row
                defense_ratings = self.parse_defense_ratings(player_row)
                
                # Update the PlayerStatSeason with defense ratings
                stat_season.defense = defense_ratings
                stat_season.save()
                
                year_successes += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {year}: {year_successes} players updated, {len(year_failures)} failures"
                )
            )
            
            failures.extend(year_failures)

        # Report failures
        output_file = options.get('output_file')
        
        if failures:
            self.stdout.write(self.style.WARNING("\n" + "="*80))
            self.stdout.write(self.style.WARNING(f"FAILURES ({len(failures)} total):"))
            self.stdout.write(self.style.WARNING("="*80))
            
            # Write to file if specified
            if output_file:
                with open(output_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['year', 'name', 'reason', 'player_id', 'player_name', 'lg', 'tm', 'first', 'last', 'use', 'b_p', 'c', '1b', '2b', '3b', 'ss', 'lf', 'cf', 'rf'])
                    writer.writeheader()
                    for failure in failures:
                        csv_row = failure.get('csv_row', {})
                        writer.writerow({
                            'year': failure.get('year', ''),
                            'name': failure.get('name', ''),
                            'reason': failure.get('reason', ''),
                            'player_id': failure.get('player_id', ''),
                            'player_name': failure.get('player_name', ''),
                            'lg': csv_row.get('LG', ''),
                            'tm': csv_row.get('TM', ''),
                            'first': csv_row.get('FIRST', ''),
                            'last': csv_row.get('LAST', ''),
                            'use': csv_row.get('USE', ''),
                            'b_p': csv_row.get('B/P', ''),
                            'c': csv_row.get('C', ''),
                            '1b': csv_row.get('1B', ''),
                            '2b': csv_row.get('2B', ''),
                            '3b': csv_row.get('3B', ''),
                            'ss': csv_row.get('SS', ''),
                            'lf': csv_row.get('LF', ''),
                            'cf': csv_row.get('CF', ''),
                            'rf': csv_row.get('RF', ''),
                        })
                self.stdout.write(self.style.SUCCESS(f"\nFailures written to: {output_file}"))
            
            # Also write to console
            for failure in failures:
                reason = failure.get('reason', 'Unknown')
                name = failure.get('name', 'Unknown')
                year = failure.get('year', 'Unknown')
                player_name = failure.get('player_name', 'N/A')
                
                self.stdout.write(
                    f"Year {year}: {name} -> {reason}"
                )
                if 'player_name' in failure:
                    self.stdout.write(f"  Matched player: {player_name} (ID: {failure.get('player_id', 'N/A')})")
                self.stdout.write(f"  CSV row: {failure.get('csv_row', {})}")
                self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("\nAll players matched successfully!"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted. Total: {len(failures)} failures across all years"
            )
        )
