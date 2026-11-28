# ABOUTME: Midseason bonus drafts are the AA draft.
# ABOUTME: Stored bonus picks become aa, and their slugs use AA.

import re

from django.db import migrations, models


_BONUS_SLUG = re.compile(r" BB(\d+)")


def bonus_picks_are_aa(apps, schema_editor):
    DraftPick = apps.get_model("ulmg", "DraftPick")
    for pick in DraftPick.objects.filter(draft_type="bonus", season="midseason"):
        slug = _BONUS_SLUG.sub(r" AA\1", pick.slug, count=1) if pick.slug else pick.slug
        DraftPick.objects.filter(pk=pick.pk).update(draft_type="aa", slug=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0116_draftpick_bonus_type"),
    ]

    operations = [
        migrations.RunPython(bonus_picks_are_aa, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="draftpick",
            name="draft_type",
            field=models.CharField(
                choices=[("aa", "aa"), ("open", "open"), ("balance", "balance")],
                max_length=255,
                null=True,
            ),
        ),
    ]
