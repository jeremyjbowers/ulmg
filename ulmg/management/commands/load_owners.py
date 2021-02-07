from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils.text import slugify

from ulmg import models


class Command(BaseCommand):
    def handle(self, *args, **options):

        owner_list = {
            "ANA": {
                "first_name": "Rus",
                "last_name": "Staniec",
                "username": "rus.staniec",
                "is_staff": False,
                "is_superuser": False,
            },
            "ATL": {
                "first_name": "Jeremy",
                "last_name": "Bowers",
                "username": "jeremy.bowers",
                "is_staff": True,
                "is_superuser": True,
            },
            "CAR": {
                "first_name": "Jon",
                "last_name": "Wile",
                "username": "jon.wile",
                "is_staff": True,
                "is_superuser": True,
            },
            "CHI": {
                "first_name": "Jeff",
                "last_name": "Bowen",
                "username": "jeff.bowen",
                "is_staff": False,
                "is_superuser": False,
            },
            "CIN": {
                "first_name": "John",
                "last_name": "Bowen",
                "username": "john.bowen",
                "is_staff": False,
                "is_superuser": False,
            },
            "CLE": {
                "first_name": "Rick",
                "last_name": "Senften",
                "username": "rick.senften",
                "is_staff": False,
                "is_superuser": False,
            },
            "DET": {
                "first_name": "Bob",
                "last_name": "Fernandez",
                "username": "bob.fernandez",
                "is_staff": False,
                "is_superuser": False,
            },
            "LNG": {
                "first_name": "Justin",
                "last_name": "Bank",
                "username": "justin.bank",
                "is_staff": False,
                "is_superuser": False,
            },
            "LOU": {
                "first_name": "David",
                "last_name": "Thorley",
                "username": "david.thorley",
                "is_staff": False,
                "is_superuser": False,
            },
            "NWW": {
                "first_name": "Joe",
                "last_name": "Fox",
                "username": "joe.fox",
                "is_staff": False,
                "is_superuser": False,
            },
            "PEN": {
                "first_name": "RB",
                "last_name": "Brenner",
                "username": "rb.brenner",
                "is_staff": False,
                "is_superuser": False,
            },
            "PHI": {
                "first_name": "ML",
                "last_name": "Schultze",
                "username": "ml.schultze",
                "is_staff": False,
                "is_superuser": False,
            },
            "PIT": {
                "first_name": "Jonas",
                "last_name": "Fortune",
                "username": "jonas.fortune",
                "is_staff": False,
                "is_superuser": False,
            },
            "STL": {
                "first_name": "Justin",
                "last_name": "Huyck",
                "username": "justin.huyck",
                "is_staff": False,
                "is_superuser": False,
            },
            "WCH": {
                "first_name": "Scott",
                "last_name": "Harrington",
                "username": "scott.harrington",
                "is_staff": False,
                "is_superuser": False,
            },
        }

        for t in models.Team.objects.all():
            owner = owner_list.get(t.abbreviation, None)

            if owner:
                firstword = f"0201{slugify(t.city)}!"

                print(firstword)

                u, u_created = User.objects.get_or_create(
                    first_name=owner["first_name"],
                    last_name=owner["last_name"],
                    username=owner["username"],
                    is_staff=owner["is_staff"],
                    is_superuser=owner["is_superuser"],
                )
                u.email = t.owner_email

                u.set_password(firstword)
                u.save()

                print(u)

                o, o_created = models.Owner.objects.get_or_create(
                    user=u, name=f"{u.first_name} {u.last_name}", email=u.email
                )

                print(o)

                t.owner_obj = o
                t.save()

                print(t)
