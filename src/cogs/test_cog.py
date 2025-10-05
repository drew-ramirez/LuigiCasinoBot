###########################################################
# File: test_cog.py
#
# Description: Dev test and sprite visualization tools
###########################################################

import io
import discord
from discord.ext import commands
from PIL import Image
from casinogames.assetloader import (
    load_memory_backs,
    load_memory_faces,
    load_slots_sheet,
)


class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("TestCog loaded.")

    ###########################################################
    # TEST COMMANDS
    ###########################################################

    @discord.app_commands.command(name="test_sprite", description="Send a test slot icon by index")
    async def test_sprite(self, interaction: discord.Interaction, index: int):
        # send a slot icon by index (0–5)
        sheet = load_slots_sheet()
        sprite = sheet.get_sprite(index)
        byte_arr = io.BytesIO()
        sprite.save(byte_arr, format="PNG")
        byte_arr.seek(0)
        file = discord.File(byte_arr, filename=f"slot_{index}.png")
        await interaction.response.send_message(file=file, ephemeral=True)

    @discord.app_commands.command(name="test_memory", description="Send a memory match card by name")
    async def test_memory(self, interaction: discord.Interaction, name: str, flip: bool = False):
        try:
            sheet = load_memory_faces()
            sprite = sheet.get_flip(name.lower()) if flip else sheet.get_face(name.lower())
            byte_arr = io.BytesIO()
            sprite.save(byte_arr, format="PNG")
            byte_arr.seek(0)
            suffix = "flip" if flip else "face"
            file = discord.File(byte_arr, filename=f"memory_{name}_{suffix}.png")
            await interaction.response.send_message(file=file, ephemeral=True)
        except KeyError:
            await interaction.response.send_message(
                (
                    f"Unknown memory face: {name}. Valid options: "
                    "mario, mushroom, goomba, luigi, flower, star, bowser, yoshi, lakitu."
                ),
                ephemeral=True,
            )

    @discord.app_commands.command(name="test_back", description="Send a memory facedown stage")
    async def test_back(self, interaction: discord.Interaction, stage: str):
        try:
            backs = load_memory_backs()
            sprite = backs.get(stage.lower())
            byte_arr = io.BytesIO()
            sprite.save(byte_arr, format="PNG")
            byte_arr.seek(0)
            file = discord.File(byte_arr, filename=f"back_{stage}.png")
            await interaction.response.send_message(file=file, ephemeral=True)
        except KeyError:
            await interaction.response.send_message(
                "Unknown stage. Valid: back_full, back_half, back_edge.",
                ephemeral=True,
            )

    @discord.app_commands.command(name="flip_demo", description="Animate a card flipping over")
    async def flip_demo(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)

        faces = load_memory_faces()
        backs = load_memory_backs()

        # sequence: face, flip, back_edge, back_half, back_full
        sequence = [
            faces.get_face(name.lower()),
            faces.get_flip(name.lower()),
            backs.get("back_edge"),
            backs.get("back_half"),
            backs.get("back_full"),
        ]

        # centering slim frames and adding background
        canvas_w, canvas_h = 136, 207
        normalized = []
        for frame in sequence:
            new_img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
            x_offset = (canvas_w - frame.width) // 2
            y_offset = (canvas_h - frame.height) // 2
            new_img.paste(frame, (x_offset, y_offset), mask=frame)
            normalized.append(new_img)

        # hold final frame to prevent loop
        final_frame = normalized[-1]
        for _ in range(10):
            normalized.append(final_frame)

        # gif settings
        byte_arr = io.BytesIO()
        normalized[0].save(
            byte_arr,
            format="GIF",
            save_all=True,
            append_images=normalized[1:],
            duration=125,
            loop=1,
        )
        byte_arr.seek(0)
        file = discord.File(byte_arr, filename=f"{name}_flip.gif")
        await interaction.followup.send(file=file, ephemeral=True)


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(TestCog(bot))
