from dataclasses import dataclass, field
from typing import List
from .zpl_commands import ZPLElement, LabelSettings


@dataclass
class LabelModel:
    settings: LabelSettings = field(default_factory=LabelSettings)
    elements: List[ZPLElement] = field(default_factory=list)

    def clear(self):
        self.elements.clear()

    def add_element(self, element: ZPLElement):
        self.elements.append(element)

    def remove_element(self, element: ZPLElement):
        if element in self.elements:
            self.elements.remove(element)
