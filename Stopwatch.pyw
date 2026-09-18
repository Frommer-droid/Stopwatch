import sys
import json
import os
import time
import threading
import ctypes
import subprocess
from pathlib import Path

from call_session import CallAction, CallSession


def relaunch_with_pythonw_if_needed():
    """Restart a source launch through pythonw.exe to keep this GUI app windowed."""
    if getattr(sys, "frozen", False) or os.name != "nt":
        return

    interpreter = Path(sys.executable)
    pythonw = interpreter.with_name("pythonw.exe")
    if interpreter.name.lower() != "python.exe" or not pythonw.is_file():
        return

    subprocess.Popen(
        [str(pythonw), str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=os.getcwd(),
        close_fds=True,
    )
    raise SystemExit(0)


if __name__ == "__main__":
    relaunch_with_pythonw_if_needed()

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
                                  QLineEdit, QDialogButtonBox, QRadioButton, QFrame, QCheckBox)
from PySide6.QtCore import QTimer, Qt, Signal, QPoint, QObject, QThread
from PySide6.QtGui import QPainter, QPixmap, QIcon, QPen, QColor, QTransform

DEFAULT_CURRENT_HOLD_WARNING_MSECS = 3 * 60_000 + 30_000
# Alert when the accumulated Hold time reaches 3 minutes 40 seconds.
DEFAULT_TOTAL_HOLD_WARNING_MSECS = 3 * 60_000 + 40_000
# Compatibility aliases for integrations and tests that need the factory defaults.
CURRENT_HOLD_WARNING_MSECS = DEFAULT_CURRENT_HOLD_WARNING_MSECS
TOTAL_HOLD_WARNING_MSECS = DEFAULT_TOTAL_HOLD_WARNING_MSECS
CURRENT_HOLD_WARNING_SOUND = "Timer-sound.mp3"
TOTAL_HOLD_WARNING_SOUND = "Stopwatch-sound.mp3"
CALL_KEY_SOUND = CURRENT_HOLD_WARNING_SOUND
HOLD_KEY_SCAN_CODE = 82
HOLD_KEY_DESCRIPTION = "Insert (физическая клавиша, scan code 82)"
CALL_KEY_SCAN_CODE = 41
CALL_KEY_DESCRIPTION = "Ё (физическая клавиша, scan code 41)"


