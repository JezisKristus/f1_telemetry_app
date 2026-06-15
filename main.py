import logging
from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
import threading


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

    # 4. Keep main thread alive (Later, FastAPI will run here)
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.is_running = False
        logging.info("Shutting down logger...")
