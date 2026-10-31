"""Roulette and slots share the bot's wager, visibility and metrics lifecycle."""
import asyncio
import discord
from discord import app_commands
from cogs.base_game_cog import BaseGameCog
from casinogames.casino_games import Roulette, Slots, BET_GROUPS, POCKETS
from casinogames.casino_render import render
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager

def placement_label(name):
    """Describe split/corner cells using pictures, without numbers on the board."""
    if name in ('red', 'black') or len(BET_GROUPS[name]) == 1:
        return name.title()
    return ('Split: ' if len(BET_GROUPS[name]) == 2 else 'Corner: ') + ' / '.join(
        ' '.join(POCKETS[i]).title() for i in BET_GROUPS[name])

class MachineView(discord.ui.View):
    def __init__(self, cog, game, player, animated):
        super().__init__(timeout=None)
        self.cog, self.game, self.player = cog, game, player
        self.animated = animated
        self.lock = asyncio.Lock()
        self.msg = None
        if isinstance(game, Roulette):
            groups = list(BET_GROUPS)
            for row, offset in enumerate(range(0, len(groups), 25)):
                select = discord.ui.Select(placeholder='Place a coin: pictures / colors' if row == 0 else 'Place a coin: splits / corners', row=row,
                    options=[discord.SelectOption(label=f'{placement_label(name)} (x{12//len(BET_GROUPS[name])})', value=name)
                             for name in groups[offset:offset+25]])
                select.callback = self.choose
                self.add_item(select)
            self.button('Spin', self.spin, row=2)
            self.button('Undo coin', self.undo, row=2)
            self.button('Clear table', self.clear, row=2)
            self.button('Rules', self.rules, row=2)
            self.refresh_controls()
        else:
            for i in range(3):
                async def stop(inter, index=i):
                    await self.act(inter, index)
                self.button(f'Stop reel {i+1}', stop)

    def button(self, label, callback, row=None):
        button = discord.ui.Button(label=label, style=discord.ButtonStyle.green, row=row)
        button.callback = callback
        self.add_item(button)

    def refresh_controls(self):
        if not isinstance(self.game, Roulette):
            return
        for child in self.children:
            if isinstance(child, discord.ui.Select):
                child.disabled = self.game.ready
            elif child.label == 'Spin':
                child.disabled = not self.game.ready
            elif child.label in ('Undo coin', 'Clear table'):
                child.disabled = not self.game.placements

    async def undo(self, inter):
        await self.edit_placement(inter, 'undo')

    async def clear(self, inter):
        await self.edit_placement(inter, 'clear')

    async def edit_placement(self, inter, action):
        await inter.response.defer()
        async with self.lock:
            if self.is_finished() or self.game.result is not None:
                return
            getattr(self.game, action)()
            self.refresh_controls()
            await inter.edit_original_response(**await self.payload(animate=self.animated))

    async def rules(self, inter):
        await inter.response.send_message(
            'Your wager is divided into up to five coins. Choose a picture, color, split or corner '
            'to place each coin; you can stack coins on the same spot. Place all coins, then Spin. '
            'Undo/Clear move your existing coins without charging again. '
            'Returns: picture ×12, split ×6, corner ×3, color ×2 (stake included). '
            'Any winning placements pay together.', ephemeral=True)

    async def interaction_check(self, inter):
        if inter.user.id != self.player.id:
            await inter.response.send_message('Not your game!', ephemeral=True)
            return False
        return True

    async def payload(self, *, animate=False):
        data = await asyncio.to_thread(render, self.game, animate)
        filename = 'casino.gif' if animate else 'casino.png'
        result = self.game.result
        status = (f'Return: {result["payout"]:,} coins | Net: {result["payout"]-self.game.bet:+,}'
                  if result else 'Choose your bet and spin.' if isinstance(self.game, Roulette)
                  else 'Press each reel button to stop it. Outcomes are random; GIF timing does not affect odds.')
        if isinstance(self.game, Roulette) and result:
            status = ' '.join(POCKETS[result['pocket']]).title() + ' | ' + status
        if isinstance(self.game, Roulette):
            if not result:
                left = len(self.game.chips)-len(self.game.placements)
                amount = self.game.chips[len(self.game.placements)] if left else 0
                status = (f'{left} coins left to place · Next coin: {amount} · Wager: {self.game.bet}'
                          if left else f'All coins placed · Wager: {self.game.bet} · Ready to spin!')
            return dict(content=status,embed=None,attachments=[discord.File(data,filename)],view=self)
        embed = discord.Embed(title=self.cog.game_name, description=f'Bet: {self.game.bet:,}\n{status}', color=0x238447)
        embed.set_image(url='attachment://' + filename)
        return dict(content=None, embed=embed, attachments=[discord.File(data, filename)], view=self)

    async def choose(self, inter):
        await inter.response.defer()
        async with self.lock:
            if self.is_finished() or self.game.result is not None:
                return
            if self.game.ready:
                return
            self.game.place(inter.data['values'][0])
            self.refresh_controls()
            await inter.edit_original_response(**await self.payload(animate=self.animated))

    async def spin(self, inter):
        await self.act(inter)

    async def act(self, inter, index=None):
        await inter.response.defer()
        async with self.lock:
            if self.is_finished() or getattr(self.game, 'metrics_logged', False):
                return
            if isinstance(self.game, Roulette):
                if not self.game.ready:
                    await inter.followup.send('Place all your coins before spinning.',ephemeral=True)
                    return
                self.game.spin()
            else:
                if self.game.reels[index] is not None:
                    return
                self.game.stop(index)
                self.children[index].disabled = True
            if self.game.result is not None:
                # No await between settlement and marking the round completed.
                payout = self.game.result['payout']
                if payout:
                    EconomyManager.payout(self.player.id, payout, self.player.name)
                self.game.metrics_logged = True
                try:
                    MetricsManager.record_game_result(getattr(self.game, 'metrics_session_id', None),
                        result='win' if payout else 'loss', payout=payout, net=payout-self.game.bet,
                        metadata={'selection': getattr(self.game, 'selection', None),
                                  'placements': getattr(self.game, 'placements', None),
                                  'chips': getattr(self.game, 'chips', None),
                                  'reels': getattr(self.game, 'reels', None), **self.game.result})
                finally:
                    await self.cog.cleanup_game(self.player.id)
                payload = await self.payload(animate=self.animated)
                if isinstance(self.game,Roulette) and self.animated:
                    payload.update(content='The wheel is spinning…',view=None)
                    await inter.edit_original_response(**payload)
                    # Match the rendered sequence; reveal text after the animation.
                    from casinogames.roulette_render import SPIN_DURATION_SECONDS
                    await asyncio.sleep(SPIN_DURATION_SECONDS)
                    payload = await self.payload()
                payload['view'] = ReplayView(self.cog, self.player.id)
                await inter.edit_original_response(**payload)
            else:
                await inter.edit_original_response(**await self.payload(animate=self.animated))

