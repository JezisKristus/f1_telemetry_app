import sqlite3
import traceback

import pyqtgraph as pg
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTabWidget

from analytics.stint_analyzer import StintAnalyzer
from ui.coach_panel import CoachPanel
from ui.history_panel import HistoryPanel
from ui.live_panel import LivePanel
from ui.track_map import TrackMapPanel


class TelemetryDashboard(QMainWindow):
    """Tabbed PyQt6 engineer dashboard."""

    def __init__(self, db_path: str, logger_obj=None, config=None):
        super().__init__()
        self.db_path = db_path
        self.logger_obj = logger_obj
        self.config = config or {}
        self.setWindowTitle("F1 25 Engineer")
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.live_panel = LivePanel(db_path, logger_obj, self.config)
        self.coach_panel = CoachPanel(db_path)
        self.track_map = TrackMapPanel(logger_obj)
        self.history_panel = HistoryPanel(db_path)

        self.tabs.addTab(self.live_panel, "Live")
        self.tabs.addTab(self.coach_panel, "Coach")
        self.tabs.addTab(self.track_map, "Track Map")
        self.tabs.addTab(self.history_panel, "History")
        layout.addWidget(self.tabs)

        # Degradation chart on Live tab bottom
        self.degradation_plot = pg.PlotWidget(title="Tire Degradation")
        self.degradation_plot.setLabel("bottom", "Lap Number")
        self.degradation_plot.setLabel("left", "Lap Time (s)")
        self.degradation_plot.showGrid(x=False, y=False)
        self.right_axis = pg.ViewBox()
        self.degradation_plot.getPlotItem().layout.addItem(self.right_axis, 2, 3)
        self.degradation_plot.getPlotItem().getAxis("right").linkToView(self.right_axis)
        self.degradation_plot.getPlotItem().getAxis("right").setLabel("Tire Wear (%)")
        self.degradation_plot.getPlotItem().vb.sigResized.connect(self._update_right_axis_geometry)
        self.right_axis.setXLink(self.degradation_plot.getPlotItem().vb)  # Links horizontal zooming
        self.actual_time_curve = pg.PlotCurveItem(pen=pg.mkPen(color="white", width=2))
        self.predicted_time_curve = pg.PlotCurveItem(pen=pg.mkPen(color="red", width=2, style=Qt.PenStyle.DashLine))
        self.wear_curve = pg.PlotCurveItem(pen=pg.mkPen(color="cyan", width=2, style=Qt.PenStyle.DashLine))
        self.wear_fl_curve = pg.PlotCurveItem(pen=pg.mkPen(color="#ff6b6b", width=1.5))
        self.wear_fr_curve = pg.PlotCurveItem(pen=pg.mkPen(color="#feca57", width=1.5))
        self.wear_rl_curve = pg.PlotCurveItem(pen=pg.mkPen(color="#1dd1a1", width=1.5))
        self.wear_rr_curve = pg.PlotCurveItem(pen=pg.mkPen(color="#48dbfb", width=1.5))
        
        self.degradation_plot.addItem(self.actual_time_curve)
        self.degradation_plot.addItem(self.predicted_time_curve)
        self.right_axis.addItem(self.wear_curve)
        self.right_axis.addItem(self.wear_fl_curve)
        self.right_axis.addItem(self.wear_fr_curve)
        self.right_axis.addItem(self.wear_rl_curve)
        self.right_axis.addItem(self.wear_rr_curve)
        self.live_panel.layout().addWidget(self.degradation_plot)

        self.history_panel.session_changed = self._on_session_selected

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)

        self._session_uid = "-"
        self.update_ui()

    def _update_right_axis_geometry(self):
        self.right_axis.setGeometry(self.degradation_plot.getPlotItem().vb.sceneBoundingRect())

    def _on_session_selected(self, session_uid):
        # Trigger update_ui so it safely fetches the correct player_car_index from the DB
        self.history_panel._current_session_uid = session_uid
        self.update_ui()

    def update_ui(self):
        self.track_map.update_positions()

        try:
            session_uid = self.history_panel.current_session_uid()
            player_car_index = 0

            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                if not session_uid:
                    cur.execute(
                        "SELECT session_uid, player_car_index FROM sessions ORDER BY rowid DESC LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row:
                        session_uid = row[0]
                        player_car_index = row[1] if row[1] is not None else 0
                else:
                    cur.execute(
                        "SELECT player_car_index FROM sessions WHERE session_uid = ?",
                        (session_uid,),
                    )
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        player_car_index = row[0]

            self.live_panel.update_data(player_car_index)

            if session_uid:
                if session_uid != self._session_uid or getattr(self.coach_panel, '_player_car_index', -1) != player_car_index:
                    self._session_uid = session_uid
                    self.coach_panel.refresh_sessions(session_uid, player_car_index)

            if session_uid:
                analyzer = StintAnalyzer(self.db_path)
                prediction = analyzer.predict_degradation_curve(session_uid, player_car_index)
                lap_numbers = prediction.get("lap_numbers", []) if prediction else []
                if lap_numbers and len(lap_numbers) > 3:
                    self.actual_time_curve.setData(
                        x=lap_numbers, y=prediction.get("actual_times", [])
                    )
                    self.predicted_time_curve.setData(
                        x=lap_numbers, y=prediction.get("predicted_times", [])
                    )
                    self.wear_curve.setData(
                        x=lap_numbers, y=prediction.get("wear_percentages", [])
                    )
                    self.wear_fl_curve.setData(
                        x=lap_numbers, y=prediction.get("wear_fl", [])
                    )
                    self.wear_fr_curve.setData(
                        x=lap_numbers, y=prediction.get("wear_fr", [])
                    )
                    self.wear_rl_curve.setData(
                        x=lap_numbers, y=prediction.get("wear_rl", [])
                    )
                    self.wear_rr_curve.setData(
                        x=lap_numbers, y=prediction.get("wear_rr", [])
                    )
                else:
                    self.actual_time_curve.setData(x=[], y=[])
                    self.predicted_time_curve.setData(x=[], y=[])
                    self.wear_curve.setData(x=[], y=[])
                    self.wear_fl_curve.setData(x=[], y=[])
                    self.wear_fr_curve.setData(x=[], y=[])
                    self.wear_rl_curve.setData(x=[], y=[])
                    self.wear_rr_curve.setData(x=[], y=[])
        except Exception as e:
            print(f"Dashboard update error: {e}")
            print(traceback.format_exc())

    def closeEvent(self, event):
        if self.timer.isActive():
            self.timer.stop()
        if self.logger_obj:
            self.logger_obj.stop()
        event.accept()
