###########################################################
# File: bot.py

# Description: Discord bot entry setup and command routing
#
###########################################################

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from economy.bank import Bank
from casinogames.assetloader import load_slots_sheet, load_memory_backs, load_memory_faces
import io
import asyncio
from PIL import Image
bank = Bank()


# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Intents
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

###########################################################
# Events
###########################################################

@bot.event
async def on_ready():
    # Sync commands
    synced = await bot.tree.sync()
    print(f"{bot.user} is online. Synced {len(synced)} command(s).")

###########################################################
# Commands
###########################################################

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Don't Ping Me.", ephemeral=True)


@bot.tree.command(name="help", description="Show available commands")
async def help_cmd(interaction: discord.Interaction):
    msg = (
        "``` **LuigiCasinoBot Commands** \n\n"
        "/ping - Health check\n"
        "/help - Show this menu\n"
        "/rules - Show the casino rules\n"
        "/slot_pull - Spin the slot machine \n"
        "/pair_start - Start a Pair-a-Gone game \n"
        "/balance - Check your coin balance\n"
        "/grant <amount> - Add coins (admin/dev only)\n ```"
    )
    # Note: only the user who ran the command sees the message when its Ephmeral
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="balance", description="Check your coin balance")
async def balance_cmd(interaction: discord.Interaction):
    bal = bank.balance(interaction.user.id)
    await interaction.response.send_message(
        f"{interaction.user.mention}, your balance is {bal} coins.", 
        ephemeral=True
    )

@bot.tree.command(name="grant", description="grant coins")
async def grant_cmd(interaction: discord.Interaction, amount: int):
    new_bal = bank.grant(interaction.user.id, amount)
    await interaction.response.send_message(
        f"Granted {amount} coins. Your new balance is {new_bal}.", 
        ephemeral=True
    )

@bot.tree.command(name="test_sprite", description="Send a test slot icon by index")
async def test_sprite(interaction: discord.Interaction, index: int):
    #Send a slot icon by index (0–5).
    sheet = load_slots_sheet()   # now returns SlotIcons
    sprite = sheet.get_sprite(index)

    byte_arr = io.BytesIO()
    sprite.save(byte_arr, format="PNG")
    byte_arr.seek(0)

    file = discord.File(byte_arr, filename=f"slot_{index}.png")
    await interaction.response.send_message(file=file, ephemeral=True)

@bot.tree.command(name="test_memory", description="Send a memory match card by name")
async def test_memory(interaction: discord.Interaction, name: str, flip: bool = False):
    sheet = load_memory_faces()
    try:
        sheet = load_memory_faces()
        if flip:
            sprite = sheet.get_flip(name.lower())
        else:
            sprite = sheet.get_face(name.lower())

        byte_arr = io.BytesIO()
        sprite.save(byte_arr, format="PNG")
        byte_arr.seek(0)

        suffix = "flip" if flip else "face"
        file = discord.File(byte_arr, filename=f"memory_{name}_{suffix}.png")
        await interaction.response.send_message(file=file, ephemeral=True)
    except KeyError:
        await interaction.response.send_message(
            f"Unknown memory face: {name}. Valid options: mario, mushroom, goomba, luigi, flower, star, bowser, yoshi, lakitu.",
            ephemeral=True
        )


@bot.tree.command(name="test_back", description="Send a memory facedown stage")
async def test_back(interaction: discord.Interaction, stage: str):
    # Send a memory back/flip stage (back_full, back_half, back_edge)
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
            #back_full, back_half, back_edge.
            ephemeral=True
        )

@bot.tree.command(name="flip_demo", description="Animate a card flipping over")
async def flip_demo(interaction: discord.Interaction, name: str):
    # Send an animated GIF of a card flipping one time only hold last frame to prevent loop
    await interaction.response.defer(ephemeral=True)

    faces = load_memory_faces()
    backs = load_memory_backs()

    # Sequence: face, flip, back_edge, back_half, back_full
    sequence = [
        faces.get_face(name.lower()),
        faces.get_flip(name.lower()),
        backs.get("back_edge"),
        backs.get("back_half"),
        backs.get("back_full"),
    ]

    # Centering slim frames and adding background
    canvas_w, canvas_h = 136, 207
    normalized = []
    for frame in sequence:
        new_img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
        x_offset = (canvas_w - frame.width) // 2
        y_offset = (canvas_h - frame.height) // 2
        new_img.paste(frame, (x_offset, y_offset), mask=frame)
        normalized.append(new_img)

    # This holds the final frame so the loop doesnt occur
    final_frame = normalized[-1]
    for _ in range(10):  # 1s hold (10 * 100ms)
        normalized.append(final_frame)

    # Gif Settings
    # Best to use gif, since discord bottlenecks message editing or else the "animation"
    # looks really slow and clunky
    byte_arr = io.BytesIO()
    normalized[0].save(
        byte_arr,
        format="GIF",
        save_all=True,
        append_images=normalized[1:],
        duration=125,  # ms per frame
        loop=1         # if loop is 0 it goes infinite, 1 = 2 flips,  final_frame above holds it
    )
    byte_arr.seek(0)

    file = discord.File(byte_arr, filename=f"{name}_flip.gif")
    await interaction.followup.send(file=file, ephemeral=True)

###########################################################
# Run Bot
###########################################################

def run_bot():
    # Entrypoint for main.py
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment variables")
    bot.run(TOKEN)

