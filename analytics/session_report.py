import sqlite3
from datetime import datetime
from pathlib import Path

from analytics.setup_evolution import SetupEvolution
from analytics.slip_angle import SlipAngleDetector
from analytics.stint_analyzer import StintAnalyzer


class SessionReportExporter:
    """Export session summary as HTML report."""

    def __init__(self, db_path):
        self.db_path = db_path

    def export_html(self, session_uid, player_car_index=0, output_path=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT track_name, session_type_name FROM sessions WHERE session_uid=?",
            (session_uid,),
        )
        session_row = cur.fetchone()
        conn.close()

        track = session_row[0] if session_row else "Unknown"
        session_type = session_row[1] if session_row else "Unknown"

        stint = StintAnalyzer(self.db_path).get_stint_summary(session_uid, player_car_index)
        slip = SlipAngleDetector(self.db_path).analyze_session(session_uid)
        setup = SetupEvolution(self.db_path).best_setup_at_track(track)

        if output_path is None:
            output_path = Path("reports") / f"session_{session_uid}_{datetime.now():%Y%m%d_%H%M%S}.html"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>F1 Session Report</title>
<style>body{{font-family:sans-serif;margin:2em;background:#111;color:#eee}}
h1{{color:#e10600}}.stat{{margin:0.5em 0}}</style></head><body>
<h1>F1 25 Session Report</h1>
<p>Track: {track} | Session: {session_type} | UID: {session_uid}</p>
<p>Generated: {datetime.now():%Y-%m-%d %H:%M:%S}</p>
<h2>Stint Summary</h2>
<p class="stat">Total laps: {stint.get('total_laps', 0)}</p>
<p class="stat">Fastest lap: {stint.get('fastest_lap', 'N/A')}</p>
<p class="stat">Laps until cliff: {stint.get('laps_until_cliff', 'N/A')}</p>
<h2>Slip Angle Analysis</h2>
<p>{slip.get('summary', 'No data')}</p>
<h2>Best Setup</h2>
<p>{f"Front wing {setup['front_wing']}, Rear wing {setup['rear_wing']}" if setup else "No setup data"}</p>
</body></html>"""

        output_path.write_text(html, encoding="utf-8")
        return str(output_path)
