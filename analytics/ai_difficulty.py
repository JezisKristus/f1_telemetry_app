import sqlite3


class AIDifficultyScaler:
    """Compare player sector times vs AI grid to recommend difficulty adjustments."""

    CLICKS_PER_TENTH = 1  # ~0.1s per difficulty click

    def __init__(self, db_path):
        self.db_path = db_path

    def analyze(self, session_uid, player_car_index=0):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("SELECT teammate_car_index, ai_difficulty FROM sessions WHERE session_uid=?", (session_uid,))
        row = cur.fetchone()
        teammate_car_index = row[0] if row and row[0] is not None else -1
        ai_difficulty = row[1] if row and row[1] is not None else 0

        cur.execute(
            "SELECT sector_1_ms, sector_2_ms, sector_3_ms FROM laps "
            "WHERE session_uid=? AND car_index=? AND is_valid=1 AND lap_time_ms>0 "
            "ORDER BY lap_time_ms LIMIT 1",
            (session_uid, player_car_index),
        )
        player_best = cur.fetchone()

        if teammate_car_index != -1:
            cur.execute(
                "SELECT MIN(sector_1_ms), MIN(sector_2_ms), MIN(sector_3_ms) FROM laps "
                "WHERE session_uid=? AND car_index=? AND is_valid=1 AND lap_time_ms>0 AND sector_1_ms>0",
                (session_uid, teammate_car_index),
            )
        else:
            cur.execute(
                "SELECT MIN(sector_1_ms), MIN(sector_2_ms), MIN(sector_3_ms) FROM laps "
                "WHERE session_uid=? AND car_index!=? AND is_valid=1 AND lap_time_ms>0 AND sector_1_ms>0",
                (session_uid, player_car_index),
            )
        ai_best = cur.fetchone()
        conn.close()

        if not player_best or not ai_best or not all(ai_best):
            return None

        # Scaling curve: above 100, 1 click = 0.2s (200ms); otherwise 1 click = 0.1s (100ms)
        click_ms = 200 if ai_difficulty > 100 else 100
        click_sec = click_ms / 1000.0

        recommendations = []
        sectors = ["Sector 1", "Sector 2", "Sector 3"]
        for i, (p, a) in enumerate(zip(player_best, ai_best)):
            if not p or not a:
                continue
            delta_ms = p - a
            if abs(delta_ms) < click_ms:
                continue
            clicks = round(abs(delta_ms) / click_ms)
            if delta_ms > 0:
                recommendations.append({
                    "sector": sectors[i],
                    "message": f"Lower AI difficulty by {clicks} clicks (~{clicks * click_sec:.1f}s) in {sectors[i]}",
                    "delta_ms": delta_ms,
                })
            else:
                recommendations.append({
                    "sector": sectors[i],
                    "message": f"Raise AI difficulty by {clicks} clicks in {sectors[i]} — you're faster",
                    "delta_ms": delta_ms,
                })
        return recommendations
