#!/usr/bin/env bash
# =====================================================================
# PostgreSQL Database Inspection Script
# Author: Kopano Kaas Nielsen (System Analyst)
# Purpose: Display current PostgreSQL status, structure, and statistics.
# =====================================================================

# CONFIGURATION --------------------------------------------------------
PG_USER="cams_user"
PG_DB="cams"
PG_HOST="localhost"
PG_PORT="5432"

# Optional: read password from environment (set before running)
# export PGPASSWORD="your_password"

# CHECKS ---------------------------------------------------------------
echo "🔍 PostgreSQL Inspection Report"
echo "Host: $PG_HOST | DB: $PG_DB | User: $PG_USER"
echo "Timestamp: $(date)"
echo "------------------------------------------------------------"

# 1️⃣ Service state
echo "🟢 Checking PostgreSQL service status..."
systemctl is-active postgresql-15 &>/dev/null && echo "✅ PostgreSQL is running" || echo "❌ PostgreSQL is NOT running"
echo "------------------------------------------------------------"

# 2️⃣ Connection test
echo "🔗 Testing connection..."
psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" -c "\conninfo" || { echo "❌ Connection failed!"; exit 1; }
echo "------------------------------------------------------------"

# 3️⃣ List all databases and sizes
echo "💾 Databases and Sizes:"
psql -h "$PG_HOST" -U "$PG_USER" -d postgres -x -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size FROM pg_database WHERE datistemplate = false;"
echo "------------------------------------------------------------"

# 4️⃣ Show schemas in the target database
echo "🏗️  Schemas in '$PG_DB':"
psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" -c "\dn+"
echo "------------------------------------------------------------"

# 5️⃣ List tables with row count and size
echo "📋 Tables in '$PG_DB' (schema-qualified):"
psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" -c "
SELECT schemaname || '.' || relname AS table,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       n_live_tup AS approx_rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
"
echo "------------------------------------------------------------"

# 6️⃣ Top 10 largest tables
echo "🏋️  Top 10 Largest Tables:"
psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" -c "
SELECT schemaname || '.' || relname AS table,
       pg_size_pretty(pg_total_relation_size(relid)) AS size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
"
echo "------------------------------------------------------------"

# 7️⃣ Active connections and client info
echo "👥 Active Connections:"
psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" -c "
SELECT pid, usename, datname, client_addr, application_name, state, query
FROM pg_stat_activity
WHERE state != 'idle';
"
echo "------------------------------------------------------------"

# 8️⃣ Summary
echo "✅ Inspection complete."
echo "------------------------------------------------------------"

