import sys
import logging
from pathlib import Path
from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
import threading

# Import the new UI framework
from PyQt6.QtWidgets import QApplication
from ui.dashboard import TelemetryDashboard

# Configure logger at module level
logger = logging.getLogger(__name__)

def _configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

if __name__ == "__main__":
    _configure_logging()

    db = None
    logger_obj = None
    logger_thread = None
    app = None
    exit_code = 0

    try:
        # 1. Initialize Database
        db = DBManager()
        logger.info("Database initialized successfully")

        # 2. Initialize Background Logger
        logger_obj = TelemetryLogger(db)
        logger_thread = threading.Thread(target=logger_obj.start_listening, daemon=True)
        logger_thread.start()
        logger.info("Telemetry logger started in background")

        # 3. Initialize and Start the Native UI Desktop App
        app = QApplication(sys.argv)

        # Resolve the database path safely for the UI to read from
        db_path = Path(__file__).resolve().parent / "database" / "f1_telemetry.db"

        window = TelemetryDashboard(str(db_path))
        window.show()
        logger.info("Dashboard UI initialized and displayed")

        # 4. Start the application event loop
        exit_code = app.exec()

    except Exception as e:
        logger.exception("Fatal error in main application: %s", e)
        exit_code = 1

    finally:
        # Graceful shutdown
        if logger_obj is not None:
            try:
                logger_obj.is_running = False
                logger.info("Telemetry logger shut down")
            except Exception as e:
                logger.warning("Error shutting down logger: %s", e)

        if db is not None:
            try:
                db.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.warning("Error closing database: %s", e)

        logger.info("Application shut down gracefully")
        sys.exit(exit_code)
