import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parents[1] / "database" / "f1_telemetry.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        session_uid TEXT PRIMARY KEY,
        track_id INTEGER,
        weather INTEGER,
        ai_difficulty INTEGER,
        session_type INTEGER
    )
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS laps (
        lap_id TEXT PRIMARY KEY,
        session_uid TEXT,
        car_index INTEGER,
        sector_1_ms INTEGER,
        sector_2_ms INTEGER,
        sector_3_ms INTEGER,
        tire_compound INTEGER,
        wear_end_pct REAL,
        lap_time_ms INTEGER
    )
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_uid TEXT,
        lap_distance REAL,
        throttle REAL,
        brake REAL,
        speed INTEGER,
        steer REAL,
        gear INTEGER,
        yaw REAL DEFAULT 0.0,
        g_forces REAL DEFAULT 0.0
    )
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS setups (
        session_uid TEXT,
        front_wing INTEGER,
        rear_wing INTEGER,
        suspension_geometry TEXT,
        tire_pressures TEXT
    )
''')

conn.commit()
conn.close()
print(f"Ensured tables exist in {db_path}")

