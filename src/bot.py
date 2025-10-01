###########################################################
# File: bot.py

# Description: Discord bot entry setup and command routing
#
###########################################################

# Standard library
import asyncio
import io
import os

# Third-party
import discord
from discord.ext import commands
from dotenv import load_dotenv
from PIL import Image

# LuigiBot Library
from economy.bank import Bank
from casinogames.assetloader import (
    load_memory_backs,
    load_memory_faces,
    load_slots_sheet,
)
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import (
    render_board_image,
    make_board_flip_gif,
    make_board_reverse_flip_gif,
)

from casinogames.memorymatch.MemoryMatchUI import (
    update_controls_for_match,
    make_flip_controls,
    update_controls_for_unmatch,
) 

from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import render_pair_board
from casinogames.pairagone.PairAGoneUI import make_pair_controls

from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import (
    make_lucky_controls,
    reveal_lucky_cards,
    disable_left_right_enable_next,
)

bank = Bank()

#MemoryMatch Globals
memory_games = {}
memory_messages = {} 
memory_views = {}

#PairAGone Globals
pair_games = {}
pair_messages = {}
pair_views = {}

# Per-user state for Lucky Stars
lucky_games: dict[int, LuckyStars] = {}
lucky_messages: dict[int, discord.Message] = {}
lucky_views: dict[int, discord.ui.View] = {}

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

##################################################################################
# MemoryMatch Section
#
#   Memory_Start
#   Memory_flip
#   test_memory_all
#   handle_memory_flip
#
##################################################################################

@bot.tree.command(name="memory_start", description="Start a Memory Match game")
async def memory_start(interaction: discord.Interaction):
    game = MemoryMatch(interaction.user.id)
    memory_games[interaction.user.id] = game

    img_bytes = render_board_image(game)
    file = discord.File(img_bytes, filename="board.png")

    # Makes button grid
    viewUpdate = make_flip_controls(len(game.board))

    # store the view so flips can find it later
    memory_views[interaction.user.id] = viewUpdate

    await interaction.response.send_message(
        f"Memory Match started!\nCoins: {game.remaining_coins}",
        file=file,
        view=viewUpdate, # This is the button UI feature
        ephemeral=True
    )

    # Save reference to this original board message
    msg = await interaction.original_response()
    memory_messages[interaction.user.id] = msg

@bot.tree.command(name="memory_flip", description="Flip a card by position")
async def memory_flip(interaction: discord.Interaction, pos: int):
    await handle_memory_flip(interaction, pos)

@bot.tree.command(name="test_memory_all", description="Show all memory match faces and flips")
async def test_memory_all(interaction: discord.Interaction):
    faces = load_memory_faces()

    cards = []
    labels = []

    # Iterate through all defined faces
    for name, (col, row) in faces.faces.items():
        face = faces.get_face(name)
        flip = faces.get_flip(name)
        cards.append(face)
        cards.append(flip)
        labels.append(f"{name}_face")
        labels.append(f"{name}_flip")

    # Layout: 2 cols (face | flip)
    cols = 2
    rows = len(cards) // cols
    card_w, card_h = 133, 193  # full card size
    margin = 10

    canvas_w = cols * (card_w + margin) - margin
    canvas_h = rows * (card_h + margin) - margin

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 128, 0, 255))

    for i, sprite in enumerate(cards):
        col = i % cols
        row = i // cols
        x = col * (card_w + margin)
        y = row * (card_h + margin)
        canvas.paste(sprite, (x, y), mask=sprite)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)

    file = discord.File(out, filename="memory_all.png")
    await interaction.response.send_message(file=file, ephemeral=True)

