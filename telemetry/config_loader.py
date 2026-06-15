import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "udp": {
        "listen_port": 20777,
        "forward_host": "127.0.0.1",
        "forward_port": 20778,
    },
    "database": {"path": "database/f1_telemetry.db"},
    "logging": {"level": "INFO"},
    "strategy": {
        "pit_loss_seconds": 22,
        "wear_cliff_pct": 70,
        "dirty_air_delta_seconds": 1.5,
        "dirty_air_lap_threshold": 3,
    },
    "player": {"car_index": None},
}


def load_config(config_path=None):
    """Load config.yaml from project root, falling back to defaults."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    else:
        config_path = Path(config_path)

    config = DEFAULT_CONFIG.copy()
    if config_path.is_file():
        try:
            with open(config_path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            for key, value in loaded.items():
                if isinstance(value, dict) and isinstance(config.get(key), dict):
                    config[key] = {**config[key], **value}
                else:
                    config[key] = value
        except Exception:
            logger.exception("Failed to load config from %s, using defaults", config_path)
    return config
