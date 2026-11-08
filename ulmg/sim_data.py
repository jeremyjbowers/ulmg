# ABOUTME: The registry of models that hold a ULMG season's simulation data, and the models kept on purpose.
# ABOUTME: Plans and runs a season's sim reset in one transaction: deletes, clears results and runs restore steps.

from dataclasses import dataclass, field

from django.apps import apps
from django.db import transaction
from django.db.models import Q

from ulmg import models


class SimResetError(Exception):
    pass


@dataclass(frozen=True)
class SimModel:
    """
    One model holding sim data. season_lookup reaches a row's ULMG season,
    on the row or through a related game, series or slot; filters narrow a
    model that also holds real rows. A schedule model is deleted only with
    the schedule; until then its clear_fields go back to these values. A
    restore step, restore(season), runs after the model's delete or clear
    and may return a line to report.
    """

    model: type
    season_lookup: str
    filters: dict = field(default_factory=dict)
    schedule: bool = False
    clear_fields: dict = field(default_factory=dict)
    restore: object = None

    def rows(self, season):
        return self.model.objects.filter(**{self.season_lookup: season}, **self.filters)

    def rows_to_clear(self, season):
        """The season's rows with any clear field not yet at its cleared value."""
        changed = Q()
        for name, value in self.clear_fields.items():
            changed |= ~Q(**{name: value})
        return self.rows(season).filter(changed)

    def action(self, include_schedule):
        if include_schedule or not self.schedule:
            return "delete"
        if self.clear_fields:
            return "clear"
        return "keep"


# In delete order: every model that points at a sim model comes before it,
# so no delete cascades and each count is the model's own rows.
SIM_MODELS = [
    SimModel(models.UsageAppearance, "game__series__slot__season"),
    SimModel(models.UsageOverride, "game__series__slot__season"),
    SimModel(models.UsagePause, "game__series__slot__season"),
    SimModel(models.UsageCounter, "season"),
    # Only the ULMG season lines; every other classification is real stats.
    SimModel(models.PlayerStatSeason, "season", filters={"classification": "6-ulmg"}),
    # A game is played once it has both scores; clearing them unplays it.
    SimModel(
        models.ScheduleGame,
        "series__slot__season",
        schedule=True,
        clear_fields={"home_score": None, "road_score": None},
    ),
    SimModel(models.ScheduleSeries, "slot__season", schedule=True),
    SimModel(models.ScheduleSlot, "season", schedule=True),
]

# Real league data. A reset never touches these.
KEPT_MODELS = [
    models.Owner,
    models.MagicLinkToken,
    models.Team,
    models.Venue,
    models.Player,
    models.Card,
    models.DraftPick,
    models.Trade,
    models.TradeReceipt,
    models.TradeSummary,
    models.Transaction,
    models.ProspectRating,
    models.Wishlist,
    models.WishlistPlayer,
    models.Event,
    models.Occurrence,
    models.DuplicatePlayerCandidate,
    models.OwnerAPIToken,
]


def entry_for(model, registry=None):
    registry = SIM_MODELS if registry is None else registry
    return next(entry for entry in registry if entry.model is model)


def unclassified_models(sim_models=None, kept_models=None):
    """Concrete ulmg models in neither list."""
    sim_models = SIM_MODELS if sim_models is None else sim_models
    kept_models = KEPT_MODELS if kept_models is None else kept_models
    classified = {entry.model for entry in sim_models} | set(kept_models)
    return [m for m in apps.get_app_config("ulmg").get_models() if m not in classified]


@dataclass
class ResetStep:
    entry: SimModel
    action: str
    count: int
    restored: str = None

    @property
    def has_restore(self):
        return self.entry.restore is not None

    def describe(self, done):
        name = self.entry.model.__name__
        if self.action == "keep":
            line = f"{name}: keep {self.count} (deleted only with --include-schedule)"
        elif self.action == "clear":
            fields = ", ".join(self.entry.clear_fields)
            verb = "cleared" if done else "would clear"
            line = f"{name}: {verb} {fields} on {self.count}"
        else:
            verb = "deleted" if done else "would delete"
            line = f"{name}: {verb} {self.count}"
        if self.has_restore and self.action != "keep":
            line += f"; restore: {self.restored or 'done'}" if done else "; would run its restore step"
        return line


def _count(entry, action, season):
    if action == "clear":
        return entry.rows_to_clear(season).count()
    return entry.rows(season).count()


def plan_reset(season, include_schedule=False, registry=None):
    """What a reset would do, per model, without changing anything."""
    registry = SIM_MODELS if registry is None else registry
    steps = []
    for entry in registry:
        action = entry.action(include_schedule)
        steps.append(ResetStep(entry, action, _count(entry, action, season)))
    return steps


def summarize(season, steps, include_schedule, done):
    """One line for the whole reset, from its steps."""
    deleted = sum(s.count for s in steps if s.action == "delete")
    cleared = sum(s.count for s in steps if s.action == "clear")
    if done:
        schedule = "the schedule is deleted" if include_schedule else "the schedule is kept"
        return f"Reset {season}: deleted {deleted} rows and cleared {cleared}; {schedule}."
    schedule = "the schedule would be deleted" if include_schedule else "the schedule would be kept"
    return f"Dry run for {season}: would delete {deleted} rows and clear {cleared}; {schedule}. Nothing changed."


def _delete(entry, season):
    total, by_model = entry.rows(season).delete()
    own = by_model.get(entry.model._meta.label, 0)
    if total != own:
        others = ", ".join(f"{label} {n}" for label, n in by_model.items() if label != entry.model._meta.label)
        raise SimResetError(
            f"Deleting {entry.model.__name__} rows also deleted {others}; nothing was changed."
        )
    return own


@transaction.atomic
def reset_season(season, include_schedule=False, registry=None, progress=None):
    """
    Delete or clear the season's sim data, model by model in registry order,
    running each restore step after its model. One transaction: any failure
    rolls everything back. progress, if given, gets a line per model.
    """
    registry = SIM_MODELS if registry is None else registry
    steps = []
    for entry in registry:
        action = entry.action(include_schedule)
        if action == "delete":
            count = _delete(entry, season)
        elif action == "clear":
            count = entry.rows_to_clear(season).update(**entry.clear_fields)
        else:
            count = entry.rows(season).count()
        step = ResetStep(entry, action, count)
        if entry.restore is not None and action != "keep":
            step.restored = entry.restore(season)
        steps.append(step)
        if progress is not None:
            progress(f"{len(steps)}/{len(registry)} {step.describe(done=True)}")
    return steps
