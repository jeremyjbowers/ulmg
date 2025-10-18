#!/usr/bin/env bash
set -euo pipefail

# Syncs the /public directory to a DigitalOcean Spaces bucket path.
# Requires AWS CLI v2 configured for the Spaces endpoint, or endpoint override via flags.

PUBLIC_DIR=${PUBLIC_DIR:-public}
BUCKET=${BUCKET:-static-theulmg}
REGION=${AWS_S3_REGION_NAME:-nyc3}
ENDPOINT_URL=${AWS_S3_ENDPOINT_URL:-https://${REGION}.digitaloceanspaces.com}
DEST_PREFIX=${DEST_PREFIX:-public}

: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/bin}"
cd "$PROJECT_ROOT"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found. Install AWS CLI v2 first." >&2
  exit 1
fi

echo "Syncing ${PUBLIC_DIR}/ to s3://${BUCKET}/${DEST_PREFIX}/ via ${ENDPOINT_URL}"
aws --endpoint-url "$ENDPOINT_URL" s3 sync \
  "$PUBLIC_DIR/" "s3://${BUCKET}/${DEST_PREFIX}/" \
  --acl public-read \
  --delete \
  --cache-control max-age=31536000,public

echo "Sync complete."


