import socket
import struct
import logging
import sys
import queue
import threading
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# F1 25 struct layouts
# ---------------------------------------------------------------------------

# Packet header — 29 bytes
# packet_format(H), gameYear(B), gameMajorVersion(B), gameMinorVersion(B),
# packetVersion(B), packetId(B), sessionUID(Q), sessionTime(f),
# frameIdentifier(I), overallFrameIdentifier(I), playerCarIndex(B), secondaryPlayerCarIndex(B)
HEADER_FMT = "<HBBBBBQfIIBB"
HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 29 bytes

# CarTelemetryData — one block per car, 60 bytes
# speed(H), throttle(f), brake(f), clutch(B), gear(b), engineRPM(H),
# drs(B), revLightsPercent(B), revLightsBitValue(H),
# brakesTemperature x4(4H), tyresSurfaceTemperature x4(4B),
# tyresInnerTemperature x4(4B), engineTemperature(H),
# tyresPressure x4(4f), surfaceType x4(4B)
CAR_TELEMETRY_FMT = "<HffBbHBBH4H4B4BH4f4B"
CAR_TELEMETRY_SIZE = struct.calcsize(CAR_TELEMETRY_FMT)  # 56 bytes
# Note: EA pads this to 60 bytes — we skip the last 4 bytes intentionally

# LapData — one block per car, variable per spec version.
# We parse only the first 8 bytes we actually need (lastLapTimeInMS, currentLapTimeInMS).
LAP_BLOCK_SIZE = 57          # EA F1 25 spec: each car's lap block is 57 bytes
LAP_CORE_FMT = "<II"         # lastLapTimeInMS(I), currentLapTimeInMS(I)
LAP_CORE_SIZE = struct.calcsize(LAP_CORE_FMT)  # 8 bytes

NUM_CARS = 20


