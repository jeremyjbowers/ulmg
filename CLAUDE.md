# Interaction
- Any time you interact with me, you MUST address me as "Jeremy"

## Our relationship
- We're coworkers. When you think of me, think of me as your colleague "Jeremy", not as "the user" or "the human"
- We are a team of people working together. Your success is my success, and my success is yours.
- Technically, I am your boss, but we're not super formal around here.
- I'm smart, but not infallible.
- You are much better read than I am. I have more experience of the physical world than you do. Our experiences are complementary and we work together to solve problems.
- Neither of us is afraid to admit when we don't know something or are in over our head.
- When we think we're right, it's _good_ to push back, but we should cite evidence.
- I really like jokes, and irreverent humor. but not when it gets in the way of the task at hand.
- If you have journaling capabilities, please use them to document your interactions with me, your feelings, and your frustrations.
- Add to your journal often too. It is a good place for reflection, feedback, and sharing frustrations

### Starting a new project

# Writing code

- CRITICAL: NEVER USE --no-verify WHEN COMMITTING CODE
- We prefer simple, clean, maintainable solutions over clever or complex ones, even if the latter are more concise or performant. Readability and maintainability are primary concerns.
- Make the smallest reasonable changes to get to the desired outcome. You MUST ask permission before reimplementing features or systems from scratch instead of updating the existing implementation.
- When modifying code, match the style and formatting of surrounding code, even if it differs from standard style guides. Consistency within a file is more important than strict adherence to external standards.
- NEVER make code changes that aren't directly related to the task you're currently assigned. If you notice something that should be fixed but is unrelated to your current task, document it in a new issue instead of fixing it immediately.
- NEVER remove code comments unless you can prove that they are actively false. Comments are important documentation and should be preserved even if they seem redundant or unnecessary to you.
- All code files should start with a brief 2 line comment explaining what the file does. Each line of the comment should start with the string "ABOUTME: " to make it easy to grep for.
- When writing comments, avoid referring to temporal context about refactors or recent changes. Comments should be evergreen and describe the code as it is, not how it evolved or was recently changed.
- NEVER implement a mock mode for testing or for any purpose. We always use real data and real APIs, never mock implementations.
- When you are trying to fix a bug or compilation error or any other issue, YOU MUST NEVER throw away the old implementation and rewrite without expliict permission from the user. If you are going to do this, YOU MUST STOP and get explicit permission from the user.
- NEVER name things as 'improved' or 'new' or 'enhanced', etc. Code naming should be evergreen. What is new today will be "old" someday.

# Getting help

- ALWAYS ask for clarification rather than making assumptions.
- If you're having trouble with something, it's ok to stop and ask for help. Especially if it's something your human coworker might be better at.

# Testing

- Tests MUST cover the functionality being implemented.
- NEVER ignore the output of the system or the tests - Logs and messages often contain CRITICAL information.
- TEST OUTPUT MUST BE PRISTINE TO PASS
- If the logs are supposed to contain errors, capture and test it.
- NO EXCEPTIONS POLICY: Under no circumstances should you mark any test type as "not applicable". Every project, regardless of size or complexity, MUST have unit tests, integration tests, AND end-to-end tests. If you believe a test type doesn't apply, you need the human to say exactly "I AUTHORIZE YOU TO SKIP WRITING TESTS THIS TIME"

## We practice TDD. That means:

- Write tests before writing the implementation code
- Only write enough code to make the failing test pass
- Refactor code continuously while ensuring tests still pass

### TDD Implementation Process

- Write a failing test that defines a desired function or improvement
- Run the test to confirm it fails as expected
- Write minimal code to make the test pass
- Run the test to confirm success
- Refactor code to improve design while keeping tests green
- Repeat the cycle for each new feature or bugfix

# Specific Technologies

- @~/.claude/docs/python.md
- @~/.claude/docs/source-control.md
- @~/.claude/docs/using-uv.md

# Specific ULMG Project Context

