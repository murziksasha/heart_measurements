"""Minimal dict-based i18n. Ukrainian is the default language."""

from __future__ import annotations

DEFAULT = "uk"
LANGUAGES = {"uk": "Українська", "en": "English"}

_T = {
    "app_title": ("ECG — ER1", "ECG — ER1"),
    "patients": ("Пацієнти", "Patients"),
    "recordings": ("Записи", "Recordings"),
    "add": ("Додати", "Add"),
    "edit": ("Змінити", "Edit"),
    "delete": ("Видалити", "Delete"),
    "file": ("Файл", "File"),
    "import_ecg": ("Імпорт ЕКГ…", "Import ECG…"),
    "migrate_vendor": ("Перенести дані старої програми…", "Migrate vendor data…"),
    "devices": ("Пристрої…", "Devices…"),
    "language": ("Мова", "Language"),
    "quit": ("Вихід", "Quit"),
    "name": ("Ім'я", "Name"),
    "gender": ("Стать", "Gender"),
    "male": ("Чоловіча", "Male"),
    "female": ("Жіноча", "Female"),
    "unknown": ("Не вказано", "Not set"),
    "birthday": ("Дата народження", "Birthday"),
    "height": ("Зріст, см", "Height, cm"),
    "weight": ("Вага, кг", "Weight, kg"),
    "contact": ("Контакт", "Contact"),
    "patient": ("Пацієнт", "Patient"),
    "confirm_delete_patient": ("Видалити пацієнта «{}»? Його записи та звіти буде переміщено до ecg_data/trash.",
                               "Delete patient “{}”? Recordings and reports will be moved to ecg_data/trash."),
    "true_proportions": ("Справжні пропорції", "True proportions"),
    "start_time": ("Початок", "Start"),
    "duration": ("Тривалість", "Duration"),
    "device": ("Пристрій", "Device"),
    "analysis": ("Аналіз", "Analysis"),
    "status_none": ("—", "—"),
    "status_cloud": ("Хмара", "Cloud"),
    "status_local": ("Локальний", "Local"),
    "viewer": ("ЕКГ", "ECG"),
    "report": ("Звіт", "Report"),
    "report_placeholder": ("Перегляд звітів буде додано на кроці 4.", "Report viewing comes in step 4."),
    "report_files": ("Файли звіту: {}", "Report files: {}"),
    "paper_grid": ("Сітка 25 мм/с, 10 мм/мВ", "Paper grid 25 mm/s, 10 mm/mV"),
    "time_s": ("Час, с", "Time, s"),
    "mv": ("мВ", "mV"),
    "no_recording": ("Оберіть запис", "Select a recording"),
    "serial": ("Серійний номер", "Serial"),
    "model": ("Модель", "Model"),
    "bind": ("Прив'язати", "Bind"),
    "unbind": ("Відв'язати", "Unbind"),
    "serial_prompt": ("Серійний номер ER1:", "ER1 serial number:"),
    "close": ("Закрити", "Close"),
    "folder": ("Папка…", "Folder…"),
    "detect_usb": ("Знайти ER1 (USB)", "Detect ER1 (USB)"),
    "import": ("Імпортувати", "Import"),
    "cancel": ("Скасувати", "Cancel"),
    "files_found": ("Знайдено файлів: {}", "Files found: {}"),
    "no_drive": ("ER1 не знайдено", "No ER1 drive found"),
    "import_done": ("Імпортовано: {}, пропущено: {}, помилок: {}", "Imported: {}, skipped: {}, errors: {}"),
    "select_patient_first": ("Спочатку оберіть пацієнта", "Select a patient first"),
    "vendor_folder": ("Папка Data старої програми", "Vendor Data folder"),
    "merge_subusers": ("Об'єднати користувачів (напр. 2=1)", "Merge subusers (e.g. 2=1)"),
    "dry_run": ("Пробний запуск", "Dry run"),
    "run": ("Запустити", "Run"),
    "restart_hint": ("Мову буде змінено після перезапуску.", "Language changes after restart."),
    "error": ("Помилка", "Error"),
    "delete_failed": ("Не вдалося перемістити файл до кошика (він відкритий в іншій програмі?):\n{}\nПацієнта не видалено.",
                      "Could not move a file to trash (open in another program?):\n{}\nThe patient was not deleted."),
    "no_results": ("Для цього запису ще немає результатів аналізу.", "No analysis results for this recording yet."),
    "result_header": ("Джерело: {} · звіт від {}", "Source: {} · report of {}"),
    "source_cloud": ("Хмара Viatom AI", "Viatom cloud AI"),
    "source_local": ("Локальний аналіз (не діагностичний)", "Local analysis (non-diagnostic)"),
    "summary": ("Підсумок", "Summary"),
    "diagnoses": ("Висновки", "Findings"),
    "events": ("Події", "Events"),
    "event_type": ("Тип", "Type"),
    "event_time": ("Час", "Time"),
    "hr": ("ЧСС", "HR"),
    "all_types": ("Усі типи", "All types"),
    "open_pdf": ("Відкрити PDF", "Open PDF"),
    "pdf_tab": ("PDF", "PDF"),
    "no_pdf": ("PDF недоступний", "No PDF"),
    "avg_hr": ("Середня ЧСС", "Average HR"),
    "max_hr": ("Макс. ЧСС", "Max HR"),
    "min_hr": ("Мін. ЧСС", "Min HR"),
    "beats": ("Кількість ударів", "Beats"),
    "analysed": ("Проаналізовано", "Analysed"),
    "bpm": ("уд/хв", "bpm"),
    "result_n": ("Результат {}", "Result {}"),
    "jump_hint": ("Подвійний клік — перейти до події на ЕКГ", "Double-click to jump to the event on the ECG"),
}

_lang = DEFAULT


def resolve_language(value) -> str:
    """Accepts 'uk'/'en'; legacy vendor ints are unmapped -> default."""
    return value if value in LANGUAGES else DEFAULT


def set_language(lang) -> None:
    global _lang
    _lang = resolve_language(lang)


def language() -> str:
    return _lang


def tr(key: str, *args) -> str:
    pair = _T.get(key)
    s = key if pair is None else pair[0 if _lang == "uk" else 1]
    return s.format(*args) if args else s