def format_duration_msecs(duration_msecs):
    """Возвращает длительность в формате ММ:СС для поля настройки."""
    total_seconds = max(0, duration_msecs) // 1_000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def parse_duration_msecs(value):
    """Преобразует ММ:СС в миллисекунды; ``None`` означает неверный формат."""
    try:
        minutes_text, seconds_text = value.strip().split(":")
        minutes, seconds = int(minutes_text), int(seconds_text)
    except (AttributeError, ValueError):
        return None

    if minutes < 0 or not 0 <= seconds < 60:
        return None
    return (minutes * 60 + seconds) * 1_000

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
    """Диалог общих настроек счётчиков."""
    def __init__(self, current_scale='normal', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Общие настройки")
        self.setWindowIcon(QIcon(resource_path("logo.ico")))

        self.setStyleSheet("""
            QDialog { background-color: #17212B; }
            QLabel, QLineEdit, QRadioButton, QCheckBox { color: white; font-size: 24px; }
            QLineEdit { background-color: #2A3440; border: 1px solid #4F5D6C; border-radius: 4px; padding: 4px; }
            QPushButton { background-color: #4F5D6C; color: white; border: none; padding: 5px 15px; border-radius: 4px; font-size: 24px; }
            QPushButton:hover { background-color: #6A7B8D; }
            QFrame[frameShape="4"] { border: 1px solid #4F5D6C; }
        """)

        self.layout = QFormLayout(self)

        self.alarm_edit = QLineEdit()
        self.layout.addRow("Сигнал общего времени в (ММ:СС):", self.alarm_edit)

        self.current_hold_warning_edit = QLineEdit()
        self.current_hold_warning_edit.setText(
            format_duration_msecs(DEFAULT_CURRENT_HOLD_WARNING_MSECS)
        )
        self.layout.addRow("Одновременный Hold (ММ:СС, 0:00 — выкл.):", self.current_hold_warning_edit)

        self.total_hold_warning_edit = QLineEdit()
        self.total_hold_warning_edit.setText(
            format_duration_msecs(DEFAULT_TOTAL_HOLD_WARNING_MSECS)
        )
        self.layout.addRow("Общий Hold (ММ:СС, 0:00 — выкл.):", self.total_hold_warning_edit)

        separator0 = QFrame()
        separator0.setFrameShape(QFrame.Shape.HLine)
        self.layout.addRow(separator0)

        self.sound_checkbox = QCheckBox("Звуковые сигналы")
        self.sound_checkbox.setChecked(True)
        self.layout.addRow(self.sound_checkbox)

        self.single_sound_checkbox = QCheckBox("Один звук (signal.mp3)")
        self.single_sound_checkbox.setChecked(False)
        self.layout.addRow(self.single_sound_checkbox)

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

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addRow(self.button_box)

    def get_values(self):
        scale_mode = 'normal'
        if self.scale_small_rb.isChecked(): scale_mode = 'small'
        elif self.scale_large_rb.isChecked(): scale_mode = 'large'

        return {
            "alarm": self.alarm_edit.text(),
            "current_hold_warning": self.current_hold_warning_edit.text(),
            "total_hold_warning": self.total_hold_warning_edit.text(),
            "scale_mode": scale_mode,
            "sound_enabled": self.sound_checkbox.isChecked(),
            "single_sound": self.single_sound_checkbox.isChecked(),
        }

    def set_values(self, values):
        self.alarm_edit.setText(values.get("alarm", "00:00"))
        self.current_hold_warning_edit.setText(
            values.get("current_hold_warning", format_duration_msecs(DEFAULT_CURRENT_HOLD_WARNING_MSECS))
        )
        self.total_hold_warning_edit.setText(
            values.get("total_hold_warning", format_duration_msecs(DEFAULT_TOTAL_HOLD_WARNING_MSECS))
        )
        self.sound_checkbox.setChecked(values.get("sound_enabled", True))
        self.single_sound_checkbox.setChecked(values.get("single_sound", False))

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
                "y": int(self.y_coord_edit.text()),
            }
        except (ValueError, TypeError): 
            return {
                "window_title": self.window_title_edit.text(),
                "x": None, 
                "y": None,
            }

    def set_values(self, title, x, y):
        self.window_title_edit.setText(title if title is not None else "")
        self.x_coord_edit.setText(str(x) if x is not None else "")
        self.y_coord_edit.setText(str(y) if y is not None else "")


