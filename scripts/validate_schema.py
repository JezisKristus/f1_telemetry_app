#!/usr/bin/env python
"""Validate that all SQL queries in logger match the DB schema."""

import sqlite3
import re
from pathlib import Path

# Parse database schema
db_path = Path(__file__).parent.parent / "database" / "f1_telemetry.db"
if not db_path.exists():
    print(f"⚠️  Database not found at {db_path}, will use fresh schema from db_manager")
    # Import db_manager to get schema
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from database.db_manager import DBManager
    db = DBManager(db_path=str(db_path))
else:
    conn = sqlite3.connect(str(db_path), timeout=10)
    db = None

# Get table schemas
def get_table_columns(db_file):
    """Extract column names from all tables."""
    conn = sqlite3.connect(str(db_file), timeout=10)
    cursor = conn.cursor()

    tables = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table_name,) in cursor.fetchall():
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        tables[table_name] = columns

    conn.close()
    return tables

# Parse all SQL queries from logger
logger_path = Path(__file__).parent.parent / "telemetry" / "logger.py"
logger_content = logger_path.read_text(encoding='utf-8')

# Extract all SQL queries (rough regex - finds quoted strings)
sql_pattern = r'"((?:INSERT|UPDATE|DELETE|SELECT)[^"]+)"'
matches = re.findall(sql_pattern, logger_content)

print("=" * 80)
print("SCHEMA VALIDATION REPORT")
print("=" * 80)

# Get tables
tables = get_table_columns(db_path)

print(f"\n📊 Found {len(tables)} tables in database:")
for table, cols in sorted(tables.items()):
    print(f"  • {table}: {sorted(cols)}")

print(f"\n🔍 Found {len(matches)} SQL queries in logger.py:")

errors = []
for i, sql in enumerate(matches, 1):
    print(f"\n  Query {i}:")
    print(f"    {sql[:70]}{'...' if len(sql) > 70 else ''}")

    # Extract table name
    table_match = re.search(r'(INSERT INTO|UPDATE|DELETE FROM)\s+(\w+)', sql)
    if table_match:
        table_name = table_match.group(2)
        if table_name not in tables:
            error = f"    ❌ Table '{table_name}' does not exist!"
            print(f"    {error}")
            errors.append(error)
        else:
            # Extract column names
            if 'INSERT' in sql:
                cols_match = re.search(r'\(([\w_,\s]+)\)\s*VALUES', sql)
                if cols_match:
                    cols = [c.strip() for c in cols_match.group(1).split(',')]
                    missing = set(cols) - tables[table_name]
                    if missing:
                        error = f"    ❌ Missing columns in {table_name}: {missing}"
                        print(f"    {error}")
                        errors.append(error)
                    else:
                        print(f"    ✅ All columns exist in {table_name}")
            elif 'UPDATE' in sql:
                cols_match = re.findall(r'SET\s+([\w_]+)\s*=', sql)
                missing = set(cols_match) - tables[table_name]
                if missing:
                    error = f"    ❌ Missing columns in {table_name}: {missing}"
                    print(f"    {error}")
                    errors.append(error)
                else:
                    print(f"    ✅ All columns exist in {table_name}")

print("\n" + "=" * 80)
if errors:
    print(f"❌ Found {len(errors)} ERRORS:")
    for error in errors:
        print(error)
    exit(1)
else:
    print("✅ All SQL queries are compatible with schema!")
    exit(0)


