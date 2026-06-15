import logging
from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
import threading
import time


def _configure_logging():
    # Basic console logging for debugging and operational visibility
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    # configure console logging early so DBManager and other modules can log
    _configure_logging()

    # 1. Initialize DB
    db = DBManager()

    # 2. Initialize Logger
    logger = TelemetryLogger(db)

    # 3. Run Logger in a background thread so the app doesn't freeze
    logger_thread = threading.Thread(target=logger.start_listening, daemon=True)
    logger_thread.start()

    # 3b. Start a monitor thread that logs how many new packets arrived every 10 seconds
    def _monitor_packets(logger_obj, interval_seconds=10):
        logging.info("Packet monitor started: reporting every %s seconds", interval_seconds)
        try:
            while True:
                time.sleep(interval_seconds)
                try:
                    count = logger_obj.get_and_reset_packet_count()
                    logging.info("📥 Packets in last %s seconds: %d", interval_seconds, count)
                except Exception:
                    logging.exception("Error while reading packet count")
        except Exception:
            logging.exception("Packet monitor exiting due to unexpected error")

    monitor_thread = threading.Thread(target=_monitor_packets, args=(logger, 10), daemon=True)
    monitor_thread.start()

    # 4. Keep main thread alive (Later, FastAPI will run here)
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.is_running = False
        logging.info("Shutting down logger...")
