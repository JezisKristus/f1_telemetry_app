import sqlite3
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor
from analytics.stint_analyzer import StintAnalyzer


class TelemetryDashboard(QMainWindow):
    """Simplified telemetry dashboard.

    Displays the current session UID and a table of recent laps from the
    `laps` table in the SQLite database pointed to by `db_path`.
    """

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.setWindowTitle("F1 Telemetry Dashboard")
        self.resize(1000, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # Session label (large, bold)
        self.session_label = QLabel("Session: -")
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        self.session_label.setFont(font)
        self.layout.addWidget(self.session_label)

        # Table for laps
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Car Index", "Lap Time", "Sector 1", "Sector 2", "Sector 3"
        ])
        header = self.table.horizontalHeader()
        # Stretch columns to fill the available space
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)

        # Degradation analysis plot
        self.degradation_plot = pg.PlotWidget(title="Tire Degradation Analysis")
        self.degradation_plot.setLabel('bottom', 'Lap Number')
        self.degradation_plot.setLabel('left', 'Lap Time (s)')

        # Configure clean aesthetic: remove grid lines, minimal ticks
        self.degradation_plot.showGrid(x=False, y=False)

        # Create right Y-axis for tire wear percentage
        self.right_axis = pg.ViewBox()
        self.degradation_plot.getPlotItem().layout.addItem(self.right_axis, 2, 3)
        self.degradation_plot.getPlotItem().getAxis('right').linkToView(self.right_axis)
        self.degradation_plot.getPlotItem().getAxis('right').setLabel('Tire Wear (%)')

        # Update geometry when plot is resized
        self.degradation_plot.getPlotItem().vb.sigResized.connect(self._update_right_axis_geometry)

        # Create curves for actual lap times, predicted lap times, and wear
        self.actual_time_curve = pg.PlotCurveItem(pen=pg.mkPen(color='white', width=2))
        self.predicted_time_curve = pg.PlotCurveItem(pen=pg.mkPen(color='red', width=2, style=Qt.PenStyle.DashLine))
        self.wear_curve = pg.PlotCurveItem(pen=pg.mkPen(color='cyan', width=2))

        # Add curves to plot
        self.degradation_plot.addItem(self.actual_time_curve)
        self.degradation_plot.addItem(self.predicted_time_curve)
        self.right_axis.addItem(self.wear_curve)

        self.layout.addWidget(self.degradation_plot)

        # Timer for periodic updates (500 ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)

        # Initial population
        self.update_ui()

    def _update_right_axis_geometry(self):
        """Update the right axis geometry when the plot is resized."""
        self.right_axis.setGeometry(self.degradation_plot.getPlotItem().vb.sceneBoundingRect())

    def update_ui(self):
        """Query the DB for the latest 15 laps (lap_time_ms > 0) and update the table.

        Also updates the session label using the most recent session_uid found in
        the `laps` table.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            # Update session label from the newest lap's session_uid
            try:
                cur.execute(
                    "SELECT session_uid FROM laps WHERE session_uid IS NOT NULL ORDER BY rowid DESC LIMIT 1"
                )
                row = cur.fetchone()
                session_uid = row[0] if row and row[0] is not None else "-"
            except Exception:
                session_uid = "-"
            self.session_label.setText(f"Session: {session_uid}")

            # Fetch latest 15 completed laps (lap_time_ms > 0)
            cur.execute(
                """
                SELECT car_index, lap_time_ms, sector_1_ms, sector_2_ms, sector_3_ms
                FROM laps
                WHERE lap_time_ms > 0
                ORDER BY rowid DESC
                LIMIT 15
                """
            )
            rows = cur.fetchall()
            conn.close()

            # Populate table; show newest first (as returned)
            self.table.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                car_index, lap_ms, s1_ms, s2_ms, s3_ms = row

                # Car Index
                item = QTableWidgetItem(str(car_index if car_index is not None else "-"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, 0, item)

                # Helper to format ms -> seconds string or hyphen
                def fmt(ms_val):
                    try:
                        if ms_val is None or int(ms_val) == 0:
                            return "-"
                        return f"{(int(ms_val) / 1000.0):.3f} s"
                    except Exception:
                        return "-"

                lap_item = QTableWidgetItem(fmt(lap_ms))
                lap_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, 1, lap_item)

                s1_item = QTableWidgetItem(fmt(s1_ms))
                s1_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, 2, s1_item)

                s2_item = QTableWidgetItem(fmt(s2_ms))
                s2_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, 3, s2_item)

                s3_item = QTableWidgetItem(fmt(s3_ms))
                s3_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r_idx, 4, s3_item)

            # Update degradation curve if session_uid is valid
            if session_uid != "-":
                try:
                    # Get the first car_index from the rows for degradation analysis
                    if rows:
                        car_index = rows[0][0]  # car_index from first row

                        # Instantiate StintAnalyzer and get degradation prediction
                        analyzer = StintAnalyzer(self.db_path)
                        prediction = analyzer.predict_degradation_curve(session_uid, car_index)

                        # Update curves if we have enough data (more than 3 valid laps)
                        if prediction and len(prediction["lap_numbers"]) > 3:
                            self.actual_time_curve.setData(
                                x=prediction["lap_numbers"],
                                y=prediction["actual_times"]
                            )
                            self.predicted_time_curve.setData(
                                x=prediction["lap_numbers"],
                                y=prediction["predicted_times"]
                            )
                            self.wear_curve.setData(
                                x=prediction["lap_numbers"],
                                y=prediction["wear_percentages"]
                            )
                except Exception as e:
                    # Log degradation analysis error but don't crash the UI
                    print(f"Degradation analysis error: {e}")


        except Exception as e:
            # Avoid crashing the UI; print for debugging
            print(f"Dashboard update error: {e}")

    def closeEvent(self, event):
        try:
            if self.timer.isActive():
                self.timer.stop()
        except Exception:
            pass
        event.accept()

