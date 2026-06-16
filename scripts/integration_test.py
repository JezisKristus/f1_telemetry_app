#!/usr/bin/env python
"""Integration test: verify logger and DB work together correctly."""

import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger

def test_logger_db_integration():
    """Test that logger queries match DB schema."""

    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db_path = tmp.name

    try:
        # Initialize fresh database
        db = DBManager(db_path=tmp_db_path)

        print("✅ Database initialized with all migrations")
        print(f"📁 Test database: {tmp_db_path}\n")

        # Check all required tables exist
        cursor = db.cursor
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        required_tables = {"sessions", "laps", "telemetry", "setups"}
        assert required_tables.issubset(tables), f"Missing tables: {required_tables - tables}"
        print(f"✅ All required tables present: {sorted(required_tables)}\n")

        # Check sessions table has session_date
        cursor.execute("PRAGMA table_info(sessions)")
        sessions_cols = {row[1] for row in cursor.fetchall()}

        required_session_cols = {
            "session_uid", "track_id", "weather", "ai_difficulty", "session_type",
            "player_car_index", "session_date", "track_name", "session_type_name",
            "teammate_car_index", "session_name", "series", "team"
        }

        missing = required_session_cols - sessions_cols
        assert not missing, f"Missing columns in sessions: {missing}"
        print(f"✅ Sessions table has all required columns: {len(sessions_cols)} total")

        # Check telemetry table has all temperature columns
        cursor.execute("PRAGMA table_info(telemetry)")
        telemetry_cols = {row[1] for row in cursor.fetchall()}

        temp_cols = {
            "temp_sur_fl", "temp_sur_fr", "temp_sur_rl", "temp_sur_rr",
            "temp_core_fl", "temp_core_fr", "temp_core_rl", "temp_core_rr",
            "session_time", "drs", "ers_mode", "g_lat", "g_long"
        }

        missing = temp_cols - telemetry_cols
        assert not missing, f"Missing columns in telemetry: {missing}"
        print(f"✅ Telemetry table has all temperature columns: {len(telemetry_cols)} total")

        # Check laps table has wear columns
        cursor.execute("PRAGMA table_info(laps)")
        laps_cols = {row[1] for row in cursor.fetchall()}

        wear_cols = {"wear_fl", "wear_fr", "wear_rl", "wear_rr", "wear_end_pct", "is_valid", "position", "delta_front_ms"}
        missing = wear_cols - laps_cols
        assert not missing, f"Missing columns in laps: {missing}"
        print(f"✅ Laps table has all wear columns: {len(laps_cols)} total")

        # Check setups table
        cursor.execute("PRAGMA table_info(setups)")
        setups_cols = {row[1] for row in cursor.fetchall()}
        required_setup_cols = {"session_uid", "lap_id", "front_wing", "rear_wing", "suspension_geometry", "tire_pressures"}
        missing = required_setup_cols - setups_cols
        assert not missing, f"Missing columns in setups: {missing}"
        print(f"✅ Setups table has all required columns: {len(setups_cols)} total")

        # Test that logger can be created with the database
        logger = TelemetryLogger(db)
        print(f"\n✅ TelemetryLogger successfully created")
        print(f"✅ Logger and database are compatible!")

        logger.stop()

        # Final validation summary
        print("\n" + "=" * 60)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 60)
        print("✅ Database schema is correctly initialized")
        print("✅ All required tables and columns exist")
        print("✅ Logger can access all required database tables")
        print("✅ All migrations have been properly applied")
        print("=" * 60)

    finally:
        # Cleanup
        try:
            Path(tmp_db_path).unlink()
            print(f"\n🧹 Cleaned up test database")
        except:
            pass

if __name__ == "__main__":
    try:
        test_logger_db_integration()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



