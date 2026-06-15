import socket
import struct
import logging
import sys


logger = logging.getLogger(__name__)


class TelemetryLogger:
    def __init__(self, db_manager, port=20777):
        self.db = db_manager
        self.port = port
        self.ip = "127.0.0.1"
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Tell Windows: "If this port was recently used but the program crashed, let me take it over."
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.sock.bind((self.ip, self.port))
            self._is_bound = True
            self.is_running = False
        except OSError as e:
            print(f"❌ CRITICAL ERROR: Could not bind to port {self.port}. It is blocked by another app. ({e})")
            # Force the script to stop completely so it doesn't trigger the 10022 loop
            sys.exit(1)

    def start_listening(self):
        """Start listening for F1 telemetry UDP packets.

        Socket binding already occurred in __init__, so we can go straight to receiving.
        """
        self.is_running = True
        logger.info("🏎️ Native F1 25 Logger started. Listening on UDP %s...", self.port)

        # Main receive loop
        while self.is_running:
            try:
                # Receive up to 2048 bytes (standard UDP buffer size for F1)
                data, _ = self.sock.recvfrom(2048)

                # Ensure the packet is at least large enough to be a valid F1 header
                if len(data) >= 29:
                    self.route_packet(data)
            except OSError as e:
                logger.error("Error receiving UDP data: %s", e)
            except Exception as e:
                logger.exception("Unexpected error receiving UDP data: %s", e)

    def route_packet(self, data):
        # --- THE F1 25 HEADER DECODER ---
        header_format = "<HBBBBBQfIIBB"
        header_size = struct.calcsize(header_format)  # Exactly 29 bytes

        # Unpack the first 29 bytes into a readable tuple
        header_data = struct.unpack(header_format, data[:header_size])

        # Extract the critical routing variables
        packet_format = header_data[0]  # Should be 2025
        packet_id = header_data[5]  # The type of data
        session_uid = header_data[6]  # Unique ID for the current race/session
        player_car_index = header_data[10]  # Which car array index is you (0-21)

        # Drop any packets that aren't from the correct game format
        if packet_format != 2025:
            return

        # Ensure the session row exists anchors our relational data before writing logs
        # Uses INSERT OR IGNORE so it only runs once per unique session UID
        try:
            # Ensure a session row exists; use a compact SQL string so analyzers parse it correctly
            self.db.cursor.execute(
                "INSERT OR IGNORE INTO sessions (session_uid, track_id, weather, ai_difficulty, session_type) VALUES (?, 0, 0, 0, 0)",
                (str(session_uid),),
            )
        except Exception as e:
            logger.exception("Database error initializing session: %s", e)

        # Route the remaining binary data to the specific unpackers
        if packet_id == 0:
            self._handle_motion_data(data, header_size, player_car_index, session_uid)
        elif packet_id == 2:
            self._handle_lap_data(data, header_size, player_car_index, session_uid)
        elif packet_id == 6:
            self._handle_car_telemetry(data, header_size, player_car_index, session_uid)

    def _handle_motion_data(self, data, offset, player_index, session_uid):
        # We will decode the high-frequency G-forces and suspension data here later
        pass

    def _handle_lap_data(self, data, offset, player_index, session_uid):
        # Each car's lap data block in F1 25 is exactly 57 bytes long.
        car_lap_struct_size = 57

        try:
            # Loop through all 20 cars on the grid to save low-frequency tracking data
            for car_idx in range(20):
                car_offset = offset + (car_idx * car_lap_struct_size)

                # Format string blueprint snippet for parsing core timing variables:
                # I = lastLapTimeInMS (uint32), I = currentLapTimeInMS (uint32)
                lap_struct_fmt = "<II"

                chunk = data[car_offset: car_offset + 8]
                lap_data = struct.unpack(lap_struct_fmt, chunk)

                current_lap_time = lap_data[1]
                lap_id = f"{session_uid}_{car_idx}"

                self.db.cursor.execute('''
                    INSERT OR REPLACE INTO laps (lap_id, session_uid, car_index, sector_1_ms, sector_2_ms, sector_3_ms, tire_compound, wear_end_pct, lap_time_ms)
                    VALUES (?, ?, ?, 0, 0, 0, 0, 0.0, ?)
                ''', (lap_id, str(session_uid), car_idx, current_lap_time))

            self.db.conn.commit()
        except Exception as e:
            logger.exception("Database error writing lap records: %s", e)

    def _handle_car_telemetry(self, data, offset, player_index, session_uid):
        # Each car's telemetry block in F1 25 is exactly 60 bytes long.
        car_telemetry_struct_size = 60
        player_offset = offset + (player_index * car_telemetry_struct_size)

        # Unpack telemetry variables matching your specific database schema:
        # H = speed, f = throttle, f = steer, f = brake, b = gear (skipping remaining array offsets)
        player_struct_fmt = "<Hffffb"
        chunk = data[player_offset: player_offset + struct.calcsize(player_struct_fmt)]
        telemetry_data = struct.unpack(player_struct_fmt, chunk)

        speed = telemetry_data[0]
        throttle = telemetry_data[1]
        steer = telemetry_data[2]
        brake = telemetry_data[3]
        gear = telemetry_data[5]

        try:
            # Compact SQL to avoid static analysis issues; commit the micro-telemetry snapshot
            # Note: yaw and g_forces use DEFAULT 0.0 from schema, so no need to specify them
            self.db.cursor.execute(
                "INSERT INTO telemetry (session_uid, lap_distance, throttle, brake, speed, steer, gear) VALUES (?, 0.0, ?, ?, ?, ?, ?)",
                (str(session_uid), throttle, brake, speed, steer, gear),
            )
            self.db.conn.commit()
        except Exception as e:
            logger.exception("Database error saving micro-telemetry snapshot: %s", e)