class ClickableLabel(QLabel):
    clicked = Signal()
    rightClicked = Signal()
    doubleClicked = Signal()
    def __init__(self, *args, wait_for_double_click=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._wait_for_double_click = wait_for_double_click
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(QApplication.doubleClickInterval())
        self._timer.timeout.connect(self.clicked.emit)
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton: self.rightClicked.emit()
        elif event.button() == Qt.LeftButton:
            if not self._wait_for_double_click:
                self.clicked.emit()
            elif self._timer.isActive():
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
    hold_key_pressed = Signal()
    call_key_pressed = Signal()
    softphone_click_finished = Signal(int, bool, str)

    BASE_WIDTH, BASE_HEIGHT = 350, 48
    BASE_FONT_SIZE, BASE_DRAG_FONT_SIZE = 25, 18
    BASE_DRAG_HANDLE_WIDTH, BASE_DRAG_HANDLE_HEIGHT = 15, 40
    BASE_CONTROL_BUTTON_SIZE, BASE_ICON_SIZE, BASE_ICON_PEN_WIDTH = 22, 16, 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Таймер и Секундомер v{__version__}")
        self.setWindowIcon(QIcon(resource_path("logo.ico")))
        
        self.is_pinned = False
        self.automation_window_title = "Naumen SoftPhone"
        
        self.settings_file = resource_path('settings.json')
        self.scale_mode = 'normal'; self.scale_factor = 1.0
        self.sound_enabled = True
        self.single_sound_enabled = False
        self.call_session = CallSession()
        self._call_generation = 0
        self._automation_in_progress = False

        self.automation_dialog = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if SOUND_AVAILABLE: pygame.mixer.init()

        self.click_position_x, self.click_position_y = None, None
        self.total_msecs = 0
        self.total_timer = QTimer(self)
        self.hold_msecs = 0
        self.hold_total_msecs = 0
        self.hold_timer = QTimer(self)
        self.hold_warning_played = False
        self.hold_total_warning_played = False
        self.hold_limit_reached = False
        self.hold_total_limit_reached = False
        self.hold_warning_blink_visible = False
        self.hold_warning_blink_timer = QTimer(self)
        self.hold_warning_blink_timer.setInterval(500)
        self.current_hold_warning_msecs = DEFAULT_CURRENT_HOLD_WARNING_MSECS
        self.total_hold_warning_msecs = DEFAULT_TOTAL_HOLD_WARNING_MSECS
        self.stopwatch_alarm_msecs, self.stopwatch_alarm_enabled = 0, False
        
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
        self.timer_label.setFont(font)
        self.hold_total_label.setFont(font)
        self.stopwatch_label.setFont(font)
        drag_font = self.font(); drag_font.setPointSize(int(self.BASE_DRAG_FONT_SIZE * self.scale_factor))
        self.drag_handle.setFont(drag_font)
        self.drag_handle.setFixedSize(int(self.BASE_DRAG_HANDLE_WIDTH*self.scale_factor), int(self.BASE_DRAG_HANDLE_HEIGHT*self.scale_factor))
        button_size = int(self.BASE_CONTROL_BUTTON_SIZE*self.scale_factor)
        
        self.hide_button.setFixedSize(button_size, button_size); self.close_button.setFixedSize(button_size, button_size)
        
        self.hide_button.setIcon(self._create_button_icon('hide')); self.close_button.setIcon(self._create_button_icon('close'))
        margin_h = int(1 * self.scale_factor)
        margin_v = int(1 * self.scale_factor)
        self.centralWidget().layout().setContentsMargins(margin_h, margin_v, 0, margin_v)

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
        main_layout = QHBoxLayout(self.container); main_layout.setContentsMargins(1, 1, 0, 1); main_layout.setSpacing(0)
        
        self.timer_label = ClickableLabel("00:00", self)
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setToolTip("ЛКМ: переключить Hold | ПКМ: общий сброс")

        self.hold_total_label = QLabel("00:00", self)
        self.hold_total_label.setAlignment(Qt.AlignCenter)
        self.hold_total_label.setStyleSheet("color: #3AE2CE;")
        self.hold_total_label.setToolTip("Сумма Hold за текущий звонок: сбрасывается клавишей Ё")
        
        self.stopwatch_label = ClickableLabel("00:00", self, wait_for_double_click=True); self.stopwatch_label.setAlignment(Qt.AlignCenter); self.stopwatch_label.setToolTip("ЛКМ: начать/завершить звонок | ПКМ: общий сброс | 2ЛКМ: настройки")
        self.drag_handle = DragHandle(self, "⋮"); self.drag_handle.setAlignment(Qt.AlignCenter); self.drag_handle.setStyleSheet("color: white;"); self.drag_handle.setToolTip("ЛКМ: Перетащить/Закрепить | 2ЛКМ: Задать позицию клика | ПКМ: Общий сброс")
        
        button_style = "QPushButton { background-color: transparent; border: none; border-radius: 4px; } QPushButton:hover { background-color: #555555; }"
        
        self.hide_button = QPushButton(self); self.hide_button.setStyleSheet(button_style); self.hide_button.setToolTip("Свернуть в трей")
        self.close_button = QPushButton(self); self.close_button.setStyleSheet(button_style); self.close_button.setToolTip("Закрыть")
        control_button_layout = QVBoxLayout(); control_button_layout.setContentsMargins(0, 0, 0, 0); control_button_layout.setSpacing(0)
        control_button_layout.addWidget(self.hide_button); control_button_layout.addWidget(self.close_button)
        
        main_layout.addWidget(self.timer_label, 1)
        main_layout.addWidget(self.hold_total_label, 1)
        main_layout.addWidget(self.drag_handle)
        main_layout.addWidget(self.stopwatch_label, 1)
        main_layout.addLayout(control_button_layout)
        
        self.apply_scale(self.scale_mode)
        self.update_pin_status()

    def connect_signals(self):
        self.total_timer.timeout.connect(self.update_total_time)
        self.hold_timer.timeout.connect(self.update_hold_time)
        self.hold_warning_blink_timer.timeout.connect(self.toggle_hold_warning_blink)
        self.timer_label.clicked.connect(self.handle_hold_timer_click)
        self.timer_label.rightClicked.connect(self.global_reset)
        self.stopwatch_label.clicked.connect(self.handle_call_key_press)
        self.stopwatch_label.rightClicked.connect(self.global_reset)
        self.stopwatch_label.doubleClicked.connect(self.open_stopwatch_settings)
        self.hide_button.clicked.connect(self.hide_to_tray)
        self.close_button.clicked.connect(self.close)
        self.drag_handle.rightClicked.connect(self.global_reset)
        self.drag_handle.doubleClicked.connect(self.open_automation_settings)
        
        self.drag_handle.clicked.connect(self.toggle_pin_window)
        
        self.hold_key_pressed.connect(self.handle_start_key_press)
        self.call_key_pressed.connect(self.handle_call_key_press)
        self.softphone_click_finished.connect(self.on_softphone_click_finished)

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

    def open_stopwatch_settings(self):
        dialog = SettingsDialog(current_scale=self.scale_mode, parent=self)
        dialog.set_values({
            "alarm": format_duration_msecs(self.stopwatch_alarm_msecs),
            "current_hold_warning": format_duration_msecs(self.current_hold_warning_msecs),
            "total_hold_warning": format_duration_msecs(self.total_hold_warning_msecs),
            "sound_enabled": self.sound_enabled,
            "single_sound": self.single_sound_enabled,
        })
        if dialog.exec():
            values = dialog.get_values()
            settings_changed = False
            parsed_durations = {
                name: parse_duration_msecs(values[name])
                for name in ("alarm", "current_hold_warning", "total_hold_warning")
            }
            if any(duration is None for duration in parsed_durations.values()):
                self.tray_icon.showMessage(
                    "Неверный формат времени",
                    "Укажите время в формате ММ:СС (например, 03:30).",
                    QSystemTrayIcon.Warning,
                    4_000,
                )
                return

            new_alarm_msecs = parsed_durations["alarm"]
            if new_alarm_msecs != self.stopwatch_alarm_msecs:
                self.stopwatch_alarm_msecs = new_alarm_msecs
                self.stopwatch_alarm_enabled = self.stopwatch_alarm_msecs > 0
                settings_changed = True

            new_current_hold_warning = parsed_durations["current_hold_warning"]
            new_total_hold_warning = parsed_durations["total_hold_warning"]
            if new_current_hold_warning != self.current_hold_warning_msecs:
                self.current_hold_warning_msecs = new_current_hold_warning
                settings_changed = True
            if new_total_hold_warning != self.total_hold_warning_msecs:
                self.total_hold_warning_msecs = new_total_hold_warning
                settings_changed = True

            self.hold_warning_played = (
                self.current_hold_warning_msecs > 0
                and self.hold_msecs >= self.current_hold_warning_msecs
            )
            self.hold_total_warning_played = (
                self.total_hold_warning_msecs > 0
                and self.hold_total_msecs >= self.total_hold_warning_msecs
            )
            self.hold_limit_reached = self.hold_warning_played
            self.hold_total_limit_reached = self.hold_total_warning_played
            self._update_hold_warning_blinking()

            new_scale_mode = values.get("scale_mode", "normal")
            if new_scale_mode != self.scale_mode: self.apply_scale(new_scale_mode); settings_changed = True

            new_sound_enabled = values.get("sound_enabled", True)
            if new_sound_enabled != self.sound_enabled:
                self.sound_enabled = new_sound_enabled
                settings_changed = True

            new_single_sound = values.get("single_sound", False)
            if new_single_sound != self.single_sound_enabled:
                self.single_sound_enabled = new_single_sound
                settings_changed = True

            if settings_changed: self.save_settings()

    def _activate_target_window(self):
        if not AUTOMATION_AVAILABLE:
            return None, "Библиотеки автоматизации не установлены."

        if not self.automation_window_title:
            return None, "Не задан заголовок окна Softphone."

        try:
            window_title = self.automation_window_title
            target_window = next(
                (window for window in pygetwindow.getAllWindows()
                 if window_title.lower() in window.title.lower()),
                None,
            )
            if not target_window:
                return None, f"Окно с '{window_title}' не найдено."

            if not target_window.isActive:
                try:
                    target_window.minimize()
                    time.sleep(0.1)
                    target_window.restore()
                except Exception:
                    target_window.activate()
                time.sleep(1)
            return target_window, ""
        except Exception as exc:
            return None, f"Не удалось активировать Softphone: {exc}"

    def _perform_click(self):
        if not AUTOMATION_AVAILABLE:
            return False, "Библиотека автоматизации не установлена."
        if self.click_position_x is None or self.click_position_y is None:
            return False, "Не заданы координаты клика."

        try:
            pyautogui.click(self.click_position_x, self.click_position_y)
            return True, ""
        except Exception as exc:
            return False, f"Не удалось выполнить клик: {exc}"

    def _run_softphone_click(self, call_generation):
        target_window, error_message = self._activate_target_window()
        if not target_window:
            self.softphone_click_finished.emit(call_generation, False, error_message)
            return

        success, error_message = self._perform_click()
        if success:
            screen_width, screen_height = pyautogui.size()
            pyautogui.moveTo(screen_width / 2, screen_height / 2)
        self.softphone_click_finished.emit(call_generation, success, error_message)
        
    def play_sound(self, sound_file):
        if not self.sound_enabled or not SOUND_AVAILABLE:
            return
        if self.single_sound_enabled:
            sound_file = "signal.mp3"
        sound_path = resource_path(sound_file)
        if os.path.exists(sound_path):
            try: pygame.mixer.music.load(sound_path); pygame.mixer.music.play()
            except Exception as e: self.tray_icon.showMessage("Ошибка звука", f"Не удалось: {e}", QSystemTrayIcon.Warning, 3000)
        else: self.tray_icon.showMessage("Ошибка", f"Файл '{sound_file}' не найден.", QSystemTrayIcon.Warning, 3000)

    def queue_sound(self, sound_file):
        """Play a second warning after the current sound instead of interrupting it."""
        if not self.sound_enabled or not SOUND_AVAILABLE:
            return
        sound_path = resource_path(sound_file)
        if not os.path.exists(sound_path):
            return
        try:
            pygame.mixer.music.queue(sound_path)
        except Exception:
            return

    def _stop_all_timers(self):
        self.hold_timer.stop()
        self.total_timer.stop()
        self.hold_warning_blink_timer.stop()

    def handle_start_key_press(self):
        """Handle the physical Hold key: click Softphone, then switch Hold."""
        if not self.call_session.is_call_active:
            return

        if self._automation_in_progress:
            return

        self._automation_in_progress = True
        threading.Thread(
            target=self._run_softphone_click,
            args=(self._call_generation,),
            daemon=True,
        ).start()

    def on_softphone_click_finished(self, call_generation, success, error_message):
        self._automation_in_progress = False
        if call_generation != self._call_generation:
            return
        if not success:
            return

        self._toggle_hold_timer()

    def handle_hold_timer_click(self):
        """Переключает Hold только в интерфейсе, без клика Softphone."""
        self._toggle_hold_timer()

    def _toggle_hold_timer(self):
        """Применяет переключение Hold после горячей клавиши или клика по таймеру."""
        if not self.call_session.is_call_active:
            return

        action = self.call_session.press_hold_key()
        if action is CallAction.HOLD_STARTED:
            self.hold_msecs = 0
            self.hold_warning_played = False
            self.hold_limit_reached = False
            self._render_hold_time()
            self._update_hold_warning_blinking()
            self.hold_timer.start(10)
            self.play_sound('Начал.mp3')
        elif action is CallAction.HOLD_ENDED:
            self.hold_timer.stop()
            self.hold_limit_reached = False
            self._update_hold_warning_blinking()
            self.play_sound('Закончил.mp3')

    def handle_call_key_press(self):
        """Начинает звонок из простоя или завершает активный звонок."""
        action = self.call_session.press_call_key()
        self._call_generation += 1
        if action is CallAction.CALL_STARTED:
            self.hold_timer.stop()
            self.total_msecs = 0
            self.hold_msecs = 0
            self.hold_total_msecs = 0
            self.hold_warning_played = False
            self.hold_total_warning_played = False
            self.hold_limit_reached = False
            self.hold_total_limit_reached = False
            self.stopwatch_alarm_enabled = self.stopwatch_alarm_msecs > 0
            self._render_total_time()
            self._render_hold_time()
            self._render_hold_total_time()
            self._update_hold_warning_blinking()
            self.total_timer.start(10)
        else:
            self._reset_call_counters()
        self.play_sound(CALL_KEY_SOUND)

    def register_hotkeys(self):
        if not KEYBOARD_AVAILABLE: return
        keyboard.unhook_all()
        try:
            if HOLD_KEY_SCAN_CODE:
                keyboard.hook(
                    self._handle_hold_key_event,
                    suppress=True,
                )
            keyboard.hook_key(
                CALL_KEY_SCAN_CODE,
                self._handle_call_key_event,
                suppress=True,
            )
            print(
                "Горячие клавиши установлены: "
                f"Hold — {HOLD_KEY_DESCRIPTION}; звонок — {CALL_KEY_DESCRIPTION}"
            )
        except Exception as e:
            print(f"Не удалось установить горячие клавиши: {e}")
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.showMessage("Ошибка горячих клавиш", f"Неверное имя клавиши. Проверьте настройки.", QSystemTrayIcon.Warning, 4000)

    def _handle_hold_key_event(self, event):
        """Блокирует отдельный Insert, не затрагивая 0 на цифровом блоке."""
        if event.scan_code != HOLD_KEY_SCAN_CODE or event.is_keypad:
            return True
        if event.event_type == keyboard.KEY_UP:
            self.hold_key_pressed.emit()
        return False

    def _handle_call_key_event(self, event):
        """Блокирует Ё и переключает звонок при отпускании."""
        if event.event_type == keyboard.KEY_UP:
            self.call_key_pressed.emit()
        return False
    
    def global_reset(self):
        if self.call_session.is_call_active:
            self.call_session.press_call_key()
            self._call_generation += 1
        self._reset_call_counters()

    def _reset_call_counters(self):
        self._stop_all_timers()
        self.total_msecs = 0
        self.hold_msecs = 0
        self.hold_total_msecs = 0
        self.hold_warning_played = False
        self.hold_total_warning_played = False
        self.hold_limit_reached = False
        self.hold_total_limit_reached = False
        self.stopwatch_alarm_enabled = self.stopwatch_alarm_msecs > 0
        self._render_total_time()
        self._render_hold_time()
        self._render_hold_total_time()
        self._update_hold_warning_blinking()

    def update_hold_time(self):
        if self.call_session.is_hold_active:
            self.hold_msecs += self.hold_timer.interval()
            self.hold_total_msecs += self.hold_timer.interval()
            self.hold_limit_reached = (
                self.current_hold_warning_msecs > 0
                and self.hold_msecs >= self.current_hold_warning_msecs
            )
            self.hold_total_limit_reached = (
                self.total_hold_warning_msecs > 0
                and self.hold_total_msecs >= self.total_hold_warning_msecs
            )
            self._play_hold_warnings()
        self._render_hold_time()
        self._render_hold_total_time()
        self._update_hold_warning_blinking()

    def _play_hold_warnings(self):
        warning_sounds = []

        if (
            not self.hold_warning_played
            and self.current_hold_warning_msecs > 0
            and self.hold_msecs >= self.current_hold_warning_msecs
        ):
            self.hold_warning_played = True
            warning_sounds.append(CURRENT_HOLD_WARNING_SOUND)

        if (
            not self.hold_total_warning_played
            and self.total_hold_warning_msecs > 0
            and self.hold_total_msecs >= self.total_hold_warning_msecs
        ):
            self.hold_total_warning_played = True
            warning_sounds.append(TOTAL_HOLD_WARNING_SOUND)

        if not warning_sounds:
            return

        self.play_sound(warning_sounds[0])
        if len(warning_sounds) > 1:
            self.queue_sound(warning_sounds[1])

    def _update_hold_warning_blinking(self):
        should_blink = self.hold_limit_reached or self.hold_total_limit_reached
        if should_blink and not self.hold_warning_blink_timer.isActive():
            self.hold_warning_blink_visible = True
            self.hold_warning_blink_timer.start()
        elif not should_blink:
            self.hold_warning_blink_timer.stop()
            self.hold_warning_blink_visible = False
        self._apply_hold_warning_styles()

    def toggle_hold_warning_blink(self):
        self.hold_warning_blink_visible = not self.hold_warning_blink_visible
        self._apply_hold_warning_styles()

    def _apply_hold_warning_styles(self):
        current_hold_color = (
            "#ff4d4f"
            if self.hold_limit_reached and self.hold_warning_blink_visible
            else "white"
        )
        total_hold_color = (
            "#ff4d4f"
            if self.hold_total_limit_reached and self.hold_warning_blink_visible
            else "#3AE2CE"
        )
        self.timer_label.setStyleSheet(f"color: {current_hold_color};")
        self.hold_total_label.setStyleSheet(f"color: {total_hold_color};")

    def _render_hold_time(self):
        total_seconds = self.hold_msecs // 1000
        self.timer_label.setText(f"{(total_seconds // 60):02d}:{(total_seconds % 60):02d}")

    def _render_hold_total_time(self):
        total_seconds = self.hold_total_msecs // 1000
        self.hold_total_label.setText(f"{(total_seconds // 60):02d}:{(total_seconds % 60):02d}")

    def update_total_time(self):
        if self.call_session.is_call_active:
            self.total_msecs += self.total_timer.interval()
        if self.stopwatch_alarm_enabled and self.total_msecs >= self.stopwatch_alarm_msecs:
            self.play_sound('Stopwatch-sound.mp3')
            self.stopwatch_alarm_enabled = False
        self._render_total_time()

    def _render_total_time(self):
        total_seconds = self.total_msecs // 1000
        self.stopwatch_label.setText(f"{(total_seconds // 60):02d}:{(total_seconds % 60):02d}")
        
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
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    pos = settings.get('position')
                    stopwatch_alarm = settings.get('stopwatch_alarm_msecs'); click_pos = settings.get('click_position')
                    scale_mode = settings.get('scale_mode', 'normal')
                    
                    self.is_pinned = settings.get('is_pinned', False)
                    self.automation_window_title = settings.get('automation_window_title', 'Naumen SoftPhone')
                    self.sound_enabled = settings.get('sound_enabled', True)
                    self.single_sound_enabled = settings.get('single_sound_enabled', False)
                    loaded_current_hold_warning = settings.get(
                        'current_hold_warning_msecs', DEFAULT_CURRENT_HOLD_WARNING_MSECS
                    )
                    loaded_total_hold_warning = settings.get(
                        'total_hold_warning_msecs', DEFAULT_TOTAL_HOLD_WARNING_MSECS
                    )
                    if isinstance(loaded_current_hold_warning, int) and loaded_current_hold_warning >= 0:
                        self.current_hold_warning_msecs = loaded_current_hold_warning
                    if isinstance(loaded_total_hold_warning, int) and loaded_total_hold_warning >= 0:
                        self.total_hold_warning_msecs = loaded_total_hold_warning
                    
                    self.apply_scale(scale_mode)
                    if pos: self.move(QPoint(pos['x'], pos['y']))
                    if stopwatch_alarm is not None: self.stopwatch_alarm_msecs = stopwatch_alarm
                    if click_pos and click_pos.get('x') is not None: self.click_position_x, self.click_position_y = click_pos['x'], click_pos['y']
                    did_load = True
            except (json.JSONDecodeError, KeyError, TypeError) as e: print(f"Ошибка загрузки настроек: {e}")
        
        if not did_load: self.apply_scale('normal')
        
        self.update_pin_status()
        
        self.register_hotkeys()
        self._reset_call_counters()

    def save_settings(self):
        settings = {
            'position': {'x': self.pos().x(), 'y': self.pos().y()},
            'stopwatch_alarm_msecs': self.stopwatch_alarm_msecs,
            'click_position': {'x': self.click_position_x, 'y': self.click_position_y},
            'scale_mode': self.scale_mode,
            'is_pinned': self.is_pinned,
            'automation_window_title': self.automation_window_title,
            'sound_enabled': self.sound_enabled,
            'single_sound_enabled': self.single_sound_enabled,
            'current_hold_warning_msecs': self.current_hold_warning_msecs,
            'total_hold_warning_msecs': self.total_hold_warning_msecs,
        }
        with open(self.settings_file, 'w', encoding='utf-8') as f: json.dump(settings, f, ensure_ascii=False, indent=4)

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
