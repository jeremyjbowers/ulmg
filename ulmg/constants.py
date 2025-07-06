# Constants for PlayerStatSeason JSON field names
# This ensures consistency between data loading scripts and views

# Hitting stats field names
HITTING_STATS = {
    'PLATE_APPEARANCES': 'pa',
    'AT_BATS': 'ab',
    'GAMES': 'g',
    'HITS': 'h',
    'RUNS': 'r',
    'DOUBLES': '2b',
    'TRIPLES': '3b',
    'HOME_RUNS': 'hr',
    'RBI': 'rbi',
    'STOLEN_BASES': 'sb',
    'CAUGHT_STEALING': 'cs',
    'WALKS': 'bb',
    'STRIKEOUTS': 'so',
    'BATTING_AVERAGE': 'avg',
    'ON_BASE_PERCENTAGE': 'obp',
    'SLUGGING_PERCENTAGE': 'slg',
    'OPS': 'ops',
    'WOBA': 'woba',
    'WRC_PLUS': 'wrc_plus',
    'WAR': 'war',
}

# Pitching stats field names  
PITCHING_STATS = {
    'GAMES': 'g',
    'GAMES_STARTED': 'gs',
    'WINS': 'w',
    'LOSSES': 'l',
    'SAVES': 'sv',
    'INNINGS_PITCHED': 'ip',
    'HITS': 'h',
    'RUNS': 'r',
    'EARNED_RUNS': 'er',
    'HOME_RUNS': 'hr',
    'WALKS': 'bb',
    'STRIKEOUTS': 'so',
    'ERA': 'era',
    'WHIP': 'whip',
    'FIP': 'fip',
    'WAR': 'war',
    'K_PER_9': 'k_9',
    'BB_PER_9': 'bb_9',
}

# Meta fields that appear in all stat records
META_FIELDS = {
    'TYPE': 'type',
    'TIMESTAMP': 'timestamp',
    'SCRIPT': 'script',
    'HOST': 'host',
}

# Stat thresholds for filtering
STAT_THRESHOLDS = {
    'MIN_PLATE_APPEARANCES': 1,
    'MIN_GAMES_PITCHED': 1,
    'MIN_INNINGS_PITCHED': 1,
    'MIN_GAMES_STARTED': 1,
} 