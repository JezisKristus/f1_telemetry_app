import sqlite3
import pandas as pd
import numpy as np  # Imported for future statistical analysis
from scipy.stats import linregress


class StintAnalyzer:
    """Analyzes telemetry data for F1 stints."""

    def __init__(self, db_path):
        """
        Initialize the StintAnalyzer with a database path.

        Args:
            db_path (str): Path to the SQLite database file.
        """
        self.db_path = db_path

    def get_stint_summary(self, session_uid, car_index):
        """
        Get a summary of a stint including lap times and tire degradation.

        Args:
            session_uid (str): The session unique identifier.
            car_index (int): The car index.

        Returns:
            dict: Dictionary containing stint summary with keys:
                - total_laps: Total number of valid laps
                - fastest_lap: Fastest lap time in seconds
                - average_lap_time: Average lap time in seconds (excluding outliers)
                - average_wear_per_lap: Average tire wear per lap
                - laps_until_cliff: Estimated laps until tire cliff (70%) based on the limiting tire
                - limiting_corner: The corner name (FL, FR, RL, RR) that will hit the cliff first
                - wear_rates: Dict of average wear per lap for each corner
                - temps: Dict of average surface/core temperatures per corner
        """
        # Connect to database and query laps
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query all laps for the session and car where lap_time_ms > 0
            cursor.execute(
                """
                SELECT lap_time_ms, wear_end_pct, wear_fl, wear_fr, wear_rl, wear_rr
                FROM laps
                WHERE session_uid = ? AND car_index = ? AND lap_time_ms > 0 AND is_valid = 1
                ORDER BY rowid
                """,
                (session_uid, car_index),
            )

            laps = cursor.fetchall()

            if not laps:
                # Return empty result if no laps found
                return {
                    "total_laps": 0,
                    "fastest_lap": None,
                    "average_lap_time": None,
                    "average_wear_per_lap": None,
                    "laps_until_cliff": None,
                    "limiting_corner": None,
                    "wear_rates": {"wear_fl": 0.0, "wear_fr": 0.0, "wear_rl": 0.0, "wear_rr": 0.0},
                    "temps": {},
                }

            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(laps)
            df["lap_time_sec"] = df["lap_time_ms"] / 1000.0

            # Find fastest lap time
            fastest_lap = df["lap_time_sec"].min()

            # Filter out extreme outliers (more than 107% of fastest lap)
            outlier_threshold = fastest_lap * 1.07
            df_filtered = df[df["lap_time_sec"] <= outlier_threshold].copy()

            # Calculate average lap time
            average_lap_time = df_filtered["lap_time_sec"].mean()

            # Calculate tire degradation using diff()
            wear_diff = df_filtered["wear_end_pct"].diff()
            # Skip the first NaN value from diff()
            valid_wear_diff = wear_diff.dropna()

            if len(valid_wear_diff) > 0:
                average_wear_per_lap = valid_wear_diff.mean()
            else:
                average_wear_per_lap = 0.0

            # Calculate wear rates and laps until cliff for each corner
            wear_rates = {}
            laps_until_cliff_corners = {}
            for corner in ["wear_fl", "wear_fr", "wear_rl", "wear_rr"]:
                diffs = df_filtered[corner].diff().dropna()
                rate = diffs.mean() if len(diffs) > 0 else 0.0
                wear_rates[corner] = rate
                
                latest_corner_wear = df_filtered[corner].iloc[-1]
                wear_remaining = 70.0 - latest_corner_wear
                if rate > 0:
                    laps_until_cliff_corners[corner] = int(wear_remaining / rate)
                else:
                    laps_until_cliff_corners[corner] = 999

            # Determine the limiting tire (the one with the lowest laps until cliff)
            limiting_corner = min(laps_until_cliff_corners, key=laps_until_cliff_corners.get)
            laps_until_cliff = laps_until_cliff_corners[limiting_corner]
            limiting_corner_name = limiting_corner.split("_")[1].upper()

            # Query average surface and core temperatures for each corner
            cursor.execute(
                """
                SELECT 
                    AVG(temp_sur_fl) as avg_sur_fl, AVG(temp_sur_fr) as avg_sur_fr,
                    AVG(temp_sur_rl) as avg_sur_rl, AVG(temp_sur_rr) as avg_sur_rr,
                    AVG(temp_core_fl) as avg_core_fl, AVG(temp_core_fr) as avg_core_fr,
                    AVG(temp_core_rl) as avg_core_rl, AVG(temp_core_rr) as avg_core_rr
                FROM telemetry
                WHERE session_uid = ?
                """,
                (session_uid,),
            )
            temp_row = cursor.fetchone()
            temps = {}
            if temp_row:
                temps = {
                    "temp_sur_fl": temp_row["avg_sur_fl"], "temp_sur_fr": temp_row["avg_sur_fr"],
                    "temp_sur_rl": temp_row["avg_sur_rl"], "temp_sur_rr": temp_row["avg_sur_rr"],
                    "temp_core_fl": temp_row["avg_core_fl"], "temp_core_fr": temp_row["avg_core_fr"],
                    "temp_core_rl": temp_row["avg_core_rl"], "temp_core_rr": temp_row["avg_core_rr"],
                }

            return {
                "total_laps": len(df_filtered),
                "fastest_lap": fastest_lap,
                "average_lap_time": average_lap_time,
                "average_wear_per_lap": average_wear_per_lap,
                "laps_until_cliff": laps_until_cliff,
                "limiting_corner": limiting_corner_name,
                "wear_rates": wear_rates,
                "temps": temps,
            }

        except Exception as e:
            import logging
            logging.exception("Error in get_stint_summary: %s", e)
            return {
                "total_laps": 0,
                "fastest_lap": None,
                "average_lap_time": None,
                "average_wear_per_lap": None,
                "laps_until_cliff": None,
                "limiting_corner": None,
                "wear_rates": {"wear_fl": 0.0, "wear_fr": 0.0, "wear_rl": 0.0, "wear_rr": 0.0},
                "temps": {},
            }
        finally:
            if conn is not None:
                conn.close()

    def predict_degradation_curve(self, session_uid, car_index):
        """
        Predict tire degradation curve using linear regression.

        Args:
            session_uid (str): The session unique identifier.
            car_index (int): The car index.

        Returns:
            dict: Dictionary containing:
                - lap_numbers: List of lap numbers
                - actual_times: List of actual lap times in seconds
                - wear_percentages: List of tire wear percentages
                - predicted_times: List of predicted lap times in seconds
                - time_lost_per_one_percent_wear: The slope (time lost per 1% wear)
                - wear_fl: List of historical wear percentages for FL corner
                - wear_fr: List of historical wear percentages for FR corner
                - wear_rl: List of historical wear percentages for RL corner
                - wear_rr: List of historical wear percentages for RR corner
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query all laps for the session and car where lap_time_ms > 0
            cursor.execute(
                """
                SELECT lap_time_ms, wear_end_pct, wear_fl, wear_fr, wear_rl, wear_rr
                FROM laps
                WHERE session_uid = ? AND car_index = ? AND lap_time_ms > 0 AND is_valid = 1
                ORDER BY rowid
                """,
                (session_uid, car_index),
            )

            laps = cursor.fetchall()

            if not laps or len(laps) < 2:
                # Return empty result if fewer than 2 laps found
                return {
                    "lap_numbers": [],
                    "actual_times": [],
                    "wear_percentages": [],
                    "predicted_times": [],
                    "time_lost_per_one_percent_wear": 0.0,
                    "wear_fl": [],
                    "wear_fr": [],
                    "wear_rl": [],
                    "wear_rr": [],
                }

            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(laps)
            df["lap_time_sec"] = df["lap_time_ms"] / 1000.0
            df["lap_number"] = range(1, len(df) + 1)

            # Find fastest lap time
            fastest_lap = df["lap_time_sec"].min()

            # Filter out dirty laps (more than 105% of fastest lap)
            outlier_threshold = fastest_lap * 1.05
            df_filtered = df[df["lap_time_sec"] <= outlier_threshold].copy()

            if len(df_filtered) < 2:
                # Not enough valid data for regression
                return {
                    "lap_numbers": [],
                    "actual_times": [],
                    "wear_percentages": [],
                    "predicted_times": [],
                    "time_lost_per_one_percent_wear": 0.0,
                    "wear_fl": [],
                    "wear_fr": [],
                    "wear_rl": [],
                    "wear_rr": [],
                }

            # Prepare data for linear regression: wear as X, lap time as Y
            X = df_filtered["wear_end_pct"].values
            Y = df_filtered["lap_time_sec"].values

            # Run linear regression
            slope, intercept, r_value, p_value, std_err = linregress(X, Y)

            # Calculate predicted lap times
            predicted_times = slope * X + intercept

            return {
                "lap_numbers": df_filtered["lap_number"].tolist(),
                "actual_times": Y.tolist(),
                "wear_percentages": X.tolist(),
                "predicted_times": predicted_times.tolist(),
                "time_lost_per_one_percent_wear": slope,
                "wear_fl": df_filtered["wear_fl"].tolist(),
                "wear_fr": df_filtered["wear_fr"].tolist(),
                "wear_rl": df_filtered["wear_rl"].tolist(),
                "wear_rr": df_filtered["wear_rr"].tolist(),
            }

        except Exception as e:
            import logging
            logging.exception("Error in predict_degradation_curve: %s", e)
            return {
                "lap_numbers": [],
                "actual_times": [],
                "wear_percentages": [],
                "predicted_times": [],
                "time_lost_per_one_percent_wear": 0.0,
            }
        finally:
            if conn is not None:
                conn.close()


if __name__ == "__main__":
    # Test with hardcoded values
    db_path = "database/f1_telemetry.db"
    session_uid = "test_session"
    car_index = 0

    analyzer = StintAnalyzer(db_path)
    summary = analyzer.get_stint_summary(session_uid, car_index)


    print(f"Stint Summary for Session {session_uid}, Car {car_index}:")
    print(f"  Total Laps: {summary['total_laps']}")
    print(f"  Fastest Lap: {summary['fastest_lap']:.3f}s" if summary['fastest_lap'] else "  Fastest Lap: N/A")
    print(
        f"  Average Lap Time: {summary['average_lap_time']:.3f}s"
        if summary['average_lap_time']
        else "  Average Lap Time: N/A"
    )
    print(
        f"  Average Wear per Lap: {summary['average_wear_per_lap']:.2f}%"
        if summary['average_wear_per_lap'] is not None
        else "  Average Wear per Lap: N/A"
    )
    print(
        f"  Laps Until Cliff: {summary['laps_until_cliff']}"
        if summary['laps_until_cliff']
        else "  Laps Until Cliff: N/A"
    )