async def handle_memory_flip(interaction: discord.Interaction, pos: int):
    game = memory_games.get(interaction.user.id)
    board_msg = memory_messages.get(interaction.user.id)
    view = memory_views.get(interaction.user.id)
    
    if not game or not board_msg or not view:
        await interaction.response.send_message("No game running or controls missing!", ephemeral=True)
        return

    if not game.flip_card(pos):
        await interaction.response.send_message("Invalid flip.", ephemeral=True)
        return

    
    symbol, _, _ = game.board[pos]

    # This disables buttons during animation.
    for child in view.children:
        child.disabled = True
    await board_msg.edit(view=view)

    # 1. Show board flip animation
    gif = make_board_flip_gif(game, pos, symbol, duration=120)
    gif_file = discord.File(gif, filename=f"board_flip_{pos}.gif")
    await board_msg.edit(content=f"Coins: {game.remaining_coins}", attachments=[gif_file])

    await asyncio.sleep(0.6)

    # 2. Update static board
    img_bytes = render_board_image(game)
    png_file = discord.File(img_bytes, filename="board.png")
    await board_msg.edit(content=f"Coins: {game.remaining_coins}", attachments=[png_file])

    # 3. Check match logic
    if len(game.revealed) % 2 == 0:
        matched = game.check_match()
        if not matched:
            # No match = pause so player sees both
            await asyncio.sleep(1.0)

            a, b = game.revealed[-2], game.revealed[-1]
            symbols = [game.board[a][0], game.board[b][0]]

            # Play reverse flip GIF
            gif = make_board_reverse_flip_gif(game, [a, b], symbols, duration=120)
            gif_file = discord.File(gif, filename="board_unflip.gif")
            await board_msg.edit(content=f"Coins: {game.remaining_coins}", attachments=[gif_file])

            await asyncio.sleep(0.6)

            # Actually hide them in game state
            game.hide_unmatched()

            # Update static PNG after hiding
            img_bytes = render_board_image(game)
            png_file = discord.File(img_bytes, filename="board.png")
            await board_msg.edit(content=f"Coins: {game.remaining_coins}", attachments=[png_file])
            await update_controls_for_unmatch(view, [a, b], board_msg)

        else:
            # Match = mark buttons 
            await update_controls_for_match(view, game.revealed[-2:], board_msg)

            if game.is_board_cleared():
                
                game.next_level()

                # Re-render board for the new level
                img_bytes = render_board_image(game)
                png_file = discord.File(img_bytes, filename="board.png")
                await board_msg.edit(content=f"Board Cleared | Stars: {game.stars} | Coins: {game.remaining_coins}", attachments=[png_file])

                # Resetting controls for the new board size incase it ups
                new_view = make_flip_controls(len(game.board))
                memory_views[interaction.user.id] = new_view
                await board_msg.edit(view=new_view)
                return
                
    # Re-enable all still-active buttons
    for i, child in enumerate(view.children):
        if i < len(game.board):
            symbol, flipped, matched = game.board[i]
            child.disabled = matched  # keep disabled if matched
        else:
            child.disabled = True
    await board_msg.edit(view=view)

##################################################################################
# Pair A Gone Section
#
##################################################################################
@bot.tree.command(name="pair_start", description="Start a Pair-a-Gone game")
async def pair_start(interaction: discord.Interaction):
    game = PairAGone(interaction.user.id)
    pair_games[interaction.user.id] = game

    # Render the starting board
    img_bytes = render_pair_board(game)
    file = discord.File(img_bytes, filename="pair_board.png")

    # Build button grid 
    view = make_pair_controls(game.COLS * game.ROWS, game.COLS)
    pair_views[interaction.user.id] = view

    await interaction.response.send_message(
        "Pair-a-Gone started!",
        file=file,
        view=view,
        ephemeral=True
    )

    # Save reference to the message so flips can edit it
    msg = await interaction.original_response()
    pair_messages[interaction.user.id] = msg
 

async def handle_pair_flip(interaction: discord.Interaction, pos: int):
    import asyncio
    from casinogames.pairagone.PairAGonePrint import (
        make_pair_flicker_gif,
        render_pair_board,
        render_pair_board_with_blanks,
        make_deal_flip_gif,
    )

    game = pair_games.get(interaction.user.id)
    msg = pair_messages.get(interaction.user.id)
    view = pair_views.get(interaction.user.id)

    if not game or not msg or not view:
        await interaction.response.send_message("No Pair-a-Gone game running!", ephemeral=True)
        return

    # Collect selections
    game.selected.append(pos)
    if len(game.selected) < 2:
        return  # wait for second click

    # Two cards chosen
    a, b = game.selected
    game.selected = []

    # Validate adjacency + symbol match
    if a == b:
        await msg.edit(content="❌ Pick two different cards.", view=view)
        return

    sa, sb = game.board[a], game.board[b]
    ra, ca = divmod(a, game.COLS)
    rb, cb = divmod(b, game.COLS)
    is_adjacent = (abs(ra - rb) <= 1 and abs(ca - cb) <= 1)
    is_match = (sa == sb and is_adjacent)

    if not is_match:
        await msg.edit(content="❌ No match!", view=view)
        return

    # ---------- 1) Disable buttons ----------
    for child in view.children:
        if hasattr(child, "disabled"):
            child.disabled = True
    await msg.edit(view=view)

    # ---------- 2) FLICKER ----------
    positions = [a, b]
    symbols = [sa, sb]
    flicker_gif = make_pair_flicker_gif(game, positions, symbols, duration=120)
    await msg.edit(
        content="✅ Match!",
        attachments=[discord.File(flicker_gif, "pair_flicker.gif")],
        view=view,
    )
    await asyncio.sleep(1.0)

    # ---------- 3) REMOVE + REFILL ----------
    new_cards = game.remove_and_fall(positions)  # [(index, symbol), ...]

    # Start with ALL new slots green
    blanks = [pos for pos, _ in new_cards]
    img_bytes = render_pair_board_with_blanks(game, blanks)
    await msg.edit(
        content="Dealer is dealing new cards...",
        attachments=[discord.File(img_bytes, "pair_board.png")],
        view=view,
    )

