import struct

from . import TRACK_NAMES, SESSION_TYPE_NAMES


def parse_session_packet(data: bytes, offset: int):
    """Parse Session packet (id 1) core metadata."""
    if len(data) < offset + 8:
        return None
    weather = data[offset]
    track_temp = struct.unpack_from("<b", data, offset + 1)[0]
    air_temp = struct.unpack_from("<b", data, offset + 2)[0]
    total_laps = data[offset + 3]
    track_length = struct.unpack_from("<H", data, offset + 4)[0]
    session_type = data[offset + 6]
    track_id = struct.unpack_from("<b", data, offset + 7)[0]
    return {
        "weather": weather,
        "track_temperature": track_temp,
        "air_temperature": air_temp,
        "total_laps": total_laps,
        "track_length": track_length,
        "session_type": session_type,
        "track_id": track_id,
        "track_name": TRACK_NAMES.get(track_id, f"Track {track_id}"),
        "session_type_name": SESSION_TYPE_NAMES.get(session_type, "Unknown"),
    }
