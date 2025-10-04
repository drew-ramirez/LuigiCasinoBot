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
    def __init__(self, game: LuckyStars, user_id: int, on_next_callback):
        super().__init__(timeout=None)
        self.game = game
        self.user_id = user_id
        self.on_next_callback = on_next_callback

        ###########################################################
        # left / next / right buttons
        ###########################################################
        self.left = LuckyStarsButton("Left", 0)
        self.right = LuckyStarsButton("Right", 1)
        self.next_button = LuckyStarsNextButton("Next", on_next_callback)
        self.next_button.disabled = True  # starts disabled each round

        self.add_item(self.left)
        self.add_item(self.next_button)
        self.add_item(self.right)

    ###########################################################
    # helper: disable L/R and enable Next
    ###########################################################
    async def disable_left_right_enable_next(self, message: discord.Message):
        self.left.disabled = True
        self.right.disabled = True
        self.next_button.disabled = False
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

        await interaction.response.defer()
        msg = await interaction.original_response()

        ###########################################################
        # disable L/R buttons, enable Next
        ###########################################################
        await view.disable_left_right_enable_next(msg)

        ###########################################################
        # play animation
        ###########################################################
        game = view.game
        game.pick_card(self.pos)
        gif = make_slide_animation(game, duration=150, tail_hold_ms=2500)
        await msg.edit(attachments=[discord.File(gif, f"luckystars_r{game.round}.gif")])
        await asyncio.sleep(0.5)

        ###########################################################
        # resolve round and show outcome
        ###########################################################
        result = game.resolve_round()
        outcome = result["outcome"]
        coins = result["coins"]

        if outcome == "win":
            text = f"You win this round! Coins: {coins}\nPress **Next** to continue."
        else:
            text = f"You lose this round! Coins: {coins}\nPress **Next** to continue."

        # handle game over
        if result["finished"]:
            text += "\n\nGame over! You ran out of coins."
            for c in view.children:
                c.disabled = True
            await msg.edit(content=text, view=view)
        else:
            await msg.edit(content=text, view=view)


###########################################################
# next button
###########################################################
class LuckyStarsNextButton(discord.ui.Button):
    def __init__(self, label: str, on_next_callback):
        super().__init__(label=label, style=discord.ButtonStyle.success, row=0)
        self.on_next_callback = on_next_callback

    async def callback(self, interaction: discord.Interaction):
        await self.on_next_callback(interaction)


###########################################################
# factory
###########################################################
def make_lucky_controls(game: LuckyStars, user_id: int, on_next_callback):
    #factory to create a new LuckyStarsView
    return LuckyStarsView(game, user_id, on_next_callback)
