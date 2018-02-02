from django.contrib import admin
import nested_admin

from .models import Owner, Team, Roster, Player, PlayerNote, PlayerPositionYearRating

class PlayerPositionYearRatingInline(nested_admin.NestedTabularInline):
    model = PlayerPositionYearRating
    fields = ["year", "rating", "position"]
    extra = 0

class PlayerInline(nested_admin.NestedTabularInline):
    model = Player
    fields = ["name"]
    readonly_fields = fields
    extra = 0

class PlayerNoteInline(nested_admin.NestedTabularInline):
    model = PlayerNote
    fields = ["note"]
    extra = 0

class RosterInline(nested_admin.NestedTabularInline):
    model = Roster
    inlines = [
        PlayerInline
    ]
    fields = ["level"]
    extra = 0

@admin.register(Owner)
class OwnerAdmin(nested_admin.NestedModelAdmin):
    model = Owner

@admin.register(Team)
class TeamAdmin(nested_admin.NestedModelAdmin):
    model = Team
    inlines = [
        RosterInline
    ]

@admin.register(Player)
class PlayerAdmin(nested_admin.NestedModelAdmin):
    model = Player
    inlines = [
        PlayerNoteInline,
        PlayerPositionYearRatingInline
    ]
    readonly_fields = ["name", "roster_conflict", "owned"]
    list_display = ["name", "owned", "team", "owner", "level", "latest_note"]
    list_filter = ["owned", "team", "level"]
    search_fields = ["name"]