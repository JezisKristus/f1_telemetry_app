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

        is_trailing = all(r[0] > 0 and r[0] < self.delta_threshold_ms for r in rows)
        if is_trailing:
            understeer_detected = False
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT steer, g_lat FROM telemetry WHERE session_uid=? ORDER BY id DESC LIMIT 100",
                (session_uid,),
            )
            telems = cur.fetchall()
            conn.close()
            
            if telems:
                corner_count = 0
                understeer_count = 0
                for steer_val, g_lat_val in telems:
                    if steer_val and abs(steer_val) > 0.2:
                        corner_count += 1
                        if g_lat_val and abs(g_lat_val) < 1.2:
                            understeer_count += 1
                if corner_count > 5 and (understeer_count / corner_count) > 0.5:
                    understeer_detected = True

            undercut_lap = max(1, current_lap - 1)
            msg = f"Dirty air — consider undercut Lap {undercut_lap}"
            if understeer_detected:
                msg += " (understeer detected)"
            return {
                "dirty_air": True,
                "wear_multiplier": self.wear_multiplier,
                "message": msg,
                "severity": "warning",
            }
        return None
