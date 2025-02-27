from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db.models import Count

from bs4 import BeautifulSoup
import requests
import ujson as json

from ulmg import models, utils

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Command(BaseCommand):

    def handle(self, *args, **options):

        HEADERS = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding":"gzip, deflate, br, zstd",
            "Accept-Language":"en-US,en;q=0.9",
            "Cache-Control":"max-age=0",
            "Cookie":'s_fid=3EA4D5F7BC4FA573-3E9F13D2C99CF004; _cb=D11LMQDqv6CrjdPbT; AAMC_mlb_0=REGION%7C7; aam_uuid=39533848411327052697484019178726820981; usprivacy=1---; __qca=P0-821109679-1727363474277; OneTrustWPCCPAGoogleOptOut=false; adobe_amp_id=amp-msw5R5XIhuczkvBohTAorA; s_ecid=amp-KrtRbhcgoOEWUeFJ61TEig; _scid=1rMirzyxOB4xPTbBaqtvodnI7il8gbYx; _tt_enable_cookie=1; OptanonAlertBoxClosed=2024-09-27T13:01:19.087Z; _bti=%7B%22app_id%22%3A%22mlb-editorial%22%2C%22bsin%22%3A%22Arqslg%2B%2BLE%2Bo7zRTNCAd3dKSWD5pigkmVJzZufS4footu9pqwun0s0tcZ%2Bssx2j%2BrgHdk5XrF4hxeaZv19EfnQ%3D%3D%22%2C%22is_identified%22%3Afalse%7D; _v__chartbeat3=CdtwnkCjC6OtDQGrUA; s_vi=[CS]v1|3394B713EB0BDBF8-4000032244825AFE[CE]; _ttp=1zi14kF7LMK2lzwOo9LPdCYNARH.tt.1; _lc2_fpi=ca79ac0ed495--01jg77awwdphp5zsjs7w1z6de6; 33acrossIdTp=bZeQA%2Bl3KTaVbaBdHiicgjUSTN9aX%2FuQwTeaZ3kzy2c%3D; amp-story=amp-05YaXTzSCwgbMpjJMeHuaA; minVersion={"experiment":341076948,"minFlavor":"remove second callmi-1.17.1.217.js100"}; adcloud={%22_les_v%22:%22c%2Cy%2Cmlb.com%2C1739726510%22}; at_check=true; AMCVS_A65F776A5245B01B0A490D44%40AdobeOrg=1; s_cc=true; _ScCbts=%5B%5D; _gid=GA1.2.908301509.1740506085; _sctr=1%7C1740459600000; kndctr_A65F776A5245B01B0A490D44_AdobeOrg_identity=CiYzOTM4MDMwNTAzMDY5NTMyNzQ5NzQ2ODk3MDA5ODM0NzUyNzExN1IQCLXDi%5FeiMhgBKgNWQTYwA%5FAB2qT98dMy; ln=jeremyjbowers@gmail.com; _gcl_au=1.1.826324387.1735409361.150127777.1740506752.1740506755; mai=_email=jeremyjbowers@gmail.com&firstName=Jeremy&lastName=Bowers&birthMonth=5&birthDay=7&birthYear=1979&avatar=cap_chc.jpg; oktaid=00u7tfkklwpSenUkJ356; __gads=ID=f96c54f4447f8544:T=1735409365:RT=1740507688:S=ALNI_MYZ8CNoFEfrHBsRjT1Q8MHvFeDGCQ; __eoi=ID=1418b179ce6023d3:T=1735409365:RT=1740507688:S=AA-AfjZkhrm89GI87dEJOG64iRut; kruxid=29cd1043a14880f18c84dfaf056dff9a80d8129e65a493527845d9df3aeb46f8; minUnifiedSessionToken10=%7B%22sessionId%22%3A%227d162f01eb-f056e1883f-9f426beb52-87a413f453-e9b37bda27%22%2C%22uid%22%3A%22a44f348246-3a4aeaee53-03786e5632-be0ca2b271-7d2ec2ce8e%22%2C%22__sidts__%22%3A1740531774641%2C%22__uidts__%22%3A1740531774641%7D; _scid_r=6DMirzyxOB4xPTbBaqtvodnI7il8gbYxJZN8JQ; _uetsid=9908f790f3a111ef9ae805fbcfe42e18; _uetvid=93c924a07cd011ef863331cf78ae84ed; s_ips=1239; s_lv_s=Less%20than%201%20day; gpv_v48=Minor%20League%20Baseball%3A%20Prospects%3A%20Prospect%20Rankings; s_ppn=Minor%20League%20Baseball%3A%20Prospects%3A%20Prospect%20Rankings; mboxEdgeCluster=34; datadome=ibUnkDdmE_qdQRnyvI6jclIvcVEiqyAWj7uPMhTt~wDoB5~pFZgwo7S9QJvJ29~Ykk~1ml~OLzY6~bACyGDWUGlkHTBz32Ij9XbQ9bkvgczFd3S5gOi6~qJlHPBqfTgl; AMCV_A65F776A5245B01B0A490D44%40AdobeOrg=1687686476%7CMCMID%7C39380305030695327497468970098347527117%7CMCAID%7C3394B713EB0BDBF8-4000032244825AFE%7CMCIDTS%7C20146%7CMCAAMLH-1741226513%7C7%7CMCAAMB-1741226513%7Cj8Odv6LonN4r3an7LhD3WZrU1bUpAkFkkiY1ncBR96t2PTI%7CMCOPTOUT-1740627663s%7CNONE%7CMCSYNCSOP%7C411-20153%7CvVersion%7C3.0.0%7CMCCIDH%7C-882924189; mbox=PC#ee88481f628142c69feea34166af6ca0.34_0#1803866515|session#1a4d7db92d9042ceb41acd66c06f6ba2#1740622324; _chartbeat2=.1727363474120.1740621714029.0001110001100011.XByt6D1zcvbBl5BWACoZqoADwIvof.1; _cb_svref=external; _ga_N8YFCZLYSZ=GS1.1.1740620410.39.1.1740621714.60.0.1634955549; OptanonConsent=isGpcEnabled=0&datestamp=Wed+Feb+26+2025+21%3A01%3A54+GMT-0500+(Eastern+Standard+Time)&version=202401.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=8b966e15-dd15-4fa0-b280-9d6fc55a1097&interactionCount=2&landingPath=NotLandingPage&groups=C0001%3A1%2CC0003%3A1%2CC0002%3A1%2CC0004%3A1&AwaitingReconsent=false&geolocation=US%3BDC; _dc_gtm_UA-129326730-1=1; _ga=GA1.1.1209240446.1727363476; _ga_W15Y4QMMP8=GS1.1.1740620410.18.1.1740621714.60.0.0; s_getNewRepeat=1740621714410-Repeat; s_lv=1740621714411; s_tp=2256; s_ppv=Minor%2520League%2520Baseball%253A%2520Prospects%253A%2520Prospect%2520Rankings%2C55%2C55%2C1239%2C1%2C1; s_sq=%5B%5BB%5D%5D; s_tps=6; s_pvs=0',
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 Edg/133.0.0.0"
        }

        def fix_pos(pos_string):
            if pos_string.lower().strip() == "c":
                return "C"

            if "p" in pos_string.lower().strip():
                return "P"

            if "b" in pos_string.lower().strip():
                return "IF"

            if "ss" in pos_string.lower().strip():
                return "IF"

            return "OF"

        r = requests.get('https://www.mlb.com/milb/prospects/draft/', headers=HEADERS, verify=False)
        soup = BeautifulSoup(r.text, "html.parser")
        row_json = json.loads(soup.select('span')[34]['data-init-state'])
        rows = [v for k,v in row_json['payload'].items() if "Person:" in k]
        for idx, row in enumerate(rows):
            player_dict = {
                "birthdate": row['birthDate'],
                "name": f"{row['useName']} {row['useLastName']}",
                "mlbam_id": row['id'],
                "position": fix_pos(row['primaryPosition']['abbreviation'])
            }
            obj = None
            try:
                obj = models.Player.objects.get(mlbam_id=player_dict['mlbam_id'])
            
            except:
                objs = models.Player.objects.filter(name=player_dict['name'])
                if len(objs) == 1:
                    obj = objs[0]

            if not obj:
                obj = models.Player(**player_dict)

            obj.level = "B"
            for k,v in player_dict.items():
                setattr(obj,k,v)

            obj.save()
            print(obj)