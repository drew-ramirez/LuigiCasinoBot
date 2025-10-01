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

       
        # Columns (x):
        self.x0 = 7
        self.full_w = 231  
        self.flip_w = 121  
        self.pair_stride = self.full_w + self.flip_w  

        # Rows (y): 
        self.row_tops = [0, 342, 690]
        self.row_heights = [342, 690 - 342, 1037 - 690]

        # mapping of faces to grid positions (col,row)
        # even cols are full, odd cols are flip
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
        # even col: full 
        # odd col: flip immediately after the full
        base = self.x0 + (col_index // 2) * self.pair_stride
        return base + (self.full_w if (col_index % 2 == 1) else 0)

    def _crop(self, col: int, row: int, is_full: bool) -> Image.Image:
        y1 = self.row_tops[row]
        y2 = y1 + self.row_heights[row]
        x1 = self._col_x(col)
        x2 = x1 + (self.full_w if is_full else self.flip_w)
        return self.sheet.crop((x1, y1, x2, y2))

    def get_face(self, name: str) -> Image.Image:
        if name not in self.faces:
            raise KeyError(f"Unknown memory face: {name}")
        col, row = self.faces[name]
        return self._crop(col, row, is_full=True)

    def get_flip(self, name: str) -> Image.Image:
        if name not in self.faces:
            raise KeyError(f"Unknown memory face: {name}")
        col, row = self.faces[name]
        return self._crop(col + 1, row, is_full=False)  # flip is right next to full
    
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

def _recolor_to_silver(img: Image.Image) -> Image.Image:
    #Convert a yellow star sprite into silver/gray tones.
    gray = Image.new("RGBA", img.size)
    src = img.load()
    dst = gray.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = src[x, y]
            if a > 0:
                avg = (r + g + b) // 3
                dst[x, y] = (avg, avg, avg, a)
    return gray


def load_lucky_assets():
    #Loads Lucky Stars assets (blank card and silver star) from cards.gif.
    #Uses the card coords you confirmed work.
    
    path = os.path.join(ASSETS_DIR_CARDART, "cards.gif")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Lucky Stars asset sheet not found: {path}")

    sheet = Image.open(path).convert("RGBA")
    assets = {}

    # --- Blank card front ---
    blank = sheet.crop((143, 64, 176, 112))
    assets["blank_full"] = blank.resize((136, 207), Image.NEAREST)

    # --- Star icon (crop then recolor to silver) ---
    star = sheet.crop((49, 0, 80, 32))
    #prev sizing, working on dynamic scaling
    #star = star.resize((32, 32), Image.NEAREST)
    assets["star"] = _recolor_to_silver(star)

    return assets