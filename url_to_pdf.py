import os
import sys
import time
import base64
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QFileDialog, QProgressBar, QMessageBox, QStatusBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

class PDFGeneratorThread(QThread):
    """Поток для генерации PDF без блокировки интерфейса"""
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(int)
    
    def __init__(self, url, output_path):
        super().__init__()
        self.url = url
        self.output_path = output_path
    
    def run(self):
        try:
            # Настройка опций Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            # Опции для печати
            print_options = {
                'recentDestinations': [{
                    'id': 'Save as PDF',
                    'origin': 'local',
                    'account': ''
                }],
                'selectedDestinationId': 'Save as PDF',
                'version': 2,
                'isHeaderFooterEnabled': False,
                'marginsType': 0,
                'scaling': 100,
            }
            
            # Добавление опций печати
            chrome_options.add_experimental_option('prefs', {
                'printing.print_preview_sticky_settings.appState': print_options,
                'download.default_directory': os.path.dirname(os.path.abspath(self.output_path)),
                'download.prompt_for_download': False,
                'plugins.always_open_pdf_externally': False
            })
            
            self.progress.emit(20)
            
            # Создание экземпляра Chrome с автоматической загрузкой совместимого драйвера
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            self.progress.emit(40)
            
            # Открытие страницы
            driver.get(self.url)
            
            # Ожидание загрузки страницы
            time.sleep(3)
            
            self.progress.emit(60)
            
            # Установка размера окна
            driver.set_window_size(1920, 1080)
            
            # Создание PDF
            print_options = {
                'landscape': False,
                'displayHeaderFooter': False,
                'printBackground': True,
                'preferCSSPageSize': True,
            }
            
            # Сохранение PDF с помощью встроенного метода Chrome
            pdf = driver.execute_cdp_cmd('Page.printToPDF', print_options)
            
            self.progress.emit(80)
            
            # Декодирование base64 в байты
            pdf_data = base64.b64decode(pdf['data'])
            
            # Запись PDF в файл
            with open(self.output_path, 'wb') as file:
                file.write(pdf_data)
            
            self.progress.emit(100)
            
            # Закрытие браузера
            driver.quit()
            
            self.finished.emit(True, "PDF успешно сохранен")
            
        except Exception as e:
            if 'driver' in locals():
                driver.quit()
            self.finished.emit(False, f"Ошибка: {str(e)}")


class URLToPDFApp(QMainWindow):
    """Главное окно приложения для конвертации URL в PDF"""
    
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        # Настройка главного окна
        self.setWindowTitle('URL to PDF Converter')
        self.setGeometry(300, 300, 600, 200)
        
        # Создание центрального виджета
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный вертикальный layout
        main_layout = QVBoxLayout(central_widget)
        
        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel('URL:')
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('https://example.com')
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)
        
        # Output path selector
        output_layout = QHBoxLayout()
        output_label = QLabel('Сохранить как:')
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText('Выберите путь для сохранения PDF')
        self.browse_button = QPushButton('Обзор')
        self.browse_button.clicked.connect(self.browse_output)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.browse_button)
        main_layout.addLayout(output_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Convert button
        self.convert_button = QPushButton('Конвертировать в PDF')
        self.convert_button.clicked.connect(self.convert_to_pdf)
        main_layout.addWidget(self.convert_button)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Готов к работе')
        
    def browse_output(self):
        """Открывает диалог выбора пути для сохранения PDF"""
        filename, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить PDF', '', 'PDF files (*.pdf)'
        )
        if filename:
            if not filename.endswith('.pdf'):
                filename += '.pdf'
            self.output_path.setText(filename)
    
    def convert_to_pdf(self):
        """Запускает процесс конвертации URL в PDF"""
        url = self.url_input.text().strip()
        output_path = self.output_path.text().strip()
        
        # Проверка введенных данных
        if not url:
            QMessageBox.warning(self, 'Ошибка', 'Пожалуйста, введите URL')
            return
            
        if not output_path:
            QMessageBox.warning(self, 'Ошибка', 'Пожалуйста, выберите путь для сохранения PDF')
            return
            
        # Проверка формата URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_input.setText(url)
        
        try:
            # Отключение кнопок во время работы
            self.convert_button.setEnabled(False)
            self.browse_button.setEnabled(False)
            
            self.status_bar.showMessage('Генерация PDF...')
            
            # Создание и запуск потока для генерации PDF
            self.pdf_thread = PDFGeneratorThread(url, output_path)
            self.pdf_thread.progress.connect(self.update_progress)
            self.pdf_thread.finished.connect(self.on_conversion_finished)
            self.pdf_thread.start()
        
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при конвертации: {str(e)}')
            self.convert_button.setEnabled(True)
            self.browse_button.setEnabled(True)
            self.status_bar.showMessage('Ошибка')
    
    def update_progress(self, value):
        """Обновляет прогресс-бар"""
        self.progress_bar.setValue(value)
    
    def on_conversion_finished(self, success, message):
        """Обрабатывает завершение конвертации"""
        self.convert_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        
        if success:
            QMessageBox.information(self, 'Успех', f'{message} в\n{self.output_path.text()}')
            self.status_bar.showMessage('PDF успешно создан')
        else:
            QMessageBox.critical(self, 'Ошибка', message)
            self.status_bar.showMessage('Ошибка при создании PDF')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = URLToPDFApp()
    window.show()
    sys.exit(app.exec_())