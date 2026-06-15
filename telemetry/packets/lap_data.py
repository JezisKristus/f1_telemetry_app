import struct

from . import LAP_BLOCK_SIZE, LAP_STRUCT_FMT, NUM_CARS


def parse_lap_packet(data: bytes, offset: int):
    """Parse LapData packet (id 2). Returns list of car lap dicts."""
    cars = []
    for car_idx in range(NUM_CARS):
        car_offset = offset + car_idx * LAP_BLOCK_SIZE
        chunk_size = struct.calcsize(LAP_STRUCT_FMT)
        if len(data) < car_offset + chunk_size:
            break
        fields = struct.unpack_from(LAP_STRUCT_FMT, data, car_offset)
        cars.append({
            "car_index": car_idx,
            "last_lap_time_ms": fields[0],
            "current_lap_time_ms": fields[1],
            "sector_1_ms": fields[2],
            "sector_2_ms": fields[4],
            "delta_front_ms": fields[6],
            "delta_leader_ms": fields[7],
            "lap_distance": fields[9],
            "position": fields[11],
            "current_lap_num": fields[12],
        })
    return cars
