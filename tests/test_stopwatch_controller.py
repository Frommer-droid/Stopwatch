import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from call_session import CallState


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_stopwatch_module():
    loader = importlib.machinery.SourceFileLoader(
        "stopwatch_test_module", str(PROJECT_ROOT / "Stopwatch.pyw")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class StopwatchControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.module = load_stopwatch_module()
        cls.module.SOUND_AVAILABLE = False
        cls.module.keyboard.unhook_all = lambda: None
        cls.key_hook_registrations = []
        cls.global_hook_registrations = []
        cls.module.keyboard.hook_key = (
            lambda *args, **kwargs: cls.key_hook_registrations.append((args, kwargs))
        )
        cls.module.keyboard.hook = (
            lambda *args, **kwargs: cls.global_hook_registrations.append((args, kwargs))
        )

    def setUp(self):
        self.key_hook_registrations.clear()
        self.global_hook_registrations.clear()
        self.window = self.module.Stopwatch()
        # Изолировать пороги Hold от локального settings.json.
        self.window.current_hold_warning_msecs = (
            self.module.DEFAULT_CURRENT_HOLD_WARNING_MSECS
        )
        self.window.total_hold_warning_msecs = (
            self.module.DEFAULT_TOTAL_HOLD_WARNING_MSECS
        )
        self.played_sounds = []
        self.queued_sounds = []
        self.window.play_sound = self.played_sounds.append
        self.window.queue_sound = self.queued_sounds.append

    def tearDown(self):
        self.window._stop_all_timers()
        self.window.tray_icon.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def test_call_and_hold_keys_drive_the_counters(self):
        self.window.handle_start_key_press()
        self.assertEqual(self.window.call_session.state, CallState.IDLE)

        self.window.handle_call_key_press()
        self.assertEqual(self.window.call_session.state, CallState.CALL_ACTIVE)
        self.assertTrue(self.window.total_timer.isActive())
        self.assertFalse(self.window.hold_timer.isActive())

        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.assertEqual(self.window.call_session.state, CallState.HOLD_ACTIVE)
        self.assertTrue(self.window.hold_timer.isActive())
        self.assertTrue(self.window.total_timer.isActive())

        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.assertEqual(self.window.call_session.state, CallState.CALL_ACTIVE)
        self.assertFalse(self.window.hold_timer.isActive())
        self.assertTrue(self.window.total_timer.isActive())

        self.window.handle_call_key_press()
        self.assertEqual(self.window.call_session.state, CallState.IDLE)
        self.assertFalse(self.window.hold_timer.isActive())
        self.assertFalse(self.window.total_timer.isActive())
        self.assertEqual(self.window.timer_label.text(), "00:00")
        self.assertEqual(self.window.stopwatch_label.text(), "00:00")

    def test_each_call_key_press_plays_the_current_hold_warning_sound(self):
        self.window.handle_call_key_press()
        self.assertEqual(
            self.played_sounds,
            [self.module.CURRENT_HOLD_WARNING_SOUND],
        )
        self.assertEqual(
            self.module.CALL_KEY_SOUND,
            self.module.CURRENT_HOLD_WARNING_SOUND,
        )

        self.window.handle_call_key_press()
        self.assertEqual(
            self.played_sounds,
            [
                self.module.CURRENT_HOLD_WARNING_SOUND,
                self.module.CURRENT_HOLD_WARNING_SOUND,
            ],
        )

    def test_total_hold_warning_threshold_is_three_minutes_forty_seconds(self):
        self.assertEqual(self.module.TOTAL_HOLD_WARNING_MSECS, 3 * 60_000 + 40_000)

    def test_hold_warning_duration_parser_supports_disabled_and_custom_thresholds(self):
        self.assertEqual(self.module.parse_duration_msecs("00:00"), 0)
        self.assertEqual(self.module.parse_duration_msecs("03:30"), 210_000)
        self.assertIsNone(self.module.parse_duration_msecs("3:60"))
        self.assertIsNone(self.module.parse_duration_msecs("three minutes"))

    def test_settings_dialog_exposes_independent_hold_warning_thresholds(self):
        dialog = self.module.SettingsDialog()
        self.assertEqual(
            dialog.get_values()["current_hold_warning"],
            self.module.format_duration_msecs(self.module.DEFAULT_CURRENT_HOLD_WARNING_MSECS),
        )
        self.assertEqual(
            dialog.get_values()["total_hold_warning"],
            self.module.format_duration_msecs(self.module.DEFAULT_TOTAL_HOLD_WARNING_MSECS),
        )

        dialog.set_values({
            "alarm": "00:00",
            "current_hold_warning": "02:15",
            "total_hold_warning": "00:00",
        })
        self.assertEqual(dialog.get_values()["current_hold_warning"], "02:15")
        self.assertEqual(dialog.get_values()["total_hold_warning"], "00:00")
        dialog.deleteLater()

    def test_hold_warning_thresholds_are_persisted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.window.settings_file = str(Path(temporary_directory) / "settings.json")
            self.window.current_hold_warning_msecs = 135_000
            self.window.total_hold_warning_msecs = 0
            self.window.save_settings()

            with open(self.window.settings_file, encoding="utf-8") as settings_file:
                saved_settings = json.load(settings_file)

        self.assertEqual(saved_settings["current_hold_warning_msecs"], 135_000)
        self.assertEqual(saved_settings["total_hold_warning_msecs"], 0)

    def test_yo_uses_scan_code_41_and_suppresses_text_input_for_the_call(self):
        call_registration = next(
            registration
            for registration in self.key_hook_registrations
            if registration[0][0] == self.module.CALL_KEY_SCAN_CODE
        )
        self.assertEqual(self.module.CALL_KEY_SCAN_CODE, 41)
        self.assertEqual(call_registration[0][0], self.module.CALL_KEY_SCAN_CODE)
        self.assertTrue(call_registration[1]["suppress"])
        call_handler = call_registration[0][1]
        emitted = []
        self.window.call_key_pressed.connect(lambda: emitted.append(True))
        key_down = SimpleNamespace(event_type=self.module.keyboard.KEY_DOWN)
        key_up = SimpleNamespace(event_type=self.module.keyboard.KEY_UP)
        self.assertFalse(call_handler(key_down))
        self.assertFalse(call_handler(key_down))
        self.assertEqual(emitted, [])
        self.assertFalse(call_handler(key_up))
        self.assertEqual(emitted, [True])
        self.assertFalse(call_handler(key_down))
        self.assertEqual(emitted, [True])
        self.assertFalse(call_handler(key_up))
        self.assertEqual(emitted, [True, True])
        self.assertFalse(
            any(registration[0][0] == "f8" for registration in self.key_hook_registrations)
        )
        self.assertFalse(
            any(registration[0][0] == 56 for registration in self.key_hook_registrations)
        )

    def test_insert_key_uses_scan_code_82_and_suppresses_text_input_for_hold(self):
        hold_registration = next(
            registration
            for registration in self.global_hook_registrations
            if registration[1].get("suppress")
        )
        self.assertEqual(self.module.HOLD_KEY_SCAN_CODE, 82)
        self.assertTrue(hold_registration[1]["suppress"])
        hold_handler = hold_registration[0][0]
        emitted = []
        self.window.hold_key_pressed.connect(lambda: emitted.append(True))
        key_down = SimpleNamespace(
            event_type=self.module.keyboard.KEY_DOWN,
            scan_code=self.module.HOLD_KEY_SCAN_CODE,
            is_keypad=False,
        )
        key_up = SimpleNamespace(
            event_type=self.module.keyboard.KEY_UP,
            scan_code=self.module.HOLD_KEY_SCAN_CODE,
            is_keypad=False,
        )
        self.assertFalse(hold_handler(key_down))
        self.assertFalse(hold_handler(key_down))
        self.assertEqual(emitted, [])
        self.assertFalse(hold_handler(key_up))
        self.assertEqual(emitted, [True])
        self.assertFalse(hold_handler(key_down))
        self.assertEqual(emitted, [True])
        self.assertFalse(hold_handler(key_up))
        self.assertEqual(emitted, [True, True])

    def test_numpad_zero_is_not_treated_as_insert(self):
        hold_registration = next(
            registration
            for registration in self.global_hook_registrations
            if registration[1].get("suppress")
        )
        hold_handler = hold_registration[0][0]
        emitted = []
        self.window.hold_key_pressed.connect(lambda: emitted.append(True))

        for event_type in (self.module.keyboard.KEY_DOWN, self.module.keyboard.KEY_UP):
            event = SimpleNamespace(
                event_type=event_type,
                scan_code=self.module.HOLD_KEY_SCAN_CODE,
                is_keypad=True,
            )
            self.assertTrue(hold_handler(event))

        self.assertEqual(emitted, [])

    def test_hold_hook_passes_unrelated_keys_through(self):
        hold_registration = next(
            registration
            for registration in self.global_hook_registrations
            if registration[1].get("suppress")
        )
        hold_handler = hold_registration[0][0]
        event = SimpleNamespace(
            event_type=self.module.keyboard.KEY_UP,
            scan_code=30,
            is_keypad=False,
        )

        self.assertTrue(hold_handler(event))

    def test_window_is_compact_with_minimal_outer_margins(self):
        self.window.apply_scale("normal")

        margins = self.window.centralWidget().layout().contentsMargins()
        self.assertEqual(self.module.Stopwatch.BASE_WIDTH, 350)
        self.assertEqual(self.window.width(), 350)
        self.assertEqual(
            (margins.left(), margins.top(), margins.right(), margins.bottom()),
            (1, 1, 0, 1),
        )

    def test_mouse_clicks_toggle_timers_and_right_click_resets_all(self):
        self.assertFalse(self.window.timer_label._wait_for_double_click)
        self.assertTrue(self.window.stopwatch_label._wait_for_double_click)

        self.window.stopwatch_label.clicked.emit()
        self.assertEqual(self.window.call_session.state, CallState.CALL_ACTIVE)
        self.window._run_softphone_click = lambda _generation: self.fail(
            "Клик по Hold-таймеру не должен обращаться к Softphone"
        )
        self.window.timer_label.clicked.emit()
        self.assertEqual(self.window.call_session.state, CallState.HOLD_ACTIVE)
        self.assertFalse(self.window._automation_in_progress)

        self.window.timer_label.rightClicked.emit()
        self.assertEqual(self.window.call_session.state, CallState.IDLE)
        self.assertEqual(self.window.timer_label.text(), "00:00")
        self.assertEqual(self.window.hold_total_label.text(), "00:00")
        self.assertEqual(self.window.stopwatch_label.text(), "00:00")

    def test_settings_do_not_offer_hotkey_configuration(self):
        dialog = self.module.SettingsDialog()
        self.assertFalse(hasattr(dialog, "hotkey_reset_edit"))
        self.assertNotIn("hotkeys", dialog.get_values())
        dialog.deleteLater()

    def test_settings_dialog_exposes_sound_mute_option(self):
        dialog = self.module.SettingsDialog()
        self.assertTrue(dialog.sound_checkbox.isChecked())
        self.assertTrue(dialog.get_values()["sound_enabled"])
        dialog.sound_checkbox.setChecked(False)
        self.assertFalse(dialog.get_values()["sound_enabled"])
        dialog.set_values({"alarm": "00:00", "sound_enabled": False})
        self.assertFalse(dialog.sound_checkbox.isChecked())
        dialog.deleteLater()

    def test_muted_window_skips_sound_playback_and_queue(self):
        self.module.SOUND_AVAILABLE = True
        self.addCleanup(setattr, self.module, "SOUND_AVAILABLE", False)
        messages = []
        self.window.tray_icon.showMessage = (
            lambda *args, **kwargs: messages.append(args)
        )

        self.window.sound_enabled = False
        self.module.Stopwatch.play_sound(self.window, "no-such-file.mp3")
        self.module.Stopwatch.queue_sound(self.window, "no-such-file.mp3")
        self.assertEqual(messages, [])

        self.window.sound_enabled = True
        self.module.Stopwatch.play_sound(self.window, "no-such-file.mp3")
        self.assertEqual(len(messages), 1)

    def test_late_softphone_click_cannot_toggle_a_new_call(self):
        self.window.handle_call_key_press()
        original_generation = self.window._call_generation

        self.window.handle_call_key_press()
        self.window.handle_call_key_press()
        self.window.on_softphone_click_finished(original_generation, True, "")

        self.assertEqual(self.window.call_session.state, CallState.CALL_ACTIVE)
        self.assertTrue(self.window.total_timer.isActive())
        self.assertFalse(self.window.hold_timer.isActive())

    def test_middle_counter_accumulates_all_hold_intervals(self):
        self.window.handle_call_key_press()

        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        for _ in range(100):
            self.window.update_hold_time()
        self.assertEqual(self.window.hold_msecs, 1_000)
        self.assertEqual(self.window.hold_total_msecs, 1_000)

        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.assertEqual(self.window.hold_msecs, 0)
        self.assertEqual(self.window.hold_total_msecs, 1_000)

        for _ in range(50):
            self.window.update_hold_time()
        self.assertEqual(self.window.hold_msecs, 500)
        self.assertEqual(self.window.hold_total_msecs, 1_500)

        self.window.handle_call_key_press()
        self.assertEqual(self.window.hold_msecs, 0)
        self.assertEqual(self.window.hold_total_msecs, 0)
        self.assertEqual(self.window.hold_total_label.text(), "00:00")

    def test_hold_warnings_play_once_and_reset_with_call_key(self):
        self.window.handle_call_key_press()
        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.played_sounds.clear()

        self.window.hold_msecs = self.module.CURRENT_HOLD_WARNING_MSECS - 10
        self.window.update_hold_time()
        self.assertEqual(
            self.played_sounds,
            [self.module.CURRENT_HOLD_WARNING_SOUND],
        )
        self.assertTrue(self.window.hold_warning_played)

        self.window.update_hold_time()
        self.assertEqual(len(self.played_sounds), 1)

        self.window.hold_total_msecs = self.module.TOTAL_HOLD_WARNING_MSECS - 10
        self.window.update_hold_time()
        self.assertEqual(
            self.played_sounds[-1],
            self.module.TOTAL_HOLD_WARNING_SOUND,
        )
        self.assertTrue(self.window.hold_total_warning_played)

        self.window.handle_call_key_press()
        self.assertFalse(self.window.hold_warning_played)
        self.assertFalse(self.window.hold_total_warning_played)

    def test_disabled_hold_warning_thresholds_do_not_play_or_blink(self):
        self.window.current_hold_warning_msecs = 0
        self.window.total_hold_warning_msecs = 0
        self.window.handle_call_key_press()
        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.played_sounds.clear()

        self.window.hold_msecs = 60_000
        self.window.hold_total_msecs = 60_000
        self.window.update_hold_time()

        self.assertEqual(self.played_sounds, [])
        self.assertFalse(self.window.hold_limit_reached)
        self.assertFalse(self.window.hold_total_limit_reached)
        self.assertFalse(self.window.hold_warning_blink_timer.isActive())

    def test_simultaneous_hold_warnings_are_queued(self):
        self.window.handle_call_key_press()
        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.played_sounds.clear()

        self.window.hold_msecs = self.module.CURRENT_HOLD_WARNING_MSECS - 10
        self.window.hold_total_msecs = self.module.TOTAL_HOLD_WARNING_MSECS - 10
        self.window.update_hold_time()

        self.assertEqual(
            self.played_sounds,
            [self.module.CURRENT_HOLD_WARNING_SOUND],
        )
        self.assertEqual(
            self.queued_sounds,
            [self.module.TOTAL_HOLD_WARNING_SOUND],
        )

    def test_hold_limit_blinks_and_resets_without_call_notifications(self):
        self.window.handle_call_key_press()
        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )

        self.window.hold_msecs = self.module.CURRENT_HOLD_WARNING_MSECS - 10
        self.window.update_hold_time()
        self.assertTrue(self.window.hold_limit_reached)
        self.assertTrue(self.window.hold_warning_blink_timer.isActive())
        self.assertEqual(self.window.timer_label.styleSheet(), "color: #ff4d4f;")

        self.window.toggle_hold_warning_blink()
        self.assertEqual(self.window.timer_label.styleSheet(), "color: white;")

        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.assertFalse(self.window.hold_limit_reached)
        self.assertEqual(self.window.timer_label.styleSheet(), "color: white;")

        self.window.on_softphone_click_finished(
            self.window._call_generation, True, ""
        )
        self.window.hold_total_msecs = self.module.TOTAL_HOLD_WARNING_MSECS - 10
        self.window.update_hold_time()
        self.assertTrue(self.window.hold_total_limit_reached)
        self.assertEqual(
            self.window.hold_total_label.styleSheet(), "color: #ff4d4f;"
        )

        self.window.handle_call_key_press()
        self.assertFalse(self.window.hold_limit_reached)
        self.assertFalse(self.window.hold_total_limit_reached)
        self.assertFalse(self.window.hold_warning_blink_timer.isActive())
        self.assertEqual(self.window.timer_label.styleSheet(), "color: white;")
        self.assertEqual(self.window.hold_total_label.styleSheet(), "color: #3AE2CE;")


if __name__ == "__main__":
    unittest.main()
