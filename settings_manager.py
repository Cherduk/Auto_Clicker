import json
from pathlib import Path

from logger_config import BASE_DIR, get_logger


LOGGER = get_logger()

CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_SETTINGS = {
    "confidence": 0.70,
    "min_sleep": 6,
    "max_sleep": 9,
    "templates_dir": "templates",
    "grayscale": True,
    "scroll_amount": 0,
    "scan_all_monitors": True,
}


def load_settings() -> dict:
    if not CONFIG_FILE.exists():
        LOGGER.info("Файл config.json не найден, используются настройки по умолчанию")
        return DEFAULT_SETTINGS.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        config = DEFAULT_SETTINGS.copy()
        config.update(data)
        LOGGER.info("Настройки загружены из %s", CONFIG_FILE)
        return config
    except Exception as exc:
        LOGGER.exception("Ошибка загрузки настроек: %s", exc)
        return DEFAULT_SETTINGS.copy()


def save_settings(data: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    LOGGER.info("Настройки сохранены в %s", CONFIG_FILE)
