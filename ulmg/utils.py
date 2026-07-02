import csv
import pickle
import os.path
import platform
import sys
from decimal import Decimal
from datetime import datetime

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection
from django.db.models import Avg, Sum, Count, Q
from django.contrib.postgres.search import TrigramSimilarity
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from googleapiclient.discovery import build
from google.oauth2 import service_account
import requests
import ujson as json
import time

from ulmg import models

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os
import logging

logger = logging.getLogger(__name__)


def get_level_order(level):
    """
    figure out how to sort stats from various levels against each other
    """
    level = level.lower()
    if level == "mlb":
        return 99
    
    if level == "aaa":
        return 98

    if level == "aa":
        return 50

    if level == 'a+':
        return 45

    if level == "a":
        return 40

    if level == "cpx":
        return 35

    if level == "dsl":
        return 30

    if level == "ncaa":
        return 25

    if level in ['npb', 'kbo']:
        return 98
    
    return 0


def get_fg_birthdate(player):
    if player.fg_id:
        player_url = f"https://www.fangraphs.com/statss.aspx?playerid={player.fg_id}"
        r = requests.get(player_url)
        soup = BeautifulSoup(r.content)
        
        try:
            date_cell = soup.select('tr.player-info__bio-birthdate td')[0].text
            player.birthdate = parse(date_cell.split('(')[0].strip())
            player.birthdate_qa = True
            player.save()
            print(player.name, player.birthdate, player_url)
        
        except:
            print(player.name, player_url, date_cell.split('(')[0].strip())

        time.sleep(1.5)


def get_ulmg_season(date):
    if date.month >= 10:
        return int(date.year) + 1
    return date.year


def get_current_season():
    season = settings.CURRENT_SEASON
    if settings.CURRENT_SEASON_TYPE == "offseason":
        season = season - 1
    return season


def mlb_appearances_q(prefix=""):
    """Return a Q object matching PlayerStatSeason rows with MLB hitting or pitching appearances."""
    field = f"{prefix}__" if prefix else ""
    hit_stats = f"{field}hit_stats"
    pitch_stats = f"{field}pitch_stats"
    return (
        Q(**{f"{hit_stats}__pa__gt": 0})
        | Q(**{f"{pitch_stats}__ip__gt": 0})
        | Q(**{f"{hit_stats}__g__gt": 0})
        | Q(**{f"{pitch_stats}__g__gt": 0})
    )


def get_stats_display_season_cap():
    """
    Latest calendar year used when choosing PlayerStatSeason rows for display (see Player.get_best_stat_season).
    Defaults to get_current_season(). When STATS_DISPLAY_SEASON_CAP is set (e.g. 2025), display never uses a
    later year than that value or than get_current_season(), whichever is lower.
    """
    natural = get_current_season()
    cap = getattr(settings, "STATS_DISPLAY_SEASON_CAP", None)
    if cap is None:
        return natural
    try:
        cap_int = int(cap)
    except (TypeError, ValueError):
        return natural
    return min(cap_int, natural)


STAT_CLASSIFICATION_CHOICES = (
    "1-mlb",
    "2-milb",
    "3-npb",
    "4-kbo",
    "5-college",
)


def get_stat_season_year_choices():
    """Years offered in team-page and search stat-season pickers."""
    current = get_current_season()
    years = [current]
    if current >= 2026:
        years.append(2025)
    years.extend([2024, 2023, 2022, 2021, 2020])
    seen = set()
    ordered = []
    for year in years:
        if year not in seen:
            seen.add(year)
            ordered.append(year)
    return ordered


def parse_team_roster_stat_filters(request):
    """
    Parse team roster stat display filters from GET params.

    When season is omitted, uses get_current_season() (exact match, no prior-year fallback).
    When classification is omitted, callers should prefer higher stat levels (1-mlb first).
    """
    season_param = request.GET.get("season", "").strip()
    allowed_years = set(get_stat_season_year_choices())
    current = get_current_season()
    allowed_years.add(current)

    if season_param:
        try:
            stat_season = int(season_param)
            if stat_season not in allowed_years:
                stat_season = current
        except ValueError:
            stat_season = current
    else:
        stat_season = current

    classification = request.GET.get("classification", "").strip()
    if classification not in STAT_CLASSIFICATION_CHOICES:
        classification = None

    return stat_season, classification


def get_midseason_open_carded_season(draft_year=None):
    """Prior MLB season whose card qualifies a player for the midseason Open draft."""
    if draft_year is None:
        draft_year = settings.CURRENT_SEASON
    return int(draft_year) - 1


