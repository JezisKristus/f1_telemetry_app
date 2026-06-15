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

    def evaluate(self):
        if len(self._temp_history) < 5:
            return None

        recent = list(self._temp_history)[-10:]
        avg = sum(recent) / len(recent)
        trend = recent[-1] - recent[0]

        if avg >= self.HOT_THRESHOLD:
            return {"state": "LIFT", "message": "LIFT — tire surface temps overheating", "severity": "critical"}
        if trend > 3 and avg > self.OPTIMAL_HIGH:
            return {"state": "SAVE", "message": "SAVE tires — surface temps rising", "severity": "warning"}
        if self.OPTIMAL_LOW <= avg <= self.OPTIMAL_HIGH:
            return {"state": "PUSH", "message": "PUSH — temps in optimal window", "severity": "success"}
        if avg < self.OPTIMAL_LOW:
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
        conn.close()
        for row in rows:
            self.update_from_telemetry({
                "temp_sur_fl": row[0], "temp_sur_fr": row[1],
                "temp_sur_rl": row[2], "temp_sur_rr": row[3],
            })
        return self.evaluate()
