import datetime
import os
import secrets

from dateutil.relativedelta import *
from django.contrib.auth.models import User
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from nameparser import HumanName

from ulmg import utils


class BaseModel(models.Model):
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    last_modified = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.__unicode__()


class Owner(BaseModel):
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    wins = models.IntegerField(blank=True, null=True)
    losses = models.IntegerField(blank=True, null=True)

    def __unicode__(self):
        return f"{self.name}, {self.email}"

    def team(self):
        return Team.objects.get(owner_obj=self)


class MagicLinkToken(BaseModel):
    """
    Stores magic link tokens for passwordless authentication.
    Tokens are valid for 60 days.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    def __unicode__(self):
        return f"Magic link for {self.user.email} (expires {self.expires_at})"
    
    @classmethod
    def create_for_user(cls, user):
        """Create a new magic link token for a user"""
        # Deactivate any existing unused tokens for this user
        cls.objects.filter(user=user, used=False).update(active=False)
        
        # Create new token
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + datetime.timedelta(days=60)
        
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )
    
    @classmethod
    def authenticate(cls, token):
        """Authenticate a user with a magic link token"""
        try:
            magic_link = cls.objects.get(
                token=token,
                active=True,
                used=False,
                expires_at__gt=timezone.now()
            )
            magic_link.used = True
            magic_link.save()
            return magic_link.user
        except cls.DoesNotExist:
            return None
    
    def is_valid(self):
        """Check if token is still valid"""
        return (
            self.active and 
            not self.used and 
            self.expires_at > timezone.now()
        )


class Team(BaseModel):
    """
    Canonical representation of a ULMG team.
    """

    city = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=3)
    nickname = models.CharField(max_length=255)
    division = models.CharField(max_length=255, null=True, blank=True)
    owner_obj = models.ForeignKey(
        Owner, on_delete=models.SET_NULL, null=True, blank=True
    )
    owner = models.CharField(max_length=255, null=True, blank=True)
    owner_email = models.CharField(max_length=255, null=True, blank=True)
    championships = ArrayField(models.CharField(max_length=4), blank=True, null=True)

    # LIVE STATS!
    ls_hits = models.IntegerField(blank=True, null=True)
    ls_2b = models.IntegerField(blank=True, null=True)
    ls_3b = models.IntegerField(blank=True, null=True)
    ls_hr = models.IntegerField(blank=True, null=True)
    ls_sb = models.IntegerField(blank=True, null=True)
    ls_runs = models.IntegerField(blank=True, null=True)
    ls_rbi = models.IntegerField(blank=True, null=True)
    ls_k = models.IntegerField(blank=True, null=True)
    ls_bb = models.IntegerField(blank=True, null=True)
    ls_plate_appearances = models.IntegerField(blank=True, null=True)
    ls_ab = models.IntegerField(blank=True, null=True)
    ls_avg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_obp = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_slg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_iso = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_k_pct = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True
    )
    ls_bb_pct = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True
    )

    ls_g = models.IntegerField(blank=True, null=True)
    ls_gs = models.IntegerField(blank=True, null=True)
    ls_ip = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    ls_pk = models.IntegerField(blank=True, null=True)
    ls_pbb = models.IntegerField(blank=True, null=True)
    ls_ha = models.IntegerField(blank=True, null=True)
    ls_hra = models.IntegerField(blank=True, null=True)
    ls_er = models.IntegerField(blank=True, null=True)
    ls_k_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_hits_9 = models.DecimalField(
        max_digits=4, decimal_places=2, blank=True, null=True
    )
    ls_bb_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_hr_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_era = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    ls_whip = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ["abbreviation"]

    def __unicode__(self):
        return self.abbreviation

    def to_api_obj(self):
        payload = {
            "city": self.city,
            "abbreviation": self.abbreviation,
            "nickname": self.nickname,
            "division": self.division,
            "owner": self.owner,
            "owner_email": self.owner_email,
        }
        return payload

    def players(self):
        """
        List of Player models associated with this team.
        """
        return Player.objects.filter(team=self)


class Venue(BaseModel):
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    mlb_team = models.CharField(max_length=255)

    first_year = models.IntegerField(null=True, blank=True)
    stadium_blurb = models.TextField(null=True, blank=True)
    clem_venue_img = models.CharField(max_length=255, null=True, blank=True)
    clem_venue_slug = models.CharField(max_length=255, null=True, blank=True)
    clem_venue_url = models.CharField(max_length=255, null=True, blank=True)

    mlb_venue_id = models.CharField(max_length=255)
    mlb_venue_url = models.CharField(max_length=255)
    park_factor = models.IntegerField(null=True, blank=True)
    pf_wobacon = models.IntegerField(null=True, blank=True)
    pf_bacon = models.IntegerField(null=True, blank=True)
    pf_runs = models.IntegerField(null=True, blank=True)
    pf_obp = models.IntegerField(null=True, blank=True)
    pf_h = models.IntegerField(null=True, blank=True)
    pf_1b = models.IntegerField(null=True, blank=True)
    pf_2b = models.IntegerField(null=True, blank=True)
    pf_3b = models.IntegerField(null=True, blank=True)
    pf_hr = models.IntegerField(null=True, blank=True)
    pf_bb = models.IntegerField(null=True, blank=True)
    pf_so = models.IntegerField(null=True, blank=True)
    pf_years = models.CharField(max_length=255, null=True, blank=True)
    pf_pa = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        if self.team:
            return f"{self.name} ({self.team.abbreviation})"
        return self.name

    def similar_parks(self):
        upper_bound = self.park_factor + 2
        lower_bound = self.park_factor - 2

        return Venue.objects.filter(
            park_factor__lte=upper_bound, park_factor__gte=lower_bound
        ).order_by("park_factor")

    def park_type(self):

        if self.park_factor < 95:
            return "extreme pitcher's"

        if self.park_factor > 105:
            return "extreme hitter's"

        if self.park_factor < 97:
            return "slight pitcher's"

        if self.park_factor > 103:
            return "slight hitter's"

        return "neutral"

    class Meta:
        ordering = ["name"]


class Player(BaseModel):
    """
    Canonical representation of a baseball player.
    """

    VETERAN = "V"
    A_LEVEL = "A"
    B_LEVEL = "B"
    PLAYER_LEVEL_CHOICES = (
        (VETERAN, "V"),
        (A_LEVEL, "A"),
        (B_LEVEL, "B"),
    )

    PITCHER = "P"
    CATCHER = "C"
    INFIELD = "IF"
    OUTFIELD = "OF"
    INFIELD_OUTFIELD = "IF-OF"
    PITCHER_OF = "OF-P"
    PITCHER_IF = "IF-P"
    PLAYER_POSITION_CHOICES = (
        (PITCHER, "Pitcher"),
        (CATCHER, "Catcher"),
        (INFIELD, "Infield"),
        (OUTFIELD, "Outfield"),
        (INFIELD_OUTFIELD, "Infield/Outfield"),
        (PITCHER_OF, "Pitcher/Outfield"),
        (PITCHER_IF, "Pitcher/Infield"),
    )

    JAPAN = "JPN"
    KOREA = "KOR"
    J2 = "J2"
    TAIWAN = "TAI"
    MEXICO = "MEX"
    NCAA = "NCAA"
    USHS = "US HS"
    OTHER = "OTH"
    OTHER_PRO_LEAGUES = (
        (NCAA, "NCAA"),
        (USHS, "US HS"),
        (JAPAN, "JPN"),
        (KOREA, "KOR"),
        (J2, "J2"),
        (TAIWAN, "TAI"),
        (MEXICO, "MEX"),
        (OTHER, "OTH"),
    )

    # STUFF ABOUT THE PLAYER
    level = models.CharField(max_length=255, null=True, choices=PLAYER_LEVEL_CHOICES)
    level_order = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    first_name = models.CharField(max_length=255, null=True)
    position = models.CharField(
        max_length=255, null=True, choices=PLAYER_POSITION_CHOICES
    )
    birthdate = models.DateField(blank=True, null=True)
    birthdate_qa = models.BooleanField(default=False)
    raw_age = models.IntegerField(default=None, blank=True, null=True)

    # PROSPECT STUFF
    is_prospect = models.BooleanField(default=False)
    prospect_rating_avg = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True
    )
    fg_fv = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    fg_eta = models.CharField(max_length=255, blank=True, null=True)
    fg_org_rank = models.IntegerField(blank=True, null=True)
    class_year = models.IntegerField(blank=True, null=True)

    # IDENTIFIERS
    ba_id = models.CharField(max_length=255, blank=True, null=True)
    mlbam_id = models.CharField(max_length=255, blank=True, null=True)
    mlb_dotcom = models.CharField(max_length=255, blank=True, null=True)
    bp_id = models.CharField(max_length=255, blank=True, null=True)
    bref_id = models.CharField(max_length=255, blank=True, null=True)
    fg_id = models.CharField(max_length=255, blank=True, null=True)
    fantrax_id = models.CharField(max_length=255, blank=True, null=True)
    baseballcube_id = models.CharField(max_length=255, blank=True, null=True)
    perfectgame_id = models.CharField(max_length=255, blank=True, null=True)

    mlbam_checked = models.BooleanField(default=False)

    # LINKS TO THE WEB
    ba_url = models.CharField(max_length=255, blank=True, null=True)
    bref_url = models.CharField(max_length=255, blank=True, null=True)
    bref_img = models.CharField(max_length=255, blank=True, null=True)
    fg_url = models.CharField(max_length=255, blank=True, null=True)
    mlb_dotcom_url = models.CharField(max_length=255, blank=True, null=True)
    fantrax_url = models.CharField(max_length=255, blank=True, null=True)

    # ULMG-SPECIFIC
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # STATUS AND SUCH
    is_owned = models.BooleanField(default=False)  # ULMG ownership stays on Player
    
    # SEASON-SPECIFIC FIELDS - MOVED TO PlayerStatSeason
    # is_carded = models.BooleanField(default=False)
    # is_amateur = models.BooleanField(default=False)
    league = models.CharField(
        max_length=255, blank=True, null=True, choices=OTHER_PRO_LEAGUES
    )

    # ULMG ROSTERS - MOVED TO PlayerStatSeason
    # is_mlb_roster = models.BooleanField(default=False)
    # is_aaa_roster = models.BooleanField(default=False)
    # is_35man_roster = models.BooleanField(default=False)

    # ULMG STATUS
    is_reserve = models.BooleanField(default=False)
    is_1h_p = models.BooleanField(default=False)
    is_1h_c = models.BooleanField(default=False)
    is_1h_pos = models.BooleanField(default=False)
    is_2h_p = models.BooleanField(default=False)
    is_2h_c = models.BooleanField(default=False)
    is_2h_pos = models.BooleanField(default=False)
    is_2h_draft = models.BooleanField(default=False)
    is_protected = models.BooleanField(default=False)
    cannot_be_protected = models.BooleanField(default=False)
    covid_protected = models.BooleanField(default=False)
    is_trade_block = models.BooleanField(default=False)

    # CAREER STATS (for level)
    cs_pa = models.IntegerField(blank=True, null=True)
    cs_gp = models.IntegerField(blank=True, null=True)
    cs_st = models.IntegerField(blank=True, null=True)
    cs_ip = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    # DEFENSE
    defense = ArrayField(models.CharField(max_length=10), blank=True, null=True)

    # STATS - DEPRECATED: Use PlayerStatSeason model instead
    # stats = models.JSONField(null=True, blank=True)  # Removed - use PlayerStatSeason

    # STRAT RATINGS
    # here's the schema for strat ratings
    # year (current), type (hit/pitch)
    # pitching and hitting stats are in separate dictionaries.
    #
    # Not used yet.
    #
    strat_ratings = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name", "level", "position"]

    def __unicode__(self):
        if self.get_team():
            return "%s (%s)" % (self.name, self.get_team().abbreviation)
        return self.name

    def is_mlb(self):
        # Check if player has any MLB-level stats in PlayerStatSeason
        return PlayerStatSeason.objects.filter(
            player=self, 
            classification='1-majors'
        ).exists()
    
    def is_carded(self):
        # Check if player has any carded seasons in PlayerStatSeason
        return PlayerStatSeason.objects.filter(
            player=self, 
            carded=True
        ).exists()
    
    def current_season_status(self):
        """Get the most recent season's status fields."""
        from datetime import datetime
        current_season = datetime.now().year
        
        return PlayerStatSeason.objects.filter(
            player=self,
            season=current_season
        ).order_by('-classification').first()
    
    def is_injured(self):
        """Check if player is currently injured."""
        current_status = self.current_season_status()
        return current_status.is_injured if current_status else False
    
    def current_mlb_org(self):
        """Get player's current MLB organization."""
        current_status = self.current_season_status()
        return current_status.mlb_org if current_status else None

    def is_35man_roster(self):
        """Check if player is on 35-man roster for current season."""
        current_status = self.current_season_status()
        return current_status.is_35man_roster if current_status else False

    def is_mlb_roster(self):
        """Check if player is on MLB roster for current season."""
        current_status = self.current_season_status()
        return current_status.is_mlb_roster if current_status else False

    def is_aaa_roster(self):
        """Check if player is on AAA roster for current season."""
        current_status = self.current_season_status()
        return current_status.is_aaa_roster if current_status else False

    def roster_status(self):
        """Get the current season's roster status."""
        current_status = self.current_season_status()
        return current_status.roster_status if current_status else None

    def role_type(self):
        """Get the current season's role type."""
        current_status = self.current_season_status()
        return current_status.role_type if current_status else None

    def role(self):
        """Get the current season's role."""
        current_status = self.current_season_status()
        return current_status.role if current_status else None

    def mlb_org(self):
        """Get the current season's MLB organization (for template compatibility)."""
        return self.current_mlb_org()

    def player_level_class(self):
        """Get the current season's player level class for CSS styling."""
        current_status = self.current_season_status()
        if current_status:
            return current_status.player_level_class()
        return 'amateur'  # Default for players with no current season data

    def latest_hit_stats(self):
        stats = PlayerStatSeason.objects.filter(player=self).first()
        if stats:
            return stats.hit_stats
        return None

    def latest_pit_stats(self):
        stats = PlayerStatSeason.objects.filter(player=self).first()
        if stats:
            return stats.pitch_stats
        return None

    @property
    def mlb_image_url(self):
        if self.mlbam_id:
            return f"https://img.mlbstatic.com/mlb-photos/image/upload/w_213,d_people:generic:headshot:silo:current.png,q_auto:best,f_auto/v1/people/{self.mlbam_id}/headshot/silo/current"
        return None

    @property
    def mlb_url(self):
        if self.mlbam_id:
            return f"https://www.mlb.com/player/{self.mlbam_id}/"
        return None

    @property
    def mlb_api_url(self):
        if self.mlbam_id:
            return f"https://statsapi.mlb.com/api/v1/people/{self.mlbam_id }"
        return None

    @property
    def latest_rating(self):
        ratings = ProspectRating.objects.filter(player=self).order_by("-year")
        if len(ratings) > 0:
            return ratings[0]
        return None

    def set_fg_url(self):
        if self.fg_id:
            self.fg_url = (
                "https://www.fangraphs.com/statss.aspx?playerid=%s" % self.fg_id
            )

    def to_api_obj(self):
        # Get current season status for season-specific fields
        current_status = self.current_season_status()
        
        payload = {
            "level": self.level,
            "name": self.name,
            "position": self.position,
            "strat_defense": self.defense_display(),
            "age": self.age,
            "bref_img": self.bref_img,
            "ids": {
                "mlbam_id": self.mlbam_id,
                "fg_id": self.fg_id,
                "fg_url": self.fg_url,
                "mlb_dotcom_url": self.mlb_dotcom_url,
            },
            "notes": self.notes,
            "is_owned": self.is_owned,
            "is_carded": self.is_carded(),
            "is_amateur": current_status.is_amateur if current_status else False,
            "is_mlb_roster": current_status.is_mlb_roster if current_status else False,
            "is_aaa_roster": current_status.is_aaa_roster if current_status else False,
            "is_35man_roster": current_status.is_35man_roster if current_status else False,
            "is_reserve": self.is_reserve,
            "is_1h_p": self.is_1h_p,
            "is_1h_c": self.is_1h_c,
            "is_1h_pos": self.is_1h_pos,
            "is_2h_p": self.is_2h_p,
            "is_2h_c": self.is_2h_c,
            "is_2h_pos": self.is_2h_pos,
            "is_2h_draft": self.is_2h_draft,
            "is_protected": self.is_protected,
            "cannot_be_protected": self.cannot_be_protected,
            "team": None,
        }

        if self.team:
            payload["team"] = self.team.to_api_obj()

        return payload

    def to_dict(self):
        return self.to_api_obj()

    def defense_display(self):
        if self.defense:
            sortdef = [
                {
                    "display": f"{d.split('-')[0]}{d.split('-')[2]}",
                    "sort": f"{d.split('-')[1]}{d.split('-')[2]}",
                }
                for d in self.defense
            ]
            return ", ".join(
                [x["display"] for x in sorted(sortdef, key=lambda x: x["sort"])]
            )
        return None

    @property
    def age(self):
        if self.birthdate:
            now = timezone.now().date()
            return relativedelta(now, self.birthdate).years
        elif self.raw_age:
            return self.raw_age
        return None

    def get_team(self):
        """
        Defaults to the denormalized team attribute, if it exists.
        """
        if self.team:
            return self.team
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
            name_string = "%s" % self.first_name
            name_string += " %s" % self.last_name
            self.name = name_string

        if self.name:
            if not self.first_name and not self.last_name:
                n = HumanName(self.name)
                self.first_name = n.first
                if n.middle:
                    self.first_name = n.first + " " + n.middle
                self.last_name = n.last
                if n.suffix:
                    self.last_name = n.last + " " + n.suffix

    def set_ids(self):
        if self.fg_url and not self.fg_id:
            if self.fg_url:
                if "?playerid=" in self.fg_url:
                    self.fg_id = self.fg_url.split("?playerid=")[1].split("&")[0]

    def set_level_order(self):
        if self.level:
            if self.level == "V":
                self.level_order = 9
            if self.level == "A":
                self.level_order = 5
            if self.level == "B":
                self.level_order = 0

    def set_owned(self):
        if self.team == None:
            self.is_owned = False
        else:
            self.is_owned = True

    def set_protected(self):
        # Set protections
        if (
            self.is_reserve
            or self.is_1h_p
            or self.is_1h_c
            or self.is_1h_pos
            or self.is_2h_p
            or self.is_2h_c
            or self.is_2h_pos
            or self.is_mlb_roster
            or self.is_protected
        ):
            self.is_protected = True
        else:
            self.is_protected = False

        if self.cannot_be_protected:
            self.is_protected = False

    def get_best_stat_season(self):
        """
        Get the best PlayerStatSeason for this player, sorted by newest season 
        and highest classification (1-majors is highest, 5-ncaa is lowest).
        Returns None if no stat seasons exist.
        """
        return PlayerStatSeason.objects.filter(
            player=self
        ).order_by('-season', 'classification').first()

    def team_display(self):
        if self.team:
            return self.team.abbreviation
        return None

    def set_position(self):
        self.position = utils.normalize_pos(self.position)

    def save(self, *args, **kwargs):
        """
        Some light housekeeping.
        """
        self.set_name()
        self.set_position()
        self.set_ids()
        self.set_fg_url()
        self.set_level_order()
        self.set_owned()
        self.set_protected()

        super().save(*args, **kwargs)

