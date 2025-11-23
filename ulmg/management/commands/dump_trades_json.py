from django.core.management.base import BaseCommand
from django.db.models import Prefetch
from ulmg import models

import json
import os


class Command(BaseCommand):
    help = "Dump all trades and receipts to a human-readable JSON file for LLM evaluation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default="data/trades_dump.json",
            help="Output path for JSON. Use '-' for stdout. Default: data/trades_dump.json",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="JSON indentation level (default: 2)",
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        indent = options["indent"]

        trades_qs = (
            models.Trade.objects
            .order_by("date", "id")
        )

        # Build JSON payload
        payload = []
        for trade in trades_qs:
            receipts = list(
                trade.reciepts()
                .select_related("team")
                .prefetch_related("players", "picks")
            )

            if len(receipts) < 2:
                # Skip malformed trades without both sides
                continue

            t1 = receipts[0]
            t2 = receipts[1]

            def format_player(player):
                return {
                    "position": getattr(player, "position", None),
                    "name": getattr(player, "name", None),
                }

            def format_pick(pick):
                return {
                    "original_team_abbr": pick.original_team.abbreviation if getattr(pick, "original_team", None) else None,
                    "year": pick.year,
                    "season": pick.season,
                    "draft_type": pick.draft_type,
                    "round": pick.draft_round,
                    "slug": pick.slug or None,
                }

            trade_obj = {
                "date": f"{trade.date.year}-{trade.date.month:02d}-{trade.date.day:02d}",
                "season": trade.season,
                "t1_abbr": t1.team.abbreviation if t1.team else None,
                "t2_abbr": t2.team.abbreviation if t2.team else None,
                # Each side "gets" what the opposite receipt "sends"
                "t1_gets": {
                    "players": [format_player(p) for p in t2.players.all()],
                    "picks": [format_pick(p) for p in t2.picks.all()],
                },
                "t2_gets": {
                    "players": [format_player(p) for p in t1.players.all()],
                    "picks": [format_pick(p) for p in t1.picks.all()],
                },
                # Keep a text version for readability
                "summary": trade.summary(),
            }

            payload.append(trade_obj)

        # Write output
        data_str = json.dumps(payload, indent=indent, ensure_ascii=False)

        if output_path == "-":
            self.stdout.write(data_str)
            return

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(data_str)

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(payload)} trades to {output_path}"))


