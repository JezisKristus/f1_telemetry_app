import sys
import logging
from pathlib import Path
from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
import threading

# Import the new UI framework
from PyQt6.QtWidgets import QApplication
from ui.dashboard import TelemetryDashboard

def _configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

if __name__ == "__main__":
    _configure_logging()

    # 1. Initialize Database
    db = DBManager()

    # 2. Initialize Background Logger
    logger = TelemetryLogger(db)
    logger_thread = threading.Thread(target=logger.start_listening, daemon=True)
    logger_thread.start()

    # 3. Initialize and Start the Native UI Desktop App
    # This automatically keeps the main thread alive and blocks the script from exiting
    app = QApplication(sys.argv)

    # Resolve the database path safely for the UI to read from
    db_path = Path(__file__).resolve().parent / "database" / "f1_telemetry.db"

    window = TelemetryDashboard(db_path)
    window.show()

    # 4. Graceful Shutdown
    try:
        sys.exit(app.exec())
    finally:
        logger.is_running = False
        logging.info("Shutting down logger and closing application...")
