# ABOUTME: How the computer manager follows the depth chart: who starts at each position, which starters run out of planned starts, and which relievers are past their planned innings.
# ABOUTME: Starts at a position go to whoever is furthest behind his share of it. The day's lineup card wins a near tie.

from collections import Counter

from django.db.models import Q

from ulmg import depth, models

# The lineup card's starter at a position keeps the job unless someone filed
# there is at least this many starts further behind his share.
CARD_EDGE = 1


def position_starts(team, season):
    """
    Starts at each position this season, from the lineups set in the team's
    games, as Counter({(player id, position): starts}).
    """
    counts = Counter()
    events = models.GameEvent.objects.filter(
        kind=models.GameEvent.START,
        log__game__series__slot__season=season,
    ).filter(
        Q(log__game__series__home_team=team) | Q(log__game__series__road_team=team)
    ).select_related("log__game__series")
    for event in events:
        series = event.log.game.series
        side = models.GameEvent.HOME if series.home_team_id == team.id else models.GameEvent.AWAY
        for entry in (event.payload.get("lineups") or {}).get(side) or []:
            counts[(entry["player"], entry["position"])] += 1
    return counts


class LineupPacer:
    """
    Picks a day's starters from the depth chart. allotments are the chart's
    lineup spots ({position: depth.Allotment}); counts are starts so far
    ({(player id, position): starts}). A position with nobody filed keeps the
    lineup card's starter. A share is plate appearances, and every lineup
    spot bats about as often, so the computer splits starts in the same
    proportion. What a position is still short belongs to the lineup card's
    starter there, on a day he is not filed at it himself.
    """

    def __init__(self, allotments, counts=None):
        self.allotments = {
            position: allotment
            for position, allotment in allotments.items()
            if position not in (depth.STARTS, depth.BULLPEN) and allotment.total > 0
        }
        self.counts = Counter(counts or {})
        self.totals = Counter()
        for (_, position), starts in self.counts.items():
            self.totals[position] += starts

    def __bool__(self):
        return bool(self.allotments)

    def _deficit(self, share, total, starts, position):
        return share / total * (self.totals[position] + 1) - starts

    def _candidates(self, card):
        """(edge, is card starter, position order, player id, position) for each filed player and the card's share."""
        candidates = []
        order = {position: index for index, position in enumerate(card)}
        for position, allotment in self.allotments.items():
            card_player = card.get(position)
            for player_id, share in allotment.shares.items():
                if share <= 0:
                    continue
                deficit = self._deficit(share, allotment.total, self.counts[(player_id, position)], position)
                is_card = player_id == card_player
                candidates.append(
                    (deficit + (CARD_EDGE if is_card else 0), is_card, order.get(position, 99), player_id, position)
                )
            if allotment.rest and card_player is not None and card_player not in allotment.shares:
                filed_starts = sum(self.counts[(player_id, position)] for player_id in allotment.shares)
                others = self.totals[position] - filed_starts
                deficit = self._deficit(allotment.rest, allotment.total, others, position)
                candidates.append((deficit + CARD_EDGE, True, order.get(position, 99), card_player, position))
        candidates.sort(key=lambda c: (-c[0], not c[1], c[2], c[3]))
        return candidates

    def choose(self, stored, available):
        """
        The day's lineup as stored entries, in the card's batting order.
        stored is the lineup card. available(player id, position) says
        whether a player can start there today. A player the chart moves
        off the card's position leaves that spot to someone the card no
        longer starts, then to anyone filed there.
        """
        if not self or not stored:
            return list(stored)
        card = {entry["position"]: entry["player"] for entry in stored}
        chosen = {}
        used = set()
        for _, _, _, player_id, position in self._candidates(card):
            if position in chosen or player_id in used or position not in card:
                continue
            if not available(player_id, position):
                continue
            chosen[position] = player_id
            used.add(player_id)
        for entry in stored:
            position, player_id = entry["position"], entry["player"]
            if position in chosen or position in self.allotments:
                continue
            if player_id not in used:
                chosen[position] = player_id
                used.add(player_id)
        displaced = [entry["player"] for entry in stored if entry["player"] not in used]
        for entry in stored:
            position = entry["position"]
            if position in chosen:
                continue
            filed = list(self.allotments.get(position).shares) if position in self.allotments else []
            pool = [player_id for player_id in displaced + filed if player_id not in used]
            pick = next((player_id for player_id in pool if available(player_id, position)), None)
            if pick is None:
                pick = next(iter(pool), entry["player"])
            chosen[position] = pick
            used.add(pick)
        return [{"player": chosen[entry["position"]], "position": entry["position"]} for entry in stored]

    def record(self, stored):
        """Count a lineup's starts, for the days after it."""
        for entry in stored:
            self.counts[(entry["player"], entry["position"])] += 1
            self.totals[entry["position"]] += 1


def lineup_pacer(team, season):
    """The team's pacer, with the starts its games have already used."""
    allotments = depth.allotments(team, season)
    if not any(code not in (depth.STARTS, depth.BULLPEN) for code in allotments):
        return LineupPacer({})
    return LineupPacer(allotments, position_starts(team, season))


def start_limits(team, season):
    """{player id: starts} for each starter the depth chart gives a number of starts."""
    return depth.limits(team, season, depth.STARTS)


def relief_outs(player_ids, season):
    """Outs each pitcher has thrown in relief this season, as {player id: outs}."""
    outs = Counter()
    rows = models.UsageAppearance.objects.filter(
        player_id__in=list(player_ids), game__series__slot__season=season, started=False
    ).values_list("player_id", "outs")
    for player_id, row_outs in rows:
        outs[player_id] += row_outs
    return outs


class ReliefPlan:
    """The bullpen innings each reliever is down for, and how many he has thrown."""

    def __init__(self, team, season):
        self.limits = {player_id: innings * 3 for player_id, innings in depth.limits(team, season, depth.BULLPEN).items()}
        self.thrown = relief_outs(self.limits, season) if self.limits else Counter()

    def problem(self, player):
        """Why the computer passes him over while another arm has innings left, or None."""
        limit = self.limits.get(player.id)
        if limit is None or self.thrown[player.id] < limit:
            return None
        return f"{player.name} has thrown his {limit // 3} planned bullpen innings."
