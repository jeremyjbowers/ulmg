def parse_roster_info():
    teams = settings.ROSTER_TEAM_IDS
    for team_id, team_abbrev, team_name in teams:
        with open(f"data/rosters/{team_abbrev}_roster.json", "r") as readfile:
            roster = json.loads(readfile.read())
            for player in roster:
                p = None
                try:
                    try:
                        p = models.Player.objects.get(fg_id=player["playerid1"])
                    except:
                        try:
                            p = models.Player.objects.get(fg_id=player["minormasterid"])
                        except:
                            pass

                    if p:
                        p.is_injured = False
                        p.is_mlb = False
                        p.is_ls_mlb = False
                        p.role = None
                        p.is_starter = False
                        p.is_bench = False
                        p.injury_description = None
                        p.is_mlb_40man = False

                        if player.get("mlevel", None):
                            p.role = player["mlevel"]
                        
                        elif player.get("role", None):
                            if player["role"] != "":
                                p.role = player["role"]

                        if p.role == "MLB":
                            p.ls_is_mlb = True
                            p.is_mlb = True


                        if player["type"] == "mlb-bp":
                            p.is_bullpen = True

                        if player["type"] == "mlb-sp":
                            p.is_starter = True

                        if player["type"] == "mlb-bn":
                            p.is_bench = True

                        if player["type"] == "mlb-sl":
                            p.is_starter = True

                        if "il" in player["type"]:
                            p.is_injured = True

                        p.injury_description = player.get("injurynotes", None)
                        p.mlbam_id = player.get("mlbamid1", None)
                        p.mlb_team = team_name
                        p.mlb_org = team_abbrev

                        if player["roster40"] == "Y":
                            p.is_mlb40man = True

                        p.save()

                except Exception as e:
                    prto_int(f"error loading {player['player']}: {e}")