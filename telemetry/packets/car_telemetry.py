import struct

from . import CAR_TELEMETRY_FMT, CAR_TELEMETRY_SIZE


def parse_car_telemetry(data: bytes, offset: int, player_index: int):
    """Parse CarTelemetry packet (id 6) for player car."""
    player_offset = offset + player_index * CAR_TELEMETRY_SIZE
    if len(data) < player_offset + CAR_TELEMETRY_SIZE:
        return None
    fields = struct.unpack_from(CAR_TELEMETRY_FMT, data, player_offset)
    return {
        "speed": fields[0],
        "throttle": fields[1],
        "brake": fields[2],
        "gear": fields[4],
        "drs": fields[6],
        "temp_sur_fl": fields[13],
        "temp_sur_fr": fields[14],
        "temp_sur_rl": fields[15],
        "temp_sur_rr": fields[16],
        "temp_core_fl": fields[17],
        "temp_core_fr": fields[18],
        "temp_core_rl": fields[19],
        "temp_core_rr": fields[20],
    }
