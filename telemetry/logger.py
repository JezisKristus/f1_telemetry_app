import logging
import queue
import socket
import struct
import sys
import threading
import time

from telemetry.packets import HEADER_FMT, HEADER_SIZE
from telemetry.packets.car_damage import parse_car_damage
from telemetry.packets.car_setup import parse_setup_packet
from telemetry.packets.car_status import parse_car_status
from telemetry.packets.car_telemetry import parse_car_telemetry
from telemetry.packets.lap_data import parse_lap_packet
from telemetry.packets.motion import parse_motion_packet
from telemetry.packets.session import parse_session_packet

logger = logging.getLogger(__name__)


class TelemetryLogger:
    def __init__(self, db_manager, port=20777, forwarder=None):
        self.db = db_manager
        self.port = port
        self.ip = "127.0.0.1"
        self.is_running = False
        self.forwarder = forwarder

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.db_queue = queue.Queue()
        self.packet_counter = 0
        self.last_packet_time = time.time()
        self.player_lap_distance = 0.0
        self._packet_lock = threading.Lock()

        self._packet_counts = {}
        self._log_interval = 500

        # Per-car lap tracking for completion detection
        self._prev_lap_num = {}
        self._last_lap_time = {}
        self._last_sectors = {}
        self._player_status = {}
        self._motion_cache = []
        self._live_timing = {}

        try:
            self.sock.bind((self.ip, self.port))
            self._is_bound = True
            threading.Thread(target=self._database_worker, daemon=True).start()
        except OSError as e:
            print(f"❌ CRITICAL ERROR: Could not bind to port {self.port}. ({e})")
            sys.exit(1)

    def _database_worker(self):
        while True:
            batch = []
            try:
                while len(batch) < 200:
                    try:
                        batch.append(self.db_queue.get(timeout=0.01))
                    except Exception:
                        break
            except Exception:
                logger.exception("Error retrieving items from queue")

            if batch:
                try:
                    for query, params in batch:
                        self.db.cursor.execute(query, params)
                    self.db.conn.commit()
                except Exception:
                    logger.exception("Database bulk-write error")
                    try:
                        self.db.conn.rollback()
                    except Exception:
                        logger.exception("Failed to rollback after database error")

    def start_listening(self):
        self.is_running = True
        logger.info("🏎️  F1 25 Logger started. Listening on UDP port %d ...", self.port)

        total = 0
        while self.is_running:
            try:
                data, _ = self.sock.recvfrom(4096)
                total += 1
                self.last_packet_time = time.time()

                if self.forwarder:
                    self.forwarder.forward(data)

                if len(data) < HEADER_SIZE:
                    continue

                self.route_packet(data)

                if total % self._log_interval == 0:
                    logger.info(
                        "📡 %d packets received. Breakdown: %s",
                        total, dict(sorted(self._packet_counts.items())),
                    )
            except OSError as e:
                if self.is_running:
                    logger.error("OSError receiving UDP data: %s", e)
            except Exception:
                logger.exception("Unexpected error in receive loop.")

    def stop(self):
        self.is_running = False
        try:
            self.sock.close()
        except OSError:
            pass

    def route_packet(self, data: bytes):
        header = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
        packet_format = header[0]
        packet_id = header[5]
        session_uid = header[6]
        session_time = header[7]
        player_car_index = header[10]

        if packet_format != 2025:
            return

        self._packet_counts[packet_id] = self._packet_counts.get(packet_id, 0) + 1
        with self._packet_lock:
            self.packet_counter += 1

        suid = str(session_uid)
        self.db_queue.put((
            "INSERT OR IGNORE INTO sessions "
            "(session_uid, track_id, weather, ai_difficulty, session_type, player_car_index) "
            "VALUES (?, 0, 0, 0, 0, ?)",
            (suid, player_car_index),
        ))

        if packet_id == 0:
            self._handle_motion_data(data, HEADER_SIZE, player_car_index, session_uid, session_time)
        elif packet_id == 1:
            self._handle_session_data(data, HEADER_SIZE, session_uid)
        elif packet_id == 2:
            self._handle_lap_data(data, HEADER_SIZE, player_car_index, session_uid)
        elif packet_id == 5:
            self._handle_car_setup(data, HEADER_SIZE, player_car_index, session_uid)
        elif packet_id == 6:
            self._handle_car_telemetry(data, HEADER_SIZE, player_car_index, session_uid, session_time)
        elif packet_id == 7:
            self._handle_car_status(data, HEADER_SIZE, player_car_index, session_uid)
        elif packet_id == 10:
            self._handle_car_damage(data, HEADER_SIZE, player_car_index, session_uid)

    def get_and_reset_packet_count(self):
        with self._packet_lock:
            val = self.packet_counter
            self.packet_counter = 0
            return val

    def get_connection_health(self):
        with self._packet_lock:
            rate = self.packet_counter
        elapsed = time.time() - self.last_packet_time
        return {"packet_rate": rate, "seconds_since_last": elapsed, "connected": elapsed < 3.0}

    def get_motion_cache(self):
        with self._packet_lock:
            return list(self._motion_cache)

    def get_live_timing(self, player_index=0):
        with self._packet_lock:
            return dict(self._live_timing.get(player_index, {}))

    def get_player_status(self):
        with self._packet_lock:
            return dict(self._player_status)

    # -----------------------------------------------------------------------
    # Packet handlers
    # -----------------------------------------------------------------------

    def _handle_motion_data(self, data, offset, player_index, session_uid, session_time):
        cars = parse_motion_packet(data, offset)
        with self._packet_lock:
            self._motion_cache = [
                {"car_index": c["car_index"], "x": c["world_x"], "z": c["world_z"],
                 "yaw": c["yaw"], "speed": (c["velocity_x"] ** 2 + c["velocity_z"] ** 2) ** 0.5}
                for c in cars
            ]

        player = next((c for c in cars if c["car_index"] == player_index), None)
        if not player:
            return

        self.db_queue.put((
            "INSERT INTO telemetry (session_uid, lap_distance, throttle, brake, speed, steer, gear, "
            "yaw, g_lat, g_long, session_time) VALUES (?, ?, 0, 0, ?, 0, 0, ?, ?, ?, ?)",
            (str(session_uid), self.player_lap_distance,
             int((player["velocity_x"] ** 2 + player["velocity_z"] ** 2) ** 0.5),
             player["yaw"], player["g_lat"], player["g_long"], session_time),
        ))

    def _handle_session_data(self, data, offset, session_uid):
        session = parse_session_packet(data, offset)
        if not session:
            return
        self.db_queue.put((
            "UPDATE sessions SET track_id=?, weather=?, session_type=?, track_name=?, session_type_name=? "
            "WHERE session_uid=?",
            (session["track_id"], session["weather"], session["session_type"],
             session["track_name"], session["session_type_name"], str(session_uid)),
        ))

    def _handle_lap_data(self, data, offset, player_index, session_uid):
        cars = parse_lap_packet(data, offset)
        if not cars:
            return

        suid = str(session_uid)
        for car in cars:
            car_idx = car["car_index"]
            current_lap_num = car["current_lap_num"]
            last_lap_time = car["last_lap_time_ms"]
            sector_1 = car["sector_1_ms"]
            sector_2 = car["sector_2_ms"]

            if car_idx == player_index:
                self.player_lap_distance = car["lap_distance"]
                with self._packet_lock:
                    self._live_timing[car_idx] = {
                        "current_lap_num": current_lap_num,
                        "current_lap_time_ms": car["current_lap_time_ms"],
                        "last_lap_time_ms": last_lap_time,
                        "best_lap_time_ms": self._live_timing.get(car_idx, {}).get("best_lap_time_ms", 0),
                        "sector_1_ms": sector_1,
                        "sector_2_ms": sector_2,
                        "position": car["position"],
                        "delta_front_ms": car["delta_front_ms"],
                        "lap_distance": car["lap_distance"],
                    }
                    if last_lap_time > 0:
                        best = self._live_timing[car_idx].get("best_lap_time_ms", 0)
                        if best == 0 or last_lap_time < best:
                            self._live_timing[car_idx]["best_lap_time_ms"] = last_lap_time

            state_key = (suid, car_idx)
            prev_lap_num = self._prev_lap_num.get(state_key, 0)
            prev_last_lap = self._last_lap_time.get(state_key, 0)

            # In-progress lap row (updated every packet)
            in_progress_id = f"{suid}_{car_idx}_{current_lap_num}"
            self.db_queue.put((
                "INSERT OR REPLACE INTO laps (lap_id, session_uid, car_index, sector_1_ms, sector_2_ms, "
                "sector_3_ms, tire_compound, wear_end_pct, lap_time_ms, position, delta_front_ms, is_valid) "
                "VALUES (?, ?, ?, ?, ?, 0, 0, 0.0, 0, ?, ?, 0)",
                (in_progress_id, suid, car_idx, sector_1, sector_2,
                 car["position"], car["delta_front_ms"]),
            ))

            # Lap completion: lap number incremented OR lastLapTimeInMS changed to new value
            completed_lap_num = None
            completed_time = None
            completed_s1 = sector_1
            completed_s2 = sector_2

            if current_lap_num > prev_lap_num and prev_lap_num > 0 and last_lap_time > 0:
                completed_lap_num = prev_lap_num
                completed_time = last_lap_time
                sectors = self._last_sectors.get(state_key, {})
                completed_s1 = sectors.get("s1", sector_1)
                completed_s2 = sectors.get("s2", sector_2)
            elif last_lap_time > 0 and last_lap_time != prev_last_lap:
                completed_lap_num = max(1, current_lap_num - 1) if current_lap_num > 1 else current_lap_num
                completed_time = last_lap_time
                sectors = self._last_sectors.get(state_key, {})
                completed_s1 = sectors.get("s1", sector_1)
                completed_s2 = sectors.get("s2", sector_2)

            if completed_lap_num and completed_time and completed_time > 0:
                sector_3 = max(0, completed_time - completed_s1 - completed_s2)
                completed_id = f"{suid}_{car_idx}_{completed_lap_num}"
                compound = self._player_status.get("compound", 0) if car_idx == player_index else 0
                self.db_queue.put((
                    "INSERT OR REPLACE INTO laps (lap_id, session_uid, car_index, sector_1_ms, sector_2_ms, "
                    "sector_3_ms, tire_compound, lap_time_ms, position, delta_front_ms, is_valid) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                    (completed_id, suid, car_idx, completed_s1, completed_s2, sector_3, compound,
                     completed_time, car["position"], car["delta_front_ms"]),
                ))

            self._last_sectors[state_key] = {"s1": sector_1, "s2": sector_2}
            self._prev_lap_num[state_key] = current_lap_num
            if last_lap_time > 0:
                self._last_lap_time[state_key] = last_lap_time

    def _handle_car_setup(self, data, offset, player_index, session_uid):
        setup = parse_setup_packet(data, offset, player_index)
        if not setup:
            return
        lap_num = self._prev_lap_num.get((str(session_uid), player_index), 0)
        lap_id = f"{session_uid}_{player_index}_{lap_num}"
        self.db_queue.put((
            "INSERT INTO setups (session_uid, lap_id, front_wing, rear_wing, suspension_geometry, tire_pressures) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(session_uid), lap_id, setup["front_wing"], setup["rear_wing"],
             setup["suspension_geometry"], setup["tire_pressures"]),
        ))

    def _handle_car_telemetry(self, data, offset, player_index, session_uid, session_time):
        telem = parse_car_telemetry(data, offset, player_index)
        if not telem:
            return

        status = self._player_status
        steer = status.get("steer", 0.0)
        ers_mode = status.get("ers_deploy_mode", 0)

        self.db_queue.put((
            "INSERT INTO telemetry (session_uid, lap_distance, throttle, brake, speed, steer, gear, "
            "session_time, drs, ers_mode, temp_sur_fl, temp_sur_fr, temp_sur_rl, temp_sur_rr, "
            "temp_core_fl, temp_core_fr, temp_core_rl, temp_core_rr) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(session_uid), self.player_lap_distance, telem["throttle"], telem["brake"],
             telem["speed"], steer, telem["gear"], session_time, telem["drs"], ers_mode,
             telem["temp_sur_fl"], telem["temp_sur_fr"], telem["temp_sur_rl"], telem["temp_sur_rr"],
             telem["temp_core_fl"], telem["temp_core_fr"], telem["temp_core_rl"], telem["temp_core_rr"]),
        ))

        with self._packet_lock:
            if player_index in self._live_timing:
                self._live_timing[player_index]["temp_sur_fl"] = telem.get("temp_sur_fl", 0.0)
                self._live_timing[player_index]["temp_sur_fr"] = telem.get("temp_sur_fr", 0.0)
                self._live_timing[player_index]["temp_sur_rl"] = telem.get("temp_sur_rl", 0.0)
                self._live_timing[player_index]["temp_sur_rr"] = telem.get("temp_sur_rr", 0.0)
                self._live_timing[player_index]["temp_core_fl"] = telem.get("temp_core_fl", 0.0)
                self._live_timing[player_index]["temp_core_fr"] = telem.get("temp_core_fr", 0.0)
                self._live_timing[player_index]["temp_core_rl"] = telem.get("temp_core_rl", 0.0)
                self._live_timing[player_index]["temp_core_rr"] = telem.get("temp_core_rr", 0.0)

    def _handle_car_status(self, data, offset, player_index, session_uid):
        status = parse_car_status(data, offset, player_index)
        if not status:
            return
        with self._packet_lock:
            self._player_status = status

        compound = status["actual_tyre_compound"]
        lap_num = self._prev_lap_num.get((str(session_uid), player_index), 0)
        if lap_num > 0:
            lap_id = f"{session_uid}_{player_index}_{lap_num}"
            self.db_queue.put((
                "UPDATE laps SET tire_compound=? WHERE lap_id=?",
                (compound, lap_id),
            ))

        with self._packet_lock:
            if player_index in self._live_timing:
                self._live_timing[player_index]["tire_compound"] = compound
                self._live_timing[player_index]["tyres_age_laps"] = status["tyres_age_laps"]
                self._live_timing[player_index]["fuel_remaining_laps"] = status["fuel_remaining_laps"]
                self._live_timing[player_index]["ers_deploy_mode"] = status["ers_deploy_mode"]

    def _handle_car_damage(self, data, offset, player_index, session_uid):
        damage = parse_car_damage(data, offset, player_index)
        if not damage:
            return

        suid = str(session_uid)
        avg_wear = (damage["wear_fl"] + damage["wear_fr"] + damage["wear_rl"] + damage["wear_rr"]) / 4.0
        lap_num = self._prev_lap_num.get((suid, player_index), 0)
        lap_id = f"{suid}_{player_index}_{lap_num}"

        self.db_queue.put((
            "UPDATE laps SET wear_end_pct=?, wear_fl=?, wear_fr=?, wear_rl=?, wear_rr=? "
            "WHERE lap_id=?",
            (avg_wear, damage["wear_fl"], damage["wear_fr"], damage["wear_rl"], damage["wear_rr"], lap_id),
        ))

        with self._packet_lock:
            if player_index in self._live_timing:
                self._live_timing[player_index]["wear"] = damage
