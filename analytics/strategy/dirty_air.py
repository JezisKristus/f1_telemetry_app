import sqlite3


class DirtyAirMonitor:
    """Detect dirty air situations from delta to car ahead."""

    def __init__(self, db_path, delta_threshold_ms=1500, lap_threshold=3, wear_multiplier=1.3):
        self.db_path = db_path
        self.delta_threshold_ms = delta_threshold_ms
        self.lap_threshold = lap_threshold
        self.wear_multiplier = wear_multiplier

    def evaluate(self, session_uid, car_index, current_lap=0):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT delta_front_ms FROM laps "
            "WHERE session_uid=? AND car_index=? AND is_valid=1 ORDER BY rowid DESC LIMIT ?",
            (session_uid, car_index, self.lap_threshold),
        )
        rows = cur.fetchall()
        conn.close()

        if len(rows) < self.lap_threshold:
            return None

        if all(r[0] > 0 and r[0] < self.delta_threshold_ms for r in rows):
            undercut_lap = max(1, current_lap - 1)
            return {
                "dirty_air": True,
                "wear_multiplier": self.wear_multiplier,
                "message": f"Dirty air — consider undercut Lap {undercut_lap}",
                "severity": "warning",
            }
        return None
