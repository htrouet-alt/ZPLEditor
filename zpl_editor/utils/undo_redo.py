from PyQt6.QtGui import QUndoCommand, QUndoStack


class MoveCommand(QUndoCommand):
    def __init__(self, element, old_x, old_y, new_x, new_y, description="Move Element"):
        super().__init__(description)
        self._element = element
        self._old_x = old_x
        self._old_y = old_y
        self._new_x = new_x
        self._new_y = new_y

    def redo(self):
        self._element.dot_x = self._new_x
        self._element.dot_y = self._new_y

    def undo(self):
        self._element.dot_x = self._old_x
        self._element.dot_y = self._old_y


class ResizeCommand(QUndoCommand):
    def __init__(self, element, old_w, old_h, new_w, new_h, description="Resize Element"):
        super().__init__(description)
        self._element = element
        self._old_w = old_w
        self._old_h = old_h
        self._new_w = new_w
        self._new_h = new_h

    def redo(self):
        self._element.dot_width = self._new_w
        self._element.dot_height = self._new_h

    def undo(self):
        self._element.dot_width = self._old_w
        self._element.dot_height = self._old_h


class PropertyCommand(QUndoCommand):
    def __init__(self, element, prop_name, old_value, new_value, description="Change Property"):
        super().__init__(description)
        self._element = element
        self._prop_name = prop_name
        self._old_value = old_value
        self._new_value = new_value

    def redo(self):
        self._element._properties[self._prop_name] = self._new_value
        self._element.update()

    def undo(self):
        self._element._properties[self._prop_name] = self._old_value
        self._element.update()
