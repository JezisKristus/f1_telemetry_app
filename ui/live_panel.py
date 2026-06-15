import sqlite3
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QProgressBar, QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from analytics.stint_analyzer import StintAnalyzer
from analytics.strategy.pit_window import PitWindowCalculator
from analytics.strategy.tire_monitor import PushSaveMonitor
from analytics.strategy.dirty_air import DirtyAirMonitor
from analytics.strategy.fuel_ers import FuelERSManager


def _format_ms(ms_val):
    try:
        if ms_val is None or int(ms_val) == 0:
            return "-"
        s = int(ms_val) / 1000.0
        m = int(s // 60)
        sec = s % 60
        return f"{m}:{sec:06.3f}" if m else f"{sec:.3f}"
    except Exception:
        return "-"


def _sector_color(sector_ms, best_ms):
    if not sector_ms or not best_ms:
        return "#cccccc"
    if sector_ms <= best_ms:
        return "#aa00ff"  # purple
    if sector_ms <= best_ms * 1.005:
        return "#00cc00"  # green
    return "#cccccc"


class LivePanel(QWidget):
    """Live timing, tire state, stint summary, and strategy alerts."""

    def __init__(self, db_path, logger_obj=None, config=None):
        super().__init__()
        self.db_path = db_path
        self.logger_obj = logger_obj
        cfg = config or {}
        strat = cfg.get("strategy", {})

        self.stint_analyzer = StintAnalyzer(db_path)
        self.pit_calc = PitWindowCalculator(
            db_path,
            pit_loss_seconds=strat.get("pit_loss_seconds", 22),
            cliff_pct=strat.get("wear_cliff_pct", 70),
        )
        self.tire_monitor = PushSaveMonitor(db_path)
        self.dirty_air = DirtyAirMonitor(
            db_path,
            delta_threshold_ms=int(strat.get("dirty_air_delta_seconds", 1.5) * 1000),
            lap_threshold=strat.get("dirty_air_lap_threshold", 3),
        )
        self.fuel_ers = FuelERSManager()

        layout = QVBoxLayout(self)

        # Header row
        header = QHBoxLayout()
        self.status_label = QLabel("● OFFLINE")
        self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.session_info = QLabel("Session: -")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        self.session_info.setFont(font)
        header.addWidget(self.session_info)
        header.addStretch()
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Timing row
        timing_box = QGroupBox("Live Timing")
        timing_layout = QGridLayout(timing_box)
        self.best_lap_label = QLabel("Best: -")
        self.last_lap_label = QLabel("Last: -")
        self.current_lap_label = QLabel("Current: -")
        self.delta_label = QLabel("Δ Best: -")
        self.s1_label = QLabel("S1: -")
        self.s2_label = QLabel("S2: -")
        self.s3_label = QLabel("S3: -")
        self.position_label = QLabel("P: -")
        for i, lbl in enumerate([
            self.best_lap_label, self.last_lap_label, self.current_lap_label,
            self.delta_label, self.s1_label, self.s2_label, self.s3_label, self.position_label,
        ]):
            timing_layout.addWidget(lbl, i // 4, i % 4)
        layout.addWidget(timing_box)

        # Tire panel
        tire_box = QGroupBox("Tires")
        tire_layout = QVBoxLayout(tire_box)
        self.compound_label = QLabel("Compound: -")
        tire_layout.addWidget(self.compound_label)
        self.wear_bars = {}
        wear_grid = QGridLayout()
        for i, corner in enumerate(["FL", "FR", "RL", "RR"]):
            lbl = QLabel(corner)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat("%v%")
            wear_grid.addWidget(lbl, i // 2, (i % 2) * 2)
            wear_grid.addWidget(bar, i // 2, (i % 2) * 2 + 1)
            self.wear_bars[corner.lower()] = bar
        tire_layout.addLayout(wear_grid)
        self.temp_label = QLabel("Surface: - | Core: -")
        tire_layout.addWidget(self.temp_label)
        layout.addWidget(tire_box)

        # Stint summary
        stint_box = QGroupBox("Stint Summary")
        stint_layout = QVBoxLayout(stint_box)
        self.stint_label = QLabel("Laps until cliff: -")
        stint_layout.addWidget(self.stint_label)
        layout.addWidget(stint_box)

        # Strategy alerts
        alerts_box = QGroupBox("Strategy Alerts")
        alerts_layout = QVBoxLayout(alerts_box)
        self.alerts_label = QLabel("No alerts")
        self.alerts_label.setWordWrap(True)
        self.alerts_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        alerts_layout.addWidget(self.alerts_label)
        layout.addWidget(alerts_box)

        layout.addStretch()
        self._session_uid = "-"
        self._best_sectors = {"s1": 0, "s2": 0, "s3": 0}

    def update_data(self, player_car_index=0):
        # Connection health
        if self.logger_obj:
            health = self.logger_obj.get_connection_health()
            if health["connected"]:
                self.status_label.setText(f"● LIVE ({health['packet_rate']} pkt/s)")
                self.status_label.setStyleSheet("color: #44ff44; font-weight: bold;")
            else:
                self.status_label.setText("● NO TELEMETRY")
                self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")

            live = self.logger_obj.get_live_timing(player_car_index)
            if live:
                self._update_timing(live)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT session_uid, track_name, session_type_name FROM sessions ORDER BY rowid DESC LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    self._session_uid = row[0]
                    track = row[1] or "Unknown"
                    stype = row[2] or ""
                    self.session_info.setText(f"{track} · {stype}")

                if self._session_uid != "-":
                    summary = self.stint_analyzer.get_stint_summary(self._session_uid, player_car_index)
                    cliff = summary.get("laps_until_cliff")
                    self.stint_label.setText(
                        f"Laps: {summary.get('total_laps', 0)} | "
                        f"Fastest: {summary.get('fastest_lap', 0):.3f}s | "
                        f"Cliff in: {cliff if cliff else '-'} laps"
                        if summary.get("fastest_lap") else "Laps until cliff: -"
                    )
                    self._update_alerts(summary, player_car_index)
        except Exception:
            pass

    def _update_timing(self, live):
        self.best_lap_label.setText(f"Best: {_format_ms(live.get('best_lap_time_ms'))}")
        self.last_lap_label.setText(f"Last: {_format_ms(live.get('last_lap_time_ms'))}")
        self.current_lap_label.setText(f"Current: {_format_ms(live.get('current_lap_time_ms'))}")

        best = live.get("best_lap_time_ms", 0)
        current = live.get("current_lap_time_ms", 0)
        if best and current:
            delta = (current - best) / 1000.0
            sign = "+" if delta >= 0 else ""
            self.delta_label.setText(f"Δ Best: {sign}{delta:.3f}")

        s1, s2 = live.get("sector_1_ms", 0), live.get("sector_2_ms", 0)
        for key, val in [("s1", s1), ("s2", s2)]:
            if val and (self._best_sectors[key] == 0 or val < self._best_sectors[key]):
                self._best_sectors[key] = val

        self.s1_label.setText(f"S1: {_format_ms(s1)}")
        self.s1_label.setStyleSheet(f"color: {_sector_color(s1, self._best_sectors['s1'])}")
        self.s2_label.setText(f"S2: {_format_ms(s2)}")
        self.s2_label.setStyleSheet(f"color: {_sector_color(s2, self._best_sectors['s2'])}")
        self.s3_label.setText("S3: -")
        self.position_label.setText(f"P: {live.get('position', '-')}")

        compound = live.get("tire_compound", 0)
        age = live.get("tyres_age_laps", 0)
        from telemetry.packets import TIRE_COMPOUND_NAMES
        cname = TIRE_COMPOUND_NAMES.get(compound, str(compound) if compound else "-")
        self.compound_label.setText(f"Compound: {cname} (Lap {age})")

        wear = live.get("wear", {})
        for corner, key in [("fl", "wear_fl"), ("fr", "wear_fr"), ("rl", "wear_rl"), ("rr", "wear_rr")]:
            if key in wear:
                self.wear_bars[corner].setValue(int(wear[key]))

    def _update_alerts(self, stint_summary, player_car_index=0):
        alerts = []
        current_lap = stint_summary.get("total_laps", 0)

        pit = self.pit_calc.calculate(self._session_uid, player_car_index, current_lap)
        if pit:
            alerts.append(pit["message"])

        tire_alert = self.tire_monitor.evaluate_from_db(self._session_uid)
        if tire_alert:
            alerts.append(tire_alert["message"])

        dirty = self.dirty_air.evaluate(self._session_uid, player_car_index, current_lap)
        if dirty:
            alerts.append(dirty["message"])

        if self.logger_obj:
            status = {**self.logger_obj.get_player_status(), **self.logger_obj.get_live_timing(player_car_index)}
            for a in self.fuel_ers.evaluate(status):
                alerts.append(a["message"])

        if alerts:
            self.alerts_label.setText("\n".join(f"• {a}" for a in alerts))
        else:
            self.alerts_label.setText("No alerts")
