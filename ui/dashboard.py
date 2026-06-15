import sqlite3
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer
import pyqtgraph as pg

class TelemetryDashboard(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.setWindowTitle("F1 25 Race Engineer - Live Feed")
        self.resize(1200, 800)  # Great starting size for a second monitor

        # 1. Main Window Setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # 2. Top Bar (Basic Text Metrics)
        self.top_bar = QHBoxLayout()
        self.speed_label = QLabel("SPEED: --- km/h")
        self.gear_label = QLabel("GEAR: -")

        # Make the text big and easy to read
        font = self.speed_label.font()
        font.setPointSize(24)
        font.setBold(True)
        self.speed_label.setFont(font)
        self.gear_label.setFont(font)

        self.top_bar.addWidget(self.speed_label)
        self.top_bar.addWidget(self.gear_label)
        self.layout.addLayout(self.top_bar)

        # 3. Live Plotting Area
        self.plot_widget = pg.PlotWidget(title="Live Micro-Telemetry (Last 10 Seconds)")
        self.plot_widget.addLegend()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setYRange(0, 1.1)  # Throttle/Brake are exactly 0.0 to 1.0

        self.throttle_curve = self.plot_widget.plot(pen=pg.mkPen('g', width=2), name='Throttle')
        self.brake_curve = self.plot_widget.plot(pen=pg.mkPen('r', width=2), name='Brake')
        self.layout.addWidget(self.plot_widget)

        # 4. Database Connection (Read-Only Polling)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        # 5. The Heartbeat Timer (Polls UI at 10Hz)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100) # 100 milliseconds

    def update_ui(self):
        try:
            cur = self.conn.cursor()
            # Grab the last ~10 seconds of telemetry at 30Hz
            cur.execute('''
                SELECT lap_distance, throttle, brake, speed, gear 
                FROM telemetry 
                ORDER BY id DESC LIMIT 300
            ''')
            rows = cur.fetchall()

            if not rows:
                return

            # Reverse rows so they plot chronologically (left to right)
            rows.reverse()

            # Update Live Text (Grab the absolute newest row at the end of the array)
            latest = rows[-1]
            self.speed_label.setText(f"SPEED: {latest[3]} km/h")
            self.gear_label.setText(f"GEAR: {latest[4]}")

            # Update Live Plot
            distances = [r[0] for r in rows]
            throttles = [r[1] for r in rows]
            brakes = [r[2] for r in rows]

            self.throttle_curve.setData(distances, throttles)
            self.brake_curve.setData(distances, brakes)

        except Exception as e:
            print(f"UI Update Error: {e}")

    def closeEvent(self, event):
        # Cleanly close the database connection if you click the X button
        self.conn.close()
        event.accept()

