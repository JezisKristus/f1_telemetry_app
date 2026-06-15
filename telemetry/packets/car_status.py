import struct

from . import TIRE_COMPOUND_NAMES

CAR_STATUS_SIZE = 60


def parse_car_status(data: bytes, offset: int, player_index: int):
    """Parse CarStatus packet (id 7) for player car using known offsets."""
    player_offset = offset + player_index * CAR_STATUS_SIZE
    if len(data) < player_offset + 56:
        return None
    fuel_in_tank = struct.unpack_from("<f", data, player_offset + 5)[0]
    fuel_capacity = struct.unpack_from("<f", data, player_offset + 9)[0]
    fuel_remaining_laps = struct.unpack_from("<f", data, player_offset + 13)[0]
    compound = data[player_offset + 25]
    tyres_age_laps = data[player_offset + 27]
    ers_store_energy = struct.unpack_from("<f", data, player_offset + 31)[0]
    ers_deploy_mode = data[player_offset + 35]
    steer = struct.unpack_from("<f", data, player_offset + 49)[0]
    return {
        "fuel_in_tank": fuel_in_tank,
        "fuel_capacity": fuel_capacity,
        "fuel_remaining_laps": fuel_remaining_laps,
        "actual_tyre_compound": compound,
        "tyre_compound_name": TIRE_COMPOUND_NAMES.get(compound, str(compound)),
        "tyres_age_laps": tyres_age_laps,
        "ers_store_energy": ers_store_energy,
        "ers_deploy_mode": ers_deploy_mode,
        "steer": steer,
        "compound": compound,
    }
