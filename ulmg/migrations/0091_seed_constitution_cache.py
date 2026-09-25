# ABOUTME: Seed the ConstitutionCache from the committed plain-text snapshot.
# ABOUTME: Safe to re-run; skips if a cache row already exists.
from django.db import migrations
from django.utils import timezone


def seed_constitution(apps, schema_editor):
    ConstitutionCache = apps.get_model("ulmg", "ConstitutionCache")
    if ConstitutionCache.objects.exists():
        return

    import hashlib
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "constitution.txt"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return

    title = text.splitlines()[0].strip()[:255] if text else "The ULMG Constitution"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    ConstitutionCache.objects.create(
        source_url=(
            "https://docs.google.com/document/d/e/"
            "2PACX-1vQmtw4gpA19fxNIFbSQZrF22z92eYbbhWPd_11PmH9fr2_vCUjTrMqZh_J2ySre0qrxKv_qtK-E9BTh"
            "/pub"
        ),
        title=title,
        text=text,
        content_sha256=digest,
        fetched_at=timezone.now(),
        active=True,
    )


def unseed_constitution(apps, schema_editor):
    ConstitutionCache = apps.get_model("ulmg", "ConstitutionCache")
    ConstitutionCache.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ulmg", "0090_constitution_cache"),
    ]

    operations = [
        migrations.RunPython(seed_constitution, unseed_constitution),
    ]
