from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

import requests
from bs4 import BeautifulSoup

from ulmg import models, utils


class Command(BaseCommand):
    headers = {
        "Referer": "https://www.milb.com/",
        "Sec-Ch-Ua": '"Not/A)Brand";v="99", "Microsoft Edge";v="115", "Chromium";v="115"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "macOS",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203",
    }





    def handle(self, *args, **options):

        self.MLB_DEPTH_URL = "https://www.mlb.com/team/roster/depth-chart"
        self.MILB_AFFILIATE_URL = "https://www.milb.com/about/teams/by-affiliate"
        self.FCL_URL = "https://www.milb.com/florida-complex"
        self.AZL_URL = "https://www.milb.com/arizona-complex"
        self.DSL_URL = "https://www.milb.com/dominican-summer"

        self.fix_mlbam_dupes()
        self.fix_fg_dupes()
        self.get_cpx_rosters()
        self.get_milb_rosters()
        self.get_mlb_rosters()
