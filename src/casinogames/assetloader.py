import os
from PIL import Image

#now that imports and loaders in subfolders we need to define the base path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ASSETS_DIR_SLOTART = os.path.join(BASE_DIR, "assets", "slotart")
ASSETS_DIR_CARDART = os.path.join(BASE_DIR, "assets", "cardart")
# -------------------------------
# Slots loader (vertical)
# -------------------------------

class SlotIcons:
    def __init__(self):
        path = os.path.join(ASSETS_DIR_SLOTART, "SlotsTogether.PNG")
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

# -------------------------------
# Memory Icons Loader
# -------------------------------
class MemoryIcons:
    def __init__(self):
        path = os.path.join(ASSETS_DIR_CARDART, "MemoryMatch.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Memory sheet not found: {path}")
        self.sheet = Image.open(path).convert("RGBA")

        # Heights
        self.card_height = 193

        # Widths
        self.full_width = 133
        self.flip_width = 67

        #  mapping of faces to grid positions (col,row)
        # col=0 always full, col=1 flip, col=2 full, col=3 flip
        self.faces = {
            "mario":    (0, 0),  
            "mushroom": (2, 0),  
            "goomba":   (4, 0),  

            "luigi":    (0, 1),  
            "flower":   (2, 1), 
            "star":     (4, 1),  

            "bowser":   (0, 2),  
            "yoshi":    (2, 2),  
            "cloud":    (4, 2), 
        }

    def _col_x(self, col_index: int) -> int:
        # Handles alternating widths (full=133, flip=67)
        if col_index % 2 == 0:  # full card
            return (col_index // 2) * (self.full_width + self.flip_width)
        else:  # flip
            return ((col_index // 2) * (self.full_width + self.flip_width)) + self.full_width

    def _crop(self, col: int, row: int, is_full: bool):
        y1 = row * self.card_height
        y2 = y1 + self.card_height
        x1 = self._col_x(col)
        if is_full:
            x2 = x1 + self.full_width
        else:
            x2 = x1 + self.flip_width
        return self.sheet.crop((x1, y1, x2, y2))

    def get_face(self, name: str):
        #Return the full card face given name
        if name not in self.faces:
            raise KeyError(f"Unknown memory face: {name}")
        col, row = self.faces[name]
        return self._crop(col, row, is_full=True)

    def get_flip(self, name: str):
        #Return the flip animation frame given name
        if name not in self.faces:
            raise KeyError(f"Unknown memory face: {name}")
        col, row = self.faces[name]
        flip_col = col + 1  # flipped is always immediately next to the face
        return self._crop(flip_col, row, is_full=False)
    
class MemoryBacks:
    def __init__(self):
        path = os.path.join(ASSETS_DIR_CARDART, "FaceDown.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"FaceDown sheet not found: {path}")
        self.sheet = Image.open(path).convert("RGBA")

        # x ranges pixel measured
        self.frames = {
            "back_full": (0,   0, 136, 207),
            "back_half": (136, 0, 210, 207),
            "back_edge": (210, 0, 240, 207),
        }

    def get(self, stage: str) -> Image.Image:
        if stage not in self.frames:
            raise KeyError(f"Unknown back stage: {stage}")
        return self.sheet.crop(self.frames[stage])

def load_memory_faces():
    return MemoryIcons()

def load_memory_backs():
    return MemoryBacks()
