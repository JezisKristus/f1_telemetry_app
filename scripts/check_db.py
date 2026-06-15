import sqlite3
import sys
from pathlib import Path

# Resolve DB path relative to project
db_path = Path(__file__).resolve().parents[1] / "database" / "f1_telemetry.db"

if not db_path.exists():
    print(f"Database file not found: {db_path}")
    sys.exit(1)

print(f"Checking database: {db_path}")
print(f"Size: {db_path.stat().st_size} bytes")
print(f"Last modified: {db_path.stat().st_mtime}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

def table_count(name):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {name}")
        return cur.fetchone()[0]
    except Exception as e:
        return f"error: {e}"

for t in ("sessions", "laps", "telemetry", "setups"):
    print(f"{t}: {table_count(t)} rows")

print('\nLast 5 telemetry rows:')
try:
    cur.execute('SELECT id, session_uid, speed, throttle, brake, steer, gear FROM telemetry ORDER BY id DESC LIMIT 5')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print('No telemetry rows yet')
except Exception as e:
    print('Could not query telemetry:', e)

print('\nLast 5 laps rows:')
try:
    cur.execute('SELECT lap_id, session_uid, car_index, lap_time_ms FROM laps ORDER BY lap_time_ms DESC LIMIT 5')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print('No laps rows yet')
except Exception as e:
    print('Could not query laps:', e)

print('\nRecent sessions:')
try:
    cur.execute('SELECT session_uid, track_id, session_type FROM sessions ORDER BY rowid DESC LIMIT 5')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(r)
    else:
        print('No sessions yet')
except Exception as e:
    print('Could not query sessions:', e)

conn.close()

