from .box_element import BoxElement


class LineElement(BoxElement):
    def __init__(self, x=0, y=0, width=100, height=0, thickness=2, color="B", parent=None):
        if height == 0:
            height = thickness
        super().__init__(x, y, width, height, thickness, color, 0, parent)
