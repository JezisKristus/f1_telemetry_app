import struct

from . import CAR_MOTION_FMT, CAR_MOTION_SIZE, NUM_CARS


def parse_motion_packet(data: bytes, offset: int):
    """Parse Motion packet (id 0). Returns list of car dicts."""
    cars = []
    for car_idx in range(NUM_CARS):
        car_offset = offset + car_idx * CAR_MOTION_SIZE
        if len(data) < car_offset + CAR_MOTION_SIZE:
            break
        fields = struct.unpack_from(CAR_MOTION_FMT, data, car_offset)
        cars.append({
            "car_index": car_idx,
            "world_x": fields[0],
            "world_y": fields[1],
            "world_z": fields[2],
            "velocity_x": fields[3],
            "velocity_y": fields[4],
            "velocity_z": fields[5],
            "g_lat": fields[12],
            "g_long": fields[13],
            "g_vert": fields[14],
            "yaw": fields[15],
            "pitch": fields[16],
            "roll": fields[17],
        })
    return cars
