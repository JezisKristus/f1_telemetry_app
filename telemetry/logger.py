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
            # Grab up to 200 items from the memory queue at once
            while not self.db_queue.empty() and len(batch) < 200:
                batch.append(self.db_queue.get())

            if batch:
                try:
                    for query, params in batch:
                        self.db.cursor.execute(query, params)
                    # ONE single hard-drive commit for up to 200 rows!
                    self.db.conn.commit()
                except Exception:
                    logger.exception("Database bulk-write error")
            else:
                # If no data is waiting, rest the thread for 10ms
                time.sleep(0.01)

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
        except Exception:
            # best-effort increment
            self.packet_counter += 1
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
            for car_idx in range(NUM_CARS):
                car_offset = offset + (car_idx * LAP_BLOCK_SIZE)
                last_lap_ms, current_lap_ms = struct.unpack_from(LAP_CORE_FMT, data, car_offset)

                lap_id = f"{session_uid}_{car_idx}"

                # Enqueue individual row — worker will batch-commit
                self.db_queue.put((
                    "INSERT OR REPLACE INTO laps (lap_id, session_uid, car_index, sector_1_ms, sector_2_ms, sector_3_ms, tire_compound, wear_end_pct, lap_time_ms) VALUES (?, ?, ?, 0, 0, 0, 0, 0.0, ?)",
                    (lap_id, str(session_uid), car_idx, current_lap_ms)
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
            speed    = fields[0]
            throttle = fields[1]
            brake    = fields[2]
            gear     = fields[4]
            # steer is NOT in CarTelemetryData — it comes from CarStatusData or MotionData
            steer    = 0.0

            # Enqueue the telemetry row; background worker will commit
            self.db_queue.put((
                "INSERT INTO telemetry (session_uid, lap_distance, throttle, brake, speed, steer, gear) VALUES (?, 0.0, ?, ?, ?, ?, ?)",
                (str(session_uid), throttle, brake, speed, steer, gear),
            ))

        except struct.error:
            logger.exception("struct.error unpacking car telemetry (packet may be malformed).")
        except Exception:
            logger.exception("DB error queueing micro-telemetry snapshot.")
