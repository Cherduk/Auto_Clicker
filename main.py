from __future__ import annotations
from pathlib import Path
from tkinter import (
    BooleanVar,
    Button,
    Checkbutton,
    DoubleVar,
    Entry,
    IntVar,
    Label,
    StringVar,
    Tk,
    filedialog,
    messagebox,
)

import ctypes
import random
import threading
import time
import cv2
import mss
import numpy as np


VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
CLICK_DELAY_SECONDS = 0.03
SCROLL_DELAY_SECONDS = 0.20
RETRY_DELAY_SECONDS = 1.0

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

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


def load_templates(folder: Path, grayscale: bool) -> list[tuple[str, np.ndarray]]:
    templates = []

    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Папка не найдена: {folder}")

    files = sorted([p for p in folder.iterdir() if p.suffix.lower() in VALID_EXTENSIONS])

    if not files:
        raise FileNotFoundError("В папке templates нет изображений.")

    read_flag = cv2.IMREAD_GRAYSCALE if grayscale else cv2.IMREAD_COLOR

    for file_path in files:
        file_bytes = np.fromfile(str(file_path), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, read_flag)

        if image is not None:
            templates.append((file_path.name, image))

    if not templates:
        raise RuntimeError("Не удалось загрузить шаблоны изображений.")

    return templates


def grab_monitor(sct: mss.mss, monitor: dict[str, int], grayscale: bool) -> np.ndarray:
    screenshot = np.array(sct.grab(monitor))
    color_code = cv2.COLOR_BGRA2GRAY if grayscale else cv2.COLOR_BGRA2BGR
    return cv2.cvtColor(screenshot, color_code)


def find_template(
    haystack: np.ndarray,
    needle: np.ndarray,
    threshold: float,
) -> tuple[bool, int, int, float]:
    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    _, max_score, _, max_loc = cv2.minMaxLoc(result)

    if max_score < threshold:
        return False, 0, 0, float(max_score)

    height, width = needle.shape[:2]
    center_x = max_loc[0] + width // 2
    center_y = max_loc[1] + height // 2
    return True, center_x, center_y, float(max_score)


class AutoClickerApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Nexus AutoDL (Dual Monitor)")
        self.root.resizable(False, False)

        self.confidence_var = DoubleVar(value=0.70)
        self.min_sleep_var = IntVar(value=6)
        self.max_sleep_var = IntVar(value=9)
        self.templates_dir_var = StringVar(value="templates")
        self.grayscale_var = BooleanVar(value=True)
        self.scroll_var = IntVar(value=0)
        self.scan_all_monitors_var = BooleanVar(value=True)

        self.running = False
        self.worker_thread: threading.Thread | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        pad_x = 8
        pad_y = 6

        Label(self.root, text="Confidence:").grid(row=0, column=0, sticky="w", padx=pad_x, pady=pad_y)
        Entry(self.root, textvariable=self.confidence_var, width=12).grid(
            row=0,
            column=1,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )

        Label(self.root, text="Min sleep seconds:").grid(row=1, column=0, sticky="w", padx=pad_x, pady=pad_y)
        Entry(self.root, textvariable=self.min_sleep_var, width=12).grid(
            row=1,
            column=1,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )

        Label(self.root, text="Max sleep seconds:").grid(row=2, column=0, sticky="w", padx=pad_x, pady=pad_y)
        Entry(self.root, textvariable=self.max_sleep_var, width=12).grid(
            row=2,
            column=1,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )

        Label(self.root, text="Templates directory:").grid(row=3, column=0, sticky="w", padx=pad_x, pady=pad_y)
        Entry(self.root, textvariable=self.templates_dir_var, width=24).grid(
            row=3,
            column=1,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )
        Button(self.root, text="...", width=4, command=self.browse_templates).grid(
            row=3,
            column=2,
            padx=pad_x,
            pady=pad_y,
        )

        Checkbutton(self.root, text="Grayscale", variable=self.grayscale_var).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )

        Label(self.root, text="Scroll amount in clicks:").grid(
            row=5,
            column=0,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )
        Entry(self.root, textvariable=self.scroll_var, width=12).grid(
            row=5,
            column=1,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )
        Label(self.root, text="Negative = up, positive = down").grid(
            row=5,
            column=2,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )

        Checkbutton(self.root, text="Scan all monitors", variable=self.scan_all_monitors_var).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="w",
            padx=pad_x,
            pady=pad_y,
        )

        self.start_button = Button(self.root, text="Start", width=12, command=self.toggle_run)
        self.start_button.grid(row=7, column=1, pady=12)

        self.status_label = Label(self.root, text="Готов", anchor="w")
        self.status_label.grid(row=8, column=0, columnspan=3, sticky="w", padx=pad_x, pady=(0, 10))

    def browse_templates(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.templates_dir_var.get() or ".")
        if folder:
            self.templates_dir_var.set(folder)

    def set_status(self, text: str) -> None:
        self.root.after(0, self.status_label.config, {"text": text})

    def _get_settings(self) -> tuple[float, int, int, Path, bool, int, bool]:
        confidence = float(str(self.confidence_var.get()).replace(",", "."))
        min_sleep = int(self.min_sleep_var.get())
        max_sleep = int(self.max_sleep_var.get())
        templates_dir = Path(self.templates_dir_var.get()).resolve()
        grayscale = self.grayscale_var.get()
        scroll_amount = int(self.scroll_var.get())
        scan_all_monitors = self.scan_all_monitors_var.get()

        if not (0 < confidence <= 1):
            raise ValueError("Confidence должен быть от 0.01 до 1.0")
        if min_sleep < 0 or max_sleep < 0:
            raise ValueError("Sleep не может быть отрицательным")
        if min_sleep > max_sleep:
            raise ValueError("Min sleep не должен быть больше Max sleep")

        return (
            confidence,
            min_sleep,
            max_sleep,
            templates_dir,
            grayscale,
            scroll_amount,
            scan_all_monitors,
        )

    def toggle_run(self) -> None:
        if self.running:
            self.running = False
            self.start_button.config(text="Start")
            self.set_status("Остановлено")
            return

        try:
            _, _, _, templates_dir, grayscale, _, _ = self._get_settings()
            load_templates(templates_dir, grayscale)
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))
            return

        self.running = True
        self.start_button.config(text="Stop")
        self.worker_thread = threading.Thread(target=self.run_loop, daemon=True)
        self.worker_thread.start()

    def run_loop(self) -> None:
        try:
            (
                confidence,
                min_sleep,
                max_sleep,
                templates_dir,
                grayscale,
                scroll_amount,
                scan_all_monitors,
            ) = self._get_settings()

            templates = load_templates(templates_dir, grayscale)
            self.set_status(f"Загружено шаблонов: {len(templates)}")

            with mss.mss() as sct:
                monitors = [sct.monitors[0]] if scan_all_monitors else [sct.monitors[1]]

                while self.running:
                    found_match = False

                    for monitor in monitors:
                        if not self.running:
                            break

                        screen = grab_monitor(sct, monitor, grayscale)

                        for template_name, template_image in templates:
                            matched, local_x, local_y, score = find_template(screen, template_image, confidence)
                            if not matched:
                                continue

                            absolute_x = monitor["left"] + local_x
                            absolute_y = monitor["top"] + local_y

                            self.set_status(
                                f"Найдено: {template_name} | score={score:.3f} | click=({absolute_x}, {absolute_y})"
                            )
                            click_at(absolute_x, absolute_y)

                            if scroll_amount != 0:
                                time.sleep(SCROLL_DELAY_SECONDS)
                                scroll_mouse(scroll_amount)

                            wait_time = random.uniform(min_sleep, max_sleep)
                            self.set_status(f"Клик по {template_name}. Жду {wait_time:.1f} сек...")
                            time.sleep(wait_time)

                            found_match = True
                            break

                        if found_match:
                            break

                    if not found_match:
                        self.set_status("Кнопка не найдена. Повторный поиск через 1 сек...")
                        time.sleep(RETRY_DELAY_SECONDS)

        except Exception as exc:
            self.set_status(f"Ошибка: {exc}")
            messagebox.showerror("Ошибка в работе", str(exc))
        finally:
            self.running = False
            self.root.after(0, self.start_button.config, {"text": "Start"})

    def on_close(self) -> None:
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    app_root = Tk()
    app = AutoClickerApp(app_root)
    app_root.mainloop()