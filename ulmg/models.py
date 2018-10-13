import datetime

from dateutil.relativedelta import *
from django.contrib.auth.models import User
from django.db import models
from django.contrib.postgres.fields import JSONField
from django.db.models.signals import post_save
from django.dispatch import receiver
from nameparser import HumanName

class BaseModel(models.Model):
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    last_modified = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.__unicode__()


class Owner(BaseModel):
    """
    Tied to a Django User model. Can decorate with additional fields.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    coach_file_url = models.CharField(max_length=255, blank=True, null=True)

    def __unicode__(self):
        if self.team():
            return "%s %s (%s)" % (self.user.first_name, self.user.last_name, self.team().abbreviation)
        return "%s %s" % (self.user.first_name, self.user.last_name)

    def team(self):
        """
        Can't have more than one team but this is not enforced in the DB.
        """
        try:
            return Team.objects.get(owner=self)
        except Team.DoesNotExist:
            pass
        return None


class Team(BaseModel):
    """
    Canonical representation of a ULMG team.
    """
    owner = models.ForeignKey(Owner, on_delete=models.SET_NULL, blank=True, null=True)
    city = models.CharField(max_length=255)
    mascot = models.CharField(max_length=255)
    field = models.CharField(max_length=255, blank=True, null=True)
    abbreviation = models.CharField(max_length=3)

    class Meta:
        ordering = ["abbreviation"]

    def __unicode__(self):
        return self.abbreviation
 
    def players(self):
        """
        List of Player models associated with this team.
        """
        return Player.objects.filter(team=self)

    def rosters(self):
        """
        List of Roster models associated with this team.
        """
        return Roster.objects.filter(team=self)


class Roster(BaseModel):
    """
    Canonical representation of a team's rosters.
    There is a roster for each level.
    Rosters have minimum / maximum player levels not enforced at the DB level.
    Rosters reverse-fk players so we can treat them like inlines.
    Ideally, a team page would have roster inlines and then players nested to the rosters.
    """
    MLB = "MLB"
    AAA = "AAA"
    AA = "AA"
    TEAM_LEVEL_CHOICES = (
        (MLB,"MLB: Major League"),
        (AAA,"AAA: Triple-A"),
        (AA,"AA: Double-A"),
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    level = models.CharField(max_length=4, choices=TEAM_LEVEL_CHOICES)
    valid = models.BooleanField(default=False)

    def __unicode__(self):
        return "%s %s" % (self.team.abbreviation, self.level)


class Player(BaseModel):
    """
    Canonical representation of a baseball player.
    Players are associated with a team for the sake of convenience.
    A player's status should be determined via roster.
    Team and Roster.team should match but there are no DB constraints to force this to be true.
    """
    VETERAN = "V"
    A_LEVEL = "A"
    B_LEVEL = "B"
    PLAYER_LEVEL_CHOICES = (
        (VETERAN,"V"),
        (A_LEVEL,"A"),
        (B_LEVEL,"B"),
    )
    PITCHER = "P"
    CATCHER = "C"
    INFIELD = "IF"
    OUTFIELD = "OF"
    INFIELD_OUTFIELD = "IF/OF"
    PITCHER_OF = "OF/P"
    PITCHER_IF = "IF/P"
    UTILITY = "UT"
    HITTER = "DH"
    PLAYER_POSITION_CHOICES = (
        (PITCHER,"Pitcher"),
        (CATCHER,"Catcher"),
        (INFIELD,"Infield"),
        (OUTFIELD,"Outfield"),
        (INFIELD_OUTFIELD,"Infield/Outfield"),
        (PITCHER_OF,"Pitcher/Outfield"),
        (PITCHER_IF,"Pitcher/Infield"),
        (UTILITY,"Utility"),
        (HITTER,"Hitter")
    )
    # STUFF ABOUT THE PLAYER
    level = models.CharField(max_length=255, null=True, choices=PLAYER_LEVEL_CHOICES)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    first_name = models.CharField(max_length=255, null=True)
    position = models.CharField(max_length=255, null=True, choices=PLAYER_POSITION_CHOICES)
    birthdate = models.DateField(blank=True, null=True)
    stats = JSONField(blank=True, null=True)

    # IDENTIFIERS
    ba_id = models.CharField(max_length=255, blank=True, null=True)
    bbref_id = models.CharField(max_length=255, blank=True, null=True)
    fangraphs_id = models.CharField(max_length=255, blank=True, null=True)
    mlb_id = models.CharField(max_length=255, blank=True, null=True)

    # LINKS TO THE WEB
    ba_url = models.CharField(max_length=255, blank=True, null=True)
    bbref_url = models.CharField(max_length=255, blank=True, null=True)
    fangraphs_url = models.CharField(max_length=255, blank=True, null=True)
    mlb_url = models.CharField(max_length=255, blank=True, null=True)

    # ULMG-SPECIFIC
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    roster = models.ForeignKey(Roster, on_delete=models.SET_NULL, blank=True, null=True)

    # PROSPECT STUFF
    fg_prospect_fv = models.CharField(max_length=4, blank=True, null=True)
    fg_prospect_rank = models.IntegerField(blank=True, null=True)
    ba_prospect_rank = models.IntegerField(blank=True, null=True)
    mlb_prospect_rank = models.IntegerField(blank=True, null=True)

    # STATUS AND SUCH
    is_owned = models.BooleanField(default=False)
    is_prospect = models.BooleanField(default=False)
    is_carded = models.BooleanField(default=False)
    is_rostered = models.BooleanField(default=False)

    class Meta:
        ordering = ["level", "last_name", "first_name", "position"]

    def __unicode__(self):
        if self.get_team():
            return "%s (%s)" % (self.name, self.get_team().abbreviation)
        return self.name

    @property
    def usage(self):
        if self.stats:
            if self.position == "P":
                if self.stats.get('gs', None) == "0":
                    if float(self.stats['ip']) > 70:
                        return "%s IP" % round((float(self.stats['ip']) * 1.5), 1)
                    else:
                        return "%s IP" % round(float(self.stats['ip']), 1)
                elif self.stats.get('gs', None):
                    if int(self.stats['g']) > (int(self.stats['gs']) * 1.5):
                        if float(self.stats['ip']) > 70:
                            return "%s IP" % round((float(self.stats['ip']) * 1.5), 1)
                        else:
                            return "%s IP" % self.stats['ip']
                    else:
                        return "%s ST" % self.stats['gs']
                else:
                    return "%s IP" % self.stats['ip']
            else:
                if int(self.stats['pa']) > 550:
                    return "Unlimited"
                else:
                    return "%s PA" % self.stats['pa']
        return None


    @property
    def age(self):
        if self.birthdate:
            now = datetime.datetime.utcnow().date()
            return relativedelta(now, self.birthdate).years
        return None

    def latest_note(self):
        notes = PlayerNote.objects.filter(player=self)
        if len(notes) > 0:
            return notes[0].note
        return ""

    def get_team(self):
        """
        Defaults to the denormalized team attribute, if it exists.
        Will accept a roster if there's no denormalized team.
        """
        if self.team:
            return self.team
        if self.roster:
            return self.roster.team
        return None

    def owner(self):
        """
        Determine who owns this player.
        """
        if self.get_team():
            return self.get_team()
        return None

    def set_name(self):
        """
        Turn first / last into a name or 
        """
        if self.first_name and self.last_name:
            if not self.name:
                name_string = "%s" % self.first_name
                if self.middle_name:
                    name_string += " %s" % self.middle_name
                name_string += " %s" % self.last_name
                if self.suffix:
                    name_string += ", %s" % self.suffix
                self.name = name_string

        if self.name:
            if not self.first_name and not self.last_name:
                n = HumanName(self.name)
                self.first_name = n.first
                self.last_name = n.last
                self.middle_name = n.middle
                self.suffix = n.suffix

    def set_owned(self):
        """
        If we can see an owner, set this player to owned.
        """
        self.owned = False
        if self.owner():
            self.owned = True

    def set_ids(self):
        if self.fangraphs_url and not self.fangraphs_id:
            if "fangraphs" in self.fangraphs_url:
                self.fangraphs_id = self.fangraphs_url.split('?playerid=')[1].split('&')[0]

    def save(self, *args, **kwargs):
        """
        Some light housekeeping.
        """
        self.set_owned()
        self.set_name()
        self.set_ids()

        super().save(*args, **kwargs)


class PlayerNote(BaseModel):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["last_modified"]

    def __unicode__(self):
        return "%s note from %s." % (self.player, self.created)


class PlayerPositionYearRating(BaseModel):
    PITCHER = "P"
    CATCHER = "C"
    FIRST_BASE = "1B"
    SECOND_BASE = "2B"
    THIRD_BASE = "3B"
    SHORTSTOP = "SS"
    LEFT_FIELD = "LF"
    CENTER_FIELD = "CF"
    RIGHT_FIELD = "RF"
    DEFENSE_POSITION_CHOICES = (
        (PITCHER,"Pitcher"),
        (CATCHER,"Catcher"),
        (FIRST_BASE,"First base"),
        (SECOND_BASE,"Second base"),
        (THIRD_BASE,"Third base"),
        (SHORTSTOP,"Shortstop"),
        (LEFT_FIELD,"Left field"),
        (CENTER_FIELD,"Center field"),
        (RIGHT_FIELD,"Right field")
    )
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    year = models.IntegerField()
    rating = models.IntegerField()
    position = models.CharField(max_length=2, choices=DEFENSE_POSITION_CHOICES)

    def __unicode__(self):
        return "%s: %s (%s)" % (self.player.name, self.position, self.year)
