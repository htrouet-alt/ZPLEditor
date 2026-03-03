from PyQt6.QtWidgets import QApplication
from ..elements.base_element import BaseElement
from ..core.zpl_commands import ZPLElement


class ClipboardManager:
    def __init__(self):
        self._copied_elements: list[ZPLElement] = []

    def copy(self, elements: list[BaseElement]):
        self._copied_elements = [elem.get_zpl_element() for elem in elements]

    def paste(self, offset_x=20, offset_y=20) -> list[ZPLElement]:
        result = []
        for elem in self._copied_elements:
            new_elem = ZPLElement(
                element_type=elem.element_type,
                x=elem.x + offset_x,
                y=elem.y + offset_y,
                properties=dict(elem.properties),
            )
            result.append(new_elem)
        return result

    def has_content(self) -> bool:
        return len(self._copied_elements) > 0

    def copy_zpl_to_clipboard(self, zpl_code: str):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(zpl_code)
