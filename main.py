from database.db_manager import DBManager
from telemetry.logger import TelemetryLogger
import threading

if __name__ == "__main__":
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
        print("Shutting down logger...")