class PlayerStatSeason(BaseModel):
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, blank=True, null=True)
    season = models.IntegerField(blank=True, null=True)
    CLASSIFICATION_CHOICES = (
        ("1-majors", "1-majors"),
        ("2-minors", "2-minors"),
        ("3-npb", "3-npb"),
        ("4-kbo", "4-kbo"),
        ("5-ncaa", "5-ncaa"),
    )
    classification = models.CharField(max_length=255, choices=CLASSIFICATION_CHOICES, null=True)
    level = models.CharField(max_length=255, blank=True, null=True)
    hit_stats = models.JSONField(null=True, blank=True)
    pitch_stats = models.JSONField(null=True, blank=True)
    minors = models.BooleanField(default=False)
    carded = models.BooleanField(default=False)
    owned = models.BooleanField(default=False)
    
    # SEASON-SPECIFIC ROSTER STATUS (moved from Player model)
    is_starter = models.BooleanField(default=False)
    is_bench = models.BooleanField(default=False)
    is_player_pool = models.BooleanField(default=False)
    is_injured = models.BooleanField(default=False)
    injury_description = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    role_type = models.CharField(max_length=255, null=True, blank=True)
    roster_status = models.CharField(max_length=255, null=True, blank=True)
    mlb_org = models.CharField(max_length=255, null=True, blank=True)
    is_mlb40man = models.BooleanField(default=False)
    is_bullpen = models.BooleanField(default=False)
    is_mlb = models.BooleanField(default=False)
    is_amateur = models.BooleanField(default=False)
    is_mlb_roster = models.BooleanField(default=False)
    is_aaa_roster = models.BooleanField(default=False)
    is_35man_roster = models.BooleanField(default=False)

    def __unicode__(self):
        return f"{self.player} @ {self.season} @ {self.classification}"

    def player_level_class(self):
        """
        Determine the player's level classification for CSS styling:
        - 'mlb': Has MLB stats (classification="1-majors" with actual stats)
        - 'milb': Has MiLB stats or MLB organization but no MLB stats
        - 'amateur': No MLB organization and no professional stats
        """
        # Check for MLB stats (classification="1-majors" with actual stats)
        if (self.classification == "1-majors" and 
            ((self.hit_stats and self.hit_stats.get('plate_appearances', 0) > 0) or
             (self.pitch_stats and self.pitch_stats.get('ip', 0) > 0))):
            return 'mlb'
        
        # Check for minor league stats (classification="2-minors" with stats) or MLB organization
        if (self.classification == "2-minors" or 
            self.mlb_org or 
            ((self.hit_stats and self.hit_stats.get('plate_appearances', 0) > 0) or
             (self.pitch_stats and self.pitch_stats.get('ip', 0) > 0))):
            return 'milb'
        
        # Default to amateur if no pro stats or organization
        return 'amateur'

    class Meta:
        ordering = ['season', 'classification']
        indexes = [
            # Single field indexes for common filters
            models.Index(fields=['season']),  # Most common filter
            models.Index(fields=['minors']),  # Majors vs minors filtering
            models.Index(fields=['owned']),   # Ownership filtering
            models.Index(fields=['carded']),  # Carded status filtering
            
            # Composite indexes for common combinations
            models.Index(fields=['season', 'minors']),  # Season + league level
            models.Index(fields=['season', 'owned']),   # Season + ownership
            models.Index(fields=['season', 'minors', 'owned']),  # Three-way common combo
            models.Index(fields=['player', 'season']),  # Player's seasons lookup
            
            # Search optimization indexes
            models.Index(fields=['minors', 'owned', 'carded']),  # Filter combinations
            models.Index(fields=['season', 'classification']),   # Already in ordering, but explicit
            models.Index(fields=['classification']),  # Individual classification filtering
            models.Index(fields=['level']),  # Individual level filtering (AAA, AA, etc.)
            
            # Index page optimization - unowned MLB players with stats
            models.Index(fields=['season', 'classification', 'owned']),  # Index page base filter
        ]

