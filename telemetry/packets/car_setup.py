from . import CAR_SETUP_SIZE


def parse_setup_packet(data: bytes, offset: int, player_index: int):
    """Parse CarSetup packet (id 5) for player car."""
    car_offset = offset + player_index * CAR_SETUP_SIZE
    if len(data) < car_offset + 4:
        return None
    front_wing = data[car_offset]
    rear_wing = data[car_offset + 1]
    on_throttle = data[car_offset + 2]
    off_throttle = data[car_offset + 3]
    # Suspension geometry as compact string from next bytes
    susp_bytes = data[car_offset + 4: car_offset + 20]
    suspension_geometry = ",".join(str(b) for b in susp_bytes)
    pressure_bytes = data[car_offset + 20: car_offset + 36]
    tire_pressures = ",".join(str(b / 10.0) for b in pressure_bytes[:4]) if pressure_bytes else ""
    return {
        "front_wing": front_wing,
        "rear_wing": rear_wing,
        "on_throttle": on_throttle,
        "off_throttle": off_throttle,
        "suspension_geometry": suspension_geometry,
        "tire_pressures": tire_pressures,
    }
