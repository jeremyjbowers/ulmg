# Stats Field Architecture

This document explains the new architecture for handling PlayerStatSeason JSON fields to prevent field name mismatches.

## Problem Solved

Previously, there were mismatches between:
- **Data loading scripts** creating JSON with field names like `PA`, `G`, `IP`
- **Views and queries** looking for field names like `plate_appearances`, `g`, `ip`

This caused unowned players with stats to not appear on the index page and other issues.

## Solution: Constants + Model Methods

### 1. Constants File (`ulmg/constants.py`)

All field names are now defined in a single location:

```python
HITTING_STATS = {
    'PLATE_APPEARANCES': 'PA',
    'AT_BATS': 'AB',
    'GAMES': 'G',
    # ... etc
}

PITCHING_STATS = {
    'GAMES': 'G',
    'INNINGS_PITCHED': 'IP',
    'GAMES_STARTED': 'GS',
    # ... etc
}
```

### 2. Model Methods (`PlayerStatSeason`)

Access stats through descriptive methods instead of direct JSON access:

```python
# OLD - error-prone direct access
player_stat.hit_stats.get('PA')
player_stat.pitch_stats.get('G')

# NEW - safe method access
player_stat.get_hitting_stat('PLATE_APPEARANCES')
player_stat.get_pitching_stat('GAMES')

# Even better - semantic methods
player_stat.has_hitting_stats()
player_stat.has_pitching_stats()
```

### 3. QuerySet Methods

Filter using QuerySet methods instead of JSON field lookups:

```python
# OLD - error-prone
PlayerStatSeason.objects.filter(hit_stats__PA__gte=1)

# NEW - safe and descriptive
PlayerStatSeason.objects.with_hitting_stats()
PlayerStatSeason.objects.with_pitching_stats(min_games=5)
```

## Updated Files

### Scripts
- `live_update_stats_from_fg_stats.py` - Uses constants for field names
- Future scripts should import and use constants

### Views
- `site.py` - Fixed field name mismatches, added comments showing new methods

### Models
- `models.py` - Added stat access methods and custom QuerySet

## Usage Guidelines

### For Data Loading Scripts

```python
from ulmg.constants import HITTING_STATS, PITCHING_STATS, META_FIELDS

# When building stats dictionaries, use constants
stats_dict = {
    HITTING_STATS['PLATE_APPEARANCES']: pa_value,
    HITTING_STATS['GAMES']: games_value,
    META_FIELDS['TYPE']: 'majors',
}
```

### For Views and Queries

```python
# Method 1: Use model methods (recommended)
if player_stat.has_hitting_stats():
    pa = player_stat.get_hitting_stat('PLATE_APPEARANCES')

# Method 2: Use QuerySet methods (recommended)
hitters = PlayerStatSeason.objects.with_hitting_stats()

# Method 3: Direct JSON access (if needed, use constants)
from ulmg.constants import HITTING_STATS
pa_field = f"hit_stats__{HITTING_STATS['PLATE_APPEARANCES']}"
players = PlayerStatSeason.objects.filter(**{f"{pa_field}__gte": 1})
```

### For Templates

Access stats through model methods:

```django
{% if player_stat.has_hitting_stats %}
    PA: {{ player_stat.get_hitting_stat:'PLATE_APPEARANCES' }}
{% endif %}
```

## Benefits

1. **Single Source of Truth**: All field names defined in one place
2. **Compile-time Safety**: Typos in constant names cause immediate errors
3. **Descriptive**: Method names are self-documenting
4. **Maintainable**: Changes to field structure only require updating constants
5. **Backward Compatible**: Existing JSON field access still works

## Migration Strategy

1. **Immediate**: Fixed critical mismatches in index view
2. **Ongoing**: Update other views to use new methods as needed
3. **Future**: All new code should use constants and methods
4. **Eventually**: Gradually migrate all direct JSON access to use methods

This architecture ensures that field name mismatches between data loading and data querying cannot happen again. 