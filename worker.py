from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Callable

import mss

from constants import RETRY_DELAY_SECONDS, SCROLL_DELAY_SECONDS
from logger_config import get_logger
from matcher import find_template, grab_monitor, load_templates
from mouse import click_at, scroll_mouse


LOGGER = get_logger()


class AutoClickerWorker:
    def __init__(
        self,
        settings: dict,
        status_callback: Callable[[str], None],
        error_callback: Callable[[str], None],
        finished_callback: Callable[[], None],
    ) -> None:
        self.settings = settings
        self.status_callback = status_callback
        self.error_callback = error_callback
        self.finished_callback = finished_callback
        self.running = False

    def stop(self) -> None:
        self.running = False
        LOGGER.info("Получен запрос на остановку worker")

    def run(self) -> None:
        self.running = True

        try:
            confidence = float(self.settings["confidence"])
            min_sleep = int(self.settings["min_sleep"])
            max_sleep = int(self.settings["max_sleep"])
            templates_dir = Path(self.settings["templates_dir"]).resolve()
            grayscale = bool(self.settings["grayscale"])
            scroll_amount = int(self.settings["scroll_amount"])
            scan_all_monitors = bool(self.settings["scan_all_monitors"])

            templates = load_templates(templates_dir, grayscale)
            self.status_callback(f"Загружено шаблонов: {len(templates)}")
            LOGGER.info(
                "Worker запущен | templates_dir=%s | grayscale=%s | templates_loaded=%s",
                templates_dir,
                grayscale,
                len(templates),
            )

            with mss.mss() as sct:
                if len(sct.monitors) < 2:
                    raise RuntimeError("Не найдено ни одного доступного монитора для захвата.")

                monitors = sct.monitors[1:] if scan_all_monitors else [sct.monitors[1]]
                LOGGER.info("Мониторов для сканирования: %s", len(monitors))

                while self.running:
                    found_match = False

                    for monitor_index, monitor in enumerate(monitors, start=1):
                        if not self.running:
                            break

                        screen = grab_monitor(sct, monitor, grayscale)

                        for template_name, template_image in templates:
                            if not self.running:
                                break

                            matched, local_x, local_y, score = find_template(
                                screen,
                                template_image,
                                confidence,
                            )
                            if not matched:
                                continue

                            absolute_x = monitor["left"] + local_x
                            absolute_y = monitor["top"] + local_y

                            self.status_callback(
                                f"Найдено: {template_name} | score={score:.3f} | click=({absolute_x}, {absolute_y})"
                            )
                            LOGGER.info(
                                "Найден шаблон | name=%s | score=%.3f | monitor=%s | click=(%s, %s)",
                                template_name,
                                score,
                                monitor_index,
                                absolute_x,
                                absolute_y,
                            )

                            click_at(absolute_x, absolute_y)

                            if scroll_amount != 0:
                                time.sleep(SCROLL_DELAY_SECONDS)
                                scroll_mouse(scroll_amount)
                                LOGGER.info("Выполнен скролл: %s", scroll_amount)

                            wait_time = random.uniform(min_sleep, max_sleep)
                            self.status_callback(f"Клик по {template_name}. Жду {wait_time:.1f} сек...")
                            LOGGER.info("Пауза после клика: %.1f сек.", wait_time)
                            time.sleep(wait_time)

                            found_match = True
                            break

                        if found_match:
                            break

                    if not found_match and self.running:
                        self.status_callback("Кнопка не найдена. Повторный поиск через 1 сек...")
                        time.sleep(RETRY_DELAY_SECONDS)

        except Exception as exc:
            LOGGER.exception("Ошибка в worker: %s", exc)
            self.status_callback(f"Ошибка: {exc}")
            self.error_callback(str(exc))
        finally:
            self.running = False
            LOGGER.info("Worker завершён")
            self.finished_callback()