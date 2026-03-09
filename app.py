from __future__ import annotations

import threading
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

from logger_config import get_logger
from matcher import load_templates
from settings_manager import load_settings, save_settings
from worker import AutoClickerWorker


LOGGER = get_logger()
LOGGER.info("Программа запущена")


class AutoClickerApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Nexus AutoDL (Dual Monitor)")
        self.root.resizable(False, False)

        config = load_settings()

        self.confidence_var = DoubleVar(value=float(config["confidence"]))
        self.min_sleep_var = IntVar(value=int(config["min_sleep"]))
        self.max_sleep_var = IntVar(value=int(config["max_sleep"]))
        self.templates_dir_var = StringVar(value=str(config["templates_dir"]))
        self.grayscale_var = BooleanVar(value=bool(config["grayscale"]))
        self.scroll_var = IntVar(value=int(config["scroll_amount"]))
        self.scan_all_monitors_var = BooleanVar(value=bool(config["scan_all_monitors"]))

        self.worker: AutoClickerWorker | None = None
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
            self._save_current_settings()
            LOGGER.info("Выбрана папка с шаблонами: %s", folder)

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_label.config(text=text))

    def show_error(self, text: str) -> None:
        self.root.after(0, lambda: messagebox.showerror("Ошибка", text))

    def _collect_settings(self) -> dict:
        confidence = float(str(self.confidence_var.get()).replace(",", "."))
        min_sleep = int(self.min_sleep_var.get())
        max_sleep = int(self.max_sleep_var.get())
        templates_dir = str(Path(self.templates_dir_var.get()).resolve())
        grayscale = bool(self.grayscale_var.get())
        scroll_amount = int(self.scroll_var.get())
        scan_all_monitors = bool(self.scan_all_monitors_var.get())

        if not (0 < confidence <= 1):
            raise ValueError("Confidence должен быть от 0.01 до 1.0")
        if min_sleep < 0 or max_sleep < 0:
            raise ValueError("Sleep не может быть отрицательным")
        if min_sleep > max_sleep:
            raise ValueError("Min sleep не должен быть больше Max sleep")

        return {
            "confidence": confidence,
            "min_sleep": min_sleep,
            "max_sleep": max_sleep,
            "templates_dir": templates_dir,
            "grayscale": grayscale,
            "scroll_amount": scroll_amount,
            "scan_all_monitors": scan_all_monitors,
        }

    def _save_current_settings(self) -> None:
        try:
            save_settings(self._collect_settings())
        except Exception as exc:
            LOGGER.exception("Не удалось сохранить настройки: %s", exc)
            self.set_status(f"Не удалось сохранить настройки: {exc}")

    def _on_worker_finished(self) -> None:
        self.root.after(0, self._reset_ui_after_worker)

    def _reset_ui_after_worker(self) -> None:
        self.start_button.config(text="Start")
        self.worker = None
        self.worker_thread = None

    def toggle_run(self) -> None:
        if self.worker and self.worker.running:
            self.worker.stop()
            self.start_button.config(text="Start")
            self.set_status("Остановлено")
            LOGGER.info("Работа остановлена пользователем")
            return

        try:
            settings = self._collect_settings()

            templates_dir = Path(settings["templates_dir"])
            grayscale = bool(settings["grayscale"])
            templates = load_templates(templates_dir, grayscale)

            self._save_current_settings()

            LOGGER.info(
                "Старт работы | templates_dir=%s | grayscale=%s | templates_loaded=%s",
                templates_dir,
                grayscale,
                len(templates),
            )
        except Exception as exc:
            LOGGER.exception("Ошибка перед запуском: %s", exc)
            messagebox.showerror("Ошибка", str(exc))
            return

        self.worker = AutoClickerWorker(
            settings=settings,
            status_callback=self.set_status,
            error_callback=self.show_error,
            finished_callback=self._on_worker_finished,
        )
        self.worker_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker_thread.start()

        self.start_button.config(text="Stop")

    def on_close(self) -> None:
        if self.worker and self.worker.running:
            self.worker.stop()

        self._save_current_settings()
        LOGGER.info("Программа закрыта")
        self.root.destroy()