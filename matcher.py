from pathlib import Path

import cv2
import mss
import numpy as np

from constants import VALID_EXTENSIONS


def load_templates(folder: Path, grayscale: bool) -> list[tuple[str, np.ndarray]]:
    templates: list[tuple[str, np.ndarray]] = []

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