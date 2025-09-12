import os
from PIL import Image

ASSETS_DIR = os.path.join(os.getcwd(), "src", "assets", "slotart")

# -------------------------------
# Slots loader (vertical stack)
# -------------------------------

class SlotIcons:
    def __init__(self):
        path = os.path.join(ASSETS_DIR, "SlotsTogether.PNG")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Slot sheet not found: {path}")
        self.sheet = Image.open(path).convert("RGBA")

        # dimensions 
        self.sprite_width = 212
        self.sprite_height = 198   # 1187 / 6 ≈ 198
        self.num_icons = 6

    def get_sprite(self, index: int) -> Image.Image:
        if index < 0 or index >= self.num_icons:
            raise IndexError(f"Slot index out of range: {index}")
        x1, y1 = 0, index * self.sprite_height
        x2, y2 = x1 + self.sprite_width, y1 + self.sprite_height
        return self.sheet.crop((x1, y1, x2, y2))

def load_slots_sheet():
    return SlotIcons()