# ABOUTME: Mint a long-lived OwnerAPIToken for MCP / agent access.
# ABOUTME: Prints the plaintext token once; only a hash is stored in the database.
from django.core.management.base import BaseCommand, CommandError

from ulmg import models


class Command(BaseCommand):
    help = (
        "Create an Owner API token for MCP access. "
        "Prints the token once — store it in the owner's Cursor mcp.json."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            help="Owner email (Owner.email or User.email)",
        )
        parser.add_argument(
            "--name",
            help="Owner name (Owner.name icontains)",
        )
        parser.add_argument(
            "--label",
            default="mcp",
            help="Label for this token (e.g. 'cursor laptop'). Default: mcp",
        )
        parser.add_argument(
            "--list-owners",
            action="store_true",
            help="List owners and exit",
        )

    def handle(self, *args, **options):
        if options["list_owners"]:
            for owner in models.Owner.objects.select_related("user").order_by("name"):
                team = owner.team()
                abbr = team.abbreviation if team else "—"
                self.stdout.write(
                    f"{owner.name or owner.user.username}  <{owner.email or owner.user.email}>  team={abbr}"
                )
            return

        email = options.get("email")
        name = options.get("name")
        if not email and not name:
            raise CommandError("Provide --email or --name (or --list-owners)")

        qs = models.Owner.objects.select_related("user")
        if email:
            qs = qs.filter(email__iexact=email) | models.Owner.objects.filter(
                user__email__iexact=email
            )
        if name:
            qs = qs.filter(name__icontains=name)

        owners = list(qs.distinct())
        if not owners:
            raise CommandError("No matching owner found")
        if len(owners) > 1:
            listing = ", ".join(
                f"{o.name}<{o.email}>" for o in owners
            )
            raise CommandError(f"Ambiguous owner match: {listing}")

        owner = owners[0]
        raw, token = models.OwnerAPIToken.create_token(
            owner, label=options["label"]
        )
        team = owner.team()
        self.stdout.write(self.style.SUCCESS("Created OwnerAPIToken"))
        self.stdout.write(f"Owner: {owner.name} <{owner.email}>")
        self.stdout.write(f"Team:  {team.abbreviation if team else 'none'}")
        self.stdout.write(f"Label: {token.label}")
        self.stdout.write("")
        self.stdout.write("Save this token now — it will not be shown again:")
        self.stdout.write(raw)
        self.stdout.write("")
        self.stdout.write(
            "Give the owner the site URL + this token.\n"
            "Preferred (HTTPS MCP — Claude / Codex / Copilot / Cursor):\n"
        )
        self.stdout.write(
            '{\n'
            '  "mcpServers": {\n'
            '    "ulmg": {\n'
            '      "url": "https://YOUR-ULMG-HOST/mcp",\n'
            '      "headers": {\n'
            f'        "Authorization": "Bearer {raw}"\n'
            '      }\n'
            '    }\n'
            '  }\n'
            '}'
        )
        self.stdout.write("")
        self.stdout.write("See documents/MCP.md for stdio fallback and curl checks.")
