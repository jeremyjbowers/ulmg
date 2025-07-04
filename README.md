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
- Historical performance across multiple seasons and leagues (MLB, MiLB, NPB, KBO, NCAA)
- Prospect rankings from multiple sources (Baseball America, FanGraphs, etc.)
- Strat-O-Matic card ratings and defensive assignments
- Custom league-specific fields (protection status, roster assignments)

## User-Facing Features

### Player Search and Discovery
- Advanced multi-criteria filtering by season, player classification (V/A/B), ownership status, and statistical thresholds
- Visual player level classification system with colored backgrounds (green for minor league, light blue for amateur, white for MLB)
- Real-time statistical leaderboards and sortable statistics tables
- Position-based player organization with comprehensive hitting and pitching statistics
- One-click access to external player profiles (MLB.com, FanGraphs, Baseball Reference)
- Robust player search with name, team, and position filtering

### Wishlist Management
- Large, accessible wishlist buttons with clear visual states (yellow "+" for add, green checkmark when added)
- Personal prospect tracking with custom notes and rankings
- Tier-based organization for draft preparation
- Future value assessments and scouting reports
- Mobile-friendly interface with proper touch targets

### Team Management Interface
- Clean, organized team roster displays with three-tier system (Major League, AAA, AA)
- Individual player detail pages with comprehensive statistics and biographical information
- Trade block functionality for showcasing available players
- Real-time roster composition analysis and rule compliance checking
- Historical team performance tracking and statistics

### Draft Tools
- Live draft interface with real-time pick tracking and player availability
- Integrated player search during draft sessions
- Draft preparation tools with customizable prospect rankings
- Pick trading and compensatory pick management
- Draft history and recap functionality

### Trade System
- Intuitive multi-player, multi-pick trade creation interface
- Trade validation with automatic roster compliance checking
- Historical trade tracking with detailed summaries and analysis
- Trade impact assessment and roster optimization suggestions

### Statistics and Analytics
- Season-specific statistical displays with league context
- Performance trending and year-over-year comparisons
- Advanced sabermetric integration (wRC+, FIP, xwOBA, etc.)
- Injury tracking and roster status monitoring
- Prospect development tracking with ETA and organizational rankings

### Administrative Tools
- Comprehensive league management dashboard
- Automated draft pick generation and order management
- Bulk roster operations and rule enforcement
- Trade processing with audit trails
- Player status updates and roster maintenance

## Technical Architecture

### Database Design
The application uses an optimized database structure with comprehensive constraints and indexing:

#### Core Models
- **Player Model**: Core player information, identifiers, V/A/B classifications, and league-specific data
- **PlayerStatSeason**: Season-specific statistics and roster information with unique constraints
- **Team Management**: Three-tier roster assignments (Major League, AAA, AA) and ownership tracking
- **Draft System**: Open and AA draft pick management with protection rule enforcement
- **Trade Processing**: Multi-party transactions including players and draft picks

#### Database Constraints and Integrity
- **Unique Constraints**: PlayerStatSeason records enforce uniqueness on (player, season, classification) to prevent duplicates
- **Foreign Key Relationships**: Comprehensive referential integrity across all player, team, and transaction data
- **Index Optimization**: Strategic database indexes on frequently queried combinations
- **Data Validation**: Model-level validation for league rules and roster requirements

### Performance Optimizations
- **Efficient Query Patterns**: Direct PlayerStatSeason queries avoid expensive Player model conversions
- **Composite Database Indexes**: Optimized for common filter combinations (season + ownership + classification)
- **Template Optimization**: PlayerStatSeason objects passed directly to templates without conversion overhead
- **S3 Data Caching**: External data cached in S3 for improved reliability and performance
- **Lazy Loading**: Deferred loading of heavy statistics data until needed

### Data Infrastructure

#### S3 Data Sharing System
ULMG implements a robust S3-compatible data sharing system for external statistics and roster data:

- **Automated Data Pipeline**: Download commands automatically upload data to DigitalOcean Spaces
- **Fallback Architecture**: Commands attempt local files first, then S3 if local unavailable
- **Environment Flexibility**: Production server downloads from APIs, development reads from S3
- **Data Persistence**: Historical statistics and roster snapshots preserved in cloud storage
- **API Rate Limiting Protection**: Reduces external API calls by sharing cached data

#### S3 Data Manager Features
- **Automatic Upload**: Downloaded FanGraphs and MLB data automatically uploaded to S3
- **Smart Fallback**: Local development reads from S3 when FanGraphs blocks access
- **File Verification**: Content validation and existence checking before processing
- **Error Handling**: Graceful degradation when S3 or source APIs unavailable

### Data Sources and Integrations

#### Primary Data Sources
- **FanGraphs**: Comprehensive MLB, MiLB, NPB, KBO, and college statistics and projections
- **MLB.com**: Official player data, roster information, and depth charts
- **Baseball America**: Prospect rankings and scouting reports
- **Python MLB Stats API**: Real-time player statistics and biographical data

#### Update Frequency
- **Live Statistics**: Daily updates during active season (March-October)
- **Roster Information**: Real-time updates for trades, signings, and roster moves
- **Prospect Rankings**: Updated during ranking publication cycles
- **Historical Data**: Archived and preserved for comparative analysis

## Local Development

### Prerequisites
- Python 3.8+ 
- PostgreSQL 12+
- Node.js (for frontend assets)
- Git
- S3-compatible storage access (optional for external data)

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

#### 4. S3 Configuration (Optional)
For S3 data sharing, configure environment variables:
```bash
export DO_SPACES_ACCESS_KEY_ID=your_access_key
export DO_SPACES_SECRET_ACCESS_KEY=your_secret_key
export DO_SPACES_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
export DO_SPACES_BUCKET_NAME=your_bucket_name
```

