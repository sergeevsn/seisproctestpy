import shutil
import json
import importlib
import numpy as np
import segyio
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from itertools import product
from sklearn.preprocessing import MinMaxScaler
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout, QWidget,
    QComboBox, QHBoxLayout, QAction, QProgressBar, QSpinBox, QMessageBox,
    QPushButton, QSizePolicy, QDialog, QTextEdit, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from about import *

class ParamEditDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Parameters")
        self.resize(600, 400)
        self.file_name = "noname"
        self.json_text = ""

        self.header_label = QLabel(self.file_name)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText('{"module.func": { ... }}')

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        apply_btn = buttons.button(QDialogButtonBox.Apply)
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        apply_btn.setText("Apply")
        cancel_btn.setText("Cancel")
        apply_btn.clicked.connect(self.apply)
        cancel_btn.clicked.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.header_label)
        layout.addWidget(self.text_edit)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def load_json(self, path, raw_json):
        self.file_name = path.split('/')[-1] if path else "noname"
        self.header_label.setText(self.file_name)
        pretty = json.dumps(raw_json, indent=2)
        self.text_edit.setPlainText(pretty)
        self.json_text = pretty

    def apply(self):
        text = self.text_edit.toPlainText()
        try:
            json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, "Invalid JSON", str(e))
            return
        self.json_text = text
        self.accept()

class SeisProcTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SeisProcTestPy")
        self.setGeometry(100, 100, 2400, 1200)

        # Data containers
        self.raw_data = None
        self.scaled_data = None
        self.denoised_real = None
        self.param_sets = []
        self.current_index = 0
        self.last_opened_file = None
        self.scaler = None

        # Parameter edit dialog
        self.params_path = None
        self.params_dialog = ParamEditDialog(self)

        # Plotting
        self.figure = plt.figure(figsize=(18, 4))
        self.ax = [self.figure.add_subplot(1, 3, i+1) for i in range(3)]
        self.canvas = FigureCanvas(self.figure)

        # Widgets
        self.file_label = QLabel("No file loaded")
        self.file_label.setMaximumHeight(20)
        self.param_combo = QComboBox()
        self.param_combo.currentIndexChanged.connect(self.on_param_combo_changed)
        self.param_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)        

        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(['gray', 'seismic', 'PuOr', 'cividis'])
        self.colormap_combo.currentTextChanged.connect(self.update_images)

        self.gain_input = QSpinBox()
        self.gain_input.setRange(0, 20)
        self.gain_input.setValue(1)
        self.gain_input.valueChanged.connect(self.update_images)

        self.progress_bar = QProgressBar()
        self.stop_button = QPushButton("Stop")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_processing)
        self.progress_bar.setVisible(False)

        # Interaction variables
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.initial_xlims = [None]*3
        self.initial_ylims = [None]*3
        self.current_xlims = [None]*3
        self.current_ylims = [None]*3

        # Mouse events
        self.canvas.mpl_connect('button_press_event', self.on_click)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.file_label)
        main_layout.addWidget(self.canvas, stretch=1)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Parameter Set:")); ctrl_layout.addWidget(self.param_combo)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel("Colormap:")); ctrl_layout.addWidget(self.colormap_combo)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(QLabel("Gain:")); ctrl_layout.addWidget(self.gain_input)
        main_layout.addLayout(ctrl_layout)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.stop_button)
        main_layout.addLayout(progress_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.init_menu()
        self.show()

    def init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(QAction("Open SEG-Y", self, triggered=self.open_file))
        file_menu.addAction(QAction("Save", self, triggered=self.save_segy))
        file_menu.addAction(QAction("Exit", self, triggered=self.close))

        params_menu = menubar.addMenu("Params")
        params_menu.addAction(QAction("Load", self, triggered=self.load_params))
        params_menu.addAction(QAction("Edit", self, triggered=self.edit_params))
        params_menu.addAction(QAction("Save Params As", self, triggered=self.save_params_as))

        process_menu = menubar.addMenu("Process")
        process_menu.addAction(QAction("Process", self, triggered=self.process_data))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(QAction("About", self, triggered=self.show_about))
        

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open SEG-Y File", "", "SEG-Y Files (*.sgy *.segy)")
        if not path: return
        self.last_opened_file = path
        with segyio.open(path, "r", ignore_geometry=True) as f:
            data = f.trace.raw[:]
        self.raw_data = data.astype(float)
        self.scaler = MinMaxScaler().fit(self.raw_data.reshape(-1,1))
        self.scaled_data = self.scaler.transform(self.raw_data.reshape(-1,1)).reshape(self.raw_data.shape)
        self.denoised_real = None
        self.param_sets.clear(); self.param_combo.clear(); self.current_index = 0
        self.file_label.setText(f"File Loaded: {path} shape={self.raw_data.shape}")
        self.update_images()
        for i, ax in enumerate(self.ax):
            self.initial_xlims[i] = ax.get_xlim()
            self.initial_ylims[i] = ax.get_ylim()

    def show_about(self):
        about = AboutDialog(self)
        about.exec_()

    def load_params(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Parameters JSON", "", "JSON files (*.json)")
        if not path: return
        try:
            raw = json.load(open(path))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return
        self.params_path = path
        self.params_dialog.load_json(path, raw)
        self.edit_params()  # Open editor immediately after loading

    def edit_params(self):
        # Pre-show current values
        self.params_dialog.header_label.setText(self.params_dialog.file_name)
        self.params_dialog.text_edit.setPlainText(self.params_dialog.json_text)
        self.params_dialog.exec_()

    def save_params_as(self):
        text = self.params_dialog.json_text
        if not text.strip():
            QMessageBox.warning(self, "No Params", "No parameters to save."); return
        try:
            parsed = json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return
        path, _ = QFileDialog.getSaveFileName(self, "Save Parameters As", "", "JSON files (*.json)")
        if not path: return
        with open(path, 'w') as f:
            json.dump(parsed, f, indent=2)
        QMessageBox.information(self, "Saved", f"Saved to:\n{path}")

    def process_data(self):
        if self.scaled_data is None:
            QMessageBox.warning(self, "No Data", "Load a SEG-Y file first"); return
        text = self.params_dialog.json_text.strip()
        if not text:
            QMessageBox.warning(self, "No Params", "Use Params->Edit to enter parameters"); return
        try:
            raw = json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e)); return
        self.param_sets.clear()
        for method, params in raw.items():
            for combo in product(*params.values()):
                pd = dict(zip(params.keys(), combo)); pd['method'] = method
                self.param_sets.append(pd)
        missing = []
        for m in {pd['method'] for pd in self.param_sets}:
            try:
                mod, fn = m.rsplit('.', 1)
                getattr(importlib.import_module(mod), fn)
            except Exception:
                missing.append(m)
        if missing:
            QMessageBox.critical(self, "Cannot import", "\n".join(missing)); return
        self.param_combo.setEnabled(False); self.progress_bar.setVisible(True); self.progress_bar.setValue(0)
        self.stop_button.setVisible(True)
        QApplication.processEvents()
        real_list = []; self.param_combo.clear(); total=len(self.param_sets); self.processing_stopped=False
        for i, pd in enumerate(self.param_sets):
            if self.processing_stopped:
                break
            QApplication.processEvents()
            try:
                mod, fn = pd['method'].rsplit('.', 1)
                func = getattr(importlib.import_module(mod), fn)
                params = {k: v for k, v in pd.items() if k != 'method'}
                den = func(self.scaled_data, **params)
            except Exception as e:
                self.progress_bar.setVisible(False)
                self.stop_button.setVisible(False)
                self.param_combo.setEnabled(True)
                QMessageBox.critical(self, "Processing Error", f"Error during processing:\n{str(e)}")
                return
            inv = self.scaler.inverse_transform(den.reshape(-1,1)).reshape(den.shape)
            real_list.append(inv)
            label = f"{i+1}: {fn} " + ", ".join(f"{k}={v}" for k, v in params.items())
            self.param_combo.addItem(label)
            self.progress_bar.setValue(int((i+1)/total*100))
        self.denoised_real = np.array(real_list)
        self.current_index = 0; self.param_combo.setCurrentIndex(0)
        self.progress_bar.setVisible(False); self.param_combo.setEnabled(True)
        self.stop_button.setVisible(False)
        self.update_images()

   
    def on_param_combo_changed(self, idx):
        if idx >= 0:
            self.current_index = idx
            self.update_images()

    def on_click(self, event):
        if event.button == 1 and event.inaxes in self.ax:
            self.start_x = event.xdata
            self.start_y = event.ydata
            self.rect = Rectangle((self.start_x, self.start_y), 0, 0,
                                  fill=False, edgecolor='red', linestyle='--')
            event.inaxes.add_patch(self.rect)
            self.canvas.draw()

    def on_motion(self, event):
        if self.rect and hasattr(self.rect, 'axes') and event.inaxes == self.rect.axes:
            dx = event.xdata - self.start_x
            dy = event.ydata - self.start_y
            self.rect.set_width(dx)
            self.rect.set_height(dy)
            self.canvas.draw()

    def on_release(self, event):
        if event.button == 1 and self.rect:
            end_x = event.xdata
            end_y = event.ydata
            x_min = min(self.start_x, end_x)
            x_max = max(self.start_x, end_x)
            y_min = min(self.start_y, end_y)
            y_max = max(self.start_y, end_y)
            for i, ax in enumerate(self.ax):
                ax.set_xlim(x_min, x_max)
                ax.set_ylim(y_max, y_min)
            self.rect.remove()
            self.rect = None
            self.canvas.draw()
        elif event.button == 3:
            for i, ax in enumerate(self.ax):
                ax.set_xlim(self.initial_xlims[i])
                ax.set_ylim(self.initial_ylims[i])
            self.canvas.draw()
            self.update_images()

    def update_images(self):
        for i in range(3):
            self.current_xlims[i] = self.ax[i].get_xlim()
            self.current_ylims[i] = self.ax[i].get_ylim()
        gain = self.gain_input.value()
        cmap = self.colormap_combo.currentText()
        self.ax[0].clear()
        if self.raw_data is not None:
            orig_disp = self.raw_data.T
            vmin, vmax = np.percentile(orig_disp, [gain, 100 - gain])
            self.ax[0].imshow(orig_disp, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
        self.ax[0].set_title("Original")
        for a in self.ax[1:]:
            a.clear()
        if self.denoised_real is not None:
            real = self.denoised_real[self.current_index]
            den_disp = real.T
            vmin, vmax = np.percentile(orig_disp, [gain, 100 - gain])
            self.ax[1].imshow(den_disp, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
            self.ax[1].set_title("Denoised")
            diff = (self.raw_data - real).T
            if gain > 0:
                dvmin = np.percentile(orig_disp, gain)
                dvmax = np.percentile(orig_disp, 100 - gain)
            else:
                dvmin, dvmax = orig_disp.min(), orig_disp.max()
            self.ax[2].imshow(diff, aspect='auto', cmap=cmap, vmin=dvmin, vmax=dvmax)
            self.ax[2].set_title("Difference")
        else:
            self.ax[1].set_title("Denoised (n/a)")
            self.ax[2].set_title("Difference (n/a)")
        for i in range(3):
            if self.current_xlims[i] != (0.0, 1.0):
                self.ax[i].set_xlim(self.current_xlims[i])
                self.ax[i].set_ylim(self.current_ylims[i])
        self.canvas.draw()

    def stop_processing(self):
        self.processing_stopped = True

    def save_segy(self):
        if self.raw_data is None or self.denoised_real is None:
            QMessageBox.warning(self, "Cannot Save", "Load & process before save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save SEG-Y File", filter="SEG-Y Files (*.sgy *.segy)")
        if not path:
            return
        shutil.copyfile(self.last_opened_file, path)
        with segyio.open(path, 'r+', ignore_geometry=True) as f:
            real = self.denoised_real[self.current_index]
            for i in range(real.shape[0]):
                f.trace.raw[i] = real[i]
        QMessageBox.information(self, "Save Successful", f"Saved to:\n{path}")

    def keyPressEvent(self, event):
        focused_widget = self.focusWidget()
        if event.key() == Qt.Key_Return:
            if isinstance(focused_widget, QSpinBox):
                super().keyPressEvent(event)
            else:
                self.process_data()
            return
        if event.key() in (Qt.Key_Up, Qt.Key_Down):
            if isinstance(focused_widget, QComboBox):
                super().keyPressEvent(event)
            else:
                val = self.gain_input.value()
                new_val = (val + 1) % 21 if event.key() == Qt.Key_Up else (val - 1) % 21
                self.gain_input.setValue(new_val)
            return
        if event.key() == Qt.Key_Left:
            new_idx = max(0, self.current_index - 1)
        elif event.key() == Qt.Key_Right:
            new_idx = min(len(self.param_sets)-1, self.current_index + 1)
        else:
            super().keyPressEvent(event)
            return
        self.current_index = new_idx
        self.param_combo.setCurrentIndex(new_idx)
        self.update_images()