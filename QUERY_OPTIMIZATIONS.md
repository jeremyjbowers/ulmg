# Database Query Optimizations for Popular Pages

This document outlines the comprehensive query optimizations implemented to improve performance on the most popular pages: index, search, and team detail views.

## Analysis Summary

The three most popular pages were analyzed for query patterns and optimization opportunities:

1. **Index Page** - Displays unowned MLB players with stats and leaderboards
2. **Search/Filter Pages** - Complex filtering on PlayerStatSeason with various criteria
3. **Team Detail Pages** - Shows team rosters with stats and relationships

## Database Index Optimizations

### Player Model Indexes Added

```python
indexes = [
    # Team filtering (heavily used in team detail views)
    models.Index(fields=['team']),
    # Name search optimization (used in search views and autocomplete)
    models.Index(fields=['name']),
    models.Index(fields=['last_name', 'first_name']),
    # Level and position filtering (used in search and filtering)
    models.Index(fields=['level', 'position']),
    models.Index(fields=['position', 'level']),
    # Ownership filtering combined with other common filters
    models.Index(fields=['is_owned', 'team']),
    models.Index(fields=['is_owned', 'level']),
    # Composite indexes for common query patterns
    models.Index(fields=['team', 'position']),
    models.Index(fields=['team', 'level', 'position']),
    # Protection status queries (used in draft views)
    models.Index(fields=['is_owned', 'level', 'is_reserve']),
]
```

### PlayerStatSeason Model Indexes Enhanced

```python
# Additional optimizations for popular query patterns
models.Index(fields=['season', 'classification', 'owned', 'player']),  # Index + player lookup
models.Index(fields=['season', 'owned', 'classification']),  # Alternative ordering for search
models.Index(fields=['owned', 'season', 'classification']),  # Ownership-first filtering
models.Index(fields=['classification', 'season', 'owned']),  # Classification-first filtering

# Protection and roster status queries
models.Index(fields=['season', 'is_35man_roster']),
models.Index(fields=['season', 'is_mlb_roster']),
models.Index(fields=['season', 'owned', 'is_35man_roster']),
```

### DraftPick Model Indexes Added

```python
indexes = [
    # Team-based queries (heavily used in team detail views)
    models.Index(fields=['team']),
    models.Index(fields=['year', 'team']),
    models.Index(fields=['year', 'season', 'team']),
    # Draft admin queries
    models.Index(fields=['year', 'season', 'draft_type']),
    # Player lookup optimization
    models.Index(fields=['player']),
    # Overall pick number for ordering
    models.Index(fields=['overall_pick_number']),
    # Common filter combinations
    models.Index(fields=['year', 'season']),
    models.Index(fields=['season', 'draft_type']),
]
```

### WishlistPlayer Model Indexes Added

```python
indexes = [
    # Wishlist-based queries (heavily used in draft prep views)
    models.Index(fields=['wishlist']),
    models.Index(fields=['wishlist', 'rank']),
    # Player ownership filtering (used in draft prep)
    models.Index(fields=['wishlist', 'player']),
    # Level filtering for draft prep
    models.Index(fields=['wishlist', 'player', 'rank']),
    # Player lookup optimization
    models.Index(fields=['player']),
    # Rank ordering optimization
    models.Index(fields=['rank']),
]
```

## Query Structure Optimizations

### Index View Optimizations

1. **Enhanced select_related**: Added deep relationships to avoid N+1 queries
   ```python
   base_stats = models.PlayerStatSeason.objects.select_related(
       'player', 'player__team', 'player__team__owner_obj', 'player__team__owner_obj__user'
   )
   ```

2. **Optimized leaderboard queries**: Added explicit LIMIT clauses for better performance
3. **Reduced redundant filtering**: Combined filters for better index utilization

### Team Detail View Optimizations

1. **Optimized player queries**: Added select_related for team relationships
2. **Improved count queries**: Used player_id IN subqueries instead of JOIN-heavy queries
3. **Efficient aggregation**: Optimized level distribution query structure

### Search/Filter View Optimizations

1. **Filter ordering**: Applied most selective filters (season, classification) first
2. **Enhanced select_related**: Added all necessary relationships upfront
3. **JSON field filtering**: Applied JSON field filters last for better performance
4. **Index-aware filtering**: Structured queries to use composite indexes effectively

## Expected Performance Improvements

### Query Performance

1. **Index scans vs Table scans**: New indexes will enable index scans for common query patterns
2. **Reduced JOIN costs**: select_related optimizations reduce database round trips
3. **Better cardinality estimation**: Composite indexes help PostgreSQL optimize query plans

### Template Rendering

1. **Eliminated N+1 queries**: select_related prevents repeated database hits during template rendering
2. **Reduced memory usage**: More efficient queries load only necessary data
3. **Faster page loads**: Fewer database operations mean faster response times

### Specific Improvements by Page

#### Index Page
- **Before**: ~8-12 queries with potential N+1 issues
- **After**: ~3-5 optimized queries with proper relationships loaded

#### Search Page
- **Before**: Complex queries without proper index utilization
- **After**: Index-optimized filtering with efficient relationship loading

#### Team Detail Page
- **Before**: Separate queries for each roster count and player relationship
- **After**: Consolidated queries with optimized aggregation

## Migration Instructions

To apply these optimizations:

1. Create and run the migration:
   ```bash
   python manage.py makemigrations --name add_performance_indexes
   python manage.py migrate
   ```

2. Monitor query performance:
   ```bash
   # Enable slow query logging in PostgreSQL
   # Monitor django.db.backends for query analysis
   ```

## Additional Optimization Opportunities

### Future Considerations

1. **Database-level optimizations**:
   - Consider partial indexes for frequently filtered boolean fields
   - Evaluate covering indexes for read-heavy query patterns
   - Monitor index usage and remove unused indexes

2. **Application-level optimizations**:
   - Implement query result caching for expensive leaderboard calculations
   - Consider pagination for large result sets
   - Add database connection pooling if not already configured

3. **JSON field optimization**:
   - Consider GIN indexes on hit_stats and pitch_stats JSON fields
   - Evaluate extracting frequently queried JSON fields to regular columns

### Monitoring and Maintenance

1. **Query monitoring**: Use Django Debug Toolbar and `django.db.backends` logging
2. **Index analysis**: Regularly check `pg_stat_user_indexes` for index usage
3. **Performance testing**: Establish baseline metrics and track improvements

## Impact Assessment

These optimizations target the most frequently accessed pages and query patterns, providing:

- **Immediate benefits**: Faster page load times for popular pages
- **Scalability improvements**: Better performance as data grows
- **User experience**: More responsive interface for search and browsing
- **Database efficiency**: Reduced CPU and I/O load on the database server

The optimizations maintain backward compatibility while significantly improving query performance through strategic indexing and query structure improvements. 