class DraftPick(BaseModel):
    AA_TYPE = "aa"
    OPEN_TYPE = "open"
    BALANCE_TYPE = "balance"
    DRAFT_TYPE_CHOICES = (
        (AA_TYPE, "aa"),
        (OPEN_TYPE, "open"),
        (BALANCE_TYPE, "balance"),
    )
    draft_type = models.CharField(max_length=255, choices=DRAFT_TYPE_CHOICES, null=True)
    draft_round = models.IntegerField(null=True)
    year = models.CharField(max_length=4)
    pick_number = models.IntegerField(null=True, blank=True)
    overall_pick_number = models.IntegerField(null=True, blank=True)
    OFFSEASON = "offseason"
    MIDSEASON = "midseason"
    SEASON_CHOICES = (
        (OFFSEASON, "offseason"),
        (MIDSEASON, "midseason"),
    )
    season = models.CharField(max_length=255, choices=SEASON_CHOICES)
    slug = models.CharField(max_length=255, null=True, blank=True)
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, blank=True, null=True, related_name="team"
    )
    team_name = models.CharField(max_length=255, blank=True, null=True)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, blank=True, null=True)
    player_name = models.CharField(max_length=255, blank=True, null=True)
    pick_notes = models.TextField(blank=True, null=True)
    original_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="original_team",
    )
    skipped = models.BooleanField(default=False)

    class Meta:
        ordering = ["-year", "-season", "draft_type", "draft_round", "pick_number"]

    def __unicode__(self):
        return "%s %s %s (%s)" % (self.year, self.season, self.slug, self.team)

    def to_api_obj(self):
        payload = {}
        payload['draft_type'] = self.draft_type
        payload['draft_round'] = self.draft_round
        payload['year'] = self.year
        payload['pick_number'] = self.pick_number
        payload['overall_pick_number'] = self.overall_pick_number
        payload['season'] = self.season
        payload['slug'] = self.slug
        payload['team_name'] = self.team_name
        payload['player_name'] = self.player_name
        payload['skipped'] = self.skipped
        payload['original_team'] = None
        payload['team'] = None
        payload['player'] = None

        if self.original_team:
            payload['original_team'] = self.original_team.to_api_obj()

        if self.team:
            payload['team'] = self.team.to_api_obj()

        if self.player:
            payload['player'] = self.player.to_api_obj()

        return payload

    def slugify(self):
        if self.draft_type == "aa":
            dt = "AA"

        if self.draft_type == "open":
            dt = "OP"

        if self.draft_type == "balance":
            dt = "CB"

        self.slug = f"{self.original_team} {dt}{self.draft_round}"
        if self.player:
            self.slug = (
                f"{self.original_team} {dt}{self.draft_round} ({self.player.name})"
            )

    def set_overall_pick_number(self):
        if self.pick_number:
            rnd = self.draft_round - 1
            self.overall_pick_number = self.pick_number + (rnd * 16)

    def set_original_team(self):
        if not self.original_team and self.team:
            self.original_team = self.team

    def set_player_name(self):
        if self.player:
            self.player_name = self.player.name

    def save(self, *args, **kwargs):
        ## Need to comment this part out if saving archived draft picks
        ## that have a player name only but not a player object
        ## so that players are not swapped to a different team.
        if self.player and self.team:
            if not self.player.team:
                self.player.team = self.team
                self.player.save()

            if self.player.team and self.player.team != self.team:
                self.player.team = self.team
                self.player.save()

        self.set_original_team()
        self.set_overall_pick_number()
        self.slugify()
        self.set_player_name()

        super().save(*args, **kwargs)


