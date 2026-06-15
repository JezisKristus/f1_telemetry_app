import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QGroupBox,
)

from analytics.ai_difficulty import AIDifficultyScaler
from analytics.delta_analyzer import DeltaAnalyzer
from analytics.session_report import SessionReportExporter
from analytics.setup_evolution import SetupEvolution
from analytics.slip_angle import SlipAngleDetector


def _format_lap_time(ms):
    if not ms:
        return "N/A"
    s = ms / 1000.0
    m = int(s // 60)
    sec = s % 60
    return f"{m}:{sec:06.3f}" if m else f"{sec:.3f}"


class CoachPanel(QWidget):
    """Post-session delta traces, slip analysis, setup history."""

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.delta = DeltaAnalyzer(db_path)
        self.slip = SlipAngleDetector(db_path)
        self.setup_evo = SetupEvolution(db_path)
        self.report = SessionReportExporter(db_path)
        self.ai_scaler = AIDifficultyScaler(db_path)

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.session_label = QLabel("Session: -")
        controls.addWidget(self.session_label)
        self.ref_combo = QComboBox()
        self.comp_combo = QComboBox()
        controls.addWidget(QLabel("Reference:"))
        controls.addWidget(self.ref_combo)
        controls.addWidget(QLabel("Compare:"))
        controls.addWidget(self.comp_combo)
        self.compare_btn = QPushButton("Compare")
        self.compare_btn.clicked.connect(self._run_comparison)
        controls.addWidget(self.compare_btn)
        self.export_btn = QPushButton("Export Report")
        self.export_btn.clicked.connect(self._export_report)
        controls.addWidget(self.export_btn)
        layout.addLayout(controls)

        self.plot = pg.PlotWidget(title="Delta Trace")
        self.plot.setLabel("bottom", "Lap Distance")
        self.plot.setLabel("left", "Speed (km/h)")
        self.plot.addLegend()
        self.speed_ref = self.plot.plot(pen=pg.mkPen("w", width=2), name="Ref Speed")
        self.speed_comp = self.plot.plot(pen=pg.mkPen("r", width=2), name="Comp Speed")
        layout.addWidget(self.plot, stretch=2)

        self.input_plot = pg.PlotWidget(title="Inputs")
        self.input_plot.setLabel("bottom", "Lap Distance")
        self.throttle_ref = self.input_plot.plot(pen=pg.mkPen("g", width=1), name="Ref Throttle")
        self.brake_ref = self.input_plot.plot(pen=pg.mkPen("r", width=1), name="Ref Brake")
        layout.addWidget(self.input_plot, stretch=1)

        info_box = QGroupBox("Coaching Insights")
        info_layout = QVBoxLayout(info_box)
        self.insights_label = QLabel("Select laps and click Compare")
        self.insights_label.setWordWrap(True)
        info_layout.addWidget(self.insights_label)
        layout.addWidget(info_box)

        self._session_uid = None

    def refresh_sessions(self, session_uid=None):
        if session_uid:
            self._session_uid = session_uid
        if not self._session_uid:
            return
        self.session_label.setText(f"Session: {self._session_uid}")
        laps = self.delta.get_valid_laps(self._session_uid, 0)
        self.ref_combo.clear()
        self.comp_combo.clear()
        for lap in laps:
            label = f"{lap['lap_id']} ({_format_lap_time(lap['lap_time_ms'])})"
            self.ref_combo.addItem(label, lap["lap_id"])
            self.comp_combo.addItem(label, lap["lap_id"])
        if laps:
            self.comp_combo.setCurrentIndex(min(1, len(laps) - 1))

        slip_result = self.slip.analyze_session(self._session_uid)
        ai_recs = self.ai_scaler.analyze(self._session_uid) or []
        setups = self.setup_evo.get_setups_for_track()[:3]
        lines = [slip_result.get("summary", "")]
        lines.extend(r["message"] for r in ai_recs)
        for s in setups:
            lines.append(
                f"Setup FW{s['front_wing']}/RW{s['rear_wing']} — {_format_lap_time(s['lap_time_ms'])}"
            )
        self.insights_label.setText("\n".join(lines) if lines else "No coaching data yet")

    def _run_comparison(self):
        if not self._session_uid:
            return
        ref_id = self.ref_combo.currentData()
        comp_id = self.comp_combo.currentData()
        if not ref_id or not comp_id:
            return
        result = self.delta.compare_laps(self._session_uid, ref_id, comp_id)
        if not result:
            self.insights_label.setText("Not enough telemetry for comparison")
            return

        d = result["distance"]
        self.speed_ref.setData(d, result["speed_ref"])
        self.speed_comp.setData(d, result["speed_comp"])
        self.throttle_ref.setData(d, result["throttle_ref"])
        self.brake_ref.setData(d, result["brake_ref"])

        hints = [f"Lost {r['delta_ms']:.0f}ms — {r['hint']}" for r in result["loss_regions"][:5]]
        total_delta = result["delta_time_ms"][-1] if len(result["delta_time_ms"]) else 0
        summary = f"Total delta: {total_delta:.0f}ms\n" + "\n".join(hints)
        self.insights_label.setText(summary)

    def _export_report(self):
        if not self._session_uid:
            return
        path = self.report.export_html(self._session_uid)
        self.insights_label.setText(f"Report exported to {path}")
