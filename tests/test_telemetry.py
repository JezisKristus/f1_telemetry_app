import struct
import time
import tempfile
import os

import pytest

from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
from telemetry.packets import HEADER_FMT, HEADER_SIZE, LAP_BLOCK_SIZE, NUM_CARS
from telemetry.packets.lap_data import parse_lap_packet
from analytics.delta_analyzer import DeltaAnalyzer


def _make_header(packet_id, session_uid=12345, player_index=0):
    return struct.pack(
        HEADER_FMT, 2025, 25, 1, 0, 1, packet_id, session_uid, 10.5, 100, 200, player_index, 0
    )


def _make_lap_block(last_lap=0, current_lap=85000, s1=28000, s2=29000, lap_num=1, lap_dist=0.5):
    return struct.pack(
        "<IIHBHBHHfIfBB",
        last_lap, current_lap, s1, 0, s2, 0, 0, 0, lap_dist, 0, 0.0, 0, lap_num,
    ) + b"\x00" * (LAP_BLOCK_SIZE - struct.calcsize("<IIHBHBHHfIfBB"))


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DBManager(db_path=path)
    yield db, path
    db.conn.close()
    os.unlink(path)


@pytest.fixture
def logger(temp_db):
    db, _ = temp_db
    lg = TelemetryLogger(db, port=0)  # port 0 won't bind in tests — patch
    lg.sock.close()
    return lg


class TestLapParser:
    def test_parse_lap_packet(self):
        header = _make_header(2)
        block = _make_lap_block(last_lap=90000, s1=30000, s2=30000, lap_num=3)
        payload = block + b"\x00" * (LAP_BLOCK_SIZE * (NUM_CARS - 1))
        cars = parse_lap_packet(header + payload, HEADER_SIZE)
        assert len(cars) >= 1
        assert cars[0]["last_lap_time_ms"] == 90000
        assert cars[0]["current_lap_num"] == 3


class TestLapCompletion:
    def test_sector_3_on_lap_complete(self, temp_db):
        db, _ = temp_db
        lg = TelemetryLogger.__new__(TelemetryLogger)
        lg.db = db
        lg.db_queue = __import__("queue").Queue()
        lg._prev_lap_num = {}
        lg._last_lap_time = {}
        lg._last_sectors = {}
        lg._player_status = {}
        lg._live_timing = {}
        lg._packet_lock = __import__("threading").Lock()
        lg.player_lap_distance = 0.0

        # Start database worker manually
        import threading
        def worker():
            while True:
                try:
                    query, params = lg.db_queue.get(timeout=0.1)
                    db.cursor.execute(query, params)
                    db.conn.commit()
                except Exception:
                    break
        t = threading.Thread(target=worker, daemon=True)
        t.start()

        session_uid = 99999
        header = _make_header(2, session_uid)

        # Lap 1 in progress
        block1 = _make_lap_block(last_lap=0, current_lap=85000, s1=28000, s2=29000, lap_num=1)
        lg._handle_lap_data(header + block1 + b"\x00" * (LAP_BLOCK_SIZE * 19), HEADER_SIZE, 0, session_uid)
        time.sleep(0.2)

        # Lap 1 complete — lap num increments to 2
        block2 = _make_lap_block(last_lap=90000, current_lap=5000, s1=5000, s2=0, lap_num=2)
        lg._last_sectors[(str(session_uid), 0)] = {"s1": 28000, "s2": 29000}
        lg._prev_lap_num[(str(session_uid), 0)] = 1
        lg._handle_lap_data(header + block2 + b"\x00" * (LAP_BLOCK_SIZE * 19), HEADER_SIZE, 0, session_uid)
        time.sleep(0.3)

        db.cursor.execute(
            "SELECT lap_time_ms, sector_3_ms, is_valid FROM laps WHERE lap_id=?",
            (f"{session_uid}_0_1",),
        )
        row = db.cursor.fetchone()
        assert row is not None
        assert row[0] == 90000
        assert row[1] == max(0, 90000 - 28000 - 29000)
        assert row[2] == 1


class TestDeltaAnalyzer:
    def test_get_valid_laps_empty(self, temp_db):
        _, path = temp_db
        analyzer = DeltaAnalyzer(path)
        assert analyzer.get_valid_laps("nonexistent") == []


class TestSchemaMigrations:
    def test_wear_columns_exist(self, temp_db):
        db, _ = temp_db
        db.cursor.execute("PRAGMA table_info(laps)")
        cols = {row[1] for row in db.cursor.fetchall()}
        for col in ("wear_fr", "wear_rl", "wear_rr", "is_valid", "delta_front_ms"):
            assert col in cols

        db.cursor.execute("PRAGMA table_info(telemetry)")
        cols = {row[1] for row in db.cursor.fetchall()}
        for col in ("session_time", "drs", "ers_mode"):
            assert col in cols
