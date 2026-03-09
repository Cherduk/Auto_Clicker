import ctypes
import time

from constants import (
    CLICK_DELAY_SECONDS,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_WHEEL,
    WHEEL_DELTA,
)

USER32 = ctypes.windll.user32


def click_at(x: int, y: int) -> None:
    USER32.SetCursorPos(int(x), int(y))
    time.sleep(CLICK_DELAY_SECONDS)
    USER32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(CLICK_DELAY_SECONDS)
    USER32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def scroll_mouse(amount: int) -> None:
    if amount == 0:
        return

    delta = -amount * WHEEL_DELTA
    USER32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)