class Trade(BaseModel):
    """
    On the frontend, there will just be two slots for teams
    and then slots for players and picks that can be selected from.
    On save, the view will create the Trade object and then two
    related TradeReceipt objects containing the players and picks.
    """

    date = models.DateField()
    season = models.IntegerField(blank=True, null=True)
    trade_summary = models.TextField(blank=True, null=True)
    trade_cache = models.JSONField(blank=True, null=True)
    teams = models.ManyToManyField(Team, blank=True)

    def __unicode__(self):
        return self.summary()

    def set_season(self):
        self.season = utils.get_ulmg_season(self.date)

    def set_teams(self):
        if self.reciepts():
            for r in self.reciepts():
                self.teams.add(r.team)

    def set_trade_summary(self):
        if self.reciepts():
            cache = {}

            t1 = self.reciepts()[0]
            t2 = self.reciepts()[1]

            cache[t1.team.abbreviation.lower()] = t1
            cache[t2.team.abbreviation.lower()] = t2

            self.trade_cache = self.summary_dict()

    def save(self, *args, **kwargs):
        self.set_season()
        super().save(*args, **kwargs)

    def reciepts(self):
        return TradeReceipt.objects.filter(trade=self)

    def summary_html(self):
        t1 = self.reciepts()[0]
        t2 = self.reciepts()[1]

        return "<td>%s</td><td style='text-align: left;'>%s</td><td>%s</td><td style='text-align: left;'>%s</td><td>%s</td>" % (
            self.date,
            "<a href='/teams/%s/'>%s</a>"
            % (t1.team.abbreviation.lower(), t1.team.abbreviation),
            ", ".join(
                [
                    "%s <a href='/players/%s/'>%s</a>" % (p.position, p.id, p.name)
                    for p in t2.players.all()
                ]
                + [f"{p.year} {p.season } {p.slug}" for p in t2.picks.all()]
            ),
            "<a href='/teams/%s/'>%s</a>"
            % (t2.team.abbreviation.lower(), t2.team.abbreviation),
            ", ".join(
                [
                    "%s <a href='/players/%s/'>%s</a>" % (p.position, p.id, p.name)
                    for p in t1.players.all()
                ]
                + [f"{p.year} {p.season } {p.slug}" for p in t1.picks.all()]
            ),
        )

    def summary_dict(self):
        t1 = self.reciepts()[0]
        t2 = self.reciepts()[1]

        def format_pick_for_cache(pick):
            """Format pick with full details for cache"""
            pick_data = {
                'id': pick.id,
                'team_abbr': pick.original_team.abbreviation if pick.original_team else '',
                'year': pick.year,
                'season': pick.season,
                'draft_type': pick.draft_type,
                'round': pick.draft_round,
                'slug': pick.slug or '',
                'player': None
            }
            
            if pick.player:
                pick_data['player'] = {
                    'id': pick.player.id,
                    'name': pick.player.name,
                    'position': pick.player.position
                }
            
            return pick_data

        return {
            "date": f"{self.date.year}-{self.date.month}-{self.date.day}",
            "t1_abbr": t1.team.abbreviation,
            "t1_players": [
                {"pos": p.position, "name": p.name, "id": p.id}
                for p in t2.players.all()
            ],
            "t1_picks": [format_pick_for_cache(p) for p in t2.picks.all()],
            "t2_abbr": t2.team.abbreviation,
            "t2_players": [
                {"pos": p.position, "name": p.name, "id": p.id}
                for p in t1.players.all()
            ],
            "t2_picks": [format_pick_for_cache(p) for p in t1.picks.all()],
        }

    def summary(self):
        t1 = self.reciepts()[0]
        t2 = self.reciepts()[1]

        return "%s: %s sends %s to %s for %s" % (
            self.date,
            t1.team.abbreviation,
            ", ".join(
                ["%s %s" % (p.position, p.name) for p in t2.players.all()]
                + [f"{p.slug}" for p in t2.picks.all()]
            ),
            t2.team.abbreviation,
            ", ".join(
                ["%s %s" % (p.position, p.name) for p in t1.players.all()]
                + [f"{p.year} {p.season } {p.slug}" for p in t1.picks.all()]
            ),
        )


