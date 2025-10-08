###########################################################
# File: AssetLoader.py
#
###########################################################
import os
from PIL import Image

# now that imports and loaders in subfolders we need to define the base path
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
        self.sprite_height = 198  # 1187 / 6 ≈ 198
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
        sheet = Image.open(path).convert("RGBA")

        # Make background transparent
        datas = sheet.getdata()
        new_data = []
        for r, g, b, a in datas:
            if (r, g, b) in [(0, 200, 255), (0, 255, 255), (173, 216, 230)]:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((r, g, b, a))
        sheet.putdata(new_data)

        self.sheet = sheet

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
            "mario": (0, 0),
            "mushroom": (2, 0),
            "goomba": (4, 0),
            "luigi": (0, 1),
            "flower": (2, 1),
            "star": (4, 1),
            "bowser": (0, 2),
            "yoshi": (2, 2),
            "cloud": (4, 2),
        }
        
        self.extras = load_pairagone_extras()


    def _col_x(self, col_index: int) -> int:
        # even col: full
        # odd col: flip immediately after the full
        base = self.x0 + (col_index // 2) * self.pair_stride
        return base + (self.full_w if (col_index % 2 == 1) else 0)

    def _crop(
        self, col: int, row: int, is_full: bool, card_w=136, card_h=207
    ) -> Image.Image:
        y1 = self.row_tops[row]
        y2 = y1 + self.row_heights[row]
        x1 = self._col_x(col)
        x2 = x1 + (self.full_w if is_full else self.flip_w)
        face = self.sheet.crop((x1, y1, x2, y2))

        # Normalize to card size
        return face.resize((card_w, card_h), Image.NEAREST)

    def get_face(self, name: str) -> Image.Image:
        if name in self.faces:
            col, row = self.faces[name]
            return self._crop(col, row, is_full=True)
        if f"{name}_full" in self.extras:
            return self.extras[f"{name}_full"]
        raise KeyError(f"Unknown memory face: {name}")


    def get_flip(self, name: str) -> Image.Image:
        if name in self.faces:
            col, row = self.faces[name]
            return self._crop(col + 1, row, is_full=False)
        if f"{name}_half" in self.extras:
            return self.extras[f"{name}_half"]
        raise KeyError(f"Unknown memory flip: {name}")



class MemoryBacks:
    def __init__(self):
        path = os.path.join(ASSETS_DIR_CARDART, "FaceDown.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"FaceDown sheet not found: {path}")
        self.sheet = Image.open(path).convert("RGBA")

        # x ranges pixel measured
        self.frames = {
            "back_full": (0, 0, 136, 207),
            "back_half": (136, 0, 210, 207),
            "back_edge": (210, 0, 240, 207),
        }

        self.extras = load_pairagone_extras()


    def get(self, stage: str) -> Image.Image:
        if stage not in self.frames:
            raise KeyError(f"Unknown back stage: {stage}")
        return self.sheet.crop(self.frames[stage])


def load_memory_faces():
    return MemoryIcons()


def load_memory_backs():
    return MemoryBacks()


def _recolor_to_silver(img: Image.Image) -> Image.Image:
    # Convert a yellow star sprite into silver/gray tones.
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
    # Loads Lucky Stars assets (blank card and silver star) from cards.gif.
    # Uses the card coords you confirmed work.

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
    # prev sizing, working on dynamic scaling
    # star = star.resize((32, 32), Image.NEAREST)
    assets["star"] = _recolor_to_silver(star)

    return assets

###########################################################
# Pair-a-Gone extras 
###########################################################
def load_pairagone_extras():
    # Loads Pair-a-Gone extras, later other visual indicators if available online

    path = os.path.join(ASSETS_DIR_CARDART, "cards.gif")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Pair-a-Gone extra asset sheet not found: {path}")

    sheet = Image.open(path).convert("RGBA")
    extras = {}

    def _resize_card(img: Image.Image) -> Image.Image:
        return img.resize((136, 207), Image.NEAREST)

    def _compose_on_blank(
        blank: Image.Image,
        sprite: Image.Image,
        *,
        margin_x_ratio: float = 0.07,
        margin_y_ratio: float = 0.14,
    ) -> Image.Image:
        card = blank.copy()
        sprite = sprite.convert("RGBA")
        max_w = max(1, int(round(blank.width * (1.0 - 2 * margin_x_ratio))))
        max_h = max(1, int(round(blank.height * (1.0 - 2 * margin_y_ratio))))
        scale = min(max_w / sprite.width, max_h / sprite.height)
        new_size = (
            max(1, int(round(sprite.width * scale))),
            max(1, int(round(sprite.height * scale))),
        )
        sprite = sprite.resize(new_size, Image.NEAREST)
        offset = (
            (blank.width - new_size[0]) // 2,
            (blank.height - new_size[1]) // 2,
        )
        card.paste(sprite, offset, mask=sprite)
        return card

    blank_full_src = sheet.crop((143, 64, 176, 112))
    blank_half_src = sheet.crop((176, 64, 192, 112))
    blank_full = _resize_card(blank_full_src)
    blank_half = _resize_card(blank_half_src)

    extras["blank_full"] = blank_full
    extras["blank_half"] = blank_half

    boo_face = sheet.crop((73, 65, 104, 93))
    boo_half_face = sheet.crop((240, 19, 256, 30))

    extras["boo_full"] = _compose_on_blank(
        blank_full, boo_face, margin_x_ratio=0.05, margin_y_ratio=0.12
    )
    extras["boo_half"] = _compose_on_blank(
        blank_half, boo_half_face, margin_x_ratio=0.1, margin_y_ratio=0.18
    )

    return extras