def get_draft_prep_year_season(draft_type, list_type=None):
    """
    Return (year, season) for manager draft prep pages.

    draft_type: "open" or "aa"
    list_type: for open draft only, "offseason" or "midseason"; when omitted, uses
        the active league period (CURRENT_SEASON_TYPE).
    """
    if draft_type == "open" and list_type == "offseason":
        draft_year = settings.CURRENT_SEASON
        if settings.CURRENT_SEASON_TYPE == "midseason":
            draft_year = settings.CURRENT_SEASON + 1
        return draft_year, "offseason"
    if draft_type == "open" and list_type == "midseason":
        return settings.CURRENT_SEASON, "midseason"
    if settings.CURRENT_SEASON_TYPE == "midseason":
        return settings.CURRENT_SEASON, "midseason"
    return settings.CURRENT_SEASON, "offseason"


def get_strat_season():
    today = datetime.today()
    return get_ulmg_season(today) - 1


def to_int(might_int, default=None):
    if type(might_int) is int:
        return might_int

    if type(might_int) is str:
        try:
            return int(might_int.strip().replace("\xa0", ""))
        except:
            pass

    try:
        return int(might_int)
    except:
        pass

    if default:
        return default

    return None


def to_float(might_float, default=None):
    try:
        return float(might_float)
    except:
        pass

    return default


def reset_player_stats(id_type=None, player_ids=None):
    """Reset player stats by deleting PlayerStatSeason objects."""
    if id_type and player_ids:
        lookup = f"player__{id_type}__in"
        models.PlayerStatSeason.objects.filter(**{lookup: player_ids}).delete()
    else:
        models.PlayerStatSeason.objects.all().delete()


def get_scriptname():
    return " ".join(sys.argv)


def get_hostname():
    return platform.node()


def generate_timestamp():
    return int(datetime.now().timestamp())


def send_email(from_email=None, to_emails=[], text=None, subject=None):
    if from_email and len(to_emails) > 0:
        return requests.post(
            "https://api.mailgun.net/v3/mail.theulmg.com/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={
                "from": from_email,
                "to": to_emails,
                "subject": subject,
                "text": text,
            },
        )
    return None


def fuzzy_find_prospectrating(
    name_fragment, score=0.7, position=None, mlb_org=None
):

    output = []

    players = models.Player.objects

    if position:
        players = players.filter(position=position)

    if mlb_org:
        players = players.filter(mlb_org=mlb_org)

    players = players.annotate(similarity=TrigramSimilarity("name", name_fragment))
    players = players.filter(similarity__gt=score)
    players = players.order_by("-similarity")

    for p in players:
        try:
            obj = models.ProspectRating.objects.get(player=p)
            output.append(obj)
        except models.ProspectRating.DoesNotExist:
            pass

    return output


def strat_find_player(
    first_initial, last_name, hitter=True, mlb_org=None, ulmg_id=None
):
    if ulmg_id:
        return models.Player.objects.filter(id=ulmg_id)[0]

    players = models.Player.objects.filter(is_carded=True)

    if hitter:
        players = players.exclude(position="P")

    else:
        players = players.filter(position="P")

    players = players.filter(first_name__startswith=first_initial)

    players = players.annotate(similarity=TrigramSimilarity("last_name", last_name))
    players = players.filter(similarity__gt=0.5)
    players = players.order_by("-similarity")

    if len(players) > 1:
        if mlb_org:
            players = players.filter(mlb_org=mlb_org)

    if len(players) == 0:
        return None

    return players[0]


def fuzzy_find_player(name_fragment, score=0.7, position=None, mlb_org=None):

    players = models.Player.objects

    if position:
        players = players.filter(position=position)

    if mlb_org:
        players = players.filter(mlb_org=mlb_org)

    players = players.annotate(similarity=TrigramSimilarity("name", name_fragment))
    players = players.filter(similarity__gt=score)
    players = players.order_by("-similarity")

    return players


def update_wishlist(playerid, wishlist, rank, tier, remove=False):
    p = models.Player.objects.get(id=playerid)
    w, created = models.WishlistPlayer.objects.get_or_create(
        player=p, wishlist=wishlist
    )

    if remove:
        player_name = str(w.player.name)
        w.delete()
        return player_name

    else:
        if tier:
            w.tier = tier

        if rank:
            w.rank = rank

        if tier or rank:
            w.save()

        return w.player.name


def parse_fg_fv(raw_fv_str):
    if raw_fv_str == "":
        return None

    if "+" in raw_fv_str:
        return Decimal(f"{raw_fv_str.split('+')[0]}.5")

    try:
        return Decimal(f"{raw_fv_str}")

    except:
        return None


def get_owner_for_user(user):
    """Return the Owner linked to a Django user, or None."""
    if not user.is_authenticated:
        return None
    return models.Owner.objects.filter(user=user).first()


