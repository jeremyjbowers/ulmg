# The ULMG (Ultimate League Manager's Guide)

A comprehensive fantasy baseball league management system built for Strat-O-Matic leagues. ULMG provides advanced player tracking, draft management, trade processing, and statistical analysis capabilities that go far beyond what standard fantasy platforms offer.

## What is ULMG?

ULMG manages a unique fantasy baseball league structure with several distinctive features:

### Multi-Level Player System
- **V-Level (Veterans)**: Established MLB players who can be protected during each half-season
- **A-Level**: Quality MLB players, part of the 40-man protected roster during Open Drafts
- **B-Level**: Future prospects including minor leaguers, high school/college players, and international prospects
- Each level has different protection rules and draft eligibility

### Advanced Draft System
- **Open Drafts**: Players not on 40-man protected rosters (excludes Type V and Type A players)
- **AA Drafts**: B-level prospects and developing players, includes special 76th roster spot in midseason
- **Offseason Drafts** (March): Both Open and AA drafts, cut to 75 players afterward
- **Midseason Drafts** (July): Both Open and AA drafts, unprotected V-level players on AAA rosters exposed
- Real-time draft administration with pick tracking and trade integration

### Comprehensive Player Data
- Live MLB statistics updated throughout the season
- Historical performance across multiple seasons and leagues
- Prospect rankings from multiple sources (Baseball America, FanGraphs, etc.)
- Strat-O-Matic card ratings and defensive assignments
- Custom league-specific fields (protection status, roster assignments)

## Key Features

### Player Search and Analytics
- Advanced filtering by season, player classification (V/A/B), ownership status, and statistical thresholds
- Optimized database queries returning PlayerStatSeason objects directly (not Player objects)
- Filter results display specific season/league statistics matching the search criteria
- Real-time statistical leaderboards (HR, SB, ERA, etc.)
- Position-based player organization with sortable statistics

### Roster Management
- Three-tier roster system: Major League (active players), AAA (call-up eligible), AA (prospects)
- 75-player maximum per team (76th player available through AA midseason draft)
- 40-man protected roster of Type V and Type A players for Open Drafts
- Veteran protection system: one V-level pitcher, catcher, and position player per half-season
- All-season reserve designation for one veteran player per season
- Minimum 20 B-level prospects required on AA roster

### Trade System
- Multi-player, multi-pick trade processing
- Historical trade tracking with detailed summaries
- Real-time roster updates upon trade completion
- Trade block functionality for available players

### Draft Administration
- Live draft interfaces with real-time pick tracking
- Automated pick generation and validation
- Player search integration during drafts
- Support for compensatory and traded picks

### Data Integration
- FanGraphs statistics and projections
- Baseball America prospect rankings
- MLB.com player data and images
- Custom prospect evaluation systems

## Technical Architecture

### Database Design
The application uses an optimized database structure with:

- **Player Model**: Core player information, identifiers, V/A/B classifications, and league-specific data
- **PlayerStatSeason**: Indexed seasonal statistics for fast querying and roster eligibility
- **Team Management**: Three-tier roster assignments (Major League, AAA, AA) and ownership tracking
- **Draft System**: Open and AA draft pick management with protection rule enforcement
- **Trade Processing**: Multi-party transactions including players and draft picks

### Performance Optimizations
- Database indexes on frequently queried fields (season, ownership, player classification)
- Composite indexes for common filter combinations
- Efficient query patterns using PlayerStatSeason for statistical operations and returning them directly to templates
- Search/filter views avoid inefficient Player model conversions by working with PlayerStatSeason objects throughout
- Cached template rendering for high-traffic pages

## Local Development

### Prerequisites
- Python 3.8+ 
- PostgreSQL 12+
- Node.js (for frontend assets)
- Git

### Setup Instructions

#### 1. Clone and Environment Setup
```bash
git clone https://github.com/jeremyjbowers/ulmg.git
cd ulmg
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r new.requirements.txt  # Additional development dependencies
```

#### 3. Database Setup
```bash
# Create PostgreSQL database
createdb ulmg_dev

# Configure environment variables
export DJANGO_SETTINGS_MODULE=config.dev.settings
export DATABASE_URL=postgresql://username:password@localhost/ulmg_dev

# Run migrations
python manage.py migrate
```

#### 4. Load Initial Data
```bash
# Create superuser
python manage.py createsuperuser

# Load team and basic league data
python manage.py loaddata teams owners

# Import player statistics (if data files available)
python manage.py migrate_stats
```

#### 5. Development Server
```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000`

### Development Commands

#### Data Management
```bash
# Migrate player statistics with progress tracking
python manage.py migrate_stats

# Update player statistics from external sources
python manage.py update_stats --season 2025

# Generate prospect rankings
python manage.py import_prospect_rankings --year 2025
```

#### League Operations
```bash
# Process trades
python manage.py process_trade --trade-id 123

# Generate draft picks
python manage.py generate_picks --year 2025 --season midseason --draft-type open

# Update roster statuses
python manage.py update_rosters
```

### Configuration

#### Environment Variables
- `DJANGO_SETTINGS_MODULE`: Settings module (config.dev.settings for development)
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Django secret key
- `DEBUG`: Enable debug mode (True for development)

#### Settings Files
- `config/dev/settings.py`: Development configuration
- `config/prd/settings.py`: Production configuration  
- `config/do_app_platform/settings.py`: DigitalOcean App Platform deployment

### Testing
```bash
# Run test suite
python manage.py test

# Run specific test modules
python manage.py test ulmg.tests.test_utils
```

## Deployment

### Production Requirements
- PostgreSQL database with sufficient storage for historical statistics
- Redis for caching (optional but recommended)
- Static file hosting (AWS S3 or similar)
- Backup strategy for player and league data

### Key Considerations
- Database indexes are crucial for search performance
- PlayerStatSeason records should be migrated when updating player statistics
- Regular backups of draft and trade history
- SSL certificates for secure owner authentication

## Data Sources and Integrations

### External APIs
- **FanGraphs**: Player statistics and projections
- **MLB.com**: Official player data and roster information
- **Baseball America**: Prospect rankings and scouting reports

### Data Updates
Statistics and player information are typically updated:
- Daily during the season for active players
- Weekly during the offseason
- Immediately following trades or transactions
- Before and after draft events

## Contributing

### Code Organization
- `ulmg/models.py`: Core data models
- `ulmg/views/`: View logic organized by functionality
- `ulmg/management/commands/`: Django management commands
- `ulmg/templates/`: HTML templates with Bulma CSS framework
- `ulmg/utils.py`: Shared utility functions

### Development Guidelines
- Use PlayerStatSeason queries for statistical operations and return PlayerStatSeason objects directly to templates
- Filter/search pages should query PlayerStatSeason with indexes rather than converting to Player objects
- Maintain database indexes when adding new filter capabilities
- Follow Django best practices for model design and view organization
- Include progress reporting for long-running management commands

For questions about league rules, data sources, or development setup, contact the project maintainers.