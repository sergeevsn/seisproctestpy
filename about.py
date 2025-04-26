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
            <p>Программа для тестирования обрабатывающих процедур для файлов в фомате SEG-Y.</p>             
            
            <h3>Основные возможности:</h3>

                <li>Загрузка/экспорт 2D сейсмических данных в формате SEG-Y</li>
                <li>Визуализация данных с настройкой цветовых карт и усиления</li>
                <li>Обработка заданных сочетаний параметров с использованием пользовательских алгоритмов</li>
                <li>Можно использовать любую процедуру из любой доступной python библиотеки, принимающую на вход 
                2D ndarray и набор параметров </li>
                <li>Сравнение оригинальных и обработанных данных</li>
                <li>Интерактивный зум с помощью мыши (выделение области - ЛКМ, сброс зума - ПКМ) </li>
            </ul>
                          
            <h3>Ограничения:</h3>
            <ul>
                <li>Загружает сразу все трассы, поэтому подходит для сейсмических разрезов или для единичных сейсмограмм</li>
                <li>Реализация на python накладывает ограничения на быстродействие интерфейса. Имеет смысл работать с небольшими файлами</li>
                <li>Редактирование параметров в JSON не очень удобна</li>                
            </ul>
            
            <h3>Технологии:</h3>
            <ul>
                <li>PyQt5 (GUI)</li>
                <li>Matplotlib (визуализация)</li>
                <li>Numpy (обработка данных)</li>
                <li>Segyio (работа с SEG-Y)</li>
            </ul>
            <p style="color: #666;">© 2025 Сергей Сергеев</p>
        ''')
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        self.setLayout(layout)

# В классе SectionProcessor добавлен метод:
def show_about(self):
    about = AboutDialog(self)
    about.exec_()