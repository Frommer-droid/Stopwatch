import sys
import json
import os
import time
import threading
import ctypes
import subprocess

# --- Блоки try-except для опциональных библиотек ---
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("Warning: 'keyboard' library not found. Global hotkeys will be disabled.")
    print("Install it using: pip install keyboard")

try:
    import pyautogui
    import pygetwindow
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False
    print("Warning: 'pyautogui' or 'pygetwindow' not found. Automation features will be disabled.")
    print("Install them using: pip install pyautogui pygetwindow")

try:
    import pygame
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False
    print("Warning: 'pygame' library not found. Sound playback will be disabled.")
    print("Install it using: pip install pygame")

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("Warning: 'pyperclip' library not found. Reading coordinates from AHK will be disabled.")
    print("Install it using: pip install pyperclip")

from version import __version__


from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                                 QLabel, QPushButton, QStyle, QSystemTrayIcon,
                                 QMenu, QDialog, QFormLayout,
                                 QLineEdit, QSpinBox, QDialogButtonBox, QRadioButton, QFrame)
from PySide6.QtCore import QTimer, Qt, Signal, QPoint, QObject, QThread
from PySide6.QtGui import QPainter, QPixmap, QIcon, QPen, QColor, QTransform

def resource_path(relative_path):
    """ 
    Получает абсолютный путь к ресурсу.
    Приоритет:
    1. Рядом с исполняемым файлом (если frozen) - для внешних конфигов/звуков.
    2. В папке _internal (если frozen) - для упакованных ресурсов.
    3. В папке скрипта (dev режим).
    """
    if getattr(sys, 'frozen', False):
        # 1. Проверяем рядом с exe
        base_path = os.path.dirname(sys.executable)
        path = os.path.join(base_path, relative_path)
        if os.path.exists(path):
            return path
            
        # 2. Проверяем в _internal (_MEIPASS)
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
            
    # 3. Dev режим
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)




