import sys
import os
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QComboBox, QDial, QSlider
from PySide6.QtCore import QTimer, Qt
from audio_capture import AudioCaptureThread, get_audio_devices

class OscilloscopeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Oscilloscope Music Viewer")
        self.resize(800, 800)
        self.setStyleSheet("background-color: #222; color: #EEE;")
        
        # UI Setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Plot Setup
        pg.setConfigOption('background', 'k')
        pg.setConfigOption('foreground', 'g')
        pg.setConfigOptions(antialias=True)
        self.plot_widget = pg.PlotWidget()
        
        # To maintain circular shapes correctly without stretching we lock the aspect ratio
        self.plot_widget.setAspectLocked(True)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setXRange(-1, 1, padding=0.1)
        self.plot_widget.setYRange(-1, 1, padding=0.1)
        
        # X and Y axes labeling 
        self.plot_widget.setLabel('bottom', "Right Channel (X)")
        self.plot_widget.setLabel('left', "Left Channel (Y)")
        
        # Set line to a faint green and add faint dots at every sample. 
        # Since samples are constant in time, fast-moving "transfer" lines spread dots out (making them dim),
        # whereas slow-moving shapes group dots closely, accumulating brightness to create a true analog phosphor effect.
        pen = pg.mkPen(color=(0, 255, 0, 60), width=1.5)
        self.curve = self.plot_widget.plot(
            pen=pen, 
            symbol='o', 
            symbolSize=2, 
            symbolPen=None, 
            symbolBrush=(0, 255, 0, 40)
        )
        
        main_layout.addWidget(self.plot_widget)
        
        # Controls Layout
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 10, 10, 10)
        
        # In oscilloscope music, L is usually Y and R is usually X, or vice versa
        # We will map L to X and R to Y by default
        self.x_scale = 1.0
        self.y_scale = 1.0
        self.line_width = 1.5
        self.trace_length = 4096
        self.base_color = (0, 255, 0)
        self.intensity = 60
        
        # X Scale Controls
        x_label = QLabel("X (Left) Volts/Div:")
        self.x_scale_label = QLabel(f"{self.x_scale:.2f}x")
        btn_x_up = QPushButton("X Scale +")
        btn_x_down = QPushButton("X Scale -")
        btn_x_up.setStyleSheet("background-color: #444; padding: 5px;")
        btn_x_down.setStyleSheet("background-color: #444; padding: 5px;")
        btn_x_up.clicked.connect(self.inc_x_scale)
        btn_x_down.clicked.connect(self.dec_x_scale)
        
        # Y Scale Controls
        y_label = QLabel("Y (Right) Volts/Div:")
        self.y_scale_label = QLabel(f"{self.y_scale:.2f}x")
        btn_y_up = QPushButton("Y Scale +")
        btn_y_down = QPushButton("Y Scale -")
        btn_y_up.setStyleSheet("background-color: #444; padding: 5px;")
        btn_y_down.setStyleSheet("background-color: #444; padding: 5px;")
        btn_y_up.clicked.connect(self.inc_y_scale)
        btn_y_down.clicked.connect(self.dec_y_scale)
        
        controls_layout.addWidget(x_label)
        controls_layout.addWidget(btn_x_down)
        controls_layout.addWidget(btn_x_up)
        controls_layout.addWidget(self.x_scale_label)
        
        controls_layout.addSpacing(40)
        
        controls_layout.addWidget(y_label)
        controls_layout.addWidget(btn_y_down)
        controls_layout.addWidget(btn_y_up)
        controls_layout.addWidget(self.y_scale_label)
        
        controls_layout.addSpacing(40)
        
        # Brightness Knob (Intensity)
        bright_layout = QVBoxLayout()
        bright_label = QLabel("Intensity")
        bright_label.setAlignment(Qt.AlignCenter)
        self.bright_dial = QDial()
        self.bright_dial.setMinimum(5)
        self.bright_dial.setMaximum(255)
        self.bright_dial.setValue(60) # Default line alpha
        self.bright_dial.setNotchesVisible(True)
        self.bright_dial.setFixedSize(60, 60)
        self.bright_dial.valueChanged.connect(self.update_brightness)
        
        bright_layout.addWidget(bright_label)
        bright_layout.addWidget(self.bright_dial)
        
        controls_layout.addLayout(bright_layout)
        
        controls_layout.addStretch()
        
        main_layout.addLayout(controls_layout)
        
        # Advanced Controls Layout
        adv_layout = QHBoxLayout()
        adv_layout.setContentsMargins(10, 0, 10, 10)
        
        trace_label = QLabel("Trace Length:")
        self.trace_slider = QSlider(Qt.Horizontal)
        self.trace_slider.setRange(100, 8192)
        self.trace_slider.setValue(4096)
        self.trace_slider.valueChanged.connect(self.update_trace_length)
        
        width_label = QLabel("Line Width:")
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 50)
        self.width_slider.setValue(15)
        self.width_slider.valueChanged.connect(self.update_line_width)
        
        color_label = QLabel("Phosphor Color:")
        self.color_combo = QComboBox()
        self.color_combo.addItems(["P31 Green", "P7 Amber", "P4 White", "Blue", "Red"])
        self.color_combo.setStyleSheet("background-color: #444; padding: 5px;")
        self.color_combo.currentIndexChanged.connect(self.update_color)
        
        adv_layout.addWidget(trace_label)
        adv_layout.addWidget(self.trace_slider, stretch=1)
        adv_layout.addSpacing(20)
        adv_layout.addWidget(width_label)
        adv_layout.addWidget(self.width_slider, stretch=1)
        adv_layout.addSpacing(20)
        adv_layout.addWidget(color_label)
        adv_layout.addWidget(self.color_combo)
        
        main_layout.addLayout(adv_layout)
        
        # Device Selection Layout
        device_layout = QHBoxLayout()
        device_layout.setContentsMargins(10, 0, 10, 10)
        device_label = QLabel("Audio Source (Select your music output):")
        self.device_combo = QComboBox()
        self.device_combo.setStyleSheet("background-color: #444; padding: 5px;")
        
        self.devices = get_audio_devices()
        for i, dev in enumerate(self.devices):
            self.device_combo.addItem(dev["name"], dev["id"])
            
        self.device_combo.currentIndexChanged.connect(self.change_audio_device)
        
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo, stretch=1)
        
        main_layout.addLayout(device_layout)
        
        # Start Audio Thread
        if self.devices:
            self.audio_thread = AudioCaptureThread(device_id=self.devices[0]["id"], buffer_size=8192)
        else:
            self.audio_thread = AudioCaptureThread(buffer_size=8192)
            
        self.audio_thread.start()
        
        # Timer for updating plot
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(16) # ~60fps rendering
        
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
            (0, 255, 0),     # P31 Green
            (255, 170, 0),   # P7 Amber
            (240, 240, 255), # P4 White
            (50, 150, 255),  # Blue
            (255, 50, 50)    # Red
        ]
        self.base_color = colors[index]
        self.apply_pen()

    def update_brightness(self, value):
        self.intensity = value
        self.apply_pen()
        
    def apply_pen(self):
        line_alpha = min(255, self.intensity)
        dot_alpha = min(255, max(1, int(self.intensity / 1.5)))
        r, g, b = self.base_color
        
        pen = pg.mkPen(color=(r, g, b, line_alpha), width=self.line_width)
        self.curve.setPen(pen)
        self.curve.setSymbolBrush((r, g, b, dot_alpha))

    def update_plot(self):
        data = self.audio_thread.get_data()
        data = data[-self.trace_length:] # Apply trace length truncation
        
        # We plot L as X and R as Y. This is typical for Jerobeam Fenderson osci-music.
        # data[:, 0] = Left
        # data[:, 1] = Right
        x_data = data[:, 0] * self.x_scale
        y_data = data[:, 1] * self.y_scale
        
        self.curve.setData(x_data, y_data)
        
    def closeEvent(self, event):
        self.timer.stop()
        self.audio_thread.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OscilloscopeApp()
    window.show()
    sys.exit(app.exec())
