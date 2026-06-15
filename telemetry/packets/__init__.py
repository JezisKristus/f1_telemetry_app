"""F1 25 UDP packet struct layouts."""

NUM_CARS = 20

# Packet header — 29 bytes
HEADER_FMT = "<HBBBBBQfIIBB"
HEADER_SIZE = 29

# CarMotionData — 60 bytes per car
CAR_MOTION_FMT = "<3f3f6h6f"
CAR_MOTION_SIZE = 60

# LapData core block — 57 bytes per car
LAP_BLOCK_SIZE = 57
LAP_STRUCT_FMT = "<IIHBHBHHfIfBB"

# CarTelemetryData — 60 bytes per car (EA pads to 60)
CAR_TELEMETRY_FMT = "<HffBbHBBH4H4B4BH4f4B"
CAR_TELEMETRY_SIZE = 60

# CarStatusData — 60 bytes per car
CAR_STATUS_FMT = "<BBBBBfffHHBBBBBfBBfffHHBB"
CAR_STATUS_SIZE = 60

# CarDamageData — 10 bytes per car (tyresWear first 4 bytes)
CAR_DAMAGE_BLOCK_SIZE = 10
TIRES_WEAR_FMT = "<4B"

# CarSetupData — 51 bytes per car (key aero fields at start)
CAR_SETUP_FMT = "<BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
CAR_SETUP_SIZE = 51
CAR_SETUP_CORE_FMT = "<BB"  # frontWing, rearWing at offset 0

# SessionData — parse key fields after header
SESSION_CORE_FMT = "<BbBHBB"

# Track ID to name map (F1 25)
TRACK_NAMES = {
    0: "Melbourne", 1: "Paul Ricard", 2: "Shanghai", 3: "Sakhir",
    4: "Catalunya", 5: "Monaco", 6: "Montreal", 7: "Silverstone",
    8: "Hockenheim", 9: "Hungaroring", 10: "Spa", 11: "Monza",
    12: "Singapore", 13: "Suzuka", 14: "Abu Dhabi", 15: "Texas",
    16: "Brazil", 17: "Austria", 18: "Sochi", 19: "Mexico",
    20: "Baku", 21: "Sakhir Short", 22: "Silverstone Short",
    23: "Texas Short", 24: "Suzuka Short", 25: "Hanoi",
    26: "Zandvoort", 27: "Imola", 28: "Portimao", 29: "Jeddah",
    30: "Miami", 31: "Las Vegas", 32: "Losail", 33: "Interlagos Short",
    34: "Shanghai Short", 35: "Miami Short", 36: "COTA Short",
    37: "Spa Short", 38: "Monza Short", 39: "Mexico Short",
    40: "Las Vegas Short", 41: "Abu Dhabi Short",
}

SESSION_TYPE_NAMES = {
    0: "Unknown", 1: "Practice 1", 2: "Practice 2", 3: "Practice 3",
    4: "Short Practice", 5: "Qualifying 1", 6: "Qualifying 2",
    7: "Qualifying 3", 8: "Short Qualifying", 9: "One-Shot Qualifying",
    10: "Race", 11: "Race 2", 12: "Time Trial",
}

TIRE_COMPOUND_NAMES = {
    16: "Soft", 17: "Medium", 18: "Hard", 7: "Inter", 8: "Wet",
}
