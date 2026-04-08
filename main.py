import sys
import os
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLabel, QComboBox, QDial, QSlider
)
from PySide6.QtCore import QTimer, Qt
from audio_capture import AudioCaptureThread, get_audio_devices


# How far the waveforms extend past the ±1 XY region (in plot units)
WAVE_EXTENT_X = 3.5   # left/right waveform half-width beyond centre
WAVE_EXTENT_Y = 2.0   # top/bottom waveform half-height beyond centre


class OscilloscopeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Oscilloscope Music Viewer")
        self.resize(900, 900)
        self.setStyleSheet("background-color: #1a1a1a; color: #EEE;")

        # ── state ──────────────────────────────────────────────────────────
        self.x_scale      = 1.0
        self.y_scale      = 1.0
        self.line_width   = 1.5
        self.trace_length = 4096
        self.base_color   = (0, 255, 0)
        self.intensity    = 60
        # "xy"        = classic XY / Lissajous only
        # "formation" = single-canvas XY + waveforms along both axes
        self.view_mode    = "xy"

        # ── central widget ─────────────────────────────────────────────────
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption('background', 'k')
        pg.setConfigOption('foreground', 'w')
        pg.setConfigOptions(antialias=True)

        # ── build both view containers ─────────────────────────────────────
        self._build_xy_view()
        self._build_formation_view()

        # start with XY view visible
        self.formation_container.hide()
        self.main_layout.addWidget(self.xy_container,        stretch=1)
        self.main_layout.addWidget(self.formation_container, stretch=1)

        # ── controls ───────────────────────────────────────────────────────
        self._build_controls()

        # ── audio ──────────────────────────────────────────────────────────
        self.devices = get_audio_devices()
        for dev in self.devices:
            self.device_combo.addItem(dev["name"], dev["id"])
        self.device_combo.currentIndexChanged.connect(self.change_audio_device)

        if self.devices:
            self.audio_thread = AudioCaptureThread(device_id=self.devices[0]["id"], buffer_size=8192)
        else:
            self.audio_thread = AudioCaptureThread(buffer_size=8192)
        self.audio_thread.start()

        # ── render timer ───────────────────────────────────────────────────
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(16)   # ~60 fps

    # ══════════════════════════════════════════════════════════════════════
    # View builders
    # ══════════════════════════════════════════════════════════════════════

    def _pen(self, alpha_override=None):
        alpha = alpha_override if alpha_override is not None else min(255, self.intensity)
        r, g, b = self.base_color
        return pg.mkPen(color=(r, g, b, alpha), width=self.line_width)

    def _build_xy_view(self):
        """Classic single-plot XY / Lissajous view."""
        self.xy_container = QWidget()
        layout = QVBoxLayout(self.xy_container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.xy_plot = pg.PlotWidget()
        self.xy_plot.setAspectLocked(True)
        self.xy_plot.showGrid(x=True, y=True, alpha=0.3)
        self.xy_plot.setXRange(-1, 1, padding=0.1)
        self.xy_plot.setYRange(-1, 1, padding=0.1)
        self.xy_plot.setLabel('bottom', "Right Channel (X)")
        self.xy_plot.setLabel('left',   "Left Channel (Y)")

        r, g, b = self.base_color
        self.xy_curve = self.xy_plot.plot(
            pen=self._pen(),
            symbol='o', symbolSize=2, symbolPen=None,
            symbolBrush=pg.mkBrush(r, g, b, max(1, int(self.intensity / 1.5)))
        )
        layout.addWidget(self.xy_plot)

    def _build_formation_view(self):
        """
        Formation view — one single canvas.

        The XY (Lissajous) figure occupies the centre ±1 region.
        The X waveform (right channel) runs horizontally left→right
          across the full canvas width, centred on Y=0.
        The Y waveform (left channel) runs vertically top→bottom
          across the full canvas height, centred on X=0.
        A white dot marks the current sample position on all three.
        """
        self.formation_container = QWidget()
        layout = QVBoxLayout(self.formation_container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.fm_plot = pg.PlotWidget()
        self.fm_plot.setBackground('k')
        self.fm_plot.showGrid(x=False, y=False)
        # Wide canvas so waveforms have plenty of room
        self.fm_plot.setXRange(-(1 + WAVE_EXTENT_X), (1 + WAVE_EXTENT_X), padding=0.02)
        self.fm_plot.setYRange(-(1 + WAVE_EXTENT_Y), (1 + WAVE_EXTENT_Y), padding=0.02)
        self.fm_plot.setAspectLocked(False)
        self.fm_plot.hideAxis('left')
        self.fm_plot.hideAxis('bottom')

        # Faint axis cross through origin
        self.fm_plot.addLine(x=0, pen=pg.mkPen((255, 255, 255, 25), width=1))
        self.fm_plot.addLine(y=0, pen=pg.mkPen((255, 255, 255, 25), width=1))

        # Faint box around the centre XY region  (±1)
        border_pen = pg.mkPen((255, 255, 255, 18), width=1, style=Qt.DashLine)
        for x in (-1, 1):
            self.fm_plot.addLine(x=x, pen=border_pen)
        for y in (-1, 1):
            self.fm_plot.addLine(y=y, pen=border_pen)

        r, g, b = self.base_color
        sym_brush = pg.mkBrush(r, g, b, max(1, int(self.intensity / 1.5)))

        # Centre XY / Lissajous curve
        self.fm_xy_curve = self.fm_plot.plot(
            pen=self._pen(),
            symbol='o', symbolSize=2, symbolPen=None, symbolBrush=sym_brush
        )

        # Horizontal X waveform (right channel), runs across full width
        self.fm_x_wave = self.fm_plot.plot(pen=self._pen())

        # Vertical Y waveform (left channel), runs across full height
        self.fm_y_wave = self.fm_plot.plot(pen=self._pen())

        # Animated white dot at current sample on the XY plot
        dot_brush = pg.mkBrush(255, 255, 255, 230)
        dot_pen   = pg.mkPen(None)
        self.fm_dot = self.fm_plot.plot(
            [0], [0], symbol='o', symbolSize=8,
            symbolBrush=dot_brush, symbolPen=dot_pen, pen=None
        )

        # Crosshair lines from dot to the waveforms
        self.fm_hline = self.fm_plot.plot(
            pen=pg.mkPen((255, 255, 255, 60), width=1, style=Qt.DotLine)
        )
        self.fm_vline = self.fm_plot.plot(
            pen=pg.mkPen((255, 255, 255, 60), width=1, style=Qt.DotLine)
        )

        # "X" and "Y" text labels near the dot (we'll update positions in update_plot)
        self.fm_xlabel = pg.TextItem("X", color=(200, 200, 200), anchor=(0, 1))
        self.fm_ylabel = pg.TextItem("Y", color=(200, 200, 200), anchor=(1, 0))
        self.fm_plot.addItem(self.fm_xlabel)
        self.fm_plot.addItem(self.fm_ylabel)

        layout.addWidget(self.fm_plot)

    # ══════════════════════════════════════════════════════════════════════
    # Controls
    # ══════════════════════════════════════════════════════════════════════

    def _build_controls(self):
        # ── mode toggle ────────────────────────────────────────────────────
        mode_layout = QHBoxLayout()
        mode_layout.setContentsMargins(10, 6, 10, 2)

        self.mode_btn = QPushButton("⊞  Switch to Formation View")
        self.mode_btn.setCheckable(True)
        self.mode_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #1e3a1e; color: #88ff88;"
            "  border: 1px solid #3a7a3a; border-radius: 4px;"
            "  padding: 6px 16px; font-weight: bold; font-size: 13px;"
            "}"
            "QPushButton:checked {"
            "  background-color: #1a2e4a; color: #88ccff;"
            "  border: 1px solid #3a6aaa;"
            "}"
        )
        self.mode_btn.clicked.connect(self.toggle_view_mode)
        mode_layout.addWidget(self.mode_btn)
        mode_layout.addStretch()
        self.main_layout.addLayout(mode_layout)

        # ── X / Y scale controls ───────────────────────────────────────────
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 4, 10, 4)
        btn_style = "background-color: #444; padding: 5px; border-radius: 3px;"

        self.x_scale_label = QLabel(f"{self.x_scale:.2f}x")
        self.y_scale_label = QLabel(f"{self.y_scale:.2f}x")

        for (lbl, up_slot, dn_slot, scale_lbl) in [
            ("X (Left) Volts/Div:", self.inc_x_scale, self.dec_x_scale, self.x_scale_label),
            ("Y (Right) Volts/Div:", self.inc_y_scale, self.dec_y_scale, self.y_scale_label),
        ]:
            controls_layout.addWidget(QLabel(lbl))
            b_dn = QPushButton(lbl.split()[0] + " Scale -"); b_dn.setStyleSheet(btn_style); b_dn.clicked.connect(dn_slot)
            b_up = QPushButton(lbl.split()[0] + " Scale +"); b_up.setStyleSheet(btn_style); b_up.clicked.connect(up_slot)
            controls_layout.addWidget(b_dn)
            controls_layout.addWidget(b_up)
            controls_layout.addWidget(scale_lbl)
            controls_layout.addSpacing(20)

        # intensity dial
        bright_layout = QVBoxLayout()
        bright_label  = QLabel("Intensity"); bright_label.setAlignment(Qt.AlignCenter)
        self.bright_dial = QDial()
        self.bright_dial.setMinimum(5); self.bright_dial.setMaximum(255)
        self.bright_dial.setValue(60); self.bright_dial.setNotchesVisible(True)
        self.bright_dial.setFixedSize(60, 60)
        self.bright_dial.valueChanged.connect(self.update_brightness)
        bright_layout.addWidget(bright_label); bright_layout.addWidget(self.bright_dial)
        controls_layout.addLayout(bright_layout)
        controls_layout.addStretch()
        self.main_layout.addLayout(controls_layout)

        # ── advanced controls ──────────────────────────────────────────────
        adv_layout = QHBoxLayout()
        adv_layout.setContentsMargins(10, 0, 10, 6)

        self.trace_slider = QSlider(Qt.Horizontal)
        self.trace_slider.setRange(100, 8192); self.trace_slider.setValue(4096)
        self.trace_slider.valueChanged.connect(self.update_trace_length)

        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 50); self.width_slider.setValue(15)
        self.width_slider.valueChanged.connect(self.update_line_width)

        self.color_combo = QComboBox()
        self.color_combo.addItems(["P31 Green", "P7 Amber", "P4 White", "Blue", "Red"])
        self.color_combo.setStyleSheet("background-color: #444; padding: 5px;")
        self.color_combo.currentIndexChanged.connect(self.update_color)

        adv_layout.addWidget(QLabel("Trace Length:"))
        adv_layout.addWidget(self.trace_slider, stretch=1)
        adv_layout.addSpacing(20)
        adv_layout.addWidget(QLabel("Line Width:"))
        adv_layout.addWidget(self.width_slider, stretch=1)
        adv_layout.addSpacing(20)
        adv_layout.addWidget(QLabel("Phosphor Color:"))
        adv_layout.addWidget(self.color_combo)
        self.main_layout.addLayout(adv_layout)

        # ── device selection ───────────────────────────────────────────────
        device_layout = QHBoxLayout()
        device_layout.setContentsMargins(10, 0, 10, 10)
        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet("background-color: #444; padding: 5px;")
        device_layout.addWidget(QLabel("Audio Source:"))
        device_layout.addWidget(self.device_combo, stretch=1)
        self.main_layout.addLayout(device_layout)

    # ══════════════════════════════════════════════════════════════════════
    # Mode toggle
    # ══════════════════════════════════════════════════════════════════════

    def toggle_view_mode(self, checked):
        if checked:
            self.view_mode = "formation"
            self.mode_btn.setText("⊡  Switch to Classic XY View")
            self.xy_container.hide()
            self.formation_container.show()
        else:
            self.view_mode = "xy"
            self.mode_btn.setText("⊞  Switch to Formation View")
            self.formation_container.hide()
            self.xy_container.show()

    # ══════════════════════════════════════════════════════════════════════
    # Scale / colour / brightness helpers
    # ══════════════════════════════════════════════════════════════════════

    def inc_x_scale(self):
        self.x_scale *= 1.2
        self.x_scale_label.setText(f"{self.x_scale:.2f}x")

    def dec_x_scale(self):
        self.x_scale /= 1.2
        self.x_scale_label.setText(f"{self.x_scale:.2f}x")

    def inc_y_scale(self):
        self.y_scale *= 1.2
        self.y_scale_label.setText(f"{self.y_scale:.2f}x")

    def dec_y_scale(self):
        self.y_scale /= 1.2
        self.y_scale_label.setText(f"{self.y_scale:.2f}x")

    def change_audio_device(self, index):
        if index < 0 or index >= len(self.devices):
            return
        device_id = self.devices[index]["id"]
        if hasattr(self, 'audio_thread') and self.audio_thread.running:
            self.audio_thread.stop()
        self.audio_thread = AudioCaptureThread(device_id=device_id, buffer_size=8192)
        self.audio_thread.start()

    def update_trace_length(self, value):
        self.trace_length = value

    def update_line_width(self, value):
        self.line_width = value / 10.0
        self.apply_pen()

    def update_color(self, index):
        colors = [
            (0,   255,   0),
            (255, 170,   0),
            (240, 240, 255),
            (50,  150, 255),
            (255,  50,  50),
        ]
        self.base_color = colors[index]
        self.apply_pen()

    def update_brightness(self, value):
        self.intensity = value
        self.apply_pen()

    def apply_pen(self):
        line_alpha = min(255, self.intensity)
        dot_alpha  = min(255, max(1, int(self.intensity / 1.5)))
        r, g, b    = self.base_color
        pen        = pg.mkPen(color=(r, g, b, line_alpha), width=self.line_width)
        sym_brush  = pg.mkBrush(r, g, b, dot_alpha)

        # XY view
        self.xy_curve.setPen(pen)
        self.xy_curve.setSymbolBrush(sym_brush)

        # Formation view
        self.fm_xy_curve.setPen(pen)
        self.fm_xy_curve.setSymbolBrush(sym_brush)
        self.fm_x_wave.setPen(pen)
        self.fm_y_wave.setPen(pen)

    # ══════════════════════════════════════════════════════════════════════
    # Plot update  (~60 fps)
    # ══════════════════════════════════════════════════════════════════════

    def update_plot(self):
        data = self.audio_thread.get_data()
        data = data[-self.trace_length:]

        # Left channel  → X axis of XY plot
        # Right channel → Y axis of XY plot
        x_data = data[:, 0] * self.x_scale
        y_data = data[:, 1] * self.y_scale

        if self.view_mode == "xy":
            self.xy_curve.setData(x_data, y_data)

        else:   # ── formation ──────────────────────────────────────────────
            n = len(x_data)

            # ── Centre XY Lissajous ─────────────────────────────────────
            self.fm_xy_curve.setData(x_data, y_data)

            # ── Horizontal X waveform ───────────────────────────────────
            # Time maps to full horizontal extent; signal amplitude on Y.
            # We mirror the trace so it reads left→right in real-time order.
            t_x = np.linspace(-(1 + WAVE_EXTENT_X), (1 + WAVE_EXTENT_X), n)
            self.fm_x_wave.setData(t_x, x_data)

            # ── Vertical Y waveform ─────────────────────────────────────
            # Time maps to full vertical extent (bottom = oldest);
            # signal amplitude on X.
            t_y = np.linspace(-(1 + WAVE_EXTENT_Y), (1 + WAVE_EXTENT_Y), n)
            self.fm_y_wave.setData(y_data, t_y)

            # ── Animated dot + crosshair at the current sample ──────────
            cur_x = float(x_data[-1])
            cur_y = float(y_data[-1])
            self.fm_dot.setData([cur_x], [cur_y])

            # Horizontal crosshair: from the Y-waveform X-pos to the dot
            self.fm_hline.setData(
                [float(y_data[-1]), cur_x],
                [float(t_y[-1]),    cur_y]
            )
            # Vertical crosshair: from the X-waveform Y-pos to the dot
            self.fm_vline.setData(
                [float(t_x[-1]),  cur_x],
                [float(x_data[-1]), cur_y]
            )

            # "X" / "Y" labels near the dot
            self.fm_xlabel.setPos(cur_x + 0.05, cur_y + 0.05)
            self.fm_ylabel.setPos(cur_x - 0.15, cur_y + 0.05)

    # ══════════════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        self.timer.stop()
        self.audio_thread.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OscilloscopeApp()
    window.show()
    sys.exit(app.exec())
