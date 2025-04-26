from PyQt5.QtWidgets import QApplication
from seisproctest import *
import sys

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QLabel {
            font-size: 10pt;
            font-family: arial;
        }
        QComboBox {
            font-size: 10pt;  /* Размер шрифта */
            
            padding: 5px;     /* Отступы для лучшей видимости */
        }
        QComboBox QAbstractItemView {
            font-size: 14pt;  /* Размер шрифта в выпадающем списке */
        }
    """)
    window = SeisProcTester()
    sys.exit(app.exec_())