def get_team_for_owner(owner):
    """Return the Team managed by an Owner, or None."""
    if owner is None:
        return None
    return models.Team.objects.filter(owner_obj=owner).first()


def build_context(request):
    context = {}

    # Season for stat display (honors STATS_DISPLAY_SEASON_CAP when set)
    context["stats_season"] = get_stats_display_season_cap()

    # to build the nav
    context["teamnav"] = models.Team.objects.all().order_by("division", "abbreviation")
    context["draftnav"] = settings.DRAFTS
    context["mlb_roster_size"] = settings.MLB_ROSTER_SIZE
    context["roster_tab"] = settings.TEAM_ROSTER_TAB
    context["protect_tab"] = settings.TEAM_PROTECT_TAB
    context["live_tab"] = settings.TEAM_LIVE_TAB
    
    # Add previous season for roster eligibility checks
    context["previous_season"] = settings.CURRENT_SEASON - 1
    context["fg_qualified_positions"] = FG_QUALIFIED_POSITIONS

    # for search
    queries_without_page = dict(request.GET)
    if queries_without_page.get("page", None):
        del queries_without_page["page"]
    context["q_string"] = "&".join(
        ["%s=%s" % (k, v[-1]) for k, v in queries_without_page.items()]
    )

    context["owner"] = get_owner_for_user(request.user)
    context["my_team"] = get_team_for_owner(context["owner"])

    return context


