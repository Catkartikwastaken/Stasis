#!/bin/bash
# STASIS — Database Backup Script
# Backs up the SQLite database

set -e

DB_PATH="${STASIS_DB:-/var/stasis/stasis.db}"
BACKUP_DIR="/var/stasis/backups"
DATE=$(date +%Y-%m-%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "$BACKUP_DIR/stasis_$DATE.db"
    echo "Backup created: $BACKUP_DIR/stasis_$DATE.db"

    # Keep only last 30 backups
    ls -t "$BACKUP_DIR"/stasis_*.db | tail -n +31 | xargs -r rm
    echo "Old backups cleaned."
else
    echo "Database not found at $DB_PATH"
    exit 1
fi
