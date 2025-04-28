from PyQt5.QtWidgets import (
    QDialog, QTextEdit, QVBoxLayout
)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About SeisProcTestPy")
        self.setFixedSize(700, 800)
        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setHtml('''
            <h1 style="color: #2c5f2d;">SeisProcTestPy</h1>
            <h3>Version 1.0</h3>
            <p>A program for testing processing procedures for files in SEG-Y format.</p>             
            
            <h3>Main Features:</h3>
            <ul>
                <li>Loading/exporting 2D seismic data in SEG-Y format</li>
                <li>Data visualization with customizable color maps and gain settings</li>
                <li>Processing specified parameter combinations using custom algorithms</li>
                <li>You can use any procedure from any available Python library that accepts a 
                2D ndarray and a set of parameters as input</li>
                <li>Comparison of original and processed data</li>
                <li>Interactive zoom using the mouse (region selection - left click, reset zoom - right click)</li>
                <li>Saving figures to mp4 movie</li>
                <li>Applying the chosen procedure/parameter set to a collection of SEG-Y files in a specified folder</li>
            </ul>
                          
            <h3>Limitations:</h3>
            <ul>
                <li>Loads all traces at once, so it is suitable for seismic sections or single seismograms</li>
                <li>The Python implementation imposes limitations on interface performance. It is recommended to work with small files</li>
                <li>All test results are stored in memory, so please avoid too many variants!</li>
                <li>Editing parameters in JSON is not very convenient</li>                
            </ul>
            
            <h3>Technologies:</h3>
            <ul>
                <li>PyQt5 (GUI)</li>
                <li>Matplotlib (visualization)</li>
                <li>Numpy (data processing)</li>
                <li>Segyio (working with SEG-Y)</li>
                <li>imageio-ffmpeg (Figures to movie)</li>
            </ul>
            <p style="color: #666;">© 2025 Sergey Sergeev</p>
        ''')
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        self.setLayout(layout)

def show_about(self):
    about = AboutDialog(self)
    about.exec_()