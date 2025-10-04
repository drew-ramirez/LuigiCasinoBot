###########################################################
# File: LuckyStarsUI.py
#
# Description: Discord UI controls and animations for Lucky Stars
###########################################################

import discord
import asyncio
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import (
    render_lucky_board,
    make_slide_animation,
)

###########################################################
# lucky stars view
###########################################################
class LuckyStarsView(discord.ui.View):
    def __init__(self, game: LuckyStars, user_id: int, on_finish=None):
        super().__init__(timeout=None)
        self.game = game
        self.user_id = user_id
        self.on_finish = on_finish

        ###########################################################
        # left / spacer / right buttons
        ###########################################################
        # inside LuckyStarsView.__init__
        self.left = LuckyStarsButton("Left", 0)
        self.spacer = discord.ui.Button(label="⠀", style=discord.ButtonStyle.gray, disabled=True, row=0)
        self.right = LuckyStarsButton("Right", 1)

        self.add_item(self.left)
        self.add_item(self.spacer)
        self.add_item(self.right)


    async def disable_buttons(self, message: discord.Message):
        for c in self.children:
            c.disabled = True
        await message.edit(view=self)

###########################################################
# left/right pick buttons
###########################################################
class LuckyStarsButton(discord.ui.Button):
    def __init__(self, label: str, pos: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=0)
        self.pos = pos

    async def callback(self, interaction: discord.Interaction):
        view: LuckyStarsView = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        await interaction.response.defer(thinking=False)
        msg = await interaction.original_response()
        await view.disable_buttons(msg)

        # play animation
        game = view.game
        game.pick_card(self.pos)
        gif = make_slide_animation(game, duration=150, tail_hold_ms=2500)
        await msg.edit(attachments=[discord.File(gif, f"luckystars_r{game.round}.gif")])
        await asyncio.sleep(0.5)

        # resolve and finish
        result = game.resolve_round()
        outcome = result["outcome"]
        coins = result["coins"]

        if outcome == "win":
            text = f"You win this round! Coins: {coins}"
        else:
            text = f"You lose this round! Coins: {coins}"

        if result["finished"]:
            text += "\n\nGame over! You ran out of coins."
        await show_replay_menu(view, msg, text, view.user_id, view.on_finish)

###########################################################
# replay / quit menu
###########################################################
async def show_replay_menu(view, msg, text, user_id, on_finish):
    replay = discord.ui.Button(label="Play Again", style=discord.ButtonStyle.green)
    quitb = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

    async def replay_cb(interaction: discord.Interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        new_game = LuckyStars()
        new_game.deal_round()
        new_view = LuckyStarsView(new_game, user_id, on_finish)
        img = render_lucky_board(new_game, reveal=False)
        await msg.edit(
            content=f"New Lucky Stars game started! You have {new_game.coins} coins.\nPick a card!",
            attachments=[discord.File(img, "lucky.png")],
            view=new_view,
        )

    async def quit_cb(interaction: discord.Interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return
        await interaction.response.defer()
        await msg.edit(content="Thanks for playing Lucky Stars!", view=None)
        if on_finish:
            await on_finish(user_id)

    replay.callback = replay_cb
    quitb.callback = quit_cb

    end_view = discord.ui.View()
    end_view.add_item(replay)
    end_view.add_item(quitb)
    await msg.edit(content=text, view=end_view)

###########################################################
# factory
###########################################################
def make_lucky_controls(game: LuckyStars, user_id: int, on_finish=None):
    return LuckyStarsView(game, user_id, on_finish)
