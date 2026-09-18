"""State machine for a call and its Hold intervals."""

from enum import Enum, auto


class CallState(Enum):
    IDLE = auto()
    CALL_ACTIVE = auto()
    HOLD_ACTIVE = auto()


class CallAction(Enum):
    CALL_STARTED = auto()
    CALL_ENDED = auto()
    HOLD_STARTED = auto()
    HOLD_ENDED = auto()
    IGNORED = auto()


class CallSession:
    """Encapsulate call and Hold state transitions independently of the GUI."""

    def __init__(self):
        self.state = CallState.IDLE

    @property
    def is_call_active(self) -> bool:
        return self.state is not CallState.IDLE

    @property
    def is_hold_active(self) -> bool:
        return self.state is CallState.HOLD_ACTIVE

    def press_call_key(self) -> CallAction:
        if self.state is CallState.IDLE:
            self.state = CallState.CALL_ACTIVE
            return CallAction.CALL_STARTED

        self.state = CallState.IDLE
        return CallAction.CALL_ENDED

    def press_hold_key(self) -> CallAction:
        if self.state is CallState.IDLE:
            return CallAction.IGNORED

        if self.state is CallState.CALL_ACTIVE:
            self.state = CallState.HOLD_ACTIVE
            return CallAction.HOLD_STARTED

        self.state = CallState.CALL_ACTIVE
        return CallAction.HOLD_ENDED