class ReplayView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=120)
        self.cog, self.user_id = cog, user_id
        self.used = False

    @discord.ui.button(label='Play again', style=discord.ButtonStyle.green)
    async def replay(self, inter, button):
        if inter.user.id != self.user_id:
            await inter.response.send_message('Not your game!', ephemeral=True)
            return
        if self.used:
            await inter.response.defer()
            return
        self.used = True
        button.disabled = True
        await inter.response.edit_message(view=self)
        await self.cog.open_game(inter)

class MachineCog(BaseGameCog):
    game_type = None

    async def open_game(self, interaction):
        command = 'casino_' + self.metrics_game_key
        self.log_command_invocation(interaction, command)
        async def start(inter, bet):
            await inter.response.defer()
            game = self.game_type(bet)
            if isinstance(game, Roulette):
                game.balance_after_wager = EconomyManager.balance(inter.user.id,inter.user.name)
            animated = EconomyManager.animations_enabled(inter.user.id, inter.user.name)
            view = MachineView(self, game, inter.user, animated)
            # Render before changing the existing tracked session.
            payload = await view.payload(animate=animated)
            self.log_game_start(inter, command, bet_amount=bet, game=game)
            await self.register_active_game(inter.user.id, game=game, view=view)
            view.msg = await inter.edit_original_response(**payload)
            self.active_games[inter.user.id]['message'] = view.msg
        await self.present_wager_menu(interaction, on_bet_selected=start,
            prompt=('Choose your total wager, then place five coins on the roulette table. '
                    'Payouts include the stake; idle sessions forfeit the wager.'
                    if self.game_type is Roulette else
                    'Choose a wager. Payouts include the stake; idle sessions forfeit the wager.'))

class RouletteCog(MachineCog):
    game_type = Roulette
    def __init__(self, bot):
        super().__init__(bot, 'Mushroom Roulette', log_label='roulette')

    @app_commands.command(name='casino_roulette', description='Play Luigi\'s Mushroom Roulette')
    async def roulette(self, interaction: discord.Interaction):
        await self.open_game(interaction)

class SlotsCog(MachineCog):
    game_type = Slots
    def __init__(self, bot):
        super().__init__(bot, 'Super Mario Slot', log_label='slots')

    @app_commands.command(name='casino_slots', description='Play Luigi\'s Super Mario Slot: stop three reels')
    async def slots(self, interaction: discord.Interaction):
        await self.open_game(interaction)

async def setup(bot):
    await bot.add_cog(RouletteCog(bot))
    await bot.add_cog(SlotsCog(bot))
