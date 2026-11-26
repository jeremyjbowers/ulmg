# ABOUTME: Which numbers a manager sees on a player card: the baseball-card line, or the advanced wash.
# ABOUTME: Staff start on advanced. Everyone else starts on normal. A saved choice beats the default.

NORMAL = "normal"
ADVANCED = "advanced"
CHOICES = (NORMAL, ADVANCED)
SESSION_KEY = "stats_view"


def resolve(user, session=None):
    """The view this person sees. A blank owner and an empty session use the default."""
    if user is None or not getattr(user, "is_authenticated", False):
        return NORMAL
    from ulmg import utils

    owner = utils.get_owner_for_user(user)
    if owner is not None and owner.stats_view in CHOICES:
        return owner.stats_view
    if session is not None and session.get(SESSION_KEY) in CHOICES:
        return session[SESSION_KEY]
    if getattr(user, "is_staff", False):
        return ADVANCED
    return NORMAL


def save(user, session, choice):
    """Remember the choice on the owner when there is one, and in the session otherwise."""
    if choice not in CHOICES:
        raise ValueError(choice)
    from ulmg import utils

    owner = utils.get_owner_for_user(user)
    if owner is not None:
        owner.stats_view = choice
        owner.save()
        return
    session[SESSION_KEY] = choice
    session.modified = True
