import sqlite3
import pandas as pd
import numpy as np


class DeltaAnalyzer:
    """Meter-by-meter lap comparison for coaching."""

    DISTANCE_BINS = 100

    def __init__(self, db_path):
        self.db_path = db_path

    def get_valid_laps(self, session_uid, car_index=0):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT lap_id, lap_time_ms, sector_1_ms, sector_2_ms, sector_3_ms "
            "FROM laps WHERE session_uid=? AND car_index=? AND is_valid=1 AND lap_time_ms>0 "
            "ORDER BY lap_time_ms",
            (session_uid, car_index),
        )
        rows = cur.fetchall()
        conn.close()
        return [{"lap_id": r[0], "lap_time_ms": r[1]} for r in rows]

    def get_lap_trace(self, session_uid, lap_id):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            "SELECT lap_distance, throttle, brake, speed, steer FROM telemetry "
            "WHERE session_uid=? ORDER BY id",
            conn, params=(session_uid,),
        )
        conn.close()
        if df.empty:
            return None
        df = df.dropna(subset=["lap_distance"])
        df = df[(df["lap_distance"] >= 0) & (df["lap_distance"] <= 1.0)]
        if df.empty:
            return None
        df["bin"] = (df["lap_distance"] * self.DISTANCE_BINS).astype(int).clip(0, self.DISTANCE_BINS - 1)
        return df.groupby("bin").mean(numeric_only=True).reset_index()

    def compare_laps(self, session_uid, reference_lap_id, comparison_lap_id):
        ref = self.get_lap_trace(session_uid, reference_lap_id)
        comp = self.get_lap_trace(session_uid, comparison_lap_id)
        if ref is None or comp is None:
            return None

        merged = ref.merge(comp, on="bin", suffixes=("_ref", "_comp"))
        if merged.empty:
            return None

        # Estimate delta from speed differential
        speed_diff = merged["speed_ref"] - merged["speed_comp"]
        dt_per_bin = speed_diff / np.maximum(merged["speed_ref"], 1) * (1.0 / self.DISTANCE_BINS)
        merged["delta_time"] = dt_per_bin.cumsum() * 1000  # ms

        loss_regions = []
        cumulative = merged["delta_time"].values
        for i in range(1, len(cumulative)):
            if cumulative[i] - cumulative[i - 1] > 50:
                loss_regions.append({
                    "bin_start": int(merged["bin"].iloc[i - 1]),
                    "bin_end": int(merged["bin"].iloc[i]),
                    "delta_ms": float(cumulative[i] - cumulative[i - 1]),
                    "hint": self._generate_hint(merged.iloc[i]),
                })

        return {
            "distance": merged["bin"].values / self.DISTANCE_BINS,
            "speed_ref": merged["speed_ref"].values,
            "speed_comp": merged["speed_comp"].values,
            "throttle_ref": merged["throttle_ref"].values,
            "throttle_comp": merged["throttle_comp"].values,
            "brake_ref": merged["brake_ref"].values,
            "brake_comp": merged["brake_comp"].values,
            "delta_time_ms": merged["delta_time"].values,
            "loss_regions": loss_regions,
        }

    def _generate_hint(self, row):
        if row.get("brake_comp", 0) > row.get("brake_ref", 0) + 0.1:
            return "Brake earlier — carrying too much speed"
        if row.get("throttle_comp", 0) < row.get("throttle_ref", 0) - 0.1:
            return "Apply throttle earlier on exit"
        return "Speed loss — check racing line"

    def fastest_valid_lap(self, session_uid, car_index=0):
        laps = self.get_valid_laps(session_uid, car_index)
        return laps[0]["lap_id"] if laps else None