class TradeReceipt(BaseModel):
    trade = models.ForeignKey(Trade, on_delete=models.SET_NULL, null=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True)
    players = models.ManyToManyField(Player, related_name="players", blank=True)
    picks = models.ManyToManyField(DraftPick, related_name="picks", blank=True)

    def __unicode__(self):
        if self.trade:
            return "Trade %s: %s" % (self.trade.id, self.team)
        return self.team.abbreviation

    def summary(self):
        return ", ".join(
            ["%s %s" % (p.position, p.name) for p in self.players.all()]
            + [f"{p.slug}" for p in self.picks.all()]
        )

    def summary_html(self):
        return ", ".join(
            [
                "<a class='has-text-weight-semibold' href='/players/%s/'>%s %s</a>"
                % (p.id, p.position, p.name)
                for p in self.players.all()
            ]
            + [f"{p.slug}" for p in self.picks.all()]
        )

    @staticmethod
    def set_team(sender, instance, action, reverse, model, pk_set, **kwargs):
        team = instance.team
        trade = instance.trade
        trade.teams.add(team)
        trade.save()

    @staticmethod
    def trade_pick(sender, instance, action, reverse, model, pk_set, **kwargs):

        # when loading fixtures, do not try to update the team reference for a pick
        if not os.environ.get("ULMG_FIXTURES", None):
            if action == "post_add":
                team = instance.team
                for p in pk_set:
                    obj = DraftPick.objects.get(id=p)
                    obj.team = instance.team
                    obj.save()

    @staticmethod
    def trade_player(sender, instance, action, reverse, model, pk_set, **kwargs):

        # when loading fixtures, do not try to update the team reference for a player
        if not os.environ.get("ULMG_FIXTURES", None):
            if action == "post_add":
                team = instance.team
                for p in pk_set:
                    obj = Player.objects.get(id=p)
                    obj.is_reserve = False
                    obj.is_1h_c = False
                    obj.is_1h_p = False
                    obj.is_1h_pos = False
                    obj.is_2h_c = False
                    obj.is_2h_p = False
                    obj.is_2h_pos = False
                    obj.is_35man_roster = False
                    obj.is_mlb = False
                    obj.is_aaa_roster = False
                    obj.is_protected = False
                    obj.is_owned = True
                    obj.team = instance.team
                    obj.save()


