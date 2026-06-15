import sqlite3
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt

from analytics.setup_evolution import SetupEvolution


def _format_ms(ms_val):
    try:
        if ms_val is None or int(ms_val) == 0:
            return "-"
        return f"{(int(ms_val) / 1000.0):.3f} s"
    except Exception:
        return "-"


class HistoryPanel(QWidget):
    """Session picker, lap history, setup table."""

    session_changed = None  # callback set by dashboard

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.setup_evo = SetupEvolution(db_path)
        layout = QVBoxLayout(self)

        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        picker_row.addWidget(self.session_combo, stretch=1)
        self.delete_btn = QPushButton("Delete Session")
        self.delete_btn.clicked.connect(self._delete_session)
        picker_row.addWidget(self.delete_btn)
        layout.addLayout(picker_row)

        self.lap_table = QTableWidget()
        self.lap_table.setColumnCount(6)
        self.lap_table.setHorizontalHeaderLabels(
            ["Car", "Lap Time", "S1", "S2", "S3", "Valid"]
        )
        self.lap_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.lap_table)

        layout.addWidget(QLabel("Setup History"))
        self.setup_table = QTableWidget()
        self.setup_table.setColumnCount(5)
        self.setup_table.setHorizontalHeaderLabels(
            ["Track", "FW", "RW", "Lap Time", "Pressures"]
        )
        self.setup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.setup_table)

        self.refresh_sessions()

    def refresh_sessions(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT session_uid, track_name, session_type_name FROM sessions ORDER BY rowid DESC"
                )
                rows = cur.fetchall()
        except Exception:
            rows = []

        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        for uid, track, stype in rows:
            label = f"{track or 'Unknown'} · {stype or 'Session'} ({uid[:8]}...)"
            self.session_combo.addItem(label, uid)
        self.session_combo.blockSignals(False)
        if rows:
            self._load_session(rows[0][0])

    def _on_session_changed(self, index):
        uid = self.session_combo.currentData()
        if uid:
            self._load_session(uid)
            if callable(self.session_changed):
                self.session_changed(uid)

    def _load_session(self, session_uid):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT car_index, lap_time_ms, sector_1_ms, sector_2_ms, sector_3_ms, is_valid "
                    "FROM laps WHERE session_uid=? AND lap_time_ms>0 ORDER BY rowid DESC LIMIT 20",
                    (session_uid,),
                )
                rows = cur.fetchall()
        except Exception:
            rows = []

        self.lap_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                text = str(val) if j == 5 else (_format_ms(val) if j > 0 else str(val))
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.lap_table.setItem(i, j, item)

        setups = self.setup_evo.get_setups_for_track()
        session_setups = [s for s in setups if s["session_uid"] == session_uid]
        self.setup_table.setRowCount(len(session_setups))
        for i, s in enumerate(session_setups):
            for j, val in enumerate([
                s.get("track_name", ""), s["front_wing"], s["rear_wing"],
                _format_ms(s["lap_time_ms"]), s.get("pressures", ""),
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setup_table.setItem(i, j, item)

    def _delete_session(self):
        uid = self.session_combo.currentData()
        if not uid:
            return
        reply = QMessageBox.question(
            self, "Delete Session", f"Delete session {uid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            from database.db_manager import DBManager
            DBManager(db_path=self.db_path).delete_session(uid)
            self.refresh_sessions()

    def current_session_uid(self):
        return self.session_combo.currentData()
