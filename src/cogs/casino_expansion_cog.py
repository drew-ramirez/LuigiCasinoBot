"""Discord adapters for saved solo challenges, Tower practice and funded Blackjack."""
import asyncio
import logging
import os

import discord
from discord.ext import commands

from casinogames.blackjack import Blackjack, RULES as BLACKJACK_RULES, hand_total
from casinogames.challenges import MemoryMaster, EndlessPairs, MEMORY_RULES, ENDLESS_RULES, coordinate
from casinogames.fortune_tower import FortuneTower
from casinogames.session_store import SessionStore
from casinogames.expansion_render import render_table
from economy.blackjack_table import BlackjackTable
from economy.EconomyManager import EconomyManager
from utils.visibility import resolve_command_visibility

log = logging.getLogger(__name__)
ENGINES = {'memory_master': MemoryMaster, 'pairagone_endless': EndlessPairs, 'fortune_tower': FortuneTower}
TITLES = {'memory_master': 'Memory Master', 'pairagone_endless': 'Pair-a-Gone and On',
          'fortune_tower': "Fortune's Tower", 'blackjack': 'Blackjack'}
RULES = {'memory_master': MEMORY_RULES, 'pairagone_endless': ENDLESS_RULES,
         'fortune_tower': FortuneTower.RULES,
         'blackjack': BLACKJACK_RULES + '. Even wagers; matching ranks only, two hands maximum; split Aces take one card. '
                      'No insurance/surrender. Gross includes returned stake. Idle timeout stands all hands.'}


def engine_for(snapshot):
    return ENGINES[snapshot['kind']].from_dict(snapshot['state']['game'])


def update_solo(snapshot, action, value=None):
    """Pure mutation called inside SessionStore's transaction, before rendering."""
    game = engine_for(snapshot)
    if snapshot['status'] == 'paused' and action not in ('resume', 'finish'):
        raise ValueError('Resume this saved run before playing.')
    if action == 'pause':
        snapshot['status'] = 'paused'
    elif action == 'resume':
        snapshot['status'] = 'active'
    elif action == 'choose':
        game.choose(value)
    elif action == 'next':
        game.next_board()
    elif action == 'finish':
        game.finish()
    elif action == 'continue':
        game.deal_next()
    elif action in ('bank', 'timeout') and snapshot['kind'] == 'fortune_tower':
        game.bank()
    else:
        raise ValueError('That action is not available.')
    snapshot['state']['game'] = game.to_dict()
    if game.finished:
        snapshot['status'] = 'finished'
        score = game.result['score'] if snapshot['kind'] == 'fortune_tower' else game.score
        reason = game.result['outcome'] if snapshot['kind'] == 'fortune_tower' else getattr(game, 'reason', 'voluntary')
        snapshot['record'] = {'score': score, 'reason': reason}


def safe_text(kind, public):
    """Complete readable fallback; input must already be a viewer-safe projection."""
    lines = [f'**{TITLES[kind]}**']
    if kind in ('memory_master', 'pairagone_endless'):
        lines.append(f"Score {public['score']} · free play · 0 coins")
        if kind == 'memory_master':
            lines.append(f"Stars {public['stars']} · mistakes {public['mistakes']}/5 · attempts {public['attempts']}")
        lines.append(public['last'])
        for start in range(0, len(public['cards']), public['cols']):
            lines.append(' | '.join(f"{coordinate(i, public['cols'])}: {public['cards'][i] or ('cleared' if public['cards'][i] == '' else 'back')}"
                                    for i in range(start, start + public['cols'])))
    elif kind == 'blackjack':
        lines.append('House v1 · community coins · S17 · 3:2 blackjack')
        lines.append('Luigi: ' + ' '.join(c or '[back]' for c in public['dealer']))
        for i, hand in enumerate(public['hands']):
            total, soft = hand_total(hand['cards'])
            marker = ' →' if i == public['active_hand'] else ''
            lines.append(f"Hand {i+1}{marker}: {' '.join(hand['cards'])} · {total}{' soft' if soft else ''} · stake {hand['bet']}")
        result = public['result']
        lines.append(f"Committed {public['total_committed']}")
        if result:
            lines.append(f"Returned {result['payout']} · net {result['profit']:+d}")
            lines.extend(f"Hand {i+1}: {h['outcome']}" for i,h in enumerate(result['hands']))
    else:
        lines.append('Diamond practice v1 · virtual points only · no wallet changes')
        lines.append(f"Row {public['row_number']}/8 · Bank {public['offer']} gross · net {public['net']:+d} · x{public['multiplier']}")
        lines.append('Gate: ' + ('back' if public['gate'] is None else str(public['gate'] or 'Hero')))
        lines.extend(f"Row {i+2}: " + ' '.join(str(c) if c else 'Hero' for c in row) for i,row in enumerate(public['rows']))
        if public['result']:
            lines.append('Result: ' + public['result']['outcome'])
        else:
            lines.append('Continue risks this offer; the next offer can be lower. Idle timeout banks it.')
    return '\n'.join(lines)