# ---------- 4) DEALER FLIP ONE AT A TIME ----------
    revealed = []
    for pos, sym in new_cards:
        # Blank out all new slots except the ones already revealed
        blanks = [p for p, _ in new_cards if p not in revealed and p != pos]

        # Base board: already revealed new cards face up, unrevealed new ones green
        img_bytes = render_pair_board_with_blanks(game, blanks)
        base_board = Image.open(img_bytes).convert("RGBA")

        # Build flip on this custom background
        flip_gif = make_deal_flip_gif(game, pos, sym, base_board, duration=120)
        await msg.edit(
            content="Dealer flips a new card...",
            attachments=[discord.File(flip_gif, "deal_flip.gif")],
            view=view,
        )
        await asyncio.sleep(0.8)

        revealed.append(pos)
    # ---------- 5) STATIC REDRAW ----------
    final_png = render_pair_board(game)
    await msg.edit(
        content="Pair-a-Gone continues!",
        attachments=[discord.File(final_png, "pair_board.png")],
        view=view,
    )

    # Re-enable buttons
    for child in view.children:
        if hasattr(child, "disabled"):
            child.disabled = False
    await msg.edit(view=view)

    # ---------- 6) END CONDITIONS ----------
    if game.is_board_cleared():
        await msg.edit(content="🎉 Board cleared!", view=None)
        return
    if not game.has_possible_moves():
        await msg.edit(content="❌ Too Bad. No moves left.", view=None)
        return

###########################################################
# Lucky Stars (Luigi’s Casino)
###########################################################


@bot.tree.command(name="lucky_start", description="Start a Lucky Stars game")
async def lucky_start(interaction: discord.Interaction):
    game = LuckyStars()
    game.deal_round()

    img_bytes = render_lucky_board(game, reveal=False)
    file = discord.File(img_bytes, filename="lucky.png")

    # Next must be disabled at the start of each round
    view = make_lucky_controls(on_pick=handle_lucky_pick, on_next=handle_lucky_next, next_enabled=False)

    await interaction.response.send_message(
        content=f"🎲 Lucky Stars started! You have {game.coins} coins.\nPick a card!",
        file=file,
        view=view,
    )
    msg = await interaction.original_response()
    lucky_games[interaction.user.id] = game
    lucky_messages[interaction.user.id] = msg
    lucky_views[interaction.user.id] = view


async def handle_lucky_pick(interaction: discord.Interaction, pos: int):
    uid = interaction.user.id
    game = lucky_games.get(uid)
    msg = lucky_messages.get(uid)
    view = lucky_views.get(uid)

    if not game or not msg or not view:
        await interaction.response.send_message("No Lucky Stars game running!", ephemeral=True)
        return

    # Immediately freeze L/R and enable Next
    await interaction.response.defer()  # keeps the interaction alive
    await disable_left_right_enable_next(view, msg)

    # Play animation and resolve
    result = await reveal_lucky_cards(game, pos, msg)

    outcome = result["outcome"]
    coins = result["coins"]
    if outcome == "win":
        text = f"✅ You win this round! Coins: {coins}\nPress **Next** to continue."
    elif outcome == "lose":
        text = f"❌ You lose this round! Coins: {coins}\nPress **Next** to continue."
    else:
        text = f"➖ Tie! Coins: {coins}\nPress **Next** to continue."

    if result["finished"]:
        text = f"{text}\n\n💀 Game over! You ran out of coins."
        # Hide Next and fully disable the view
        for c in view.children:
            if isinstance(c, discord.ui.Button):
                c.disabled = True
        await msg.edit(content=text, view=view)
        # cleanup
        lucky_games.pop(uid, None)
        lucky_messages.pop(uid, None)
        lucky_views.pop(uid, None)
    else:
        await msg.edit(content=text, view=view)


async def handle_lucky_next(interaction: discord.Interaction):
    """Advance to the next round when the user presses Next."""
    uid = interaction.user.id
    game = lucky_games.get(uid)
    msg = lucky_messages.get(uid)
    old_view = lucky_views.get(uid)

    if not game or not msg or not old_view:
        await interaction.response.send_message("No Lucky Stars game running!", ephemeral=True)
        return

    await interaction.response.defer()

    # Deal next round and render the facedown board
    game.deal_round()
    img = render_lucky_board(game, reveal=False)
    file = discord.File(img, filename="lucky.png")

    # Build a fresh view for the new round: L/R enabled, Next disabled
    new_view = make_lucky_controls(on_pick=handle_lucky_pick, on_next=handle_lucky_next, next_enabled=False)
    await msg.edit(content=f"Pick again! (Coins: {game.coins})", attachments=[file], view=new_view)

    lucky_views[uid] = new_view

###########################################################
# Run Bot
###########################################################

def run_bot():
    # Entrypoint for main.py
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment variables")
    bot.run(TOKEN)