See `S3_DATA_SETUP.md` for detailed S3 configuration instructions.

#### 5. Load Initial Data
```bash
# Create superuser
python manage.py createsuperuser

# Load team and basic league data
python manage.py loaddata teams owners

# Import player statistics (if data files available)
python manage.py migrate_stats

# Clean up any duplicate PlayerStatSeason records
python manage.py deduplicate_playerstatseason --dry-run
python manage.py deduplicate_playerstatseason
```

#### 6. Development Server
```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000`

### Development Commands

#### Data Management
```bash
# Download external statistics (uploads to S3 automatically)
python manage.py live_download_fg_stats
python manage.py live_download_fg_rosters
python manage.py live_download_mlb_depthcharts

# Process statistics from local files or S3
python manage.py live_update_stats_from_fg_stats
python manage.py live_update_status_from_fg_rosters
python manage.py archive_update_stats_from_fg_stats --season 2024

# Migrate player statistics with progress tracking
python manage.py migrate_stats

# Load MLB statistics via API
python manage.py load_mlb_stats --season 2025

# Set player carded status based on MLB appearances  
python manage.py set_player_carded_status

# Clean duplicate PlayerStatSeason records
python manage.py deduplicate_playerstatseason
```

#### League Operations
```bash
# Process trades
python manage.py process_trade --trade-id 123

# Generate draft picks
python manage.py generate_picks --year 2025 --season midseason --draft-type open

# Post-draft roster updates
python manage.py post_offseason_draft
python manage.py offseason
```

#### Analytics and Maintenance
```bash
# Analyze lineup performance
python manage.py analyze_lineups

# Reset player statistics (caution: destructive)
python manage.py reset_stats --season 2025
```

### Configuration

#### Environment Variables
- `DJANGO_SETTINGS_MODULE`: Settings module (config.dev.settings for development)
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Django secret key
- `DEBUG`: Enable debug mode (True for development)
- `DO_SPACES_*`: S3-compatible storage configuration (optional)

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

## Data Integrity and Maintenance

### Database Constraints
- **PlayerStatSeason Uniqueness**: Prevents duplicate season records for the same player/classification
- **Foreign Key Integrity**: Maintains referential integrity across all relationships
- **League Rule Enforcement**: Model-level validation for roster limits and draft eligibility

### Maintenance Commands
```bash
# Identify and resolve data inconsistencies
python manage.py deduplicate_playerstatseason

# Verify database integrity
python manage.py check

# Update database indexes after model changes
python manage.py migrate
```

### Backup Strategy
- **Database Backups**: Regular PostgreSQL dumps of all league data
- **S3 Data Archival**: Historical statistics preserved in cloud storage
- **Transaction Logging**: Complete audit trail for trades and draft actions
- **Configuration Backups**: Environment and settings preservation

## Deployment

### Production Requirements
- PostgreSQL database with sufficient storage for historical statistics
- S3-compatible storage for external data caching
- SSL certificates for secure owner authentication
- Environment variable management for API keys and database credentials

### DigitalOcean App Platform Configuration
```yaml
# app.yaml example
name: ulmg
services:
- name: web
  source_dir: /
  github:
    repo: jeremyjbowers/ulmg
    branch: main
  run_command: gunicorn --worker-tmp-dir /dev/shm config.do_app_platform.asgi:application -k uvicorn.workers.UvicornWorker
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  
databases:
- name: ulmg-db
  engine: PG
  version: "12"
```

### Key Deployment Considerations
- **Database Indexes**: Essential for search performance at scale
- **S3 Configuration**: Required for external data access and caching
- **Environment Security**: Secure management of API keys and database credentials
- **SSL/TLS**: HTTPS required for authentication and data security
- **Monitoring**: Application performance and database query monitoring

## Code Organization and Development Guidelines

### Project Structure
- `ulmg/models.py`: Core data models with comprehensive relationships
- `ulmg/views/`: View logic organized by functionality (api, auth, csv, my, site, special)
- `ulmg/management/commands/`: Django management commands for data processing
- `ulmg/templates/`: HTML templates with Bulma CSS framework
- `ulmg/utils.py`: Shared utility functions including S3DataManager
- `ulmg/admin.py`: Django admin customizations for league management

### Development Best Practices
- **PlayerStatSeason Priority**: Use PlayerStatSeason queries for statistical operations
- **Direct Template Passing**: Return PlayerStatSeason objects directly to templates
- **Index Awareness**: Maintain database indexes when adding filter capabilities
- **S3 Integration**: Use S3DataManager for external data operations
- **Error Handling**: Implement graceful degradation for external service failures
- **Progress Reporting**: Include progress indicators for long-running commands

### Contributing Guidelines
- Follow Django best practices for model design and view organization
- Use PlayerStatSeason model for season-specific data rather than Player fields
- Implement proper database constraints and validation
- Include comprehensive error handling for external API integrations
- Write management commands with --dry-run options where appropriate
- Maintain documentation for new features and data sources

## League Rules and Data Model

### Roster Management Rules
- **Team Size Limits**: 75 players maximum (76th available through AA midseason draft)
- **Protection System**: 40-man protected roster for Open Drafts
- **Veteran Protections**: One V-level pitcher, catcher, and position player per half-season
- **Prospect Requirements**: Minimum 20 B-level prospects on AA roster
- **Tier Assignments**: Major League (active), AAA (call-up eligible), AA (prospects)

### Draft Eligibility
- **Open Draft**: Unprotected players (excludes V and A levels)
- **AA Draft**: B-level prospects and developing players
- **Protection Rules**: V-level players on AAA rosters become unprotected at midseason
- **Draft Order**: Determined by league standings and previous draft history

For questions about league rules, data sources, or development setup, contact the project maintainers.