import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QLineEdit, QGridLayout
)

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

        details_group = QGroupBox("Session Details")
        details_layout = QGridLayout()
        
        self.name_input = QLineEdit()
        self.series_input = QLineEdit()
        self.team_input = QLineEdit()
        self.date_input = QLineEdit()
        self.track_input = QLineEdit()
        self.type_input = QLineEdit()
        
        details_layout.addWidget(QLabel("Name:"), 0, 0)
        details_layout.addWidget(self.name_input, 0, 1)
        details_layout.addWidget(QLabel("Series:"), 0, 2)
        details_layout.addWidget(self.series_input, 0, 3)
        details_layout.addWidget(QLabel("Team:"), 0, 4)
        details_layout.addWidget(self.team_input, 0, 5)
        
        details_layout.addWidget(QLabel("Date:"), 1, 0)
        details_layout.addWidget(self.date_input, 1, 1)
        details_layout.addWidget(QLabel("Track:"), 1, 2)
        details_layout.addWidget(self.track_input, 1, 3)
        details_layout.addWidget(QLabel("Type:"), 1, 4)
        details_layout.addWidget(self.type_input, 1, 5)
        
        self.save_details_btn = QPushButton("Save Details")
        self.save_details_btn.clicked.connect(self._save_session_details)
        details_layout.addWidget(self.save_details_btn, 1, 6)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

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
                    "SELECT session_uid, track_name, session_type_name, session_name, series, team, session_date "
                    "FROM sessions ORDER BY rowid DESC"
                )
                rows = cur.fetchall()
        except Exception:
            try:
                # Fallback for old schema
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT session_uid, track_name, session_type_name, '', '', '', '' "
                        "FROM sessions ORDER BY rowid DESC"
                    )
                    rows = cur.fetchall()
            except Exception:
                rows = []

        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        for row in rows:
            uid = row[0]
            track = row[1]
            stype = row[2]
            sname = row[3] if len(row) > 3 else ""
            series = row[4] if len(row) > 4 else ""
            team = row[5] if len(row) > 5 else ""
            sdate = row[6] if len(row) > 6 else ""

            parts = []
            if sname:
                parts.append(sname)
            else:
                parts.append(track or 'Unknown Track')
            
            subparts = []
            if series:
                subparts.append(series)
            if team:
                subparts.append(team)
            if sdate:
                subparts.append(sdate)
            
            if not sname:
                subparts.append(stype or 'Session')
            else:
                if track:
                    subparts.append(track)
                if stype:
                    subparts.append(stype)

            if subparts:
                label = f"{parts[0]} ({' · '.join(subparts)}) [{uid[:8]}...]"
            else:
                label = f"{parts[0]} [{uid[:8]}...]"
                
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

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT track_name, session_type_name, session_name, series, team, session_date "
                    "FROM sessions WHERE session_uid=?",
                    (session_uid,),
                )
                sess_row = cur.fetchone()
        except Exception:
            sess_row = None

        if sess_row and hasattr(self, 'name_input'):
            track, stype, sname, series, team, sdate = sess_row
            self.name_input.setText(sname or "")
            self.series_input.setText(series or "")
            self.team_input.setText(team or "")
            self.date_input.setText(sdate or "")
            self.track_input.setText(track or "")
            self.type_input.setText(stype or "")
        elif hasattr(self, 'name_input'):
            self.name_input.clear()
            self.series_input.clear()
            self.team_input.clear()
            self.date_input.clear()
            self.track_input.clear()
            self.type_input.clear()

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

    def _save_session_details(self):
        uid = self.session_combo.currentData()
        if not uid:
            return
        
        sname = self.name_input.text().strip()
        series = self.series_input.text().strip()
        team = self.team_input.text().strip()
        sdate = self.date_input.text().strip()
        track = self.track_input.text().strip()
        stype = self.type_input.text().strip()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE sessions SET session_name=?, series=?, team=?, session_date=?, track_name=?, session_type_name=? "
                    "WHERE session_uid=?",
                    (sname, series, team, sdate, track, stype, uid),
                )
                conn.commit()
            QMessageBox.information(self, "Success", "Session details updated successfully.")
            self.refresh_sessions()
            index = self.session_combo.findData(uid)
            if index != -1:
                self.session_combo.blockSignals(True)
                self.session_combo.setCurrentIndex(index)
                self.session_combo.blockSignals(False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save details: {e}")

    def current_session_uid(self):
        return self.session_combo.currentData()
