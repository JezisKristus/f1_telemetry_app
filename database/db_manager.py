import sqlite3
import os
import shutil
import time
import logging


logger = logging.getLogger(__name__)


class DBManager:
    def __init__(self, db_name="f1_telemetry.db"):
        # Safely resolve the directory of this script to store the DB locally
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(current_dir, db_name)

        # ensure directory exists (defensive)
        try:
            os.makedirs(current_dir, exist_ok=True)
        except OSError:
            # If creating the directory fails, let sqlite raise a useful error later
            logger.exception("Failed to ensure database directory exists: %s", current_dir)

        # Try to connect. If the DB file is missing it will be created by sqlite3.
        # If the file exists but is corrupted, detect it and recreate a fresh DB
        self.conn = None
        self.cursor = None
        try:
            self._connect()
            self._ensure_tables()
        except sqlite3.DatabaseError as e:
            # Common case: "file is not a database" or other corruption
            logger.warning("Database error on open/setup: %s", e)
            # Move corrupt DB aside and recreate
            try:
                timestamp = int(time.time())
                corrupt_name = f"{self.db_path}.corrupt.{timestamp}"
                shutil.move(self.db_path, corrupt_name)
                logger.warning("Moved corrupt DB to %s and will recreate a fresh DB.", corrupt_name)
            except Exception:
                logger.exception("Failed to move corrupt DB file. Proceeding to attempt recreate anyway.")

            # Retry connecting to a new DB file
            self._connect()
            self._ensure_tables()

    def _connect(self):
        # Encapsulate connect so we can retry cleanly
        # check_same_thread=False allows our UDP listener thread to write to it
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self.cursor = self.conn.cursor()

    def _ensure_tables(self):
        # Verify that expected tables exist; if not, (re)create them.
        try:
            cur = self.cursor
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {row[0] for row in cur.fetchall()}
            required = {"sessions", "laps", "telemetry", "setups"}
            if not required.issubset(existing):
                logger.info("Missing tables detected (%s). Creating tables...", required - existing)
                self.setup_tables()
        except sqlite3.DatabaseError:
            # Propagate to caller to handle (e.g. treat as corruption)
            raise

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
                yaw REAL DEFAULT 0.0,
                g_forces REAL DEFAULT 0.0
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