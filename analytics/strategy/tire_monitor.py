import sqlite3
from collections import deque


class PushSaveMonitor:
    """Monitor tire temps and emit PUSH/SAVE/LIFT alerts."""

    OPTIMAL_LOW = 85
    OPTIMAL_HIGH = 105
    HOT_THRESHOLD = 115

    def __init__(self, db_path, window_seconds=10):
        self.db_path = db_path
        self.window_seconds = window_seconds
        self._temp_history = deque(maxlen=50)

    def update_from_telemetry(self, temps):
        """temps: dict with temp_sur_fl/fr/rl/rr"""
        avg = sum(temps.get(k, 0) for k in ("temp_sur_fl", "temp_sur_fr", "temp_sur_rl", "temp_sur_rr")) / 4.0
        self._temp_history.append(avg)

    def get_windows(self, compound):
        # 18: Hard, 17: Medium, 16: Soft, 7: Inter, 8: Wet
        if compound in (18, "Hard", "C1", "C2"):
            return 90, 115, 125
        elif compound in (17, "Medium", "C3", "C4"):
            return 85, 105, 115
        elif compound in (16, "Soft", "C5", "C6"):
            return 65, 85, 95
        elif compound in (7, 8, "Inter", "Wet"):
            return 60, 80, 90
        return 85, 105, 115  # default

    def evaluate(self, compound=17):
        if len(self._temp_history) < 5:
            return None

        recent = list(self._temp_history)[-10:]
        avg = sum(recent) / len(recent)
        trend = recent[-1] - recent[0]

        low, high, hot = self.get_windows(compound)

        if avg >= hot:
            return {"state": "LIFT", "message": "LIFT — tire surface temps overheating", "severity": "critical"}
        if trend > 3 and avg > high:
            return {"state": "SAVE", "message": "SAVE tires — surface temps rising", "severity": "warning"}
        if low <= avg <= high:
            return {"state": "PUSH", "message": "PUSH — temps in optimal window", "severity": "success"}
        if avg < low:
            return {"state": "WARM", "message": "Warm tires — push to bring temps up", "severity": "info"}
        return None

    def evaluate_from_db(self, session_uid):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT temp_sur_fl, temp_sur_fr, temp_sur_rl, temp_sur_rr FROM telemetry "
            "WHERE session_uid=? ORDER BY id DESC LIMIT 20",
            (session_uid,),
        )
        rows = cur.fetchall()

        # Query active tire compound from the last lap in this session
        cur.execute(
            "SELECT tire_compound FROM laps "
            "WHERE session_uid=? AND tire_compound > 0 ORDER BY rowid DESC LIMIT 1",
            (session_uid,),
        )
        comp_row = cur.fetchone()
        compound = comp_row[0] if comp_row else 17  # default to medium
        conn.close()

        self._temp_history.clear()
        for row in rows:
            self.update_from_telemetry({
                "temp_sur_fl": row[0], "temp_sur_fr": row[1],
                "temp_sur_rl": row[2], "temp_sur_rr": row[3],
            })
        return self.evaluate(compound)
