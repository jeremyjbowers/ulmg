# ABOUTME: Manually refresh the DB-cached ULMG constitution text.
# ABOUTME: Fetch from Google Docs pub HTML, or load from a local file (no auto-refresh).
from django.core.management.base import BaseCommand, CommandError

from ulmg import models
from ulmg.constitution import (
    CONSTITUTION_PUB_URL,
    extract_constitution_text,
    fetch_constitution_html,
    load_text_from_path,
)


class Command(BaseCommand):
    help = (
        "Refresh the cached ULMG constitution. "
        "Run after offseason rule changes; reads never hit Google live."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=CONSTITUTION_PUB_URL,
            help="Google Docs pub URL (default: league constitution pub link)",
        )
        parser.add_argument(
            "--from-file",
            dest="from_file",
            help="Load from a local .txt or .html file instead of fetching",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch/parse and print stats without writing the cache",
        )

    def handle(self, *args, **options):
        source_url = options["url"]
        from_file = options.get("from_file")

        if from_file:
            try:
                text = load_text_from_path(from_file)
            except OSError as exc:
                raise CommandError(f"Could not read {from_file}: {exc}") from exc
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            source_url = f"file:{from_file}"
            self.stdout.write(f"Loaded constitution text from {from_file}")
        else:
            self.stdout.write(f"Fetching {source_url}")
            try:
                html = fetch_constitution_html(url=source_url)
                text = extract_constitution_text(html)
            except Exception as exc:
                raise CommandError(f"Failed to fetch/parse constitution: {exc}") from exc

        title = "The ULMG Constitution"
        first_line = text.splitlines()[0].strip() if text else ""
        if first_line:
            title = first_line[:255]

        self.stdout.write(f"Parsed {len(text)} characters")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — cache not written"))
            self.stdout.write(text[:400] + ("…" if len(text) > 400 else ""))
            return

        doc = models.ConstitutionCache.store(
            text=text,
            source_url=CONSTITUTION_PUB_URL if from_file else source_url,
            title=title,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Constitution cache refreshed ({len(doc.text)} chars, "
                f"sha256={doc.content_sha256[:12]}…)"
            )
        )
