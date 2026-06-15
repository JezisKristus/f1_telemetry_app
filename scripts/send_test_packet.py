import socket
import struct

# Build header using the same format as TelemetryLogger
header_format = "<HBBBBBQfIIBB"
# Fields: packet_format(H), ver1(B), ver2(B), ver3(B), ver4(B), packet_id(B), session_uid(Q), some_float(f), valI1(I), valI2(I), player_car_index(B), last(B)
packet_format = 2025
ver1 = 1
ver2 = 1
ver3 = 1
ver4 = 1
packet_id = 6  # send a telemetry packet
session_uid = 987654321
some_float = 0.0
valI1 = 0
valI2 = 0
player_car_index = 0
last_b = 0

header = struct.pack(header_format, packet_format, ver1, ver2, ver3, ver4, packet_id, session_uid, some_float, valI1, valI2, player_car_index, last_b)

# Append dummy payload large enough for the telemetry handler (use 60 bytes per car block)
payload = bytes(60)

data = header + payload

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(data, ("127.0.0.1", 20777))
print("Test packet sent")