class SoloView(discord.ui.View):
    def __init__(self, cog, snapshot, kind, owner, animations):
        super().__init__(timeout=480)
        self.cog, self.snapshot, self.kind = cog, snapshot, kind
        self.owner, self.animations = owner, animations
        self.message = None
        self.lock = cog.locks.setdefault((owner, kind), asyncio.Lock())
        if kind == 'blackjack':
            game = Blackjack.from_dict(snapshot['game'])
            if game.result:
                self.add_action('Play again', 'deal', row=0)
            else:
                for action in game.allowed_actions():
                    cost = game.extra_stake(action)
                    self.add_action(action.title() + (f' +{cost}' if cost else ''), action, row=0,
                                    disabled=cost > snapshot['balance'])
            self.add_action('Rules', 'rules', row=1)
        else:
            game = engine_for(snapshot)
            if snapshot['status'] == 'paused':
                self.add_action('Resume saved run', 'resume', row=0)
            elif not game.finished:
                if kind == 'fortune_tower':
                    self.add_action(f'Bank {game.offer}', 'bank', row=0)
                    self.add_action('Continue', 'continue', row=0)
                elif kind == 'memory_master' and game.status != 'playing':
                    self.add_action('Next board', 'next', row=0)
                elif game.cols == 6:
                    choices = [discord.SelectOption(label=coordinate(i, game.cols), value=str(i))
                               for i in range(len(game.board)) if i not in game.matched and i not in game.selected]
                    select = discord.ui.Select(placeholder='Choose a card (6 columns × 3 rows)', options=choices, row=0)
                    async def choose(inter):
                        await self.run(inter, 'choose', int(select.values[0]))
                    select.callback = choose
                    self.add_item(select)
                else:
                    for i in range(len(game.board)):
                        disabled = kind == 'memory_master' and (i in game.matched or i in game.selected)
                        self.add_action(coordinate(i, game.cols), 'choose', i, row=i//game.cols, disabled=disabled)
            if not game.finished and kind != 'fortune_tower':
                if snapshot['status'] != 'paused':
                    self.add_action('Pause', 'pause', row=4)
                self.add_action('Finish & save', 'finish', row=4)
            if kind == 'memory_master':
                self.add_action('Known cards', 'notes', row=4)
            self.add_action('Rules', 'rules', row=4)
            self.add_action('My records', 'records', row=4)

    def add_action(self, label, action, value=None, *, row=0, disabled=False):
        button = discord.ui.Button(label=label, row=row, disabled=disabled,
                                   style=discord.ButtonStyle.primary if action in ('bank', 'deal', 'next', 'resume') else discord.ButtonStyle.secondary)
        async def callback(inter):
            await self.run(inter, action, value)
        button.callback = callback
        self.add_item(button)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner:
            await interaction.response.send_message('This is another player\'s table.', ephemeral=True)
            return False
        return True

    async def run(self, interaction, action, value=None):
        # Check here as well so direct callback invocations cannot bypass ownership.
        if interaction.user.id != self.owner:
            await interaction.response.send_message('This is another player\'s table.', ephemeral=True)
            return
        if action == 'rules':
            await interaction.response.send_message(RULES[self.kind], ephemeral=True)
            return
        if action == 'notes':
            game = engine_for(self.snapshot)
            notes = ', '.join(f'{coordinate(int(i), game.cols)}: {v}' for i,v in sorted(game.known.items(), key=lambda p: int(p[0])))
            await interaction.response.send_message('**Known cards (assisted play)**\n' + notes, ephemeral=True)
            return
        if action == 'records':
            await interaction.response.defer(ephemeral=True)
            rows = await asyncio.to_thread(self.cog.store.records, self.snapshot['guild'], self.owner, self.kind)
            text = '\n'.join(f"{r['score']} points — {r['reason']}" for r in rows) or 'No finalized runs yet.'
            await interaction.followup.send('**Your finalized records**\n' + text, ephemeral=True)
            return
        await interaction.response.defer()
        async with self.lock:
            try:
                previous = self.public()
                if self.kind == 'blackjack':
                    if action == 'deal':
                        saved = await asyncio.to_thread(self.cog.blackjack.start, self.owner, self.snapshot['game']['bet'],
                                                       interaction.user.name, expected_round_id=self.snapshot['id'],
                                                       expected_revision=self.snapshot['revision'])
                    else:
                        saved = await asyncio.to_thread(self.cog.blackjack.act, self.owner, self.snapshot['id'], self.snapshot['revision'], action)
                else:
                    saved, _ = await asyncio.to_thread(self.cog.store.apply, self.snapshot['id'], self.snapshot['revision'],
                                                      self.owner, lambda s: update_solo(s, action, value))
                await self.cog.publish(interaction, saved, self.kind, self.owner, self.animations, previous=previous)
            except (ValueError, PermissionError) as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
            except Exception:
                log.exception('Saved casino action delivery failed')
                await interaction.followup.send('Delivery failed. Reopen this game command to recover the saved table; no result is rerolled.', ephemeral=True)

    def public(self):
        return (Blackjack.from_dict(self.snapshot['game']) if self.kind == 'blackjack' else engine_for(self.snapshot)).public_state()

    async def on_timeout(self):
        async with self.lock:
            if self.cog.views.get((self.owner, self.kind)) is not self:
                return
            try:
                if self.kind == 'blackjack':
                    saved = await asyncio.to_thread(self.cog.blackjack.act, self.owner, self.snapshot['id'], self.snapshot['revision'], 'timeout')
                elif self.snapshot['status'] == 'active':
                    action = 'timeout' if self.kind == 'fortune_tower' else 'pause'
                    saved, _ = await asyncio.to_thread(self.cog.store.apply, self.snapshot['id'], self.snapshot['revision'], self.owner,
                                                      lambda s: update_solo(s, action))
                else:
                    return
                public = (Blackjack.from_dict(saved['game']) if self.kind == 'blackjack' else engine_for(saved)).public_state()
                if self.message:
                    payload = await self.cog.payload(self.kind, public, False)
                    await self.message.edit(**payload, view=None)
            except Exception:
                log.exception('Casino timeout saved state could not be displayed')


class CasinoExpansionCog(commands.Cog):
    def __init__(self, bot, *, store=None, blackjack=None):
        self.bot = bot
        self.store = store or SessionStore(os.getenv('CASINO_SESSION_DB', 'data/casino_sessions.sqlite3'))
        self.blackjack = blackjack or BlackjackTable()
        self.views = {}
        self.locks = {}

    def cog_unload(self):
        for view in self.views.values():
            view.stop()

    async def payload(self, kind, public, animations, previous=None):
        content = safe_text(kind, public)
        try:
            media = await asyncio.to_thread(render_table, kind, public, previous=previous, animate=animations)
            animated = media.getvalue()[:3] == b'GIF'
            return {'content': content, 'embed': None, 'attachments': [discord.File(media, filename='casino.gif' if animated else 'casino.png')]}
        except Exception:
            log.exception('Casino media failed; using saved public text')
            return {'content': content + '\nImage unavailable; this is the saved table.', 'embed': None, 'attachments': []}

    async def publish(self, interaction, snapshot, kind, owner, animations, previous=None):
        view = SoloView(self, snapshot, kind, owner, animations)
        public = view.public()
        payload = await self.payload(kind, public, animations, previous)
        if kind != 'blackjack' and snapshot['status'] == 'paused':
            payload['content'] = '**Paused — exact board saved.**\n' + payload['content']
        try:
            message = await interaction.edit_original_response(**payload, view=view)
        except discord.HTTPException:
            # Upload errors cannot change the already-committed outcome.
            message = await interaction.edit_original_response(content=safe_text(kind, public), embed=None, attachments=[], view=view)
        view.message = message
        key = (owner, kind)
        old = self.views.get(key)
        if old:
            old.stop()
        self.views[key] = view

    async def start_solo(self, interaction, kind, animations=None):
        visibility = resolve_command_visibility(interaction, kind)
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        async with self.locks.setdefault((interaction.user.id, kind), asyncio.Lock()):
            guild = interaction.guild_id or 0
            owner = interaction.user.id
            snapshot = await asyncio.to_thread(self.store.active, guild, owner, kind)
            if snapshot is None:
                game = ENGINES[kind]()
                snapshot = await asyncio.to_thread(self.store.create, guild, owner, kind, {'game': game.to_dict()})
                if engine_for(snapshot).finished:
                    # Natural initial terminal states still finalize a record once.
                    def finalize(s):
                        g = engine_for(s)
                        s['status'] = 'finished'
                        s['record'] = {'score': g.result['score'] if kind == 'fortune_tower' else g.score,
                                       'reason': g.result['outcome'] if kind == 'fortune_tower' else g.reason}
                    snapshot, _ = await asyncio.to_thread(self.store.apply, snapshot['id'], snapshot['revision'], owner, finalize)
            if animations is None:
                animations = await asyncio.to_thread(EconomyManager.animations_enabled, owner, interaction.user.name)
            await self.publish(interaction, snapshot, kind, owner, animations)

    @discord.app_commands.command(name='casino_memorymaster', description='Advanced Memory Match: hints, Stars, saved boards and personal scores')
    async def memory_master(self, interaction: discord.Interaction, animations: bool | None = None):
        await self.start_solo(interaction, 'memory_master', animations)

    @discord.app_commands.command(name='casino_pairagone_endless', description='Pair-a-Gone and On: endless refill, pause/resume and saved scores')
    async def endless(self, interaction: discord.Interaction, animations: bool | None = None):
        await self.start_solo(interaction, 'pairagone_endless', animations)

    @discord.app_commands.command(name='casino_fortune_tower', description="Fortune's Tower: bank or continue in the Diamond practice variant")
    async def tower(self, interaction: discord.Interaction, animations: bool | None = None):
        await self.start_solo(interaction, 'fortune_tower', animations)

    @discord.app_commands.command(name='casino_blackjack', description='Play or resume Blackjack with Luigi: hit, stand, double and split')
    async def blackjack_start(self, interaction: discord.Interaction, wager: discord.app_commands.Range[int, 2, 1000000] = 20,
                              animations: bool | None = None):
        visibility = resolve_command_visibility(interaction, 'blackjack')
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        async with self.locks.setdefault((interaction.user.id, 'blackjack'), asyncio.Lock()):
            if wager % 2:
                await interaction.edit_original_response(content='Choose an even wager so blackjack pays exactly 3:2.')
                return
            owner = interaction.user.id
            if animations is None:
                animations = await asyncio.to_thread(EconomyManager.animations_enabled, owner, interaction.user.name)
            saved = await asyncio.to_thread(self.blackjack.get, owner)
            if saved and saved['game']['result'] is None:
                await self.publish(interaction, saved, 'blackjack', owner, animations)
                return
            # A displayed result is not permission to spend again; Deal is explicit.
            menu = discord.ui.View(timeout=120)
            deal = discord.ui.Button(label=f'Deal — stake {wager}', style=discord.ButtonStyle.primary)
            menu.add_item(deal)
            lock = self.locks[(owner, 'blackjack')]
            accepted = False
            async def confirm(inter):
                nonlocal accepted
                if inter.user.id != owner:
                    await inter.response.send_message('This wager belongs to another player.', ephemeral=True)
                    return
                await inter.response.defer()
                async with lock:
                    if accepted:
                        current = await asyncio.to_thread(self.blackjack.get, owner)
                    else:
                        try:
                            current = await asyncio.to_thread(self.blackjack.start, owner, wager, inter.user.name,
                                                              expected_round_id=saved['id'] if saved else None,
                                                              expected_revision=saved['revision'] if saved else None)
                        except ValueError as exc:
                            await inter.followup.send(str(exc), ephemeral=True)
                            return
                        accepted = True
                    await self.publish(inter, current, 'blackjack', owner, animations)
                    menu.stop()
            deal.callback = confirm
            await interaction.edit_original_response(content='**Blackjack — confirm wager**\n' + RULES['blackjack'] +
                                                      f'\nStake {wager}; splitting/doubling can commit up to {4*wager}. Extra stakes are checked at each decision.', view=menu)


async def setup(bot):
    await bot.add_cog(CasinoExpansionCog(bot))