m2m_changed.connect(
    receiver=TradeReceipt.trade_player, sender=TradeReceipt.players.through
)
m2m_changed.connect(receiver=TradeReceipt.trade_pick, sender=TradeReceipt.picks.through)


class TradeSummary(BaseModel):
    season = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    PLAYERS = "players only"
    PICKS = "players and picks"
    TRADE_TYPE_CHOICES = (
        (PLAYERS, "players only"),
        (PICKS, "players and picks"),
    )
    trade_type = models.CharField(max_length=255, choices=TRADE_TYPE_CHOICES)

    def __unicode__(self):
        return "%s: %s (%s)" % (self.season, self.trade_type, self.pk)

    class Meta:
        ordering = ["-season", "trade_type"]


class Transaction(BaseModel):
    TRANSACTION_TYPE_CHOICES = (
        ("drafted", "drafted"),
        ("dropped", "dropped"),
        ("traded", "traded"),
    )
    transaction_type = models.CharField(
        max_length=255, choices=TRANSACTION_TYPE_CHOICES
    )
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    player_name = models.CharField(max_length=255, blank=True, null=True)
    season = models.IntegerField()
    date = models.DateField(auto_now=True)
    origination_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        related_name="origination_team",
        blank=True,
    )
    destination_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        related_name="destination_team",
        blank=True,
    )

    def set_player_name(self):
        if self.player:
            self.player_name = self.player.name

    def set_season(self):
        self.season = utils.get_ulmg_season(self.date)

    def save(self, *args, **kwargs):
        self.set_season()
        self.set_player_name()

        super().save(*args, **kwargs)


