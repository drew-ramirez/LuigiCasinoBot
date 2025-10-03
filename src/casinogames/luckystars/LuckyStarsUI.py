###########################################################
# File: LuckyStarsUi.py
#
# Description: Discord UI for Lucky Stars game
###########################################################

import discord
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import (
    render_lucky_board,
    make_slide_animation,
)


class LuckyControls(discord.ui.View):

    # Left / Next / Right buttons
    # Left/Right call the bot's handle_lucky_pick(interaction, pos)
    # Next calls the bot's handle_lucky_next(interaction)

    def __init__(
        self,
        on_pick,
        on_next,
        next_enabled: bool = False,
        *,
        timeout: float | None = 180,
    ):
        super().__init__(timeout=timeout)
        self.on_pick = on_pick  # coroutine (interaction, pos:int)
        self.on_next = on_next  # coroutine (interaction)
        # Create buttons in order: Left, Next, Right
        self.left = discord.ui.Button(
            label="Left", style=discord.ButtonStyle.secondary, row=0
        )
        self.next = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=not next_enabled,
        )
        self.right = discord.ui.Button(
            label="Right", style=discord.ButtonStyle.secondary, row=0
        )
        # store helper attrs
        self.left.pos = 0
        self.right.pos = 1

        # wire callbacks
        async def _left_cb(interaction: discord.Interaction):
            await self.on_pick(interaction, 0)

        async def _right_cb(interaction: discord.Interaction):
            await self.on_pick(interaction, 1)

        async def _next_cb(interaction: discord.Interaction):
            await self.on_next(interaction)

        self.left.callback = _left_cb
        self.right.callback = _right_cb
        self.next.callback = _next_cb

        # add to view
        self.add_item(self.left)
        self.add_item(self.next)
        self.add_item(self.right)


def make_lucky_controls(
    on_pick, on_next, *, next_enabled: bool = False
) -> discord.ui.View:
    # Factory used by bot.py
    return LuckyControls(on_pick=on_pick, on_next=on_next, next_enabled=next_enabled)


async def disable_left_right_enable_next(
    view: discord.ui.View, message: discord.Message
):
    # After a pick: freeze L/R, enable Next
    for child in view.children:
        if isinstance(child, discord.ui.Button):
            if getattr(child, "pos", None) in (0, 1):
                child.disabled = True
            if child.label == "Next":
                child.disabled = False
    await message.edit(view=view)


async def reveal_lucky_cards(
    game: LuckyStars,
    picked: int,
    message: discord.Message,
    duration: int = 200,
):
    game.pick_card(picked)

    gif = make_slide_animation(game, duration=duration, tail_hold_ms=2500)
    file = discord.File(gif, filename=f"luckystars_r{game.round}.gif")
    await message.edit(attachments=[file])

    # Immediately compute and return the result; the visual holds on its own
    result = game.resolve_round()
    return result
