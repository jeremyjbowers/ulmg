from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class BaseModel(models.Model):
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

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

    def __unicode__(self):
        return "%s %s" % (self.city, self.mascot)
 
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
        (VETERAN,"Veteran"),
        (A_LEVEL,"A-Level"),
        (B_LEVEL,"B-Level"),
    )
    PITCHER = "P"
    CATCHER = "C"
    INFIELD = "IF"
    OUTFIELD = "OF"
    UTILITY = "UT"
    HITTER = "DH"
    PLAYER_POSITION_CHOICES = (
        (PITCHER,"Pitcher"),
        (CATCHER,"Catcher"),
        (INFIELD,"Infield"),
        (OUTFIELD,"Outfield"),
        (UTILITY,"Utility"),
        (HITTER,"Hitter")
    )
    level = models.CharField(max_length=255, null=True, choices=PLAYER_LEVEL_CHOICES)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    first_name = models.CharField(max_length=255, null=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    roster = models.ForeignKey(Roster, on_delete=models.SET_NULL, blank=True, null=True)
    fangraphs_id = models.CharField(max_length=255, blank=True, null=True)
    fangraphs_url = models.CharField(max_length=255, blank=True, null=True)
    bbref_id = models.CharField(max_length=255, blank=True, null=True)
    bbref_url = models.CharField(max_length=255, blank=True, null=True)
    mlb_id = models.CharField(max_length=255, blank=True, null=True)
    mlb_url = models.CharField(max_length=255, blank=True, null=True)
    owned = models.BooleanField(default=False)
    roster_conflict = models.BooleanField(default=False)
    position = models.CharField(max_length=255, null=True, choices=PLAYER_POSITION_CHOICES)

    def __unicode__(self):
        if self.get_team():
            return "%s (%s)" % (self.name, self.get_team().abbreviation)
        return self.name

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
            return self.get_team().owner
        return None

    def set_name(self):
        self.name = "%s %s" % (self.first_name, self.last_name)

    def set_roster_conflict(self):
        """
        If the team and roster.team attributes are different, set a flag.
        """
        if self.roster and self.team:
            if self.team != self.roster.team:
                self.roster_conflict = True
        self.roster_conflict = False

    def set_owned(self):
        """
        If we can see an owner, set this player to owned.
        """
        self.owned = False
        if self.owner():
            self.owned = True    

    def save(self, *args, **kwargs):
        """
        Some light housekeeping.
        """
        self.set_owned()
        self.set_name()
        self.set_roster_conflict()

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
