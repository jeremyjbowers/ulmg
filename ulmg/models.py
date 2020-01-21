import datetime

from dateutil.relativedelta import *
from django.contrib.auth.models import User
from django.db import models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings
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
        (JAPAN,"JPN"),
        (KOREA,"KOR"),
        (J2,"J2"),
        (TAIWAN,"TAI"),
        (MEXICO,"MEX"),
        (OTHER,"OTH"),
    )

    # STUFF ABOUT THE PLAYER
    level = models.CharField(max_length=255, null=True, choices=PLAYER_LEVEL_CHOICES)
    level_order = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True)
    first_name = models.CharField(max_length=255, null=True)
    position = models.CharField(max_length=255, null=True, choices=PLAYER_POSITION_CHOICES)
    birthdate = models.DateField(blank=True, null=True)

    # IDENTIFIERS
    ba_id = models.CharField(max_length=255, blank=True, null=True)
    mlbam_id = models.CharField(max_length=255, blank=True, null=True)
    mlb_dotcom = models.CharField(max_length=255, blank=True, null=True)
    bp_id = models.CharField(max_length=255, blank=True, null=True)
    bref_id = models.CharField(max_length=255, blank=True, null=True)
    fg_id = models.CharField(max_length=255, blank=True, null=True)
    fantrax_id = models.CharField(max_length=255, blank=True, null=True)

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
    scouting_reports = ArrayField(models.TextField(blank=True, null=True), default=list)

    # STATUS AND SUCH
    is_owned = models.BooleanField(default=False)
    is_carded = models.BooleanField(default=False)
    is_amateur = models.BooleanField(default=False)
    league = models.CharField(max_length=255, blank=True, null=True, choices=OTHER_PRO_LEAGUES)

    # ROSTERS
    is_mlb_roster = models.BooleanField(default=False)
    is_aaa_roster = models.BooleanField(default=False)
    is_35man_roster = models.BooleanField(default=False)

    # PROTECTION
    is_reserve = models.BooleanField(default=False)
    is_1h_p = models.BooleanField(default=False)
    is_1h_c = models.BooleanField(default=False)
    is_1h_pos = models.BooleanField(default=False)
    is_2h_draft = models.BooleanField(default=False)

    # CAREER STATS (for level)
    cs_pa = models.IntegerField(blank=True, null=True)
    cs_gp = models.IntegerField(blank=True, null=True)
    cs_st = models.IntegerField(blank=True, null=True)
    cs_ip = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    # DEFENSE
    defense = ArrayField(models.CharField(max_length=10), blank=True, null=True)

    # POSSIBLY FAKE SOMWORLD STATS
    raar = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    raal = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    raat = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)

    # PROJECTED STATS
    ps_stat_origin = models.CharField(blank=True, null=True, max_length=255)
    ps_is_mlb = models.BooleanField(default=False)
    ps_g = models.IntegerField(blank=True, null=True)
    ps_pa = models.IntegerField(blank=True, null=True)
    ps_hr = models.IntegerField(blank=True, null=True)
    ps_bb = models.IntegerField(blank=True, null=True)
    ps_k = models.IntegerField(blank=True, null=True)
    ps_sb = models.IntegerField(blank=True, null=True)
    ps_cs = models.IntegerField(blank=True, null=True)
    ps_avg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ps_obp = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ps_slg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ps_ops = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ps_woba = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ps_wrc_plus = models.IntegerField(blank=True, null=True)
    ps_bsr = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ps_fld = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ps_off = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ps_def = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ps_war = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ps_era = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ps_fip = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ps_gs = models.IntegerField(blank=True, null=True)
    ps_sv = models.IntegerField(blank=True, null=True)
    ps_ip = models.IntegerField(blank=True, null=True)
    ps_h = models.IntegerField(blank=True, null=True)
    ps_er = models.IntegerField(blank=True, null=True)
    ps_hr = models.IntegerField(blank=True, null=True)
    ps_so = models.IntegerField(blank=True, null=True)
    ps_bb = models.IntegerField(blank=True, null=True)
    ps_whip = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ps_k_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ps_bb_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ps_ra9_war = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)

    # LIVE STATS
    ls_is_mlb = models.BooleanField(default=False)
    ls_hr = models.IntegerField(blank=True, null=True)
    ls_sb = models.IntegerField(blank=True, null=True)
    ls_runs = models.IntegerField(blank=True, null=True)
    ls_rbi = models.IntegerField(blank=True, null=True)
    ls_avg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_obp = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_slg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_babip = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_wrc_plus = models.IntegerField(blank=True, null=True)
    ls_plate_appearances = models.IntegerField(blank=True, null=True)
    ls_iso = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_k_pct = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ls_bb_pct = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    ls_woba = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_g = models.IntegerField(blank=True, null=True)
    ls_gs = models.IntegerField(blank=True, null=True)
    ls_ip = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    ls_k_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_bb_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_hr_9 = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_lob_pct = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    ls_gb_pct = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    ls_hr_fb = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    ls_era = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_fip = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_xfip = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_siera = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ls_xavg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_xwoba = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_xslg = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_xavg_diff = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_xwoba_diff = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    ls_xslg_diff = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)

    class Meta:
        ordering = ["last_name", "first_name", "level", "position"]

    def __unicode__(self):
        if self.get_team():
            return "%s (%s)" % (self.name, self.get_team().abbreviation)
        return self.name

    def set_fg_url(self):
        if self.fg_id:
            self.fg_url = "https://www.fangraphs.com/statss.aspx?playerid=%s" % self.fg_id

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

    def defense_display(self):
        if self.defense:
            sortdef = [{"display": f"{d.split('-')[0]}{d.split('-')[2]}", "sort": f"{d.split('-')[1]}{d.split('-')[2]}"} for d in self.defense]
            return ", ".join([x['display'] for x in sorted(sortdef, key=lambda x: x['sort'])])
        return None

    @property
    def age(self):
        if self.birthdate:
            now = datetime.datetime.utcnow().date()
            return relativedelta(now, self.birthdate).years
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

    def set_owned(self):
        if self.team == None:
            self.is_owned = False
        else:
            self.is_owned = True

    def team_display(self):
        if self.team:
            return self.team.abbreviation
        return None

    def save(self, *args, **kwargs):
        """
        Some light housekeeping.
        """
        self.set_name()
        self.set_ids()
        self.set_fg_url()
        self.set_level_order()
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
    pick_number = models.IntegerField(null=True, blank=True)
    overall_pick_number = models.IntegerField(null=True, blank=True)
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
        if self.player:
            self.player_name = self.player.name

    def save(self, *args, **kwargs):
        if self.player and self.team:
            if not self.player.team:
                self.player.team = self.team
                self.player.save()

            if self.player.team and self.player.team != self.team:
                self.player.team = self.team
                self.player.save()

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

    def summary_html(self):
        r = self.reciepts()
        t1 = r[0]
        t2 = r[1]

        return "%s: %s sends %s to %s for %s" % (
            self.date,
            "<a href='/teams/%s/'>%s</a>" % (t1.team.abbreviation.lower(), t1.team.abbreviation),
            ", ".join(["%s <a href='/players/%s/'>%s</a>" % (p.position, p.id, p.name) for p in t2.players.all()] + ["%s" % (p.slug) for p in t2.picks.all()]),
            "<a href='/teams/%s/'>%s</a>" % (t2.team.abbreviation.lower(), t2.team.abbreviation),
            ", ".join(["%s <a href='/players/%s/'>%s</a>" % (p.position, p.id, p.name) for p in t1.players.all()] + ["%s" % (p.slug) for p in t1.picks.all()]),
        )

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
        return ", ".join(["%s %s" % (p.position, p.name) for p in self.players.all()] + ["%s" % (p.slug) for p in self.picks.all()])

    def summary_html(self):
        return ", ".join(["<a class='has-text-weight-semibold' href='/players/%s/'>%s %s</a>" % (p.id, p.position, p.name) for p in self.players.all()] + ["%s" % (p.slug) for p in self.picks.all()])

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
    report = models.TextField(blank=True)

    def __unicode__(self):
        base = "%(organization)s %(date)s: %(player_name)s" % self.__dict__
        if self.fv:
            base += " (%s)" % self.fv
        return base

    def set_season(self):
        if not self.season:
            self.season = settings.CURRENT_SEASON

    def set_player_name(self):
        if self.player:
            self.player_name = self.player.name

    def save(self, *args, **kwargs):
        self.set_player_name()
        self.set_season()

        super().save(*args, **kwargs)