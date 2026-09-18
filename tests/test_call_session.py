import unittest

from call_session import CallAction, CallSession, CallState


class CallSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = CallSession()

    def test_hold_key_is_ignored_until_call_key_starts_a_call(self):
        self.assertEqual(self.session.press_hold_key(), CallAction.IGNORED)
        self.assertEqual(self.session.state, CallState.IDLE)

    def test_call_key_starts_and_then_ends_a_call(self):
        self.assertEqual(self.session.press_call_key(), CallAction.CALL_STARTED)
        self.assertEqual(self.session.state, CallState.CALL_ACTIVE)

        self.assertEqual(self.session.press_call_key(), CallAction.CALL_ENDED)
        self.assertEqual(self.session.state, CallState.IDLE)

    def test_hold_key_cycles_hold_for_an_active_call(self):
        self.session.press_call_key()

        self.assertEqual(self.session.press_hold_key(), CallAction.HOLD_STARTED)
        self.assertTrue(self.session.is_hold_active)

        self.assertEqual(self.session.press_hold_key(), CallAction.HOLD_ENDED)
        self.assertEqual(self.session.state, CallState.CALL_ACTIVE)

        self.assertEqual(self.session.press_hold_key(), CallAction.HOLD_STARTED)
        self.assertTrue(self.session.is_hold_active)

    def test_call_key_ends_a_call_even_while_hold_is_active(self):
        self.session.press_call_key()
        self.session.press_hold_key()

        self.assertEqual(self.session.press_call_key(), CallAction.CALL_ENDED)
        self.assertEqual(self.session.state, CallState.IDLE)
        self.assertEqual(self.session.press_hold_key(), CallAction.IGNORED)


if __name__ == "__main__":
    unittest.main()
