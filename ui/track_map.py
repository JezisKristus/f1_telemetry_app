import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont


class TrackMapPanel(QWidget):
    """2D track radar showing 20-car positions from Motion packet cache."""

    PLAYER_COLOR = "#e10600"
    CAR_COLOR = "#888888"

    def __init__(self, logger_obj=None):
        super().__init__()
        self.logger_obj = logger_obj
        layout = QVBoxLayout(self)

        title = QLabel("Track Radar")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        self.plot = pg.PlotWidget(title="Car Positions (X/Z)")
        self.plot.setAspectLocked(True)
        self.plot.setLabel("bottom", "World X")
        self.plot.setLabel("left", "World Z")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self.plot)

        self.car_scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush(self.CAR_COLOR))
        self.player_scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen("w", width=2), brush=pg.mkBrush(self.PLAYER_COLOR))
        self.plot.addItem(self.car_scatter)
        self.plot.addItem(self.player_scatter)

        self.gap_label = QLabel("Gap ahead: - | Gap behind: -")
        layout.addWidget(self.gap_label)

    def update_positions(self):
        if not self.logger_obj:
            return
        cars = self.logger_obj.get_motion_cache()
        if not cars:
            return

        player = next((c for c in cars if c["car_index"] == 0), None)
        others = [c for c in cars if c["car_index"] != 0]

        if others:
            spots = [{"pos": (c["x"], c["z"])} for c in others]
            self.car_scatter.setData([s["pos"][0] for s in spots], [s["pos"][1] for s in spots])

        if player:
            self.player_scatter.setData([player["x"]], [player["z"]])

        live = self.logger_obj.get_live_timing(0)
        delta_front = live.get("delta_front_ms", 0)
        if delta_front:
            self.gap_label.setText(f"Gap ahead: {delta_front / 1000:.3f}s")
        else:
            self.gap_label.setText("Gap ahead: -")
