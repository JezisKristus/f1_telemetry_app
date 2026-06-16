#!/usr/bin/env python
"""Deep validation: check all SQL queries used throughout the app."""

import sqlite3
import re
from pathlib import Path

def get_table_columns(db_file):
    """Extract column names from all tables."""
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    tables = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table_name,) in cursor.fetchall():
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cursor.fetchall()}
        tables[table_name] = columns

    conn.close()
    return tables

def extract_queries_from_files(root_dir):
    """Extract all SQL queries from Python files."""
    queries = []
    for py_file in Path(root_dir).rglob("*.py"):
        try:
            content = py_file.read_text(encoding='utf-8')
            # Look for execute() calls with SQL
            pattern = r'\.execute\(["\']([^"\']+)'
            matches = re.findall(pattern, content)
            for match in matches:
                if any(kw in match.upper() for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                    queries.append((str(py_file), match))
        except Exception as e:
            print(f"⚠️  Could not read {py_file}: {e}")

    return queries

def validate_query(sql, tables):
    """Validate a single SQL query against schema."""
    try:
        # Extract table name
        table_match = re.search(r'(?:FROM|INTO|UPDATE)\s+(\w+)', sql, re.IGNORECASE)
        if not table_match:
            return None, None

        table_name = table_match.group(1).lower()
        if table_name not in tables:
            return f"❌ Table '{table_name}' not found", table_name

        table_cols = tables[table_name]

        # Extract referenced columns
        cols_to_check = set()

        # Find columns in SELECT
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE)
        if select_match:
            cols_part = select_match.group(1)
            for col in re.findall(r'\b([a-zA-Z_]\w*)\b', cols_part):
                if col.upper() not in ['COUNT', 'MIN', 'MAX', 'SUM', 'AVG', 'AS', 'DISTINCT']:
                    cols_to_check.add(col)

        # Find columns in UPDATE SET
        update_match = re.findall(r'SET\s+(\w+)\s*=', sql, re.IGNORECASE)
        cols_to_check.update(update_match)

        # Find columns in INSERT
        insert_match = re.search(r'INSERT\s+INTO\s+\w+\s*\((.*?)\)', sql, re.IGNORECASE)
        if insert_match:
            for col in re.findall(r'\b(\w+)\b', insert_match.group(1)):
                cols_to_check.add(col)

        # Find columns in WHERE
        where_match = re.search(r'WHERE\s+(.*?)(?:LIMIT|ORDER|GROUP|HAVING|$)', sql, re.IGNORECASE)
        if where_match:
            for col in re.findall(r'\b([a-zA-Z_]\w*)\b', where_match.group(1)):
                if col not in ['AND', 'OR', 'NOT', 'IN', 'LIKE', 'IS', 'NULL', 'TRUE', 'FALSE']:
                    cols_to_check.add(col)

        # Check if all columns exist
        missing = cols_to_check - table_cols
        if missing:
            return f"❌ Missing columns in {table_name}: {missing}", table_name

        return "✅", table_name
    except Exception as e:
        return f"⚠️  Error validating: {e}", None

# Main
db_path = Path(__file__).parent.parent / "database" / "f1_telemetry.db"
tables = get_table_columns(db_path)

print("=" * 90)
print("DEEP SQL VALIDATION ACROSS ENTIRE APP")
print("=" * 90)

print(f"\n📊 Database tables and columns:")
for table, cols in sorted(tables.items()):
    if table != 'sqlite_sequence':
        print(f"  • {table}: {len(cols)} columns")

queries = extract_queries_from_files(Path(__file__).parent.parent)
print(f"\n🔍 Found {len(queries)} SQL queries:\n")

errors = []
by_table = {}

for file_path, sql in queries:
    status, table = validate_query(sql, tables)

    file_short = file_path.replace(str(Path(__file__).parent.parent), "")

    if status and status.startswith("❌"):
        errors.append(f"{file_short}:\n  {sql[:70]}...\n  {status}")

    if table:
        if table not in by_table:
            by_table[table] = []
        by_table[table].append(status)

print("Validation by table:")
for table in sorted(by_table.keys()):
    ok_count = sum(1 for s in by_table[table] if s == "✅")
    total = len(by_table[table])
    print(f"  • {table}: {ok_count}/{total} queries OK")

print("\n" + "=" * 90)
if errors:
    print(f"❌ Found {len(errors)} ERRORS:\n")
    for error in errors:
        print(error)
        print()
    exit(1)
else:
    print("✅ All SQL queries validated successfully!")
    exit(0)

