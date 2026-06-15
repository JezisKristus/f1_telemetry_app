import sqlite3

from scipy.stats import linregress


class PitWindowCalculator:
    """Predict optimal pit window based on tire wear regression."""

    def __init__(self, db_path, pit_loss_seconds=22, cliff_pct=70):
        self.db_path = db_path
        self.pit_loss_seconds = pit_loss_seconds
        self.cliff_pct = cliff_pct

    def calculate(self, session_uid, car_index, current_lap=0):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT lap_time_ms, wear_end_pct FROM laps "
            "WHERE session_uid=? AND car_index=? AND is_valid=1 AND lap_time_ms>0 ORDER BY rowid",
            (session_uid, car_index),
        )
        rows = cur.fetchall()
        conn.close()

        if len(rows) < 3:
            return None

        wear = [r[1] for r in rows]
        times = [r[0] / 1000.0 for r in rows]

        try:
            slope, intercept, r_value, _, _ = linregress(wear, times)
        except Exception:
            return None

        latest_wear = wear[-1]
        if slope <= 0:
            return None

        wear_rate = (wear[-1] - wear[0]) / max(len(rows) - 1, 1)
        if wear_rate <= 0:
            return None

        laps_to_cliff = (self.cliff_pct - latest_wear) / wear_rate
        pit_lap = int(current_lap + laps_to_cliff - self.pit_loss_seconds / (times[-1] if times[-1] > 0 else 90))
        window_start = max(1, pit_lap - 1)
        window_end = pit_lap + 1

        return {
            "window_start": window_start,
            "window_end": window_end,
            "confidence": round(r_value ** 2, 2),
            "laps_to_cliff": int(laps_to_cliff),
            "message": f"Pit window: Lap {window_start}-{window_end} ({self.cliff_pct}% cliff)",
            "severity": "info",
        }
