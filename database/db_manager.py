import sqlite3
import os


class DBManager:
    def __init__(self, db_name="f1_telemetry.db"):
        # Safely resolve the directory of this script to store the DB locally
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(current_dir, db_name)

        # check_same_thread=False allows our UDP listener thread to write to it
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.setup_tables()

    def setup_tables(self):
        # Master session data
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_uid TEXT PRIMARY KEY,
                track_id INTEGER,
                weather INTEGER,
                ai_difficulty INTEGER,
                session_type INTEGER
            )
        ''')

        # Grid-wide lap data (Low-frequency)
        self.cursor.execute('''
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

        # Player/Teammate Micro-telemetry (High-frequency)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uid TEXT,
                lap_distance REAL,
                throttle REAL,
                brake REAL,
                speed INTEGER,
                steer REAL,
                gear INTEGER,
                yaw REAL,
                g_forces REAL
            )
        ''')

        # Setup and aerodynamic data
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS setups (
                session_uid TEXT,
                front_wing INTEGER,
                rear_wing INTEGER,
                suspension_geometry TEXT,
                tire_pressures TEXT
            )
        ''')
        self.conn.commit()