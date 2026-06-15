import sqlite3
import pandas as pd
import numpy as np  # Imported for future statistical analysis


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
                - laps_until_cliff: Estimated laps until tire cliff (70%)
        """
        # Connect to database and query laps
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Query all laps for the session and car where lap_time_ms > 0
            cursor.execute(
                """
                SELECT lap_time_ms, wear_end_pct
                FROM laps
                WHERE session_uid = ? AND car_index = ? AND lap_time_ms > 0
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

            # Calculate laps until cliff
            # Get the latest wear percentage
            latest_wear = df_filtered["wear_end_pct"].iloc[-1]
            cliff_threshold = 70.0
            wear_remaining = cliff_threshold - latest_wear

            if average_wear_per_lap > 0:
                laps_until_cliff = int(wear_remaining / average_wear_per_lap)
            else:
                laps_until_cliff = 999  # Very high number if no degradation

            return {
                "total_laps": len(df_filtered),
                "fastest_lap": fastest_lap,
                "average_lap_time": average_lap_time,
                "average_wear_per_lap": average_wear_per_lap,
                "laps_until_cliff": laps_until_cliff,
            }

        finally:
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



