import sqlite3


class AIDifficultyScaler:
    """Compare player sector times vs AI grid to recommend difficulty adjustments."""

    CLICKS_PER_TENTH = 1  # ~0.1s per difficulty click

    def __init__(self, db_path):
        self.db_path = db_path

    def analyze(self, session_uid, player_car_index=0):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            "SELECT sector_1_ms, sector_2_ms, sector_3_ms FROM laps "
            "WHERE session_uid=? AND car_index=? AND is_valid=1 AND lap_time_ms>0 "
            "ORDER BY lap_time_ms LIMIT 1",
            (session_uid, player_car_index),
        )
        player_best = cur.fetchone()

        cur.execute(
            "SELECT MIN(sector_1_ms), MIN(sector_2_ms), MIN(sector_3_ms) FROM laps "
            "WHERE session_uid=? AND car_index!=? AND is_valid=1 AND lap_time_ms>0 AND sector_1_ms>0",
            (session_uid, player_car_index),
        )
        ai_best = cur.fetchone()
        conn.close()

        if not player_best or not ai_best or not all(ai_best):
            return None

        recommendations = []
        sectors = ["Sector 1", "Sector 2", "Sector 3"]
        for i, (p, a) in enumerate(zip(player_best, ai_best)):
            if not p or not a:
                continue
            delta_ms = p - a
            if abs(delta_ms) < 100:
                continue
            clicks = round(abs(delta_ms) / 100)
            if delta_ms > 0:
                recommendations.append({
                    "sector": sectors[i],
                    "message": f"Lower AI difficulty by {clicks} clicks (~{clicks * 0.1:.1f}s) in {sectors[i]}",
                    "delta_ms": delta_ms,
                })
            else:
                recommendations.append({
                    "sector": sectors[i],
                    "message": f"Raise AI difficulty by {clicks} clicks in {sectors[i]} — you're faster",
                    "delta_ms": delta_ms,
                })
        return recommendations
