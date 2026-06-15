#!/usr/bin/env python
"""Test script to verify telemetry data insertion works without errors."""

import struct
import time
import logging
from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Initialize DB and Logger
db = DBManager()
logger = TelemetryLogger(db)

# Create mock F1 25 telemetry packet (simplified)
# Header: packet_format(H)=2025, gameYear(B)=25, gameMS(B)=1, gameMn(B)=0,
#         packetVer(B)=1, packetId(B)=6, sessionUID(Q)=12345, sessionTime(f)=10.5,
#         frameId(I)=100, overallFrameId(I)=200, playerCarIdx(B)=0, secondaryPlayerIdx(B)=0
header = struct.pack("<HBBBBBQfIIBB", 2025, 25, 1, 0, 1, 6, 12345, 10.5, 100, 200, 0, 0)

# CarTelemetryData for player car (simplified):
# speed(H)=200, throttle(f)=0.75, brake(f)=0.1, clutch(B)=0, gear(b)=5,
# engineRPM(H)=7000, drs(B)=0, revLights(B)=50, revLightsBitVal(H)=0,
# brakesTemp(4H)=100,101,102,103, tyresSurfaceTemp(4B)=45,48,42,44,
# tyresInnerTemp(4B)=78,75,71,73, engineTemp(H)=95, tyresPressure(4f)=28.5,28.3,27.9,28.1,
# surfaceType(4B)=0,0,0,0
car_data = struct.pack("<HffBbHBBH4H4B4BH4f4B",
    200, 0.75, 0.1, 0, 5, 7000, 0, 50, 0,
    100, 101, 102, 103,  # brake temps
    45, 48, 42, 44,       # surface temps
    78, 75, 71, 73,       # inner temps
    95,                    # engine temp
    28.5, 28.3, 27.9, 28.1,  # tire pressures
    0, 0, 0, 0)           # surface types

# Pad to 60 bytes
car_data = car_data + b'\x00' * (60 - len(car_data))

# Pad for 20 cars (we only created for 1, pad rest with zeros)
full_packet = header + car_data + (b'\x00' * 60 * 19)

# Route the packet through the logger
print("📡 Simulating telemetry packet reception...")
try:
    logger.route_packet(full_packet)

    # Give database worker time to process
    time.sleep(0.5)

    # Check if data was inserted
    cursor = db.cursor
    cursor.execute("SELECT COUNT(*) FROM telemetry WHERE session_uid = '12345'")
    count = cursor.fetchone()[0]

    if count > 0:
        print(f"✅ SUCCESS: {count} telemetry record(s) inserted without errors!")
        cursor.execute("SELECT throttle, brake, speed, temp_sur_fl, temp_core_fl FROM telemetry WHERE session_uid = '12345' LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"   Sample data: throttle={row[0]}, brake={row[1]}, speed={row[2]}, temp_sur_fl={row[3]}, temp_core_fl={row[4]}")
    else:
        print("❌ ERROR: No telemetry records inserted!")
except Exception as e:
    print(f"❌ CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

