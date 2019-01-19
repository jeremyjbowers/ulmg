import datetime

from dateutil.relativedelta import *
from django.contrib.auth.models import User
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db.models.signals import post_save, m2m_changed
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


class Team(BaseModel):
    """
    Canonical representation of a ULMG team.
    """
    city = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=3)
    nickname = models.CharField(max_length=255)
    division = models.CharField(max_length=255, null=True, blank=True)
    owner = models.CharField(max_length=255, null=True, blank=True)
    owner_email = models.CharField(max_length=255, null=True, blank=True)
    championships = ArrayField(models.CharField(max_length=4), blank=True, null=True)

    class Meta:
        ordering = ["abbreviation"]

    def __unicode__(self):
        return self.abbreviation
 
    def players(self):
        """
        List of Player models associated with this team.
        """
        return Player.objects.filter(team=self)


class Player(BaseModel):
    """
    Canonical representation of a baseball player.
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
    INFIELD_OUTFIELD = "IF-OF"
    PITCHER_OF = "OF-P"
    PITCHER_IF = "IF-P"
    PLAYER_POSITION_CHOICES = (
        (PITCHER,"Pitcher"),
        (CATCHER,"Catcher"),
        (INFIELD,"Infield"),
        (OUTFIELD,"Outfield"),
        (INFIELD_OUTFIELD,"Infield/Outfield"),
        (PITCHER_OF,"Pitcher/Outfield"),
        (PITCHER_IF,"Pitcher/Infield"),
    )
    # STUFF ABOUT THE PLAYER
    level = models.CharField(max_length=255, null=True, choices=PLAYER_LEVEL_CHOICES)
    level_order = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    first_name = models.CharField(max_length=255, null=True)
    position = models.CharField(max_length=255, null=True, choices=PLAYER_POSITION_CHOICES)
    birthdate = models.DateField(blank=True, null=True)
    stats = JSONField(blank=True, null=True)
    steamer_predix = JSONField(blank=True, null=True)
    draft_eligibility_year = models.CharField(max_length=4, blank=True, null=True)
    starts = models.IntegerField(blank=True, null=True)
    relief_innings_pitched = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    plate_appearances = models.CharField(max_length=255, blank=True, null=True)
    is_relief_eligible = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    bats = models.CharField(max_length=255, blank=True, null=True)
    throws = models.CharField(max_length=255, blank=True, null=True)
    birth_year = models.CharField(max_length=255, blank=True, null=True)
    debut = models.CharField(max_length=255, blank=True, null=True)

    # IDENTIFIERS
    ba_id = models.CharField(max_length=255, blank=True, null=True)
    mlb_id = models.CharField(max_length=255, blank=True, null=True)
    mlb_name = models.CharField(max_length=255, blank=True, null=True)
    mlb_pos = models.CharField(max_length=255, blank=True, null=True)
    mlb_team = models.CharField(max_length=255, blank=True, null=True)
    mlb_team_long = models.CharField(max_length=255, blank=True, null=True)
    bp_id = models.CharField(max_length=255, blank=True, null=True)
    bref_id = models.CharField(max_length=255, blank=True, null=True)
    bref_name = models.CharField(max_length=255, blank=True, null=True)
    cbs_id = models.CharField(max_length=255, blank=True, null=True)
    cbs_name = models.CharField(max_length=255, blank=True, null=True)
    cbs_pos = models.CharField(max_length=255, blank=True, null=True)
    espn_id = models.CharField(max_length=255, blank=True, null=True)
    espn_name = models.CharField(max_length=255, blank=True, null=True)
    espn_pos = models.CharField(max_length=255, blank=True, null=True)
    fg_id = models.CharField(max_length=255, blank=True, null=True)
    fg_name = models.CharField(max_length=255, blank=True, null=True)
    fg_pos = models.CharField(max_length=255, blank=True, null=True)
    lahman_id = models.CharField(max_length=255, blank=True, null=True)
    nfbc_id = models.CharField(max_length=255, blank=True, null=True)
    nfbc_name = models.CharField(max_length=255, blank=True, null=True)
    nfbc_pos = models.CharField(max_length=255, blank=True, null=True)
    retro_id = models.CharField(max_length=255, blank=True, null=True)
    retro_name = models.CharField(max_length=255, blank=True, null=True)
    yahoo_id = models.CharField(max_length=255, blank=True, null=True)
    yahoo_name = models.CharField(max_length=255, blank=True, null=True)
    yahoo_pos = models.CharField(max_length=255, blank=True, null=True)
    mlb_depth = models.CharField(max_length=255, blank=True, null=True)
    ottoneu_id = models.CharField(max_length=255, blank=True, null=True)
    ottoneu_name = models.CharField(max_length=255, blank=True, null=True)
    ottoneu_pos = models.CharField(max_length=255, blank=True, null=True)
    rotowire_id = models.CharField(max_length=255, blank=True, null=True)
    rotowire_name = models.CharField(max_length=255, blank=True, null=True)
    rotowire_pos = models.CharField(max_length=255, blank=True, null=True)

    # Value
    raar = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    raal = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    raat = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    defense = ArrayField(models.CharField(max_length=3), blank=True, null=True)

    # LINKS TO THE WEB
    ba_url = models.CharField(max_length=255, blank=True, null=True)
    bref_url = models.CharField(max_length=255, blank=True, null=True)
    fg_url = models.CharField(max_length=255, blank=True, null=True)
    mlb_url = models.CharField(max_length=255, blank=True, null=True)

    # ULMG-SPECIFIC
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # PROSPECT STUFF
    fg_prospect_fv = models.CharField(max_length=4, blank=True, null=True)
    fg_prospect_rank = models.IntegerField(blank=True, null=True)
    ba_prospect_rank = models.IntegerField(blank=True, null=True)
    mlb_prospect_rank = models.IntegerField(blank=True, null=True)
    ba_draft_rank = models.IntegerField(blank=True, null=True)

    # STATUS AND SUCH
    is_owned = models.BooleanField(default=False)
    is_prospect = models.BooleanField(default=False)
    is_carded = models.BooleanField(default=False)
    is_amateur = models.BooleanField(default=False)

    # ROSTERS
    is_mlb_roster = models.BooleanField(default=False)
    is_aaa_roster = models.BooleanField(default=False)
    is_35man_roster = models.BooleanField(default=False)

    # PROTECTION
    is_reserve = models.BooleanField(default=False)
    is_1h_p = models.BooleanField(default=False)
    is_1h_c = models.BooleanField(default=False)
    is_1h_pos = models.BooleanField(default=False)

    class Meta:
        ordering = ["last_name", "first_name", "level", "position"]

    def __unicode__(self):
        if self.get_team():
            return "%s (%s)" % (self.name, self.get_team().abbreviation)
        return self.name

    def to_dict(self):
        return {
            "name": self.name,
            "position": self.position,
            "level": self.level,
            "age": self.age,
            "carded": self.is_carded,
            "amateur": self.is_amateur,
            "bref_url": self.bref_url,
            # "team": self.team.abbreviation
        }

    def set_usage(self):
        if self.stats:
            if "P" in self.position:
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
                if self.stats['pa']:
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
                    self.first_name = n.first + ' ' + n.middle
                self.last_name = n.last
                if n.suffix:
                    self.last_name = n.last + ' ' + n.suffix

    def set_ids(self):
        if self.fg_url and not self.fg_id:
            if self.fg_url:
                if "?playerid=" in self.fg_url:
                    self.fg_id = self.fg_url.split('?playerid=')[1].split('&')[0]

    def set_level_order(self):
        if self.level:
            if self.level == "V":
                self.level_order = 9
            if self.level == "A":
                self.level_order = 5
            if self.level == "B":
                self.level_order = 0

    def set_stats(self):
        if self.stats:
            if self.position != "P" and  self.stats.get('pa', None):
                self.plate_appearances = self.stats['pa']
            if self.position == "P":
                if self.stats.get('ip', None) and self.stats.get('gs', None) and self.stats.get('g', None):
                    if int(self.stats['g']) > int(self.stats['gs']):
                        self.is_relief_eligible = True
                        if float(self.stats['ip']) > 75.0:
                            self.relief_innings_pitched = float(self.stats['ip']) * 1.5
                        else:
                            self.relief_innings_pitched = float(self.stats['ip'])
                    if int(self.stats['gs']) > 0:
                        self.starts = int(self.stats['gs'])

    def set_owned(self):
        if self.team == None:
            self.is_owned = False
        else:
            self.is_owned = True

    def save(self, *args, **kwargs):
        """
        Some light housekeeping.
        """
        self.set_name()
        self.set_ids()
        self.set_level_order()
        self.usage = self.set_usage()
        self.set_stats()
        self.set_owned()

        super().save(*args, **kwargs)


class DraftPick(BaseModel):
    AA_TYPE = "aa"
    OPEN_TYPE = "open"
    BALANCE_TYPE = "balance"
    DRAFT_TYPE_CHOICES = (
        (AA_TYPE,"aa"),
        (OPEN_TYPE,"open"),
        (BALANCE_TYPE,"balance"),
    )
    draft_type = models.CharField(max_length=255, choices=DRAFT_TYPE_CHOICES, null=True)
    draft_round = models.IntegerField(null=True)
    year = models.CharField(max_length=4)
    pick_number = models.IntegerField(null=True)
    overall_pick_number = models.IntegerField(null=True)
    OFFSEASON = "offseason"
    MIDSEASON = "midseason"
    SEASON_CHOICES = (
        (OFFSEASON,"offseason"),
        (MIDSEASON,"midseason"),
    )
    season = models.CharField(max_length=255, choices=SEASON_CHOICES)
    slug = models.CharField(max_length=255, null=True, blank=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True, related_name="team")
    team_name = models.CharField(max_length=255, blank=True, null=True)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, blank=True, null=True)
    player_name = models.CharField(max_length=255, blank=True, null=True)
    pick_notes = models.TextField(blank=True, null=True)
    original_team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True, related_name="original_team")

    class Meta:
        ordering = ["year", "-season", "draft_type", "draft_round", "pick_number"]

    def __unicode__(self):
        return "%s %s %s (%s)" % (self.year, self.season, self.slug, self.team)

    def slugify(self):
        if self.draft_type == "aa":
            dt = "AA"

        if self.draft_type == "open":
            dt = "OP"

        if self.draft_type == "balance":
            dt = "CB"

        self.slug = "%s %s%s" % (self.original_team, dt, self.draft_round)

    def set_overalL_pick_number(self):
        if self.pick_number:
            rnd = self.draft_round - 1
            self.overall_pick_number = self.pick_number + (rnd * 16)

    def set_original_team(self):
        if not self.original_team and self.team:
            self.original_team = self.team

    def set_player_name(self):
        if self.player and not self.player_name:
            self.player_name = self.player.name

    def save(self, *args, **kwargs):
        self.set_original_team()
        self.set_overalL_pick_number()
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

    def __unicode__(self):
        return self.summary()

    def set_season(self):
        if self.date.month >= 10:
            self.season = int(self.date.year) + 1
        else:
            self.season = self.date.year

    def save(self, *args, **kwargs):
        self.set_season()

        super().save(*args, **kwargs)

    def reciepts(self):
        return TradeReceipt.objects.filter(trade=self)

    def summary(self):
        r = self.reciepts()
        t1 = r[0]
        t2 = r[1]

        return "%s: %s sends %s to %s for %s" % (
            self.date,
            t1.team.abbreviation,
            ", ".join(["%s %s" % (p.position, p.name) for p in t2.players.all()] + ["%s" % (p.slug) for p in t2.picks.all()]),
            t2.team.abbreviation,
            ", ".join(["%s %s" % (p.position, p.name) for p in t1.players.all()] + ["%s" % (p.slug) for p in t1.picks.all()]),
        )

    def summary_html(self):
        r = self.reciepts()
        t1 = r[0]
        t2 = r[1]

        return "%s: <a href='/teams/%s/other/'>%s</a> sends %s to <a href='/teams/%s/other/'>%s</a> for %s" % (
            self.date,
            t1.team.abbreviation.lower(),
            t1.team.abbreviation,
            ", ".join(["%s %s" % (p.position, p.name) for p in t2.players.all()] + ["%s" % (p.slug) for p in t2.picks.all()]),
            t2.team.abbreviation.lower(),
            t2.team.abbreviation,
            ", ".join(["%s %s" % (p.position, p.name) for p in t1.players.all()] + ["%s" % (p.slug) for p in t1.picks.all()]),
        )

class TradeReceipt(BaseModel):
    trade = models.ForeignKey(Trade, on_delete=models.SET_NULL, null=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True)
    players = models.ManyToManyField(Player, related_name="players", blank=True)
    picks = models.ManyToManyField(DraftPick, related_name="picks", blank=True)

    def __unicode__(self):
        return "Trade %s: %s" % (self.trade.id, self.team)

    @staticmethod
    def trade_pick(sender, instance, action, reverse, model, pk_set, **kwargs):
        if action == 'post_add':
            team = instance.team
            for p in pk_set:
                obj = DraftPick.objects.get(id=p)
                obj.team = instance.team
                obj.save()

    @staticmethod
    def trade_player(sender, instance, action, reverse, model, pk_set, **kwargs):
        if action == 'post_add':
            team = instance.team
            for p in pk_set:
                obj = Player.objects.get(id=p)
                obj.is_reserve = False
                obj.is_1h_c = False
                obj.is_1h_p = False
                obj.is_1h_pos = False
                obj.is_35man_roster = False
                obj.is_owned = True
                obj.team = instance.team
                obj.save()


m2m_changed.connect(receiver=TradeReceipt.trade_player, sender=TradeReceipt.players.through)
m2m_changed.connect(receiver=TradeReceipt.trade_pick, sender=TradeReceipt.picks.through)


class TradeSummary(BaseModel):
    season = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    PLAYERS = "players only"
    PICKS = "players and picks"
    TRADE_TYPE_CHOICES = (
        (PLAYERS,"players only"),
        (PICKS,"players and picks"),
    )
    trade_type = models.CharField(max_length=255, choices=TRADE_TYPE_CHOICES)
    
    def __unicode__(self):
        return "%s: %s (%s)" % (self.season, self.trade_type, self.pk)

    class Meta:
        ordering = ['-season', 'trade_type']


class SomRunsYear(BaseModel):
    season = models.IntegerField()
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True)
    player_name = models.CharField(max_length=255, blank=True)
    raar = models.DecimalField(max_digits=4, decimal_places=1)
    raal = models.DecimalField(max_digits=4, decimal_places=1)
    raat = models.DecimalField(max_digits=4, decimal_places=1)

    def __unicode__(self):
        return "%(player_name)s: %(raal)s (L) (R) %(raat)s [%(raat)s]" % self

    def set_player_name(self):
        if self.player:
            self.player_name = self.player.name

    def save(self, *args, **kwargs):
        self.set_player_name()

        super().save(*args, **kwargs)

class ScoutingReport(BaseModel):
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True)
    player_name = models.CharField(max_length=255, blank=True)
    season = models.IntegerField()
    date = models.DateField()
    pv = models.CharField(max_length=5, blank=True, null=True)
    fv = models.CharField(max_length=5, blank=True, null=True)
    risk = models.IntegerField(blank=True, null=True)
    risk_name = models.CharField(max_length=255, blank=True, null=True)
    url = models.CharField(max_length=255, blank=True, null=True)
    organization = models.CharField(max_length=255, blank=True, null=True)
    rank = models.IntegerField(blank=True, null=True)
    evaluator = models.CharField(max_length=255, blank=True, null=True)
    report_type = models.CharField(max_length=255, blank=True, null=True)
    level = models.CharField(max_length=255, blank=True, null=True)

    def __unicode__(self):
        base = "%(organization)s %(date)s: %(player_name)s" % self.__dict__
        if self.fv:
            base += " (%s)" % self.fv
        return base

    def set_player_name(self):
        if self.player:
            self.player_name = self.player.name

    def save(self, *args, **kwargs):
        self.set_player_name()

        super().save(*args, **kwargs)