import logging
import os
import shutil
import sqlite3
import time

logger = logging.getLogger(__name__)


class DBManager:
    def __init__(self, db_name="f1_telemetry.db", db_path=None):
        if db_path:
            self.db_path = db_path
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(current_dir, db_name)

        try:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        except OSError:
            logger.exception("Failed to ensure database directory exists")

        self.conn = None
        self.cursor = None
        try:
            self._connect()
            self._ensure_tables()
        except sqlite3.DatabaseError as e:
            logger.warning("Database error on open/setup: %s", e)
            try:
                timestamp = int(time.time())
                corrupt_name = f"{self.db_path}.corrupt.{timestamp}"
                shutil.move(self.db_path, corrupt_name)
                logger.warning("Moved corrupt DB to %s and will recreate a fresh DB.", corrupt_name)
            except Exception:
                logger.exception("Failed to move corrupt DB file.")
            self._connect()
            self._ensure_tables()

    def _connect(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        self.cursor = self.conn.cursor()

    def _ensure_tables(self):
        try:
            cur = self.cursor
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {row[0] for row in cur.fetchall()}
            required = {"sessions", "laps", "telemetry", "setups"}
            if not required.issubset(existing):
                logger.info("Missing tables detected (%s). Creating tables...", required - existing)
                self.setup_tables()
            self._run_migrations()
        except sqlite3.DatabaseError:
            raise

    def _add_column_if_missing(self, table, column, col_type):
        cur = self.cursor
        cur.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cur.fetchall()}
        if column not in existing:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                logger.info("Added column %s.%s", table, column)
            except sqlite3.OperationalError as e:
                logger.warning("Could not add column %s.%s: %s", table, column, e)

    def _run_migrations(self):
        """Apply incremental schema migrations."""
        try:
            # telemetry columns
            for col, typ in [
                ("temp_sur_fl", "REAL DEFAULT 0.0"), ("temp_sur_fr", "REAL DEFAULT 0.0"),
                ("temp_sur_rl", "REAL DEFAULT 0.0"), ("temp_sur_rr", "REAL DEFAULT 0.0"),
                ("temp_core_fl", "REAL DEFAULT 0.0"), ("temp_core_fr", "REAL DEFAULT 0.0"),
                ("temp_core_rl", "REAL DEFAULT 0.0"), ("temp_core_rr", "REAL DEFAULT 0.0"),
                ("session_time", "REAL DEFAULT 0.0"), ("drs", "INTEGER DEFAULT 0"),
                ("ers_mode", "INTEGER DEFAULT 0"), ("g_lat", "REAL DEFAULT 0.0"),
                ("g_long", "REAL DEFAULT 0.0"),
            ]:
                self._add_column_if_missing("telemetry", col, typ)

            # laps columns
            for col, typ in [
                ("wear_fr", "REAL DEFAULT 0.0"), ("wear_rl", "REAL DEFAULT 0.0"),
                ("wear_rr", "REAL DEFAULT 0.0"), ("is_valid", "INTEGER DEFAULT 1"),
                ("position", "INTEGER DEFAULT 0"), ("delta_front_ms", "INTEGER DEFAULT 0"),
                ("wear_fl", "REAL DEFAULT 0.0"),
            ]:
                self._add_column_if_missing("laps", col, typ)

            # sessions columns
            for col, typ in [
                ("track_name", "TEXT DEFAULT ''"),
                ("session_type_name", "TEXT DEFAULT ''"),
                ("player_car_index", "INTEGER DEFAULT 0"),
            ]:
                self._add_column_if_missing("sessions", col, typ)

            # setups columns
            self._add_column_if_missing("setups", "lap_id", "TEXT DEFAULT ''")
            self._add_column_if_missing("setups", "id", "INTEGER")

            # index for delta queries
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_telemetry_session_distance "
                "ON telemetry (session_uid, lap_distance)"
            )
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_laps_session_car "
                "ON laps (session_uid, car_index)"
            )
            self.conn.commit()
        except Exception:
            logger.exception("Error during schema migration")

    def setup_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_uid TEXT PRIMARY KEY,
                track_id INTEGER,
                weather INTEGER,
                ai_difficulty INTEGER,
                session_type INTEGER,
                track_name TEXT DEFAULT '',
                session_type_name TEXT DEFAULT '',
                player_car_index INTEGER DEFAULT 0
            )
        ''')

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
                wear_fl REAL DEFAULT 0.0,
                wear_fr REAL DEFAULT 0.0,
                wear_rl REAL DEFAULT 0.0,
                wear_rr REAL DEFAULT 0.0,
                lap_time_ms INTEGER,
                is_valid INTEGER DEFAULT 1,
                position INTEGER DEFAULT 0,
                delta_front_ms INTEGER DEFAULT 0
            )
        ''')

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
                g_lat REAL DEFAULT 0.0,
                g_long REAL DEFAULT 0.0,
                session_time REAL DEFAULT 0.0,
                drs INTEGER DEFAULT 0,
                ers_mode INTEGER DEFAULT 0,
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

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS setups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uid TEXT,
                lap_id TEXT DEFAULT '',
                front_wing INTEGER,
                rear_wing INTEGER,
                suspension_geometry TEXT,
                tire_pressures TEXT
            )
        ''')
        self.conn.commit()

    def list_sessions(self):
        self.cursor.execute(
            "SELECT session_uid, track_name, session_type_name, track_id "
            "FROM sessions ORDER BY rowid DESC"
        )
        return self.cursor.fetchall()

    def delete_session(self, session_uid):
        for table in ("telemetry", "laps", "setups", "sessions"):
            self.cursor.execute(f"DELETE FROM {table} WHERE session_uid = ?", (session_uid,))
        self.conn.commit()
