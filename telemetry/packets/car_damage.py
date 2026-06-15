import struct

from . import CAR_DAMAGE_BLOCK_SIZE, TIRES_WEAR_FMT, NUM_CARS


def parse_car_damage(data: bytes, offset: int, player_index: int):
    """Parse CarDamage packet (id 10) for player car — all 4 tire wear values."""
    player_offset = offset + player_index * CAR_DAMAGE_BLOCK_SIZE
    if len(data) < player_offset + struct.calcsize(TIRES_WEAR_FMT):
        return None
    wear = struct.unpack_from(TIRES_WEAR_FMT, data, player_offset)
    return {
        "wear_fl": wear[0],
        "wear_fr": wear[1],
        "wear_rl": wear[2],
        "wear_rr": wear[3],
    }


def parse_all_car_damage(data: bytes, offset: int):
    """Parse wear for all cars (used for grid analysis)."""
    result = []
    for car_idx in range(NUM_CARS):
        car_offset = offset + car_idx * CAR_DAMAGE_BLOCK_SIZE
        if len(data) < car_offset + 4:
            break
        wear = struct.unpack_from(TIRES_WEAR_FMT, data, car_offset)
        result.append({
            "car_index": car_idx,
            "wear_fl": wear[0],
            "wear_fr": wear[1],
            "wear_rl": wear[2],
            "wear_rr": wear[3],
        })
    return result
