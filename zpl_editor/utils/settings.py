from PyQt6.QtCore import QSettings

DEFAULT_TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class AppSettings:
    def __init__(self):
        self._settings = QSettings("ZPLEditor", "ZPLEditor")

    def get(self, key: str, default=None):
        return self._settings.value(key, default)

    def set(self, key: str, value):
        self._settings.setValue(key, value)

    @property
    def last_file(self) -> str:
        return self._settings.value("lastFile", "")

    @last_file.setter
    def last_file(self, path: str):
        self._settings.setValue("lastFile", path)

    @property
    def dpi(self) -> int:
        return int(self._settings.value("dpi", 203))

    @dpi.setter
    def dpi(self, value: int):
        self._settings.setValue("dpi", value)

    @property
    def dark_theme(self) -> bool:
        return self._settings.value("darkTheme", True, type=bool)

    @dark_theme.setter
    def dark_theme(self, value: bool):
        self._settings.setValue("darkTheme", value)

    @property
    def tesseract_path(self) -> str:
        return self._settings.value("tesseractPath", DEFAULT_TESSERACT_PATH)

    @tesseract_path.setter
    def tesseract_path(self, path: str):
        self._settings.setValue("tesseractPath", path)