class SettingsDialog(QDialog):
    """Кастомное диалоговое окно для настроек таймера и секундомера."""
    def __init__(self, mode='timer', current_scale='normal', current_hotkeys=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle(f"Настройки {'таймера' if mode == 'timer' else 'общие'}")
        self.setWindowIcon(QIcon(resource_path("logo.ico")))

        self.setStyleSheet("""
            QDialog { background-color: #17212B; }
            QLabel, QLineEdit, QSpinBox, QRadioButton { color: white; font-size: 24px; }
            QLineEdit, QSpinBox { background-color: #2A3440; border: 1px solid #4F5D6C; border-radius: 4px; padding: 4px; }
            QPushButton { background-color: #4F5D6C; color: white; border: none; padding: 5px 15px; border-radius: 4px; font-size: 24px; }
            QPushButton:hover { background-color: #6A7B8D; }
            QFrame[frameShape="4"] { border: 1px solid #4F5D6C; }
        """)

        self.layout = QFormLayout(self)

        if self.mode == 'timer':
            self.duration_edit = QLineEdit()
            self.beep_delay_spinbox = QSpinBox()
            self.beep_delay_spinbox.setRange(1, 9999)
            self.beep_delay_spinbox.setSuffix(" сек")
            self.layout.addRow("Длительность (ММ:СС):", self.duration_edit)
            self.layout.addRow("Сигнал после старта через:", self.beep_delay_spinbox)
        else:
            self.alarm_edit = QLineEdit()
            self.layout.addRow("Сигнал в (ММ:СС):", self.alarm_edit)
            
            # --- Настройки масштаба ---
            separator1 = QFrame()
            separator1.setFrameShape(QFrame.Shape.HLine)
            self.layout.addRow(separator1)
            
            self.scale_group_label = QLabel("Масштаб интерфейса:")
            self.scale_small_rb = QRadioButton("Маленький")
            self.scale_normal_rb = QRadioButton("Нормальный")
            self.scale_large_rb = QRadioButton("Большой")
            
            scale_widget = QWidget()
            scale_layout = QHBoxLayout(scale_widget)
            scale_layout.addWidget(self.scale_small_rb)
            scale_layout.addWidget(self.scale_normal_rb)
            scale_layout.addWidget(self.scale_large_rb)
            scale_layout.setContentsMargins(0,0,0,0)
            self.layout.addRow(self.scale_group_label, scale_widget)

            if current_scale == 'small': self.scale_small_rb.setChecked(True)
            elif current_scale == 'large': self.scale_large_rb.setChecked(True)
            else: self.scale_normal_rb.setChecked(True)

            # --- Настройки горячих клавиш ---
            if current_hotkeys:
                separator2 = QFrame()
                separator2.setFrameShape(QFrame.Shape.HLine)
                self.layout.addRow(separator2)
                
                self.hotkeys_label = QLabel("Горячие клавиши:")
                self.layout.addRow(self.hotkeys_label)

                self.hotkey_start_edit = QLineEdit(current_hotkeys.get('start', 'f3'))
                self.hotkey_reset_edit = QLineEdit(current_hotkeys.get('reset', 'f8'))
                
                self.layout.addRow("Старт/Стоп таймера:", self.hotkey_start_edit)
                self.layout.addRow("Сброс таймера:", self.hotkey_reset_edit)


        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addRow(self.button_box)

    def get_values(self):
        result = {}
        if self.mode == 'timer':
            result = {"duration": self.duration_edit.text(), "beep_delay": self.beep_delay_spinbox.value()}
        else:
            scale_mode = 'normal'
            if self.scale_small_rb.isChecked(): scale_mode = 'small'
            elif self.scale_large_rb.isChecked(): scale_mode = 'large'
            
            result["alarm"] = self.alarm_edit.text()
            result["scale_mode"] = scale_mode

            if hasattr(self, 'hotkey_start_edit'):
                result["hotkeys"] = {
                    "start": self.hotkey_start_edit.text().lower(),
                    "reset": self.hotkey_reset_edit.text().lower()
                }
        return result

    def set_values(self, values):
        if self.mode == 'timer':
            self.duration_edit.setText(values.get("duration", "05:00"))
            self.beep_delay_spinbox.setValue(values.get("beep_delay", 90))
        else:
            self.alarm_edit.setText(values.get("alarm", "00:00"))

class AHKWorker(QObject):
    finished = Signal(str)

    def __init__(self, ahk_exe_path, parent=None):
        super().__init__(parent)
        self.ahk_exe_path = ahk_exe_path
        self.original_clipboard = ""

    def run(self):
        try:
            self.original_clipboard = pyperclip.paste()
            pyperclip.copy("")
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen([self.ahk_exe_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
            process.communicate()
            coords_str = pyperclip.paste()
            pyperclip.copy(self.original_clipboard)
            self.finished.emit(coords_str)
        except Exception as e:
            print(f"Критическая ошибка в AHKWorker: {e}")
            if self.original_clipboard: pyperclip.copy(self.original_clipboard)
            self.finished.emit("")

class AutomationSettingsDialog(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.setWindowTitle("Настройки автоматизации")
        self.setWindowIcon(QIcon(resource_path("logo.ico")))
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.thread = None
        self.worker = None

        self.setStyleSheet("""
            QDialog { background-color: #17212B; }
            QLabel, QLineEdit, QPushButton { color: white; font-size: 24px; }
            QLineEdit { background-color: #2A3440; border: 1px solid #4F5D6C; border-radius: 4px; padding: 4px; }
            QPushButton { background-color: #4F5D6C; color: white; border: none; padding: 5px 15px; border-radius: 4px; font-size: 24px; }
            QPushButton:hover { background-color: #6A7B8D; }
        """)

        self.layout = QFormLayout(self)

        self.window_title_edit = QLineEdit()
        self.layout.addRow("Часть заголовка окна:", self.window_title_edit)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("border-top: 1px solid #4F5D6C;")
        self.layout.addRow(separator)

        self.x_coord_edit = QLineEdit()
        self.y_coord_edit = QLineEdit()
        self.pick_button = QPushButton("Выбрать место на экране")

        self.layout.addRow("Координата X:", self.x_coord_edit)
        self.layout.addRow("Координата Y:", self.y_coord_edit)
        self.layout.addRow(self.pick_button)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addRow(self.button_box)
        self.pick_button.clicked.connect(self.initiate_picking)

    def initiate_picking(self):
        if not CLIPBOARD_AVAILABLE:
            self.parent_window.tray_icon.showMessage("Ошибка", "Библиотека 'pyperclip' не найдена.", QSystemTrayIcon.Warning, 3000)
            return
        ahk_exe_path = resource_path('get_coords.exe')
        if not os.path.exists(ahk_exe_path):
            self.parent_window.tray_icon.showMessage("Ошибка", "Файл 'get_coords.exe' не найден.", QSystemTrayIcon.Critical, 4000)
            return

        self.hide()
        self.thread = QThread()
        self.worker = AHKWorker(ahk_exe_path)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_picking_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_picking_finished(self, coords_str):
        self.show()
        self.raise_()
        self.activateWindow()
        if coords_str:
            try:
                x, y = map(int, coords_str.split(','))
                self.x_coord_edit.setText(str(x))
                self.y_coord_edit.setText(str(y))
            except (ValueError, TypeError): pass

    def get_values(self):
        try:
            return {
                "window_title": self.window_title_edit.text(),
                "x": int(self.x_coord_edit.text()), 
                "y": int(self.y_coord_edit.text())
            }
        except (ValueError, TypeError): 
            return {
                "window_title": self.window_title_edit.text(),
                "x": None, 
                "y": None
            }

    def set_values(self, title, x, y):
        self.window_title_edit.setText(title if title is not None else "")
        self.x_coord_edit.setText(str(x) if x is not None else "")
        self.y_coord_edit.setText(str(y) if y is not None else "")


class ClickableLabel(QLabel):
    clicked = Signal()
    rightClicked = Signal()
    doubleClicked = Signal()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(QApplication.doubleClickInterval())
        self._timer.timeout.connect(self.clicked.emit)
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton: self.rightClicked.emit()
        elif event.button() == Qt.LeftButton:
            if self._timer.isActive():
                self._timer.stop()
                self.doubleClicked.emit()
            else: self._timer.start()

class DragHandle(QLabel):
    clicked = Signal()
    rightClicked = Signal()
    doubleClicked = Signal()
    def __init__(self, parent_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_window = parent_window
        self.drag_position = None
        self.setCursor(Qt.SizeAllCursor)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(QApplication.doubleClickInterval())
        self._timer.timeout.connect(self.clicked.emit)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._timer.isActive():
                self._timer.stop()
                self.drag_position = None 
                self.doubleClicked.emit()
            else:
                self._timer.start()
                if not self.parent_window.is_pinned:
                    self.drag_position = event.globalPosition().toPoint() - self.parent_window.pos()
            event.accept()
        elif event.button() == Qt.RightButton: self.rightClicked.emit(); event.accept()
    def mouseMoveEvent(self, event):
        if self._timer.isActive(): self._timer.stop()
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
    def mouseReleaseEvent(self, event): self.drag_position = None; event.accept()

class Stopwatch(QMainWindow):
    hotkey_start_pressed = Signal()
    hotkey_reset_pressed = Signal()

    BASE_WIDTH, BASE_HEIGHT = 315, 48
    BASE_FONT_SIZE, BASE_DRAG_FONT_SIZE = 25, 18
    BASE_DRAG_HANDLE_WIDTH, BASE_DRAG_HANDLE_HEIGHT = 15, 40
    BASE_CONTROL_BUTTON_SIZE, BASE_ICON_SIZE, BASE_ICON_PEN_WIDTH = 22, 16, 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Таймер и Секундомер v{__version__}")
        self.setWindowIcon(QIcon(resource_path("logo.ico")))
        
        self.is_pinned = False
        self.automation_window_title = "Naumen SoftPhone"
        
        self.settings_file = 'settings.json'
        self.scale_mode = 'normal'; self.scale_factor = 1.0
        self.hotkey_start, self.hotkey_reset = 'f3', 'f8'
        self.start_key_state = 'start' # 'start' or 'stop'

        self.automation_dialog = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if SOUND_AVAILABLE: pygame.mixer.init()

        self.click_position_x, self.click_position_y = None, None
        self.stopwatch_msecs, self.is_stopwatch_running = 0, False
        self.stopwatch_timer = QTimer(self)
        self.stopwatch_alarm_msecs, self.stopwatch_alarm_enabled = 0, False
        self.initial_timer_msecs = 300000
        self.timer_msecs = self.initial_timer_msecs
        self.countdown_timer = QTimer(self)
        self.is_timer_running = False
        self.blink_timer = QTimer(self)
        self.is_blinking = False
        self.start_beep_delay_secs = 90
        self.start_beep_timer = QTimer(self)
        self.start_beep_timer.setSingleShot(True)
        self.start_beep_timer.timeout.connect(lambda: self.play_sound('Timer-sound.mp3'))
        
        self.tray_icon_resource = None
        
        self.setup_ui()
        self.connect_signals()
        self.setup_tray_icon()
        self.load_settings()
        
    def apply_scale(self, scale_mode):
        self.scale_mode = scale_mode
        if self.scale_mode == 'small': self.scale_factor = 0.8
        elif self.scale_mode == 'large': self.scale_factor = 1.2
        else: self.scale_factor = 1.0

        self.setFixedSize(int(self.BASE_WIDTH * self.scale_factor), int(self.BASE_HEIGHT * self.scale_factor))
        font = self.font(); font.setPointSize(int(self.BASE_FONT_SIZE * self.scale_factor))
        self.timer_label.setFont(font); self.stopwatch_label.setFont(font)
        drag_font = self.font(); drag_font.setPointSize(int(self.BASE_DRAG_FONT_SIZE * self.scale_factor))
        self.drag_handle.setFont(drag_font)
        self.drag_handle.setFixedSize(int(self.BASE_DRAG_HANDLE_WIDTH*self.scale_factor), int(self.BASE_DRAG_HANDLE_HEIGHT*self.scale_factor))
        button_size = int(self.BASE_CONTROL_BUTTON_SIZE*self.scale_factor)
        
        self.hide_button.setFixedSize(button_size, button_size); self.close_button.setFixedSize(button_size, button_size)
        
        self.hide_button.setIcon(self._create_button_icon('hide')); self.close_button.setIcon(self._create_button_icon('close'))
        margin_h, margin_v = int(3 * self.scale_factor), int(2 * self.scale_factor)
        self.centralWidget().layout().setContentsMargins(margin_h, margin_v, int(1*self.scale_factor), margin_v)

    def _create_button_icon(self, icon_type):
        size = int(self.BASE_ICON_SIZE * self.scale_factor)
        if size < 2: size = 2
        pen_width = max(1, int(self.BASE_ICON_PEN_WIDTH * self.scale_factor))
        pixmap = QPixmap(size, size); pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor("#3AE2CE"), pen_width)

        painter.setPen(pen); painter.setRenderHint(QPainter.Antialiasing)
        p1 = int(0.25 * size)
        p2 = int(size - p1)
        if icon_type == 'close': painter.drawLine(p1, p1, p2, p2); painter.drawLine(p1, p2, p2, p1)
        elif icon_type == 'hide':
            x1, y1 = int(0.25*size), int(0.375*size); x2, y2 = int(0.5*size), int(0.625*size); x3 = int(0.75*size)
            painter.drawLine(x1, y1, x2, y2); painter.drawLine(x3, y1, x2, y2)

        painter.end(); return QIcon(pixmap)

    def setup_ui(self):
        self.container = QWidget(); self.container.setStyleSheet("background-color: #17212B; border-radius: 8px; color: white;")
        self.setCentralWidget(self.container)
        main_layout = QHBoxLayout(self.container); main_layout.setContentsMargins(3, 2, 1, 2); main_layout.setSpacing(0)
        
        self.timer_label = ClickableLabel("05:00", self)
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setToolTip("ЛКМ: Старт/Пауза | ПКМ: Сброс и запуск таймера | 2ЛКМ: Установить время")
        
        self.stopwatch_label = ClickableLabel("00:00", self); self.stopwatch_label.setAlignment(Qt.AlignCenter); self.stopwatch_label.setToolTip("ЛКМ: Старт/Пауза | ПКМ: Сброс и старт | 2ЛКМ: Общие настройки")
        self.drag_handle = DragHandle(self, "⋮"); self.drag_handle.setAlignment(Qt.AlignCenter); self.drag_handle.setStyleSheet("color: white;"); self.drag_handle.setToolTip("ЛКМ: Перетащить/Закрепить | 2ЛКМ: Задать позицию клика | ПКМ: Общий сброс")
        
        button_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; } QPushButton:hover { background-color: #555555; }"
        
        self.hide_button = QPushButton(self); self.hide_button.setStyleSheet(button_style); self.hide_button.setToolTip("Свернуть в трей")
        self.close_button = QPushButton(self); self.close_button.setStyleSheet(button_style); self.close_button.setToolTip("Закрыть")
        control_button_layout = QVBoxLayout(); control_button_layout.setContentsMargins(2, 0, 0, 0); control_button_layout.setSpacing(0)
        control_button_layout.addWidget(self.hide_button); control_button_layout.addWidget(self.close_button)
        
        main_layout.addWidget(self.timer_label, 1)
        main_layout.addWidget(self.drag_handle)
        main_layout.addWidget(self.stopwatch_label, 1)
        main_layout.addLayout(control_button_layout)
        
        self.apply_scale(self.scale_mode)
        self.update_pin_status()

    def connect_signals(self):
        self.stopwatch_timer.timeout.connect(self.update_stopwatch_time)
        self.stopwatch_label.clicked.connect(self.toggle_stopwatch)
        self.stopwatch_label.rightClicked.connect(self.reset_stopwatch)
        self.stopwatch_label.doubleClicked.connect(self.open_stopwatch_settings)
        self.countdown_timer.timeout.connect(self.update_countdown_time)
        self.timer_label.clicked.connect(self.toggle_timer)
        self.timer_label.rightClicked.connect(self.execute_right_click_sequence)
        self.timer_label.doubleClicked.connect(self.open_timer_settings)
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.hide_button.clicked.connect(self.hide_to_tray)
        self.close_button.clicked.connect(self.close)
        self.drag_handle.rightClicked.connect(self.global_reset)
        self.drag_handle.doubleClicked.connect(self.open_automation_settings)
        
        self.drag_handle.clicked.connect(self.toggle_pin_window)
        
        self.hotkey_start_pressed.connect(self.handle_start_key_press)
        self.hotkey_reset_pressed.connect(self.reset_timer)

    def toggle_pin_window(self):
        """Переключает состояние закрепления окна."""
        self.is_pinned = not self.is_pinned
        self.update_pin_status()

    def update_pin_status(self):
        """Обновляет значок, курсор и подсказки для ручки перетаскивания в зависимости от self.is_pinned."""
        if self.is_pinned:
            self.drag_handle.setText("⋮")
            self.drag_handle.setCursor(Qt.ArrowCursor)
            self.drag_handle.setStyleSheet("color: #3AE2CE;") # Бирюзовый цвет
            self.drag_handle.setToolTip("Окно закреплено. Кликните, чтобы открепить.")
        else:
            self.drag_handle.setText("✥") # Символ перемещения (скрещенные стрелки)
            self.drag_handle.setCursor(Qt.SizeAllCursor)
            self.drag_handle.setStyleSheet("color: white;")
            self.drag_handle.setToolTip("ЛКМ: Перетащить/Закрепить | 2ЛКМ: Задать позицию клика | ПКМ: Общий сброс")

    def open_automation_settings(self):
        if self.automation_dialog and self.automation_dialog.isVisible(): self.automation_dialog.raise_(); self.automation_dialog.activateWindow(); return
        self.automation_dialog = AutomationSettingsDialog(self)
        self.automation_dialog.set_values(self.automation_window_title, self.click_position_x, self.click_position_y)
        self.automation_dialog.finished.connect(self.on_automation_dialog_finished); self.automation_dialog.show()

    def on_automation_dialog_finished(self, result):
        if result == QDialog.Accepted:
            values = self.automation_dialog.get_values()
            
            self.automation_window_title = values.get('window_title')
            
            if values['x'] is not None and values['y'] is not None:
                self.click_position_x, self.click_position_y = values['x'], values['y']
                self.tray_icon.showMessage("Позиция сохранена", f"Новая позиция: X={self.click_position_x}, Y={self.click_position_y}", QSystemTrayIcon.Information, 3000)
            
            self.save_settings() # Сохраняем все измененные параметры
        self.automation_dialog = None

    def open_timer_settings(self):
        dialog = SettingsDialog(mode='timer', parent=self)
        current_text = f"{(self.initial_timer_msecs // 60000):02d}:{(self.initial_timer_msecs % 60000 // 1000):02d}"
        dialog.set_values({"duration": current_text, "beep_delay": self.start_beep_delay_secs})
        if dialog.exec():
            values = dialog.get_values()
            self.start_beep_delay_secs = values["beep_delay"]
            try:
                minutes, seconds = map(int, values["duration"].split(':'))
                if 0 <= minutes and 0 <= seconds < 60: self.initial_timer_msecs = (minutes * 60 + seconds) * 1000; self.reset_timer()
            except ValueError: pass
            self.save_settings()

    def open_stopwatch_settings(self):
        current_hotkeys = {"start": self.hotkey_start, "reset": self.hotkey_reset}
        dialog = SettingsDialog(mode='stopwatch', current_scale=self.scale_mode, current_hotkeys=current_hotkeys, parent=self)
        current_text = f"{(self.stopwatch_alarm_msecs // 60000):02d}:{(self.stopwatch_alarm_msecs % 60000 // 1000):02d}"
        dialog.set_values({"alarm": current_text})
        if dialog.exec():
            values = dialog.get_values()
            try:
                minutes, seconds = map(int, values["alarm"].split(':'))
                if 0 <= minutes and 0 <= seconds < 60: self.stopwatch_alarm_msecs = (minutes*60+seconds)*1000; self.stopwatch_alarm_enabled = self.stopwatch_alarm_msecs > 0
            except ValueError: pass
            
            settings_changed = False
            new_scale_mode = values.get("scale_mode", "normal")
            if new_scale_mode != self.scale_mode: self.apply_scale(new_scale_mode); settings_changed = True

            new_hotkeys = values.get("hotkeys")
            if new_hotkeys and (new_hotkeys['start'] != self.hotkey_start or new_hotkeys['reset'] != self.hotkey_reset):
                self.hotkey_start, self.hotkey_reset = new_hotkeys['start'], new_hotkeys['reset']
                self.register_hotkeys(); settings_changed = True
            
            if settings_changed: self.save_settings()

    def _activate_target_window(self):
        if not AUTOMATION_AVAILABLE: 
            return None
        
        if not self.automation_window_title:
            self.tray_icon.showMessage("Заголовок не задан", "2ЛКМ на '✥' чтобы задать заголовок окна.", QSystemTrayIcon.Warning, 4000)
            return None
            
        try:
            w_title = self.automation_window_title
            all_windows = pygetwindow.getAllWindows()
            # log_debug(f"Found {len(all_windows)} windows: {[w.title for w in all_windows]}") # Uncomment if needed, can be verbose
            
            target_window = next((w for w in all_windows if w_title.lower() in w.title.lower()), None)
            
            if not target_window: 
                self.tray_icon.showMessage("Ошибка", f"Окно с '{w_title}' не найдено.", QSystemTrayIcon.Warning, 3000)
                return None
            
            if not target_window.isActive:
                try: 
                    target_window.minimize()
                    time.sleep(0.1)
                    target_window.restore()
                except Exception as e: 
                    target_window.activate()
                time.sleep(1)
            return target_window
        except Exception as e: 
            self.tray_icon.showMessage("Ошибка активации окна", str(e), QSystemTrayIcon.Warning, 3000)
            return None

    def _perform_click(self):
        if self.click_position_x is not None and self.click_position_y is not None:
            try: pyautogui.click(self.click_position_x, self.click_position_y); return True
            except Exception as e: self.tray_icon.showMessage("Ошибка клика", str(e), QSystemTrayIcon.Warning, 3000); return False
        else: self.tray_icon.showMessage("Позиция не задана", "2ЛКМ на '⋮' чтобы задать позицию.", QSystemTrayIcon.Warning, 4000); return False

    def _automation_task_start(self):
        if self._activate_target_window() and self._perform_click():
            screenWidth, screenHeight = pyautogui.size(); pyautogui.moveTo(screenWidth / 2, screenHeight / 2)
    def _automation_task_stop(self):
        if self._activate_target_window(): self._perform_click()
        if AUTOMATION_AVAILABLE: screenWidth, screenHeight = pyautogui.size(); pyautogui.moveTo(screenWidth/2, screenHeight/2)
    
    def _timer_end_task(self):
        self._automation_task_stop()
        self.play_sound('Вернись.mp3')
        self.start_key_state = 'start' # Сброс состояния клавиши для следующего запуска
        
    def play_sound(self, sound_file):
        if SOUND_AVAILABLE:
            sound_path = resource_path(sound_file)
            if os.path.exists(sound_path):
                try: pygame.mixer.music.load(sound_path); pygame.mixer.music.play()
                except Exception as e: self.tray_icon.showMessage("Ошибка звука", f"Не удалось: {e}", QSystemTrayIcon.Warning, 3000)
            else: self.tray_icon.showMessage("Ошибка", f"Файл '{sound_file}' не найден.", QSystemTrayIcon.Warning, 3000)

    def _stop_timer_components(self):
        """Останавливает только компоненты, связанные с таймером обратного отсчета."""
        self.countdown_timer.stop()
        self.start_beep_timer.stop()
        self.blink_timer.stop()
        self.is_timer_running = False
        self.is_blinking = False
        self.timer_label.setStyleSheet("color: white;")

    def _stop_all_timers(self):
        """Останавливает абсолютно все таймеры (для общего сброса или закрытия)."""
        self._stop_timer_components()
        self.stopwatch_timer.stop()
        self.is_stopwatch_running = False

    def handle_start_key_press(self):
        """Обрабатывает логику переключения для горячей клавиши старта (например, F3)."""
        if self.start_key_state == 'start':
            # Первое нажатие: выполнить последовательность запуска
            self.execute_start_sequence()
        else:
            # Второе нажатие: выполнить последовательность остановки
            self.execute_stop_sequence()

    def execute_start_sequence(self):
        self.play_sound('Начал.mp3')
        self.reset_and_start_timer()
        self.start_beep_timer.stop()
        self.start_beep_timer.start(self.start_beep_delay_secs * 1000)
        threading.Thread(target=self._automation_task_start, daemon=True).start()
    
    def execute_right_click_sequence(self):
        self.play_sound('Начал.mp3')
        self.reset_and_start_timer()
        self.start_beep_timer.stop()
        self.start_beep_timer.start(self.start_beep_delay_secs * 1000)

    def execute_stop_sequence(self):
        self.play_sound('Закончил.mp3')
        self.reset_timer()
        threading.Thread(target=self._automation_task_stop, daemon=True).start()

    def register_hotkeys(self):
        if not KEYBOARD_AVAILABLE: return
        keyboard.unhook_all()
        try:
            keyboard.add_hotkey(self.hotkey_start, lambda: self.hotkey_start_pressed.emit())
            keyboard.add_hotkey(self.hotkey_reset, lambda: self.hotkey_reset_pressed.emit())
            print(f"Горячие клавиши установлены: {self.hotkey_start}, {self.hotkey_reset}")
        except Exception as e:
            print(f"Не удалось установить горячие клавиши: {e}")
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage("Ошибка горячих клавиш", f"Неверное имя клавиши. Проверьте настройки.", QSystemTrayIcon.Warning, 4000)
    
    def global_reset(self): self.reset_timer(); self.stop_and_reset_stopwatch()
    
    def toggle_timer(self):
        self.stop_blinking()
        if self.timer_msecs <= 0: return
        self.is_timer_running = not self.is_timer_running
        if self.is_timer_running:
            self.countdown_timer.start(10)
            self.start_beep_timer.stop()
            self.start_beep_timer.start(self.start_beep_delay_secs * 1000)
        else:
            self.countdown_timer.stop()
            self.start_beep_timer.stop()
        
    def reset_timer(self): 
        self._stop_timer_components()
        self.timer_msecs = self.initial_timer_msecs
        self.update_countdown_time()
        self.start_key_state = 'start' # Сброс состояния клавиши Start

    def reset_and_start_timer(self):
        self._stop_timer_components()
        self.timer_msecs = self.initial_timer_msecs
        self.update_countdown_time()
        if self.timer_msecs > 0:
            self.is_timer_running = True
            self.countdown_timer.start(10)
            self.start_key_state = 'stop' # Установить состояние для следующего нажатия
        else:
            self.is_timer_running = False
            self.start_key_state = 'start' # Сбросить, если таймер не удалось запустить
        
    def update_countdown_time(self):
        if self.is_timer_running: self.timer_msecs -= self.countdown_timer.interval()
        if self.timer_msecs < 0:
            self.timer_msecs = 0; self.countdown_timer.stop(); self.is_timer_running = False
            self.start_blinking(); threading.Thread(target=self._timer_end_task, daemon=True).start()
        total_seconds = (self.timer_msecs + 999) // 1000
        self.timer_label.setText(f"{(total_seconds // 60):02d}:{(total_seconds % 60):02d}")
        
    def start_blinking(self):
        if not self.is_blinking: self.is_blinking = True; self.blink_timer.start(500)
        
    def stop_blinking(self):
        if self.is_blinking: self.is_blinking = False; self.blink_timer.stop(); self.timer_label.setStyleSheet("color: white;")
        
    def toggle_blink(self): self.timer_label.setStyleSheet("color: red;" if "white" in self.timer_label.styleSheet() else "color: white;")
    
    def update_stopwatch_time(self):
        if self.is_stopwatch_running: self.stopwatch_msecs += self.stopwatch_timer.interval()
        if self.stopwatch_alarm_enabled and self.stopwatch_msecs >= self.stopwatch_alarm_msecs:
            self.play_sound('Stopwatch-sound.mp3'); self.stopwatch_alarm_enabled = False
        total_seconds = self.stopwatch_msecs // 1000
        self.stopwatch_label.setText(f"{(total_seconds // 60):02d}:{(total_seconds % 60):02d}")
        
    def toggle_stopwatch(self):
        self.is_stopwatch_running = not self.is_stopwatch_running
        if self.is_stopwatch_running: self.stopwatch_timer.start(10)
        else: self.stopwatch_timer.stop()
        
    def reset_stopwatch(self):
        self.stopwatch_timer.stop(); self.stopwatch_msecs = 0; self.stopwatch_label.setText("00:00")
        self.stopwatch_timer.start(10); self.is_stopwatch_running = True
        if self.stopwatch_alarm_msecs > 0: self.stopwatch_alarm_enabled = True
        
    def stop_and_reset_stopwatch(self):
        self.stopwatch_timer.stop(); self.is_stopwatch_running = False; self.stopwatch_msecs = 0; self.stopwatch_label.setText("00:00")
        if self.stopwatch_alarm_msecs > 0: self.stopwatch_alarm_enabled = True
        
    def setup_tray_icon(self):
        self.tray_icon_resource = QIcon(resource_path("logo.ico")); self.tray_icon = QSystemTrayIcon(self.tray_icon_resource, self)
        self.tray_icon.setToolTip("Таймер и Секундомер"); tray_menu = QMenu()
        show_action = tray_menu.addAction("Показать/Скрыть"); show_action.triggered.connect(self.toggle_visibility)
        exit_action = tray_menu.addAction("Выход"); exit_action.triggered.connect(self.close)
        self.tray_icon.setContextMenu(tray_menu); self.tray_icon.show(); self.tray_icon.activated.connect(self.tray_icon_activated)
        
    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else: self.showNormal(); self.activateWindow()
        
    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger: self.toggle_visibility()
        
    def hide_to_tray(self): self.hide(); self.tray_icon.showMessage("Свернуто", "Приложение скрыто.", QSystemTrayIcon.Information, 2000)

    def load_settings(self):
        did_load = False
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    pos = settings.get('position'); timer_duration = settings.get('timer_duration'); beep_delay = settings.get('start_beep_delay_secs')
                    stopwatch_alarm = settings.get('stopwatch_alarm_msecs'); click_pos = settings.get('click_position')
                    scale_mode = settings.get('scale_mode', 'normal')
                    hotkeys = settings.get('hotkeys')
                    
                    self.is_pinned = settings.get('is_pinned', False)
                    self.automation_window_title = settings.get('automation_window_title', 'Naumen SoftPhone')
                    
                    self.apply_scale(scale_mode)
                    if pos: self.move(QPoint(pos['x'], pos['y']))
                    if timer_duration: self.initial_timer_msecs = timer_duration
                    if beep_delay: self.start_beep_delay_secs = beep_delay
                    if stopwatch_alarm: self.stopwatch_alarm_msecs = stopwatch_alarm
                    if click_pos and click_pos.get('x') is not None: self.click_position_x, self.click_position_y = click_pos['x'], click_pos['y']
                    if hotkeys: 
                        self.hotkey_start = hotkeys.get('start', 'f3')
                        self.hotkey_reset = hotkeys.get('reset', 'f8')
                    did_load = True
            except (json.JSONDecodeError, KeyError, TypeError) as e: print(f"Ошибка загрузки настроек: {e}")
        
        if not did_load: self.apply_scale('normal')
        
        self.update_pin_status()
        
        self.register_hotkeys()
        self.reset_timer(); self.stop_and_reset_stopwatch()

    def save_settings(self):
        settings = {
            'position': {'x': self.pos().x(), 'y': self.pos().y()},
            'timer_duration': self.initial_timer_msecs,
            'start_beep_delay_secs': self.start_beep_delay_secs,
            'stopwatch_alarm_msecs': self.stopwatch_alarm_msecs,
            'click_position': {'x': self.click_position_x, 'y': self.click_position_y},
            'scale_mode': self.scale_mode,
            'hotkeys': {'start': self.hotkey_start, 'reset': self.hotkey_reset},
            'is_pinned': self.is_pinned,
            'automation_window_title': self.automation_window_title,
        }
        with open(self.settings_file, 'w') as f: json.dump(settings, f, indent=4)

    def closeEvent(self, event):
        self.save_settings(); self._stop_all_timers(); self.tray_icon.hide()
        if KEYBOARD_AVAILABLE:
            try: keyboard.unhook_all()
            except Exception as e: print(f"Error unhooking keyboard: {e}")
        QApplication.instance().quit(); event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myappid = 'mycompany.myproduct.stopwatch.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app.setWindowIcon(QIcon(resource_path("logo.ico")))
    app.setQuitOnLastWindowClosed(False)
    stopwatch_app = Stopwatch()
    stopwatch_app.show()
    sys.exit(app.exec())

