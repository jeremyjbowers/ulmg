# S3 Data Sharing Setup

This document describes the new S3-based data sharing functionality for FanGraphs data files.

## Overview

The system now supports uploading and downloading FanGraphs data files to/from DigitalOcean Spaces (S3-compatible storage). This solves the IP blocking issue by allowing the production server to download FanGraphs data and share it with development environments.

## Required Environment Variables

```bash
# Required for S3 functionality
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=your_bucket_name
AWS_S3_ENDPOINT_URL=https://your-region.digitaloceanspaces.com
AWS_S3_REGION_NAME=your-region
```

## Commands Updated

### Download Commands (Upload to S3)
These commands now save files both locally and upload to S3:

- `live_download_fg_stats` - Downloads current season stats
- `live_download_fg_rosters` - Downloads current roster data  
- `archive_download_fg_stats <season>` - Downloads historical stats

**Options:**
- `--local-only` - Skip S3 upload, save locally only

### Update Commands (Read from S3)
These commands now read from local files first, then fall back to S3:

- `live_update_stats_from_fg_stats` - Updates player stats from FanGraphs data
- `archive_update_stats_from_fg_stats <season>` - Updates historical stats
- `live_update_status_from_fg_rosters` - Updates roster status from FanGraphs data

## Data Organization in S3

Files are stored under the `fangraphs-data/` prefix:

```
fangraphs-data/
├── 2024/
│   ├── fg_mlb_bat.json
│   ├── fg_mlb_pit.json
│   ├── fg_milb_bat.json
│   ├── fg_milb_pit.json
│   ├── fg_college_bat.json
│   ├── fg_college_pit.json
│   ├── fg_npb_bat.json
│   ├── fg_npb_pit.json
│   ├── fg_kbo_bat.json
│   └── fg_kbo_pit.json
├── 2025/
│   └── (same structure)
└── rosters/
    ├── SF_roster.json
    ├── LAD_roster.json
    └── (all team rosters)
```

## Typical Workflow

### Production Server (can access FanGraphs):
1. Run download commands to fetch latest data
2. Data is automatically uploaded to S3
3. Local processing continues as normal

### Development Environment (blocked by FanGraphs):
1. Run update commands as usual
2. If local files don't exist, they're automatically downloaded from S3
3. Processing continues with the shared data

## Error Handling

- If S3 is not configured, commands fall back to local-only mode
- If S3 files don't exist, commands report the missing data
- All S3 operations are non-blocking - local functionality continues to work

## Technical Details

The `S3DataManager` class in `ulmg/utils.py` handles all S3 operations:

- `save_and_upload_json(data, path)` - Save locally and upload to S3
- `get_file_content(path)` - Get content from local file or S3
- `upload_file(local_path)` - Upload existing local file to S3
- `download_file(s3_key, local_path)` - Download S3 file to local path

## Migration Notes

- Existing local files continue to work without changes
- S3 functionality is additive - no breaking changes
- Commands maintain backward compatibility
- All commands include appropriate logging for S3 operations 