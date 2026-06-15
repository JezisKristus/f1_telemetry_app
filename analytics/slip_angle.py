import math
import sqlite3


class SlipAngleDetector:
    """Detect micro-slides from yaw vs velocity heading."""

    SLIP_THRESHOLD_DEG = 5.0

    def __init__(self, db_path, threshold_deg=None):
        self.db_path = db_path
        self.threshold = threshold_deg or self.SLIP_THRESHOLD_DEG

    def detect_from_motion(self, yaw, velocity_x, velocity_z):
        speed = math.sqrt(velocity_x ** 2 + velocity_z ** 2)
        if speed < 5:
            return None
        heading = math.atan2(velocity_z, velocity_x)
        slip_rad = abs(yaw - heading)
        slip_deg = math.degrees(min(slip_rad, 2 * math.pi - slip_rad))
        if slip_deg > self.threshold:
            return {"slip_deg": slip_deg, "speed": speed}
        return None

    def analyze_session(self, session_uid):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT yaw, g_lat, lap_distance FROM telemetry "
            "WHERE session_uid=? AND yaw != 0 ORDER BY id",
            (session_uid,),
        )
        rows = cur.fetchall()
        conn.close()

        events = []
        for yaw, g_lat, dist in rows:
            if abs(g_lat) > 2.0 and abs(yaw) > 0.1:
                slip_deg = abs(math.degrees(yaw))
                if slip_deg > self.threshold:
                    events.append({
                        "lap_distance": dist,
                        "slip_deg": slip_deg,
                        "g_lat": g_lat,
                    })

        return {
            "total_events": len(events),
            "events": events[:20],
            "summary": f"{len(events)} micro-slides detected — check corner exits for tire overheating",
        }
