import socket
import struct
import logging
import sys
import queue
import threading
import time

logger = logging.getLogger(__name__)


class TelemetryLogger:
    def __init__(self, db_manager, port=20777):
        self.db = db_manager
        self.port = port
        self.ip = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # --- THE NEW QUEUE SYSTEM ---
        self.db_queue = queue.Queue()
        # Packet counter and lock for monitor access
        self.packet_counter = 0
        self._packet_lock = threading.Lock()

        try:
            self.sock.bind((self.ip, self.port))
            self._is_bound = True
            self.is_running = False

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
                except Exception as e:
                    logger.exception("Database bulk-write error: %s", e)
            else:
                # If no data is waiting, rest the thread for 10ms
                time.sleep(0.01)

    def start_listening(self):
        self.is_running = True
        logger.info("🏎️ Native F1 25 Logger started. Listening on UDP %s...", self.port)

        while self.is_running:
            try:
                data, _ = self.sock.recvfrom(2048)
                if len(data) >= 29:
                    self.route_packet(data)
            except OSError as e:
                logger.error("Error receiving UDP data: %s", e)

    def route_packet(self, data):
        header_format = "<HBBBBBQfIIBB"
        header_size = struct.calcsize(header_format)
        header_data = struct.unpack(header_format, data[:header_size])

        packet_format = header_data[0]
        packet_id = header_data[5]
        session_uid = header_data[6]
        player_car_index = header_data[10]

        if packet_format != 2025:
            return

        # THE HEARTBEAT (Will now fire precisely every ~10 seconds at 30Hz)
        # increment counter in a thread-safe manner
        try:
            with self._packet_lock:
                self.packet_counter += 1
        except Exception:
            # keep going even if counting fails
            self.packet_counter += 1
        if self.packet_counter % 1200 == 0:
            logger.info(f"📡 Telemetry flowing perfectly... ({self.packet_counter} total packets processed)")

        # Send Session Init to Queue
        self.db_queue.put((
            "INSERT OR IGNORE INTO sessions (session_uid, track_id, weather, ai_difficulty, session_type) VALUES (?, 0, 0, 0, 0)",
            (str(session_uid),)
        ))

        if packet_id == 0:
            self._handle_motion_data(data, header_size, player_car_index, session_uid)
        elif packet_id == 2:
            self._handle_lap_data(data, header_size, player_car_index, session_uid)
        elif packet_id == 6:
            self._handle_car_telemetry(data, header_size, player_car_index, session_uid)

    def get_and_reset_packet_count(self):
        """Return number of packets seen since last call and reset the counter.

        Thread-safe; used by external monitor threads.
        """
        with self._packet_lock:
            val = self.packet_counter
            self.packet_counter = 0
            return val

    def _handle_lap_data(self, data, offset, player_index, session_uid):
        car_lap_struct_size = 57
        for car_idx in range(20):
            car_offset = offset + (car_idx * car_lap_struct_size)
            lap_struct_fmt = "<II"
            chunk = data[car_offset: car_offset + 8]
            lap_data = struct.unpack(lap_struct_fmt, chunk)

            current_lap_time = lap_data[1]
            lap_id = f"{session_uid}_{car_idx}"

            # TOSS INTO QUEUE, NO COMMIT HERE
            self.db_queue.put((
                '''INSERT OR REPLACE INTO laps (lap_id, session_uid, car_index, sector_1_ms, sector_2_ms, sector_3_ms, tire_compound, wear_end_pct, lap_time_ms)
                   VALUES (?, ?, ?, 0, 0, 0, 0, 0.0, ?)''',
                (lap_id, str(session_uid), car_idx, current_lap_time)
            ))

    def _handle_car_telemetry(self, data, offset, player_index, session_uid):
        car_telemetry_struct_size = 60
        player_offset = offset + (player_index * car_telemetry_struct_size)

        player_struct_fmt = "<Hffffb"
        chunk = data[player_offset: player_offset + struct.calcsize(player_struct_fmt)]
        telemetry_data = struct.unpack(player_struct_fmt, chunk)

        speed = telemetry_data[0]
        throttle = telemetry_data[1]
        steer = telemetry_data[2]
        brake = telemetry_data[3]
        gear = telemetry_data[5]

        # TOSS INTO QUEUE, NO COMMIT HERE
        self.db_queue.put((
            "INSERT INTO telemetry (session_uid, lap_distance, throttle, brake, speed, steer, gear) VALUES (?, 0.0, ?, ?, ?, ?, ?)",
            (str(session_uid), throttle, brake, speed, steer, gear)
        ))