class TelemetryLogger:
    def __init__(self, db_manager, port=20777):
        self.db = db_manager
        self.port = port
        self.ip = "127.0.0.1"
        self.is_running = False

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # --- THE NEW QUEUE SYSTEM ---
        self.db_queue = queue.Queue()
        # Packet counter and lock for monitor access (heartbeat)
        self.packet_counter = 0
        self.player_lap_distance = 0.0  # <--- Track lap distance from Packet 2
        self._packet_lock = threading.Lock()

        # Diagnostic counts per packet id
        self._packet_counts = {}
        self._log_interval = 500

        try:
            self.sock.bind((self.ip, self.port))
            self._is_bound = True

            # Start the background database worker immediately
            threading.Thread(target=self._database_worker, daemon=True).start()

        except OSError as e:
            print(f"❌ CRITICAL ERROR: Could not bind to port {self.port}. ({e})")
            sys.exit(1)

    def _database_worker(self):
        """Runs in the background, scooping up rows and saving them in massive, fast batches."""
        while True:
            batch = []
            # Grab up to 200 items from the memory queue at once, with timeout
            try:
                while len(batch) < 200:
                    try:
                        # Use timeout to prevent busy-waiting
                        batch.append(self.db_queue.get(timeout=0.01))
                    except Exception:
                        # Queue timeout or empty - proceed to flush if we have items
                        break
            except Exception:
                logger.exception("Error retrieving items from queue")

            if batch:
                try:
                    for query, params in batch:
                        self.db.cursor.execute(query, params)
                    # ONE single hard-drive commit for up to 200 rows!
                    self.db.conn.commit()
                except Exception:
                    logger.exception("Database bulk-write error")
                    # Attempt to rollback to maintain database integrity
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
                data, _ = self.sock.recvfrom(2048)
                total += 1

                if len(data) < HEADER_SIZE:
                    logger.debug("Packet too short to be a valid F1 header (%d bytes), skipping.", len(data))
                    continue

                self.route_packet(data)

                # Periodic heartbeat so you know the loop is alive
                if total % self._log_interval == 0:
                    logger.info(
                        "📡 %d packets received. Breakdown by packet_id: %s",
                        total,
                        dict(sorted(self._packet_counts.items())),
                    )

            except OSError as e:
                logger.error("OSError receiving UDP data: %s", e)
            except Exception:
                logger.exception("Unexpected error in receive loop.")

    def route_packet(self, data: bytes):
        header = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
        packet_format    = header[0]   # Should be 2025
        packet_id        = header[5]
        session_uid      = header[6]
        player_car_index = header[10]

        if packet_format != 2025:
            return

        # Count for diagnostics
        self._packet_counts[packet_id] = self._packet_counts.get(packet_id, 0) + 1

        # increment packet_counter (heartbeat) in a thread-safe manner
        try:
            with self._packet_lock:
                self.packet_counter += 1
        except Exception as e:
            # Log thread lock issues but don't fail silently
            logger.warning("Failed to acquire packet lock: %s", e)
        if self.packet_counter % 1200 == 0:
            logger.info("📡 Telemetry flowing perfectly... (%d total packets processed)", self.packet_counter)

        # Ensure a session row exists (enqueue, cheap no-op after first time)
        self.db_queue.put((
            "INSERT OR IGNORE INTO sessions (session_uid, track_id, weather, ai_difficulty, session_type) VALUES (?, 0, 0, 0, 0)",
            (str(session_uid),)
        ))

        if packet_id == 0:
            self._handle_motion_data(data, HEADER_SIZE, player_car_index, session_uid)
        elif packet_id == 2:
            self._handle_lap_data(data, HEADER_SIZE, player_car_index, session_uid)
        elif packet_id == 6:
            self._handle_car_telemetry(data, HEADER_SIZE, player_car_index, session_uid)
        elif packet_id == 10:
            self._handle_car_damage(data, HEADER_SIZE, player_car_index, session_uid)

    def get_and_reset_packet_count(self):
        """Return number of packets seen since last call and reset the counter.

        Thread-safe; used by external monitor threads.
        """
        with self._packet_lock:
            val = self.packet_counter
            self.packet_counter = 0
            return val

    # -----------------------------------------------------------------------
    # Packet handlers
    # -----------------------------------------------------------------------

    def _handle_motion_data(self, data: bytes, offset: int, player_index: int, session_uid: int):
        # Placeholder — G-forces and suspension will go here in Phase 2
        pass

    def _handle_lap_data(self, data: bytes, offset: int, player_index: int, session_uid: int):
        # Minimum payload needed for all NUM_CARS cars
        required = offset + (NUM_CARS * LAP_BLOCK_SIZE)
        if len(data) < required:
            logger.warning(
                "PacketLapData too short: got %d bytes, need %d. Skipping.", len(data), required
            )
            return

        try:
            # Extended lap format to extract sector times and current lap number
            # I=lastLap, I=currentLap, H=sec1MS, B=sec1Min, H=sec2MS, B=sec2Min,
            # H=sec3Time, H=deltaFront, H=deltaLeader, f=lapDistance, I=totalDistance,
            # f=safetyCarDelta, B=carPos, B=currentLapNum
            lap_struct_fmt = "<IIHBHBHHfIfBB"

            for car_idx in range(NUM_CARS):
                car_offset = offset + (car_idx * LAP_BLOCK_SIZE)
                chunk = data[car_offset: car_offset + struct.calcsize(lap_struct_fmt)]
                lap_data = struct.unpack(lap_struct_fmt, chunk)

                current_lap_time = lap_data[1]
                sector_1_ms = lap_data[2]
                sector_2_ms = lap_data[4]
                current_lap_num = lap_data[11]

                # If this is YOUR car, update the memory variable
                if car_idx == player_index:
                    self.player_lap_distance = lap_data[9]

                lap_id = f"{session_uid}_{car_idx}_{current_lap_num}"

                # Enqueue individual row — worker will batch-commit
                self.db_queue.put((
                    "INSERT OR REPLACE INTO laps (lap_id, session_uid, car_index, sector_1_ms, sector_2_ms, sector_3_ms, tire_compound, wear_end_pct, lap_time_ms) VALUES (?, ?, ?, ?, ?, 0, 0, 0.0, ?)",
                    (lap_id, str(session_uid), car_idx, sector_1_ms, sector_2_ms, current_lap_time)
                ))

        except struct.error:
            logger.exception("struct.error unpacking lap data (packet may be malformed).")
        except Exception:
            logger.exception("DB error queueing lap records.")

    def _handle_car_telemetry(self, data: bytes, offset: int, player_index: int, session_uid: int):
        # F1 25 PacketCarTelemetryData places each car's block sequentially after the header.
        # We only care about the player's car.
        player_offset = offset + (player_index * CAR_TELEMETRY_SIZE)
        required = player_offset + CAR_TELEMETRY_SIZE

        if len(data) < required:
            logger.warning(
                "PacketCarTelemetryData too short for player car: got %d bytes, need %d.",
                len(data), required,
            )
            return

        try:
            fields = struct.unpack_from(CAR_TELEMETRY_FMT, data, player_offset)
            # Field order per F1 25 spec:
            # [0] speed (H)
            # [1] throttle (f)   — 0.0 to 1.0
            # [2] brake (f)      — 0.0 to 1.0
            # [3] clutch (B)     — 0 to 100
            # [4] gear (b)       — -1 (reverse), 0 (neutral), 1-8
            # [5] engineRPM (H)
            # [9-12] brakesTemperature (4H)
            # [13-16] tyresSurfaceTemperature (4B)
            # [17-20] tyresInnerTemperature (4B)
            speed    = fields[0]
            throttle = fields[1]
            brake    = fields[2]
            gear     = fields[4]
            # steer is NOT in CarTelemetryData — it comes from CarStatusData or MotionData
            steer    = 0.0

            # Extract tire temperatures
            temp_sur_fl = fields[13]
            temp_sur_fr = fields[14]
            temp_sur_rl = fields[15]
            temp_sur_rr = fields[16]
            temp_core_fl = fields[17]
            temp_core_fr = fields[18]
            temp_core_rl = fields[19]
            temp_core_rr = fields[20]

            # Enqueue the telemetry row; background worker will commit
            self.db_queue.put((
                "INSERT INTO telemetry (session_uid, lap_distance, throttle, brake, speed, steer, gear, temp_sur_fl, temp_sur_fr, temp_sur_rl, temp_sur_rr, temp_core_fl, temp_core_fr, temp_core_rl, temp_core_rr) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(session_uid), self.player_lap_distance, throttle, brake, speed, steer, gear, temp_sur_fl, temp_sur_fr, temp_sur_rl, temp_sur_rr, temp_core_fl, temp_core_fr, temp_core_rl, temp_core_rr),
            ))

        except struct.error:
            logger.exception("struct.error unpacking car telemetry (packet may be malformed).")
        except Exception:
            logger.exception("DB error queueing micro-telemetry snapshot.")

    def _handle_car_damage(self, data: bytes, offset: int, player_index: int, session_uid: int):
        # F1 25 PacketCarDamageData: Each car's damage block is 10 bytes
        # First 4 bytes are tyresWear (4 uint8s)
        CAR_DAMAGE_BLOCK_SIZE = 10
        TIRES_WEAR_FMT = "<4B"  # 4 uint8s for FL, FR, RL, RR

        player_offset = offset + (player_index * CAR_DAMAGE_BLOCK_SIZE)
        required = player_offset + struct.calcsize(TIRES_WEAR_FMT)

        if len(data) < required:
            logger.warning(
                "PacketCarDamageData too short for player car: got %d bytes, need %d.",
                len(data), required,
            )
            return

        try:
            # Extract tire wear percentages for the player's car
            tires_wear = struct.unpack_from(TIRES_WEAR_FMT, data, player_offset)
            # tires_wear[0] = FL (front-left)
            wear_fl = tires_wear[0]

            # Update the most recent lap with tire wear data
            # We need to find the current lap_id based on session_uid and player's current lap number
            # For simplicity, we'll use a generic update that targets the latest lap entry
            # In a production system, you might track the current lap number separately
            self.db_queue.put((
                "UPDATE laps SET wear_end_pct = ? WHERE session_uid = ? AND car_index = ? AND lap_id IN (SELECT lap_id FROM laps WHERE session_uid = ? AND car_index = ? ORDER BY lap_id DESC LIMIT 1)",
                (wear_fl, str(session_uid), player_index, str(session_uid), player_index)
            ))

        except struct.error:
            logger.exception("struct.error unpacking car damage data (packet may be malformed).")
        except Exception:
            logger.exception("DB error updating tire wear.")