def write_csv(path, payload):
    with open(path, "w") as csvfile:
        fieldnames = list(payload[0].keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for p in payload:
            writer.writerow(p)


FG_PITCHER_POSITIONS = {"SP", "RP", "P"}
FG_QUALIFIED_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
FG_POSITION_SORT_ORDER = {
    "C": 1,
    "1B": 2,
    "2B": 3,
    "3B": 4,
    "SS": 5,
    "LF": 6,
    "CF": 7,
    "RF": 8,
    "DH": 9,
}


def parse_fg_position1(position1):
    """
    Parse FanGraphs roster position1 into hitter position tokens.
    Returns an empty list for pitcher-only profiles.
    """
    if not position1:
        return []

    positions = []
    seen = set()
    for part in str(position1).strip().split("/"):
        pos = part.strip().upper()
        if not pos or pos in FG_PITCHER_POSITIONS or pos in seen:
            continue
        positions.append(pos)
        seen.add(pos)
    return positions


def format_fg_positions_display(positions):
    """Format parsed FanGraphs positions for display."""
    if not positions:
        return None
    sorted_positions = sorted(
        positions,
        key=lambda pos: (FG_POSITION_SORT_ORDER.get(pos, 99), pos),
    )
    return ", ".join(sorted_positions)


def fg_position1_from_roster(player_data):
    """Extract position1 from a FanGraphs roster resource row."""
    return player_data.get("position1") or player_data.get("position") or ""


def normalize_hand(value):
    """Normalize a roster handedness token to L, R, S, or None."""
    if value is None:
        return None
    token = str(value).strip().upper()
    if not token:
        return None
    if token in ("L", "R", "S"):
        return token
    if token.startswith("L"):
        return "L"
    if token.startswith("R"):
        return "R"
    if token.startswith("S"):
        return "S"
    return None


def hands_from_fg_roster(player_data):
    """
    Extract bats and throws from a FanGraphs roster resource row.
    Pitchers may only have ``handed``; that value maps to throws when throws is absent.
    """
    bats = normalize_hand(player_data.get("bats"))
    throws = normalize_hand(player_data.get("throws")) or normalize_hand(
        player_data.get("handed")
    )
    return {"bats": bats, "throws": throws}


# covered
def normalize_pos(pos):
    """
    Normalize positions to P, C, IF, OF or IF/OF
    """
    # Handle None or empty positions
    if not pos or pos is None:
        return "DH"  # Default for unknown positions
    
    # Convert to string and strip whitespace
    pos = str(pos).strip()
    if not pos:
        return "DH"

    if pos.upper().strip() in ["OF", "OUTFIELD"]:
        return "OF"

    if pos.upper().strip() in ['IF', "INFIELD", "SHORTSTOP", "SECOND BASE", "FIRST BASE", "THIRD BASE"]:
        return "IF"

    # Any pitcher.
    if "P" in pos.upper():
        return "P"

    # Catcher-only.
    if pos.upper() == "C":
        return "C"

    # One of the IF positions.
    if pos.upper() in ["1B", "2B", "3B", "SS"]:
        return "IF"

    # One of the OF positions.
    if pos.upper() in ["RF", "CF", "LF"]:
        return "OF"

    # Catch folks who are more than one OF and maybe some IF.
    if "OF" in pos.upper():
        if "B" in pos.upper() or "SS" in pos.upper():
            return "IF-OF"
        return "OF"

    # If you're left, you're a mix of IF.
    if "B" in pos.upper() or "SS" in pos.upper():
        return "IF"

    # Die if we cannot get a position.
    # This will likely fail to save, as positions are required?
    return "DH"


# covered
def str_to_bool(possible_bool):
    if isinstance(possible_bool, str):
        if possible_bool.lower() in ["y", "yes", "t", "true"]:
            return True
        if possible_bool.lower() in ["n", "no", "f", "false"]:
            return False
    return None


def int_or_none(possible_int):
    if isinstance(possible_int, int):
        return possible_int
    try:
        return to_int(possible_int)
    except:
        pass
    return None


def is_even(possible_int):
    possible_int = int_or_none(possible_int)
    if possible_int:
        if possible_int == 0:
            return True
        if possible_int % 2 == 0:
            return True
    return False


def get_sheet(sheet_id, sheet_range):
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    creds = service_account.Credentials.from_service_account_file(
        "credentials.json", scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()

    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    values = result.get("values", None)

    if values:
        return [dict(zip(values[0], r)) for r in values[1:]]
    return []


class S3DataManager:
    """
    Utility class for managing FanGraphs data in S3-compatible storage (DigitalOcean Spaces).
    Provides upload/download functionality with local fallback.
    """
    
    def __init__(self):
        self.s3_client = None
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        self.data_prefix = 'fg-stats/'  # Prefix for all FanGraphs data in bucket
        
        # Initialize S3 client if credentials are available
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=getattr(settings, 'AWS_S3_ENDPOINT_URL', None),
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            )
            # Test connection
            if self.bucket_name:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"S3 connection established to bucket: {self.bucket_name}")
        except (ClientError, NoCredentialsError, Exception) as e:
            logger.warning(f"S3 connection failed: {e}. Will use local files only.")
            self.s3_client = None
    
    def _get_s3_key(self, local_path):
        """Convert local file path to S3 key."""
        # Remove leading 'data/' and prepend our prefix
        if local_path.startswith('data/'):
            local_path = local_path[5:]
        return f"{self.data_prefix}{local_path}"
    
    def upload_file(self, local_path, s3_key=None):
        """
        Upload a local file to S3 with public read access.
        
        Args:
            local_path: Path to local file (e.g., 'data/2025/fg_mlb_bat.json')
            s3_key: Optional custom S3 key, otherwise derived from local_path
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.s3_client or not self.bucket_name:
            logger.debug("S3 not configured, skipping upload")
            return False
        
        if s3_key is None:
            s3_key = self._get_s3_key(local_path)
        
        try:
            self.s3_client.upload_file(
                local_path, 
                self.bucket_name, 
                s3_key,
                ExtraArgs={'ACL': 'public-read'}
            )
            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{s3_key} (public read)")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}")
            return False
    
    def download_file(self, s3_key, local_path):
        """
        Download a file from S3 to local path.
        
        Args:
            s3_key: S3 object key
            local_path: Where to save the file locally
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.s3_client or not self.bucket_name:
            logger.debug("S3 not configured, cannot download")
            return False
        
        try:
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {s3_key} from S3: {e}")
            return False
    
    def file_exists_in_s3(self, s3_key):
        """Check if a file exists in S3."""
        if not self.s3_client or not self.bucket_name:
            return False
        
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except:
            return False
    
    def get_file_content(self, local_path):
        """
        Get file content, trying local file first, then S3.
        
        Args:
            local_path: Path to local file (e.g., 'data/2025/fg_mlb_bat.json')
        
        Returns:
            dict: Parsed JSON content or None if not found
        """
        # Try local file first
        if os.path.exists(local_path):
            try:
                with open(local_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read local file {local_path}: {e}")
        
        # Try S3 if local file doesn't exist or failed to read
        if self.s3_client and self.bucket_name:
            s3_key = self._get_s3_key(local_path)
            if self.download_file(s3_key, local_path):
                try:
                    with open(local_path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to read downloaded file {local_path}: {e}")
        
        logger.warning(f"Could not find or read file: {local_path}")
        return None
    
    def save_and_upload_json(self, data, local_path):
        """
        Save JSON data to local file and upload to S3.
        
        Args:
            data: Data to save (will be JSON serialized)
            local_path: Local file path to save to
        
        Returns:
            bool: True if local save succeeded (S3 upload is best-effort)
        """
        try:
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Save locally
            with open(local_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved data to {local_path}")
            
            # Upload to S3 (best effort)
            self.upload_file(local_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save data to {local_path}: {e}")
            return False


# Global instance for easy access
s3_manager = S3DataManager()