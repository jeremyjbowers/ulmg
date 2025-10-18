#!/usr/bin/env bash
set -euo pipefail

# Collects static files to DigitalOcean Spaces using django-storages.
# Uses the DO App Platform settings module which already enables S3Boto3Storage.

# Required env vars for Spaces auth (S3-compatible)
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"

# Optional: override bucket/endpoint with env if needed (these are read by settings)
# export AWS_STORAGE_BUCKET_NAME=static-theulmg
# export AWS_S3_REGION_NAME=nyc3
# export AWS_S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/bin}"
cd "$PROJECT_ROOT"

echo "Running collectstatic with DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
django-admin collectstatic --noinput

echo "collectstatic complete."


