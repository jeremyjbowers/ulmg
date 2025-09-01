import csv
import json
import os
from decimal import Decimal

from bs4 import BeautifulSoup
from dateutil.parser import parse
from django.apps import apps
from django.db import connection, transaction
from django.db.models import Avg, Sum, Count
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import requests

from ulmg import models, utils


class Command(BaseCommand):
    """
        mlb bat dict_keys(['Bats', 'xMLBAMID', 'Name', 'Team', 'Season', 'Age', 'AgeR', 'SeasonMin', 'SeasonMax', 'G', 'AB', 'PA', 'H', '1B', '2B', '3B', 'HR', 'R', 'RBI', 'BB', 'IBB', 'SO', 'HBP', 'SF', 'SH', 'GDP', 'SB', 'CS', 'AVG', 'GB', 'FB', 'LD', 'IFFB', 'Pitches', 'Balls', 'Strikes', 'IFH', 'BU', 'BUH', 'BB%', 'K%', 'BB/K', 'OBP', 'SLG', 'OPS', 'ISO', 'BABIP', 'GB/FB', 'LD%', 'GB%', 'FB%', 'IFFB%', 'HR/FB', 'IFH%', 'BUH%', 'TTO%', 'wOBA', 'wRAA', 'wRC', 'Batting', 'Fielding', 'Replacement', 'Positional', 'wLeague', 'CFraming', 'Defense', 'Offense', 'RAR', 'WAR', 'WAROld', 'Dollars', 'BaseRunning', 'Spd', 'wRC+', 'wBsR', 'WPA', '-WPA', '+WPA', 'RE24', 'REW', 'pLI', 'phLI', 'PH', 'WPA/LI', 'Clutch', 'FB%1', 'FBv', 'SL%', 'SLv', 'CT%', 'CTv', 'CB%', 'CBv', 'CH%', 'CHv', 'SF%', 'SFv', 'KN%', 'KNv', 'XX%', 'PO%', 'wFB', 'wSL', 'wCT', 'wCB', 'wCH', 'wSF', 'wKN', 'wFB/C', 'wSL/C', 'wCT/C', 'wCB/C', 'wCH/C', 'wSF/C', 'wKN/C', 'O-Swing%', 'Z-Swing%', 'Swing%', 'O-Contact%', 'Z-Contact%', 'Contact%', 'Zone%', 'F-Strike%', 'SwStr%', 'CStr%', 'C+SwStr%', 'Pull', 'Cent', 'Oppo', 'Soft', 'Med', 'Hard', 'bipCount', 'Pull%', 'Cent%', 'Oppo%', 'Soft%', 'Med%', 'Hard%', 'UBR', 'GDPRuns', 'AVG+', 'BB%+', 'K%+', 'OBP+', 'SLG+', 'ISO+', 'BABIP+', 'LD%+', 'GB%+', 'FB%+', 'HRFB%+', 'Pull%+', 'Cent%+', 'Oppo%+', 'Soft%+', 'Med%+', 'Hard%+', 'xwOBA', 'xAVG', 'xSLG', 'XBR', 'PPTV', 'CPTV', 'BPTV', 'DSV', 'DGV', 'BTV', 'rPPTV', 'rCPTV', 'rBPTV', 'rDSV', 'rDGV', 'rBTV', 'EBV', 'ESV', 'rFTeamV', 'rBTeamV', 'rTV', 'pfxFA%', 'pfxFT%', 'pfxFC%', 'pfxFS%', 'pfxFO%', 'pfxSI%', 'pfxSL%', 'pfxCU%', 'pfxKC%', 'pfxEP%', 'pfxCH%', 'pfxSC%', 'pfxKN%', 'pfxUN%', 'pfxvFA', 'pfxvFT', 'pfxvFC', 'pfxvFS', 'pfxvFO', 'pfxvSI', 'pfxvSL', 'pfxvCU', 'pfxvKC', 'pfxvEP', 'pfxvCH', 'pfxvSC', 'pfxvKN', 'pfxFA-X', 'pfxFT-X', 'pfxFC-X', 'pfxFS-X', 'pfxFO-X', 'pfxSI-X', 'pfxSL-X', 'pfxCU-X', 'pfxKC-X', 'pfxEP-X', 'pfxCH-X', 'pfxSC-X', 'pfxKN-X', 'pfxFA-Z', 'pfxFT-Z', 'pfxFC-Z', 'pfxFS-Z', 'pfxFO-Z', 'pfxSI-Z', 'pfxSL-Z', 'pfxCU-Z', 'pfxKC-Z', 'pfxEP-Z', 'pfxCH-Z', 'pfxSC-Z', 'pfxKN-Z', 'pfxwFA', 'pfxwFT', 'pfxwFC', 'pfxwFS', 'pfxwFO', 'pfxwSI', 'pfxwSL', 'pfxwCU', 'pfxwKC', 'pfxwEP', 'pfxwCH', 'pfxwSC', 'pfxwKN', 'pfxwFA/C', 'pfxwFT/C', 'pfxwFC/C', 'pfxwFS/C', 'pfxwFO/C', 'pfxwSI/C', 'pfxwSL/C', 'pfxwCU/C', 'pfxwKC/C', 'pfxwEP/C', 'pfxwCH/C', 'pfxwSC/C', 'pfxwKN/C', 'pfxO-Swing%', 'pfxZ-Swing%', 'pfxSwing%', 'pfxO-Contact%', 'pfxZ-Contact%', 'pfxContact%', 'pfxZone%', 'pfxPace', 'piCH%', 'piCS%', 'piCU%', 'piFA%', 'piFC%', 'piFS%', 'piKN%', 'piSB%', 'piSI%', 'piSL%', 'piXX%', 'pivCH', 'pivCS', 'pivCU', 'pivFA', 'pivFC', 'pivFS', 'pivKN', 'pivSB', 'pivSI', 'pivSL', 'pivXX', 'piCH-X', 'piCS-X', 'piCU-X', 'piFA-X', 'piFC-X', 'piFS-X', 'piKN-X', 'piSB-X', 'piSI-X', 'piSL-X', 'piXX-X', 'piCH-Z', 'piCS-Z', 'piCU-Z', 'piFA-Z', 'piFC-Z', 'piFS-Z', 'piKN-Z', 'piSB-Z', 'piSI-Z', 'piSL-Z', 'piXX-Z', 'piwCH', 'piwCS', 'piwCU', 'piwFA', 'piwFC', 'piwFS', 'piwKN', 'piwSB', 'piwSI', 'piwSL', 'piwXX', 'piwCH/C', 'piwCS/C', 'piwCU/C', 'piwFA/C', 'piwFC/C', 'piwFS/C', 'piwKN/C', 'piwSB/C', 'piwSI/C', 'piwSL/C', 'piwXX/C', 'piO-Swing%', 'piZ-Swing%', 'piSwing%', 'piO-Contact%', 'piZ-Contact%', 'piContact%', 'piZone%', 'piPace', 'Events', 'EV', 'LA', 'Barrels', 'Barrel%', 'maxEV', 'HardHit', 'HardHit%', 'Q', 'TG', 'TPA', 'PlayerNameRoute', 'PlayerName', 'position', 'playerid', 'TeamName', 'TeamNameAbb', 'teamid', 'Pos', 'EV90'])
        mlb pit dict_keys(['Throws', 'xMLBAMID', 'Name', 'Team', 'Season', 'Age', 'AgeR', 'SeasonMin', 'SeasonMax', 'W', 'L', 'ERA', 'G', 'GS', 'QS', 'CG', 'ShO', 'SV', 'BS', 'IP', 'TBF', 'H', 'R', 'ER', 'HR', 'BB', 'IBB', 'HBP', 'WP', 'BK', 'SO', 'GB', 'FB', 'LD', 'IFFB', 'Pitches', 'Balls', 'Strikes', 'RS', 'IFH', 'BU', 'BUH', 'K/9', 'BB/9', 'K/BB', 'H/9', 'HR/9', 'AVG', 'WHIP', 'BABIP', 'LOB%', 'FIP', 'GB/FB', 'LD%', 'GB%', 'FB%', 'IFFB%', 'HR/FB', 'IFH%', 'BUH%', 'TTO%', 'CFraming', 'Starting', 'Start-IP', 'Relieving', 'Relief-IP', 'RAR', 'WAR', 'Dollars', 'RA9-Wins', 'LOB-Wins', 'BIP-Wins', 'BS-Wins', 'tERA', 'xFIP', 'WPA', '-WPA', '+WPA', 'RE24', 'REW', 'pLI', 'inLI', 'gmLI', 'exLI', 'Pulls', 'Games', 'WPA/LI', 'Clutch', 'FB%1', 'FBv', 'SL%', 'SLv', 'CT%', 'CTv', 'CB%', 'CBv', 'CH%', 'CHv', 'SF%', 'SFv', 'KN%', 'KNv', 'XX%', 'PO%', 'wFB', 'wSL', 'wCT', 'wCB', 'wCH', 'wSF', 'wKN', 'wFB/C', 'wSL/C', 'wCT/C', 'wCB/C', 'wCH/C', 'wSF/C', 'wKN/C', 'O-Swing%', 'Z-Swing%', 'Swing%', 'O-Contact%', 'Z-Contact%', 'Contact%', 'Zone%', 'F-Strike%', 'SwStr%', 'CStr%', 'C+SwStr%', 'HLD', 'SD', 'MD', 'ERA-', 'FIP-', 'xFIP-', 'K%', 'BB%', 'K-BB%', 'SIERA', 'kwERA', 'RS/9', 'E-F', 'Pull', 'Cent', 'Oppo', 'Soft', 'Med', 'Hard', 'bipCount', 'Pull%', 'Cent%', 'Oppo%', 'Soft%', 'Med%', 'Hard%', 'K/9+', 'BB/9+', 'K/BB+', 'H/9+', 'HR/9+', 'AVG+', 'WHIP+', 'BABIP+', 'LOB%+', 'K%+', 'BB%+', 'LD%+', 'GB%+', 'FB%+', 'HRFB%+', 'Pull%+', 'Cent%+', 'Oppo%+', 'Soft%+', 'Med%+', 'Hard%+', 'xERA', 'pb_o_CH', 'pb_s_CH', 'pb_c_CH', 'pb_o_CU', 'pb_s_CU', 'pb_c_CU', 'pb_o_FF', 'pb_s_FF', 'pb_c_FF', 'pb_o_SI', 'pb_s_SI', 'pb_c_SI', 'pb_o_SL', 'pb_s_SL', 'pb_c_SL', 'pb_o_KC', 'pb_s_KC', 'pb_c_KC', 'pb_o_FC', 'pb_s_FC', 'pb_c_FC', 'pb_o_FS', 'pb_s_FS', 'pb_c_FS', 'pb_overall', 'pb_stuff', 'pb_command', 'pb_xRV100', 'pb_ERA', 'sp_s_CH', 'sp_l_CH', 'sp_p_CH', 'sp_s_CU', 'sp_l_CU', 'sp_p_CU', 'sp_s_FF', 'sp_l_FF', 'sp_p_FF', 'sp_s_SI', 'sp_l_SI', 'sp_p_SI', 'sp_s_SL', 'sp_l_SL', 'sp_p_SL', 'sp_s_KC', 'sp_l_KC', 'sp_p_KC', 'sp_s_FC', 'sp_l_FC', 'sp_p_FC', 'sp_s_FS', 'sp_l_FS', 'sp_p_FS', 'sp_s_FO', 'sp_l_FO', 'sp_p_FO', 'sp_stuff', 'sp_location', 'sp_pitching', 'PPTV', 'CPTV', 'BPTV', 'DSV', 'DGV', 'BTV', 'rPPTV', 'rCPTV', 'rBPTV', 'rDSV', 'rDGV', 'rBTV', 'EBV', 'ESV', 'rFTeamV', 'rBTeamV', 'rTV', 'pfxFA%', 'pfxFT%', 'pfxFC%', 'pfxFS%', 'pfxFO%', 'pfxSI%', 'pfxSL%', 'pfxCU%', 'pfxKC%', 'pfxEP%', 'pfxCH%', 'pfxSC%', 'pfxKN%', 'pfxUN%', 'pfxvFA', 'pfxvFT', 'pfxvFC', 'pfxvFS', 'pfxvFO', 'pfxvSI', 'pfxvSL', 'pfxvCU', 'pfxvKC', 'pfxvEP', 'pfxvCH', 'pfxvSC', 'pfxvKN', 'pfxFA-X', 'pfxFT-X', 'pfxFC-X', 'pfxFS-X', 'pfxFO-X', 'pfxSI-X', 'pfxSL-X', 'pfxCU-X', 'pfxKC-X', 'pfxEP-X', 'pfxCH-X', 'pfxSC-X', 'pfxKN-X', 'pfxFA-Z', 'pfxFT-Z', 'pfxFC-Z', 'pfxFS-Z', 'pfxFO-Z', 'pfxSI-Z', 'pfxSL-Z', 'pfxCU-Z', 'pfxKC-Z', 'pfxEP-Z', 'pfxCH-Z', 'pfxSC-Z', 'pfxKN-Z', 'pfxwFA', 'pfxwFT', 'pfxwFC', 'pfxwFS', 'pfxwFO', 'pfxwSI', 'pfxwSL', 'pfxwCU', 'pfxwKC', 'pfxwEP', 'pfxwCH', 'pfxwSC', 'pfxwKN', 'pfxwFA/C', 'pfxwFT/C', 'pfxwFC/C', 'pfxwFS/C', 'pfxwFO/C', 'pfxwSI/C', 'pfxwSL/C', 'pfxwCU/C', 'pfxwKC/C', 'pfxwEP/C', 'pfxwCH/C', 'pfxwSC/C', 'pfxwKN/C', 'pfxO-Swing%', 'pfxZ-Swing%', 'pfxSwing%', 'pfxO-Contact%', 'pfxZ-Contact%', 'pfxContact%', 'pfxZone%', 'pfxPace', 'piCH%', 'piCS%', 'piCU%', 'piFA%', 'piFC%', 'piFS%', 'piKN%', 'piSB%', 'piSI%', 'piSL%', 'piXX%', 'pivCH', 'pivCS', 'pivCU', 'pivFA', 'pivFC', 'pivFS', 'pivKN', 'pivSB', 'pivSI', 'pivSL', 'pivXX', 'piCH-X', 'piCS-X', 'piCU-X', 'piFA-X', 'piFC-X', 'piFS-X', 'piKN-X', 'piSB-X', 'piSI-X', 'piSL-X', 'piXX-X', 'piCH-Z', 'piCS-Z', 'piCU-Z', 'piFA-Z', 'piFC-Z', 'piFS-Z', 'piKN-Z', 'piSB-Z', 'piSI-Z', 'piSL-Z', 'piXX-Z', 'piwCH', 'piwCS', 'piwCU', 'piwFA', 'piwFC', 'piwFS', 'piwKN', 'piwSB', 'piwSI', 'piwSL', 'piwXX', 'piwCH/C', 'piwCS/C', 'piwCU/C', 'piwFA/C', 'piwFC/C', 'piwFS/C', 'piwKN/C', 'piwSB/C', 'piwSI/C', 'piwSL/C', 'piwXX/C', 'piO-Swing%', 'piZ-Swing%', 'piSwing%', 'piO-Contact%', 'piZ-Contact%', 'piContact%', 'piZone%', 'piPace', 'Events', 'EV', 'LA', 'Barrels', 'Barrel%', 'maxEV', 'HardHit', 'HardHit%', 'Q', 'TG', 'TIP', 'PlayerNameRoute', 'PlayerName', 'position', 'TeamName', 'TeamNameAbb', 'teamid', 'playerid', 'EV90'])
        milb bat dict_keys(['Name', 'Team', 'G', 'AB', 'PA', 'H', '1B', '2B', '3B', 'HR', 'R', 'RBI', 'BB', 'IBB', 'SO', 'HBP', 'SF', 'SH', 'GDP', 'SB', 'CS', 'AVG', 'BB%', 'K%', 'BB/K', 'OBP', 'SLG', 'OPS', 'ISO', 'Spd', 'BABIP', 'wRC', 'wRAA', 'wOBA', 'wRC+', 'wBsR', 'GB%', 'LD%', 'FB%', 'IFFB%', 'HR/FB', 'GB/FB', 'Oppo%', 'Pull%', 'Cent%', 'Balls', 'Strikes', 'Pitches', 'SwStr%', 'Age', 'MaxAge', 'Season', 'PlayerName', 'TeamName', 'AffId', 'AffAbbName', 'aLevel', 'playerids', 'minormasterid'])
        milb pit dict_keys(['Name', 'Team', 'W', 'L', 'ERA', 'G', 'GS', 'CG', 'ShO', 'SV', 'IP', 'TBF', 'H', 'R', 'ER', 'HR', 'BB', 'IBB', 'HBP', 'WP', 'BK', 'SO', 'K/9', 'BB/9', 'K/BB', 'HR/9', 'K%', 'BB%', 'AVG', 'WHIP', 'BABIP', 'LOB%', 'FIP', 'E-F', 'K-BB%', 'GB%', 'LD%', 'FB%', 'IFFB%', 'HR/FB', 'GB/FB', 'Oppo%', 'Pull%', 'Cent%', 'Balls', 'Strikes', 'Pitches', 'SwStr%', 'xFIP', 'Hld', 'BS', 'Age', 'MaxAge', 'Season', 'PlayerName', 'TeamName', 'AffAbbName', 'AffId', 'aLevel', 'playerids', 'minormasterid'])
        npb bat dict_keys(['Name', 'Team', 'G', 'AB', 'PA', 'H', '1B', '2B', '3B', 'HR', 'R', 'RBI', 'BB', 'IBB', 'SO', 'HBP', 'SF', 'SH', 'GDP', 'SB', 'CS', 'AVG', 'BB%', 'K%', 'BB/K', 'OBP', 'SLG', 'OPS', 'ISO', 'Spd', 'BABIP', 'wRC', 'wRAA', 'wOBA', 'wRC+', 'wBsR', 'Age', 'Season', 'PlayerName', 'JName', 'teamid', 'playerids', 'minormasterid'])
        npb pit dict_keys(['Name', 'Team', 'W', 'L', 'ERA', 'G', 'GS', 'CG', 'ShO', 'SV', 'IP', 'TBF', 'H', 'R', 'ER', 'HR', 'BB', 'IBB', 'HBP', 'WP', 'BK', 'SO', 'K/9', 'BB/9', 'K/BB', 'HR/9', 'K%', 'BB%', 'AVG', 'WHIP', 'BABIP', 'LOB%', 'FIP', 'E-F', 'K-BB%', 'Pitches', 'HLD', 'BS', 'Age', 'Season', 'PlayerName', 'JName', 'playerids', 'minormasterid'])
        kbo bat dict_keys(['Name', 'Team', 'G', 'AB', 'PA', 'H', '1B', '2B', '3B', 'HR', 'R', 'RBI', 'BB', 'IBB', 'SO', 'HBP', 'SF', 'SH', 'GDP', 'SB', 'CS', 'AVG', 'BB%', 'K%', 'BB/K', 'OBP', 'SLG', 'OPS', 'ISO', 'Spd', 'BABIP', 'wRC', 'wRAA', 'wOBA', 'wRC+', 'wBsR', 'Age', 'Season', 'PlayerName', 'KName', 'teamid', 'playerids', 'minormasterid'])
        kbo pit dict_keys(['Name', 'Team', 'W', 'L', 'ERA', 'G', 'GS', 'CG', 'ShO', 'SV', 'IP', 'TBF', 'H', 'R', 'ER', 'HR', 'BB', 'IBB', 'HBP', 'WP', 'BK', 'SO', 'K/9', 'BB/9', 'K/BB', 'HR/9', 'K%', 'BB%', 'AVG', 'WHIP', 'BABIP', 'LOB%', 'FIP', 'E-F', 'K-BB%', 'Pitches', 'HLD', 'BS', 'Age', 'Season', 'PlayerName', 'KName', 'playerids', 'minormasterid'])
        college bat dict_keys(['G', 'AB', 'PA', 'H', '1B', '2B', '3B', 'HR', 'R', 'RBI', 'BB', 'IBB', 'SO', 'HBP', 'SF', 'SH', 'GDP', 'SB', 'CS', 'AVG', 'BB%', 'K%', 'BB/K', 'OBP', 'SLG', 'OPS', 'ISO', 'Spd', 'BABIP', 'wRC', 'wRAA', 'wOBA', 'wRC+', 'wBsR', 'Age', 'MaxAge', 'Season', 'PlayerName', 'Team', 'UPID', 'UPURL', 'xMLBAMID', 'teamid', 'FullTeamName'])
        college pit dict_keys(['W', 'L', 'ERA', 'G', 'GS', 'CG', 'ShO', 'SV', 'IP', 'TBF', 'H', 'R', 'ER', 'HR', 'BB', 'HBP', 'WP', 'BK', 'SO', 'K/9', 'BB/9', 'K/BB', 'HR/9', 'K%', 'BB%', 'AVG', 'WHIP', 'BABIP', 'LOB%', 'FIP', 'E-F', 'K-BB%', 'Age', 'MaxAge', 'Season', 'PlayerName', 'Team', 'UPID', 'xMLBAMID', 'UPURL', 'teamid', 'FullTeamName'])
    """

    def _process_k(self, k):
        key_char_replace = {
            "-": "_minus",
            "+": "_plus",
            "%": "_pct",
            "/": "_",
            'aLevel': "level",
            'TeamNameAbb': "mlb_org",
            "AffAbbName": "mlb_org"
            ""
        }

        for _k, _v in key_char_replace.items():
            k = k.replace(_k, _v)

        return k.lower()

    def _process_v(self, k, v):
        int_keys = ['Age', 'AgeR', 'G', 'AB', 'PA', 'H', '1B', '2B', '3B', 'HR', 'R', 'RBI', 'BB', 'IBB', 'SO', 'HBP', 'SF', 'SH', 'GDP', 'SB', 'CS', 'GB', 'FB', 'LD', 'IFFB', 'Pitches', 'Balls', 'Strikes', 'IFH', 'BU', 'BUH', 'SeasonMin', 'SeasonMax', 'W', 'L', 'G', 'GS', 'QS', 'CG', 'ShO', 'SV', 'BS', 'IP', 'TBF', 'H', 'R', 'ER', 'HR', 'BB', 'IBB', 'HBP', 'WP', 'BK', 'SO', 'GB', 'FB', 'LD', 'IFFB', 'Pitches', 'Balls', 'Strikes', 'RS', 'IFH', 'BU', 'BUH']

        if k in int_keys:

            try:
                v = int(v)

            except:
                v = 0

        return v


    def handle(self, *args, **options):
        season = 2025
        leagues = ['mlb', 'milb', 'npb', 'kbo', 'college']
        sides = ['bat', 'pit']

        for idx, league in enumerate(leagues):
            classification = f"{idx+1}-{league}"

            for side in sides:
                url = f"https://static-theulmg.nyc3.digitaloceanspaces.com/fg-stats/{season}/fg_{league}_{side}.json"
                r = requests.get(url)
                stats = r.json()

                for stat in stats:
                    stat_dict = {self._process_k(k): self._process_v(k, v) for k, v in stat.items()}
                    p_obj = None
                    mlbam_id = None
                    fg_id = None

                    if stat.get('UPID'):
                        fg_id = stat.get('UPID')

                    if stat.get('minormasterid'):
                        fg_id = stat.get('minormasterid')

                    if stat.get('playerids'):
                        fg_id = stat.get('playerids')

                    if stat.get('playerid'):
                        fg_id = stat.get('playerid')

                    if stat.get('xMLBAMID'):
                        mlbam_id = stat.get('xMLBAMID')

                    if fg_id:
                        try:
                            p_obj = models.Player.objects.get(fg_id=fg_id)
                        except models.Player.DoesNotExist:
                            """
                            We do not create players here. FG stats doesn't have all fields we expect for player creation.
                            """
                            pass

                    if not p_obj:
                        if mlbam_id:
                            try:
                                p_obj = models.Player.objects.get(mlbam_id=mlbam_id)
                                if fg_id:
                                    p_obj.fg_id = fg_id
                                    p_obj.save()

                            except models.Player.DoesNotExist:
                                """
                                We do not create players here. FG stats doesn't have all fields we expect for player creation.
                                """
                                pass

                    if p_obj:
                        # Guard: Only create 1-mlb records if there are actual MLB stats
                        if league == "mlb":
                            has_stats = False
                            if side == "bat":
                                has_stats = (stat_dict.get('pa') or 0) > 0
                            if side == "pit":
                                # Accept either IP > 0 or Games > 0 as evidence of MLB appearance
                                ip_val = stat_dict.get('ip') or 0
                                g_val = stat_dict.get('g') or 0
                                has_stats = (ip_val > 0) or (g_val > 0)

                            if not has_stats:
                                # Skip creating an MLB classification for players without MLB appearances
                                continue

                        pss_obj, created = models.PlayerStatSeason.objects.get_or_create(season=season, classification=classification, player=p_obj)

                        pss_obj.mlb_org = stat_dict.get('mlb_org')

                        if league == "mlb":
                            pss_obj.carded = True

                        if side == "bat":
                            pss_obj.hit_stats = stat_dict

                        if side == "pit":
                            pss_obj.pitch_stats = stat_dict

                        pss_obj.save()

                        print(created, pss_obj)
                            