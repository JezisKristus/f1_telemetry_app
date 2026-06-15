import sys
import logging
from pathlib import Path

from telemetry.config_loader import load_config

# Configure logging from config before other imports use it
_config = load_config()
_log_level = getattr(logging, _config.get("logging", {}).get("level", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
from telemetry.proxy import UDPForwarder
import threading

from PyQt6.QtWidgets import QApplication
from ui.dashboard import TelemetryDashboard

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    db = None
    logger_obj = None
    logger_thread = None
    forwarder = None
    app = None
    exit_code = 0

    try:
        db_path = Path(__file__).resolve().parent / _config["database"]["path"]
        db = DBManager(db_path=str(db_path))

        udp_cfg = _config["udp"]
        forwarder = UDPForwarder(
            forward_host=udp_cfg.get("forward_host", "127.0.0.1"),
            forward_port=udp_cfg.get("forward_port", 20778),
        )

        logger_obj = TelemetryLogger(
            db,
            port=udp_cfg.get("listen_port", 20777),
            forwarder=forwarder,
        )
        logger_thread = threading.Thread(target=logger_obj.start_listening, daemon=True)
        logger_thread.start()
        logger.info("Telemetry logger started on port %d (forwarding to %s:%d)",
                    udp_cfg.get("listen_port", 20777),
                    udp_cfg.get("forward_host", "127.0.0.1"),
                    udp_cfg.get("forward_port", 20778))

        app = QApplication(sys.argv)
        window = TelemetryDashboard(str(db_path), logger_obj=logger_obj, config=_config)
        window.show()
        exit_code = app.exec()

    except Exception:
        logger.exception("Fatal error in main application")
        exit_code = 1

    finally:
        if logger_obj is not None:
            try:
                logger_obj.stop()
            except Exception:
                logger.warning("Error shutting down logger")
        if forwarder is not None:
            forwarder.close()
        if db is not None:
            try:
                db.conn.close()
            except Exception:
                pass
        sys.exit(exit_code)
