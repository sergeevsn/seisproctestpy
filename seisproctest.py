import shutil
import json
import importlib
import numpy as np
import segyio
import matplotlib.pyplot as plt
import matplotlib
import imageio
import os
import tempfile
matplotlib.use('Qt5Agg')

from matplotlib.patches import Rectangle
from itertools import product
from sklearn.preprocessing import MinMaxScaler
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout, QWidget,
    QComboBox, QHBoxLayout, QAction, QProgressBar, QSpinBox, QMessageBox,
    QPushButton, QSizePolicy, QDialog, QTextEdit, QDialogButtonBox, QInputDialog
)
from PyQt5.QtCore import Qt
from about import *
from PyQt5.QtGui import QScreen

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
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        width = int(screen_geometry.width() * 0.9)
        height = int(screen_geometry.height() * 0.9)
        self.resize(width, height)
        self.move(
            (screen_geometry.width() - width) // 2,
            (screen_geometry.height() - height) // 2
        )

        # Data containers
        self.raw_data = None
        self.scaled_data = None
        self.processed_real = None
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

        self.processing_label = QLabel("")
        self.processing_label.setVisible(False)

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

        main_layout.addWidget(self.processing_label)
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
        file_menu.addAction(QAction("Save Figures", self, triggered=self.save_figures))  # New menu item
        file_menu.addAction(QAction("Exit", self, triggered=self.close))

        params_menu = menubar.addMenu("Params")
        params_menu.addAction(QAction("Load", self, triggered=self.load_params))
        params_menu.addAction(QAction("Edit", self, triggered=self.edit_params))
        params_menu.addAction(QAction("Save Params As", self, triggered=self.save_params_as))

        process_menu = menubar.addMenu("Process")     
        process_menu.addAction(QAction("Run testing", self, triggered=self.process_data))
        process_menu.addAction(QAction("Apply to Folder", self, triggered=self.apply_to_folder))

        help_menu = menubar.addMenu("Help")
        help_menu.addAction(QAction("About", self, triggered=self.show_about))

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open SEG-Y File", "", "SEG-Y Files (*.sgy *.segy)")
        if not path: return
        self.last_opened_file = path
        with segyio.open(path, "r", ignore_geometry=True) as f:
            data = f.trace.raw[:]
        self.raw_data = data.astype(np.float64)
        self.scaler = MinMaxScaler().fit(self.raw_data.reshape(-1,1))
        self.scaled_data = self.scaler.transform(self.raw_data.reshape(-1,1)).reshape(self.raw_data.shape)
        self.processed_real = None
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
        self.edit_params()

    def edit_params(self):
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
        self.processing_label.setVisible(True)
        self.stop_button.setVisible(True)
        QApplication.processEvents()
        real_list = []; self.param_combo.clear(); total=len(self.param_sets); self.processing_stopped=False
        for i, pd in enumerate(self.param_sets):
            if self.processing_stopped:
                break
            fn = pd['method'].split('.')[-1]
            params = {k: v for k, v in pd.items() if k != 'method'}
            self.processing_label.setText(f"Processing: {fn} with " + ", ".join(f"{k}={v}" for k, v in params.items()))
            QApplication.processEvents()
            try:
                mod, fn = pd['method'].rsplit('.', 1)
                func = getattr(importlib.import_module(mod), fn)
                den = func(self.scaled_data, **params)
            except Exception as e:
                self.progress_bar.setVisible(False)
                self.stop_button.setVisible(False)
                self.param_combo.setEnabled(True)
                self.processing_label.setVisible(False)
                QMessageBox.critical(self, "Processing Error", f"Error during processing:\n{str(e)}")
                return
            inv = self.scaler.inverse_transform(den.reshape(-1,1)).reshape(den.shape)
            real_list.append(inv)
            label = f"{i+1}: {fn} " + ", ".join(f"{k}={v}" for k, v in params.items())
            self.param_combo.addItem(label)
            self.progress_bar.setValue(int((i+1)/total*100))
        self.processed_real = np.array(real_list)
        self.current_index = 0; self.param_combo.setCurrentIndex(0)
        self.progress_bar.setVisible(False); self.param_combo.setEnabled(True)
        self.stop_button.setVisible(False)
        self.processing_label.setVisible(False)
        self.update_images()

    def save_figures(self):
        if self.raw_data is None or self.processed_real is None:
            QMessageBox.warning(self, "Cannot Save", "Load & process data before saving figures.")
            return

        # Update visualization to ensure current_xlims and current_ylims are up-to-date
        self.update_images()

        # Prompt for frame rate (allow fractional FPS)
        fps, ok = QInputDialog.getDouble(self, "Frame Rate", "Enter frames per second (fps):", 5.0, 0.1, 60.0, 1)
        if not ok:
            return

        # Prompt for save location
        path, _ = QFileDialog.getSaveFileName(self, "Save Movie", "", "MP4 Files (*.mp4)")
        if not path:
            return

        # Create temporary directory for frames
        temp_dir = tempfile.mkdtemp()
        frame_paths = []

        try:
            # Parameters for rendering
            gain = self.gain_input.value()
            cmap = self.colormap_combo.currentText()
            orig_disp = self.raw_data.T
            total_frames = len(self.processed_real)

            # Set up progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total_frames)
            self.progress_bar.setValue(0)
            self.processing_label.setVisible(True)
            self.processing_label.setText("Generating frames...")
            QApplication.processEvents()

            # Generate frames
            for idx in range(total_frames):
                # Create new figure for each frame
                fig = plt.figure(figsize=(12, 4))
                axes = [fig.add_subplot(1, 3, i+1) for i in range(3)]

                # Original
                vmin, vmax = np.percentile(orig_disp, [gain, 100 - gain]) if gain > 0 else (orig_disp.min(), orig_disp.max())
                axes[0].imshow(orig_disp, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
                axes[0].set_title("Original")

                # Processed
                real = self.processed_real[idx]
                den_disp = real.T
                axes[1].imshow(den_disp, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
                axes[1].set_title("Processed")

                # Difference
                diff = (self.raw_data - real).T
                dvmin, dvmax = np.percentile(orig_disp, [gain, 100 - gain]) if gain > 0 else (orig_disp.min(), orig_disp.max())
                axes[2].imshow(diff, aspect='auto', cmap=cmap, vmin=dvmin, vmax=dvmax)
                axes[2].set_title("Difference")

                # Apply current zoom to all subplots
                for i, ax in enumerate(axes):
                    if self.current_xlims[i] is not None and self.current_ylims[i] is not None:
                        ax.set_xlim(self.current_xlims[i])
                        ax.set_ylim(self.current_ylims[i])

                # Suptitle with method and parameters
                pd = self.param_sets[idx]
                fn = pd['method'].split('.')[-1]
                params = {k: v for k, v in pd.items() if k != 'method'}
                suptitle = f"{fn}: " + ", ".join(f"{k}={v}" for k, v in params.items())
                fig.suptitle(suptitle, fontsize=12)

                # Save frame as PNG
                frame_path = os.path.join(temp_dir, f"frame_{idx:04d}.png")
                fig.savefig(frame_path, bbox_inches='tight')
                frame_paths.append(frame_path)
                plt.close(fig)

                # Update progress bar
                self.progress_bar.setValue(idx + 1)
                QApplication.processEvents()

            # Hide progress bar and label after frame generation
            self.progress_bar.setVisible(False)
            self.processing_label.setVisible(False)
            QApplication.processEvents()

            # Create video using imageio with frame cropping
            with imageio.get_writer(path, fps=fps, macro_block_size=1) as writer:
                for frame_path in frame_paths:
                    frame = imageio.v2.imread(frame_path)                   
                    
                    # Crop to even dimensions
                    height, width = frame.shape[:2]
                    even_height = height - (height % 2)  # Nearest even number
                    even_width = width - (width % 2)      # Nearest even number
                    if even_height < height or even_width < width:
                        frame = frame[:even_height, :even_width, :]
                                       
                    
                    writer.append_data(frame)

            QMessageBox.information(self, "Save Successful", f"Movie saved to:\n{path}")

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.processing_label.setVisible(False)
            QMessageBox.critical(self, "Save Error", f"Error saving movie:\n{str(e)}")

        finally:
            # Clean up temporary files
            for frame_path in frame_paths:
                try:
                    os.remove(frame_path)
                except OSError:
                    pass
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass

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
        if self.processed_real is not None:
            real = self.processed_real[self.current_index]
            den_disp = real.T
            vmin, vmax = np.percentile(orig_disp, [gain, 100 - gain])
            self.ax[1].imshow(den_disp, aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
            self.ax[1].set_title("Processed")
            diff = (self.raw_data - real).T
            if gain > 0:
                dvmin = np.percentile(orig_disp, gain)
                dvmax = np.percentile(orig_disp, 100 - gain)
            else:
                dvmin, dvmax = orig_disp.min(), orig_disp.max()
            self.ax[2].imshow(diff, aspect='auto', cmap=cmap, vmin=dvmin, vmax=dvmax)
            self.ax[2].set_title("Difference")
        else:
            self.ax[1].set_title("Processed (n/a)")
            self.ax[2].set_title("Difference (n/a)")
        for i in range(3):
            if self.current_xlims[i] != (0.0, 1.0):
                self.ax[i].set_xlim(self.current_xlims[i])
                self.ax[i].set_ylim(self.current_ylims[i])
        self.canvas.draw()

    def stop_processing(self):
        self.processing_stopped = True

    def save_segy(self):
        if self.raw_data is None or self.processed_real is None:
            QMessageBox.warning(self, "Cannot Save", "Load & process before save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save SEG-Y File", filter="SEG-Y Files (*.sgy *.segy)")
        if not path:
            return
        shutil.copyfile(self.last_opened_file, path)
        with segyio.open(path, 'r+', ignore_geometry=True) as f:
            real = self.processed_real[self.current_index]
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
    
    def apply_to_folder(self):
        # Убедимся, что есть наборы параметров и выбран какой-то из них
        if not self.param_sets:
            QMessageBox.warning(self, "Нет параметров", 
                                "Сначала выполните Process, чтобы сгенерировать наборы параметров.")
            return

        # Выбираем папку
        folder = QFileDialog.getExistingDirectory(self, "Select Folder with SEG-Y files")
        if not folder:
            return

        # Находим все .sgy/.segy в корне папки
        files = [f for f in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(('.sgy', '.segy'))]
        if not files:
            QMessageBox.information(self, "Нет файлов", 
                                    "В выбранной папке нет .sgy или .segy файлов.")
            return

        # Берём текущий выбранный метод + параметры
        pd = self.param_sets[self.current_index]
        proc_name = pd['method'].split('.')[-1]
        params = {k: v for k, v in pd.items() if k != 'method'}
        suffix = "_".join(f"{k}{v}" for k, v in params.items())
        subfolder_name = f"{proc_name}_{suffix}" if suffix else proc_name
        out_dir = os.path.join(folder, subfolder_name)
        os.makedirs(out_dir, exist_ok=True)

        # Подготовка прогресса
        total = len(files)
        self.processing_stopped = False
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.processing_label.setVisible(True)
        self.processing_label.setText(f"Processing folder: {folder}, subfolder for results: {subfolder_name}")
        self.stop_button.setVisible(True)
        QApplication.processEvents()

        # Обрабатываем каждый файл
        processed_count = 0
        for idx, fname in enumerate(files, 1):
            if self.processing_stopped:
                break

            src = os.path.join(folder, fname)
            dst = os.path.join(out_dir, fname)
            shutil.copyfile(src, dst)

            try:
                with segyio.open(dst, 'r+', ignore_geometry=True) as f:
                    # читаем, масштабируем, обрабатываем и записываем обратно
                    traces = f.trace.raw[:].T.astype(np.float32)
                    scaler = MinMaxScaler().fit(traces.reshape(-1,1))
                    scaled = scaler.transform(traces.reshape(-1,1)).reshape(traces.shape)
                    mod, fn = pd['method'].rsplit('.', 1)
                    func = getattr(importlib.import_module(mod), fn)
                    processed = func(scaled, **params)
                    inv = scaler.inverse_transform(processed.reshape(-1,1)).reshape(processed.shape).T
                    for i in range(inv.shape[0]):
                        f.trace.raw[i] = inv[i]
            except Exception as e:
                QMessageBox.critical(self, "Ошибка обработки",
                                     f"При обработке файла {fname} произошла ошибка:\n{e}")
                break

            processed_count += 1
            self.progress_bar.setValue(idx)
            QApplication.processEvents()

        # Скрываем прогресс и stop-кнопку
        self.progress_bar.setVisible(False)
        self.processing_label.setVisible(False)
        self.stop_button.setVisible(False)

        # Итоговое сообщение
        if self.processing_stopped:
            QMessageBox.information(self, "Остановлено",
                                    f"Процесс был остановлен пользователем.\n"
                                    f"Обработано файлов: {processed_count}/{total}")
        else:
            QMessageBox.information(self, "Готово",
                                    f"Обработано файлов: {processed_count}/{total}\n"
                                    f"Результаты в папке:\n{out_dir}")



if __name__ == '__main__':
    app = QApplication([])
    window = SeisProcTester()
    app.exec_()