class ProspectRating(BaseModel):
    year = models.CharField(max_length=4)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True)
    player_name = models.CharField(max_length=255, null=True, blank=True)

    skew = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    med = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    avg = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    law = models.IntegerField(blank=True, null=True)
    ba = models.IntegerField(blank=True, null=True)
    bp = models.IntegerField(blank=True, null=True)
    mlb = models.IntegerField(blank=True, null=True)
    fg = models.IntegerField(blank=True, null=True)
    p365 = models.IntegerField(blank=True, null=True)
    plive = models.IntegerField(blank=True, null=True)
    p1500 = models.IntegerField(blank=True, null=True)
    ftrax = models.IntegerField(blank=True, null=True)
    cbs = models.IntegerField(blank=True, null=True)
    espn = models.IntegerField(blank=True, null=True)

    rank_type = models.CharField(max_length=255, null=True, blank=True)

    def __unicode__(self):
        return f"{self.year}: Prospect ratings for {self.player}"


class Wishlist(BaseModel):
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE)

    def __unicode__(self):
        return f"{self.owner.name}"


class WishlistPlayer(BaseModel):
    """
    Denormalized player record for wishlists
    """
    COL_LVL = "COL"
    HS_LVL = "HS"
    MLB_LVL = "MLB"
    MINOR_LVL = "MINORS"
    NPB_LVL = "NPB"
    KBO_LVL = "KBO"
    INTAM_LVL = "INT-AM"
    PLAYER_LEVEL_CHOICES = (
        (COL_LVL, "col"),
        (HS_LVL, "hs"),
        (MLB_LVL, "mlb"),
        (MINOR_LVL, "minors"),
        (NPB_LVL, "npb"),
        (KBO_LVL, "kbo"),
        (INTAM_LVL, "int-am"),
    )

    PRO_TYPE = "PRO"
    AM_TYPE = "AM"
    INT_TYPE = "INT"
    PLAYER_TYPE_CHOICES = (
        (PRO_TYPE, "pro"),
        (AM_TYPE, "am"),
        (INT_TYPE, "int"),
    )

    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE)
    rank = models.IntegerField(blank=True, null=True)
    tier = models.IntegerField(blank=True, null=True)
    future_value = models.IntegerField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    tags = ArrayField(models.CharField(max_length=255), blank=True, null=True)
    player_type = models.CharField(max_length=255, choices=PLAYER_TYPE_CHOICES, blank=True, null=True)
    player_school = models.CharField(max_length=255, blank=True, null=True)
    player_level = models.CharField(max_length=255, choices=PLAYER_LEVEL_CHOICES, blank=True, null=True)
    player_year = models.IntegerField(blank=True, null=True)
    player_fv = models.IntegerField(blank=True, null=True)

    # stats = models.JSONField(null=True, blank=True)  # Removed - use PlayerStatSeason

    def __unicode__(self):
        return f"{self.player} [{self.rank}][{self.tier}]"

    def pit_stats(self):
        payload = []
        
        # Get pitching stats from PlayerStatSeason for this player
        stat_seasons = PlayerStatSeason.objects.filter(
            player=self.player,
            pitch_stats__isnull=False
        ).order_by('-season', 'classification')
        
        for stat_season in stat_seasons:
            if stat_season.pitch_stats and stat_season.pitch_stats.get('g', 0) >= 1:
                payload.append(stat_season.pitch_stats)
        
        return payload

    def hit_stats(self):
        payload = []
        
        # Get hitting stats from PlayerStatSeason for this player
        stat_seasons = PlayerStatSeason.objects.filter(
            player=self.player,
            hit_stats__isnull=False
        ).order_by('-season', 'classification')
        
        for stat_season in stat_seasons:
            if stat_season.hit_stats and stat_season.hit_stats.get('plate_appearances', 0) >= 1:
                payload.append(stat_season.hit_stats)
        
        return payload

    def latest_hit_stats(self):
        hit_stats = self.hit_stats()
        if len(hit_stats) > 0:
            return hit_stats[0]
        return None

    def latest_pit_stats(self):
        pit_stats = self.pit_stats()
        if len(pit_stats) > 0:
            return pit_stats[0]
        return None

    @property
    def owner_name(self):
        return self.wishlist.owner.name

    def save(self, *args, **kwargs):
        # Note: stats field will be populated from PlayerStatSeason when needed
        super().save(*args, **kwargs)


class Event(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return self.title


class Occurrence(BaseModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True, null=True)
    season = models.IntegerField()
    date = models.DateField()
    time = models.TimeField(blank=True, null=True)
    chat_link = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return f"{self.date} — {self.event.title}"

    def set_season(self):
        self.season = utils.get_ulmg_season(self.date)

    def save(self, *args, **kwargs):
        self.set_season()

        super().save(*args, **kwargs)