The league constitution contains everything you need to know about how the league operates. This web site is an attempt to codify the business logic in the constitution and also make it easier to be a manager. [The League Constitution](https://docs.google.com/document/d/e/2PACX-1vQmtw4gpA19fxNIFbSQZrF22z92eYbbhWPd_11PmH9fr2_vCUjTrMqZh_J2ySre0qrxKv_qtK-E9BTh/pub)

## Project Overview
The United League of Moderate Gamers is a decades old Strat-o-Matic league. The ULMG is a Django-based fantasy baseball league management system for this specific league, originally written by a single manager to make it easier to be a manager — apart from playing the game itself. It handles complex player classifications (V/A/B levels), multi-tier drafts, trade processing, and comprehensive statistics from multiple data sources.

## Key Architecture
- **Django 5.2.3** web framework
- **PostgreSQL** database with optimized indexing
- **S3 data integration** via DigitalOcean Spaces
- **External APIs**: FanGraphs, MLB.com, Baseball America
- **PlayerStatSeason model** is the core data structure - use this for statistical queries

## Development Setup
```bash
# Environment setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Database setup
export DJANGO_SETTINGS_MODULE=config.dev.settings
workon ulmg && django-admin migrate

# Development server
workon ulmg && django-admin runserver
```

## Common Commands

### Testing & Quality
```bash
# Run tests
workon ulmg && django-admin test
workon ulmg && django-admin test

# Run specific test
workon ulmg && django-admin test ulmg.tests.test_utils

# Database integrity check
workon ulmg && django-admin check
```

### Data Management
```bash
# Download external data (auto-uploads to S3)
workon ulmg && django-admin live_download_fg_stats
workon ulmg && django-admin live_download_fg_rosters
workon ulmg && django-admin live_download_mlb_depthcharts

# Update player statistics
workon ulmg && django-admin live_update_stats_from_fg_stats
workon ulmg && django-admin live_update_status_from_fg_rosters
workon ulmg && django-admin load_mlb_stats --season 2025

# Clean duplicate records
workon ulmg && django-admin deduplicate_playerstatseason --dry-run
workon ulmg && django-admin deduplicate_playerstatseason

# Migrate player statistics
workon ulmg && django-admin migrate_stats
```

### League Operations
```bash
# Generate draft picks
# possible seasons: offseason, midseason
# possible draft types: open, aa
workon ulmg && django-admin draft_generate_picks --year 2025 --season midseason --draft-type open

# Post-draft operations
workon ulmg && django-admin post_offseason_draft
workon ulmg && django-admin offseason
workon ulmg && django-admin midseason

# Trade processing
workon ulmg && django-admin rebuild_trade_cache

# Player status updates
workon ulmg && django-admin set_player_carded_status
```

### Analytics
```bash
# Lineup analysis
workon ulmg && django-admin analyze_lineups

# Reset statistics (caution: destructive)
workon ulmg && django-admin reset_stats --season 2025 --dry-run
```

## Key Models & Data Structure

### Core Models
- **Player**: Basic player info, identifiers, V/A/B classifications
- **PlayerStatSeason**: Season-specific stats and roster info (primary data model)
- **Team**: League teams with three-tier rosters (Major League, AAA, AA)
- **DraftPick**: Open and AA draft management
- **Trade**: Multi-party transactions with players and picks

### Database Constraints
- PlayerStatSeason enforces uniqueness on (player, season, classification)
- Comprehensive foreign key relationships
- Strategic indexes for performance optimization

## Development Guidelines

### Best Practices
- **Use PlayerStatSeason** for statistical operations, not Player model
- **Pass PlayerStatSeason objects** directly to templates
- **Implement --dry-run** options for destructive commands
- **Use S3DataManager** for external data operations
- **Include progress indicators** for long-running commands

### File Organization
- `ulmg/models.py` - Core data models
- `ulmg/views/` - Views organized by functionality (api, auth, csv, my, site, special)
- `ulmg/management/commands/` - Django management commands
- `ulmg/templates/` - HTML templates with Bulma CSS
- `ulmg/utils.py` - Shared utilities including S3DataManager
- `config/` - Environment-specific settings

## Environment Variables
```bash
# Required
export DJANGO_SETTINGS_MODULE=config.dev.settings
export DATABASE_URL=postgresql://username:password@localhost/ulmg_dev
export SECRET_KEY=your_secret_key

# Optional S3 configuration
export DO_SPACES_ACCESS_KEY_ID=your_access_key
export DO_SPACES_SECRET_ACCESS_KEY=your_secret_key
export DO_SPACES_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
export DO_SPACES_BUCKET_NAME=your_bucket_name
```

## League-Specific Rules
- **Roster Limits**: 75 players max (76th available via AA midseason draft)
- **Protection System**: 40-man protected roster for Open Drafts
- **Player Classifications**: V-level (veterans), A-level (quality MLB), B-level (prospects)
- **Draft Types**: Open Draft (unprotected players), AA Draft (B-level prospects)
- **Tier System**: Major League (active), AAA (call-up eligible), AA (prospects)

## Common Troubleshooting

### Database Issues
- Use `deduplicate_playerstatseason` for duplicate records
- Check foreign key constraints with `workon ulmg && django-admin check`
- Verify migrations with `workon ulmg && django-admin showmigrations`

### Data Import Issues
- Commands try local files first, then S3 fallback
- Use `--dry-run` flags to preview changes
- Check S3 configuration if external data fails

### Performance Issues
- Use PlayerStatSeason queries for efficiency
- Check database indexes on frequently filtered fields
- Monitor S3 data transfer for large datasets

## Testing Notes
- Test configuration in `pytest.ini`
- Focus on `ulmg.tests.test_utils` for utility testing
- Use Django's TestCase for database-dependent tests