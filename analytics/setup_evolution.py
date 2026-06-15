import sqlite3


class SetupEvolution:
    """Query historical setup data linked to laps."""

    def __init__(self, db_path):
        self.db_path = db_path

    def get_setups_for_track(self, track_name=None, max_lap_time_ms=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        query = (
            "SELECT s.session_uid, s.lap_id, s.front_wing, s.rear_wing, "
            "s.suspension_geometry, s.tire_pressures, l.lap_time_ms, "
            "sess.track_name "
            "FROM setups s "
            "LEFT JOIN laps l ON s.lap_id = l.lap_id "
            "LEFT JOIN sessions sess ON s.session_uid = sess.session_uid "
            "WHERE l.lap_time_ms > 0"
        )
        params = []
        if track_name:
            query += " AND sess.track_name = ?"
            params.append(track_name)
        if max_lap_time_ms:
            query += " AND l.lap_time_ms <= ?"
            params.append(max_lap_time_ms)
        query += " ORDER BY l.lap_time_ms ASC"
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "session_uid": r[0], "lap_id": r[1], "front_wing": r[2], "rear_wing": r[3],
                "suspension": r[4], "pressures": r[5], "lap_time_ms": r[6], "track_name": r[7],
            }
            for r in rows
        ]

    def best_setup_at_track(self, track_name):
        setups = self.get_setups_for_track(track_name=track_name)
        return setups[0] if setups else None
