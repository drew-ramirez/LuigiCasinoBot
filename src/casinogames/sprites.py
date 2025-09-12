import os
from PIL import Image

#Could potentially be used for sheets made with Sprite Sheet Maker for future deck styles
#As of not probably just depreciated.
class SpriteSheet:
    def __init__(self, path: str, sprite_width: int, sprite_height: int, num_cols: int):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Sprite sheet not found: {path}")
        self.sheet = Image.open(path).convert("RGBA")
        self.sprite_width = sprite_width
        self.sprite_height = sprite_height
        self.num_cols = num_cols

    def get_sprite(self, col: int, row: int) -> Image.Image:
        #Extract a sprite from (col, row)
        x = col * self.sprite_width
        y = row * self.sprite_height
        return self.sheet.crop((x, y, x + self.sprite_width, y + self.sprite_height))

    def get_sprite_by_index(self, index: int) -> Image.Image:
        #Extract a sprite using linear index
        row = index // self.num_cols
        col = index % self.num_cols
        return self.get_sprite(col, row)
