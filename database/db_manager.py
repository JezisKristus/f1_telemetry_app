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
            else:
                # Tables exist, but check if we need to add missing columns (schema migration)
                self._migrate_telemetry_schema()
        except sqlite3.DatabaseError:
            # Propagate to caller to handle (e.g. treat as corruption)
            raise

    def _migrate_telemetry_schema(self):
        """Add missing columns to telemetry table if they don't exist."""
        try:
            cur = self.cursor
            # Get existing columns in telemetry table
            cur.execute("PRAGMA table_info(telemetry)")
            existing_columns = {row[1] for row in cur.fetchall()}

            # Define the columns we need
            required_columns = {
                "temp_sur_fl", "temp_sur_fr", "temp_sur_rl", "temp_sur_rr",
                "temp_core_fl", "temp_core_fr", "temp_core_rl", "temp_core_rr"
            }

            # Add missing columns
            missing = required_columns - existing_columns
            if missing:
                logger.info("Adding missing columns to telemetry table: %s", missing)
                for col in missing:
                    try:
                        # Use parameterized query to avoid SQL injection
                        query = f"ALTER TABLE telemetry ADD COLUMN {col} REAL DEFAULT 0.0"
                        self.cursor.execute(query)
                        logger.info("Added column %s to telemetry table", col)
                    except sqlite3.OperationalError as e:
                        # Column might already exist, or other issue
                        logger.warning("Could not add column %s: %s", col, e)
                self.conn.commit()
        except Exception:
            logger.exception("Error during telemetry schema migration")

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
                g_forces REAL DEFAULT 0.0,
                temp_sur_fl REAL DEFAULT 0.0,
                temp_sur_fr REAL DEFAULT 0.0,
                temp_sur_rl REAL DEFAULT 0.0,
                temp_sur_rr REAL DEFAULT 0.0,
                temp_core_fl REAL DEFAULT 0.0,
                temp_core_fr REAL DEFAULT 0.0,
                temp_core_rl REAL DEFAULT 0.0,
                temp_core_rr REAL DEFAULT 0.0
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