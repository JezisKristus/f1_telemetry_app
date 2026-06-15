import socket
import struct


class TelemetryLogger:
    def __init__(self, db_manager, port=20777):
        self.db = db_manager
        self.port = port
        self.ip = "127.0.0.1"
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))

    def start_listening(self):
        print(f"🏎️ Native F1 25 Logger started. Listening on UDP {self.port}...")
        while True:
            # Receive up to 2048 bytes (standard UDP buffer size for F1)
            data, _ = self.sock.recvfrom(2048)

            # Ensure the packet is at least large enough to be a valid F1 header
            if len(data) >= 29:
                self.route_packet(data)

    def route_packet(self, data):
        # --- THE F1 25 HEADER DECODER ---
        # The string below tells Python exactly how the C-struct is laid out in memory:
        # < = Little Endian (Standard for F1)
        # H = uint16 (Packet Format)
        # B = uint8 (Game Year, Major/Minor Version, Packet Version, Packet ID)
        # Q = uint64 (Session UID)
        # f = float (Session Time)
        # I = uint32 (Frame Identifier, Overall Frame Identifier)
        # B = uint8 (Player Car Index, Secondary Car Index)

        header_format = "<HBBBBBQfIIBB"
        header_size = struct.calcsize(header_format)  # Exactly 29 bytes

        # Unpack the first 29 bytes into a readable tuple
        header_data = struct.unpack(header_format, data[:header_size])

        # Extract the critical routing variables
        packet_format = header_data[0]  # Should be 2025
        packet_id = header_data[5]  # The type of data
        session_uid = header_data[6]  # Unique ID for the current race/session
        player_car_index = header_data[10]  # Which car array index is you (0-21)

        # Drop any packets that aren't from the correct game
        if packet_format != 2025:
            return

        # Route the remaining binary data to the specific unpackers
        if packet_id == 0:
            self._handle_motion_data(data, header_size, player_car_index, session_uid)
        elif packet_id == 2:
            self._handle_lap_data(data, header_size, player_car_index, session_uid)
        elif packet_id == 6:
            self._handle_car_telemetry(data, header_size, player_car_index, session_uid)

    def _handle_motion_data(self, data, offset, player_index, session_uid):
        # We will decode the high-frequency G-forces and suspension data here
        pass

    def _handle_lap_data(self, data, offset, player_index, session_uid):
        # We will decode sector times and grid positions here
        pass

    def _handle_car_telemetry(self, data, offset, player_index, session_uid):
        # We will decode throttle, brake, and steering inputs here
        pass