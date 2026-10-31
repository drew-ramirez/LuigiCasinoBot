"""Voluntary, durable practice tables for Luigi's Thrilling Cards.

Only viewer-filtered engine projections reach renderers or Discord. SQLite
commits accepted actions before publication; missing uploads pause the saved
hand instead of dealing again. Restarted tables wait for explicit resume.
"""
import asyncio
import logging
import os
import time
import uuid
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from casinogames.session_store import SessionStore
from casinogames.thrilling_cards import ThrillingMatch

log = logging.getLogger(__name__)
KIND = 'thrilling_cards'
RULES = (
    "Luigi's Thrilling Cards — bounded practice adaptation. 2–4 humans; five hands, "
    "rotating opener. Each seat starts with 75 practice chips, never community coins. "
    "Maximum commitment: 15 chips per hand. Ready confirms this limit. Everyone antes 1; "
    "open at 1–5 total, call only the gap, or raise by 1–5 (two raises per hand). "
    "Your own card stays hidden; your private table shows the others. Highest rank "
    "2–Ace wins, then clubs < diamonds < hearts < spades. Fold/leave/90-second turn "
    "timeout forfeits committed chips. Winner takes the conserved pot. Public showdown "
    "reveals only eligible cards; a fold win reveals none. Screenshots can be shared, "
    "so this is trust-based social play. Lobby expires after 120 seconds. "
    "Refresh and Rules never extend the clock. After a bot restart, use "
    "/casino_thrilling with the table ID to resume the same hand."
)


def _projection(snapshot, viewer=None):
    state = snapshot['state']
    if state.get('match'):
        match = ThrillingMatch.from_dict(state['match'])
        result = match.hand.view(viewer)
        result['standings'] = match.standings()
        result['hand_number'] = min(5, len(match.hands) + (match.hand not in match.hands))
    else:
        result = {'game': KIND, 'seats': [dict(player_id=p, card=None, committed=0,
                  folded=False, ready=p in state['ready']) for p in state['players']],
                  'pot': 0, 'target': 0, 'turn': None, 'result': None, 'actions': ()}
    result['phase'] = state['phase']
    return result


def _clock_token(snapshot):
    if snapshot['status'] != 'active':
        return None
    if snapshot['state']['phase'] == 'lobby':
        return ('lobby',)
    if snapshot['state']['phase'] == 'playing':
        match = ThrillingMatch.from_dict(snapshot['state']['match'])
        if match.hand.result is None:
            return ('turn', len(match.hands), match.hand.turn)
    return None


class ThrillingView(discord.ui.View):
    def __init__(self, cog, snapshot, viewer=None):
        super().__init__(timeout=None)
        self.cog, self.snapshot, self.viewer = cog, snapshot, viewer
        state = snapshot['state']
        if viewer is None:
            if state['phase'] == 'lobby' and snapshot['status'] != 'finished':
                for label, action in [('Join', 'join'), ('Ready · max 15', 'ready'),
                                      ('Leave', 'leave'), ('Start', 'start'), ('Cancel', 'cancel')]:
                    self.button(label, action, row=0)
            elif state['phase'] == 'playing' and snapshot['status'] != 'finished':
                self.button('View my table', 'private', row=0)
                self.button('Leave table', 'leave', row=0)
                if ThrillingMatch.from_dict(state['match']).hand.result is not None:
                    self.button('Next hand', 'next', row=0)
            self.button('Refresh', 'refresh', row=1)
            self.button('Rules', 'rules', row=1)
        else:
            projection = _projection(snapshot, viewer)
            for action in projection['actions']:
                if action in ('open', 'raise'):
                    label = 'Open at total' if action == 'open' else 'Raise by'
                    select = discord.ui.Select(placeholder=f'{label} 1–5 chips', row=0,
                        options=[discord.SelectOption(label=f'{label} {n}', value=str(n)) for n in range(1, 6)])
                    async def choose(inter, act=action):
                        await self.dispatch(inter, act, int(inter.data['values'][0]))
                    select.callback = choose
                    self.add_item(select)
                else:
                    cost = projection.get('call_cost', 0)
                    label = ('Check' if cost == 0 else f'Call +{cost}') if action == 'call' else 'Fold'
                    self.button(label, action, row=1)
            self.button('Refresh my table', 'private', row=2)
            self.button('Rules', 'rules', row=2)

    def button(self, label, action, row):
        button = discord.ui.Button(label=label, row=row, style=discord.ButtonStyle.secondary)
        async def callback(inter):
            await self.dispatch(inter, action)
        button.callback = callback
        self.add_item(button)

    async def interaction_check(self, inter):
        if self.viewer is not None and inter.user.id != self.viewer:
            await inter.response.send_message('This private view belongs to another player.', ephemeral=True)
            return False
        return True

    async def dispatch(self, inter, action, amount=None):
        if not await self.interaction_check(inter):
            return
        await self.cog.handle(inter, self.snapshot['id'], self.snapshot['revision'], action,
                              amount, private=self.viewer is not None)


class ThrillingCardsCog(commands.Cog):
    def __init__(self, bot, *, store=None):
        self.bot = bot
        self.store = store or SessionStore(os.getenv('CASINO_SESSION_DB', 'data/casino_sessions.sqlite3'))
        self.boot_id = uuid.uuid4().hex
        self.locks, self.messages, self.deadlines, self.tasks = {}, {}, {}, {}
        self.lobby_seconds, self.turn_seconds = 120, 90

    def cog_unload(self):
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()
        self.deadlines.clear()

    def _lock(self, table_id):
        return self.locks.setdefault(table_id, asyncio.Lock())

    async def _get(self, table_id, guild):
        saved = await asyncio.to_thread(self.store.get, table_id)
        if saved is None or saved['kind'] != KIND or saved['guild'] != str(guild):
            raise ValueError('No Thrilling Cards table with that ID exists in this server.')
        return saved

    async def _public_allowed(self, guild_id, channel_id):
        from utils.visibility import resolve_command_visibility
        context = SimpleNamespace(guild=SimpleNamespace(id=int(guild_id)), channel_id=channel_id)
        decision = await asyncio.to_thread(resolve_command_visibility, context, KIND)
        return not decision.ephemeral

    @app_commands.command(name='casino_thrilling', description="Create or resume Luigi's multiplayer practice card table")
    @app_commands.guild_only()
    @app_commands.describe(table='Saved table ID, including a table where you joined another player')
    async def thrilling(self, inter: discord.Interaction, table: str | None = None):
        await inter.response.defer(ephemeral=True, thinking=True)
        try:
            if table:
                snapshot = await self._get(table, inter.guild_id)
                if inter.user.id not in snapshot['state']['players']:
                    raise PermissionError('Only a seated player can resume this table. Use Join on its public lobby.')
            else:
                existing = await asyncio.to_thread(self.store.active, inter.guild_id, inter.user.id, KIND)
                if existing is None and not await self._public_allowed(inter.guild_id, inter.channel_id):
                    raise PermissionError('Multiplayer needs a public table. Use the configured public casino channel for Thrilling Cards.')
                state = {'phase': 'lobby', 'players': [inter.user.id], 'ready': [], 'match': None,
                         'boot': self.boot_id, 'channel_id': inter.channel_id, 'message_id': None}
                snapshot = await asyncio.to_thread(self.store.create, inter.guild_id, inter.user.id, KIND, state)
            async with self._lock(snapshot['id']):
                snapshot = await self._get(snapshot['id'], inter.guild_id)
                if snapshot['status'] != 'finished' and (snapshot['state']['boot'] != self.boot_id or snapshot['status'] == 'paused'):
                    self.deadlines.pop(snapshot['id'], None)
                    def resume(saved):
                        saved['state']['boot'] = self.boot_id
                        saved['status'] = 'active'
                    snapshot, _ = await asyncio.to_thread(self.store.apply, snapshot['id'], snapshot['revision'],
                        inter.user.id, resume, authorize=lambda s, a: int(a) in s['state']['players'])
                await self._publish(snapshot, inter=inter, allow_create=True)
            await inter.followup.send(f"Table `{snapshot['id']}` is available in its public channel. "
                                      'Practice chips only; Ready confirms maximum 15 per hand.', ephemeral=True)
        except (ValueError, PermissionError, discord.HTTPException) as exc:
            await inter.followup.send(str(exc), ephemeral=True)
        except Exception:
            log.exception('Thrilling Cards operation failed; saved state retained')
            await inter.followup.send('The saved table is preserved. Use /casino_thrilling with its ID to resume after the display recovers.', ephemeral=True)

    def _change(self, saved, actor, action, amount=None):
        state = saved['state']
        if state['boot'] != self.boot_id or saved['status'] == 'paused':
            raise ValueError('This table is paused. Use /casino_thrilling with its ID to resume.')
        owner = int(saved['owner'])
        if action == 'join':
            if state['phase'] != 'lobby' or actor in state['players'] or len(state['players']) >= 4:
                raise ValueError('Join requires an open lobby with a free seat.')
            state['players'].append(actor)
        elif action == 'ready':
            if state['phase'] != 'lobby' or actor not in state['players']:
                raise ValueError('Join this lobby before confirming readiness.')
            if actor in state['ready']:
                raise ValueError('You are already ready.')
            state['ready'].append(actor)
        elif action == 'cancel':
            if actor != owner or state['phase'] != 'lobby':
                raise ValueError('Only the owner can cancel an undealt lobby.')
            state['phase'], saved['status'] = 'cancelled', 'finished'
        elif action == 'start':
            if actor != owner or state['phase'] != 'lobby':
                raise ValueError('Only the owner can start this lobby.')
            if len(state['players']) < 2 or set(state['ready']) != set(state['players']):
                raise ValueError('Start needs 2–4 players, all ready for the 15-chip maximum.')
            match = ThrillingMatch(state['players'])
            match.next_hand()
            state['match'], state['phase'] = match.to_dict(), 'playing'
        elif action == 'leave':
            if actor not in state['players']:
                raise ValueError('You are not seated at this table.')
            if state['phase'] == 'lobby':
                if actor == owner:
                    raise ValueError('The owner can cancel this lobby instead.')
                state['players'].remove(actor)
                state['ready'] = [p for p in state['ready'] if p != actor]
            else:
                match = ThrillingMatch.from_dict(state['match'])
                match.leave(actor)
                self._save_match(saved, match)
        else:
            if state['phase'] != 'playing' or actor not in state['players']:
                raise ValueError('You are not playing in this table.')
            match = ThrillingMatch.from_dict(state['match'])
            if action == 'next':
                host = next((p for p in match.players if p not in match.departed), None)
                if actor != host:
                    raise ValueError('Only the first remaining seat can deal the next hand.')
                match.next_hand()
            else:
                match.hand.act(actor, action, amount)
            self._save_match(saved, match)

    @staticmethod
    def _save_match(saved, match):
        if match.hand.result is not None:
            match.settle_hand()
        if match.finished:
            saved['status'] = 'finished'
            saved['state']['phase'] = 'finished'
        saved['state']['match'] = match.to_dict()

    async def handle(self, inter, table_id, revision, action, amount=None, *, private=False):
        await inter.response.defer(ephemeral=True, thinking=True)
        try:
            async with self._lock(table_id):
                snapshot = await self._get(table_id, inter.guild_id)
                if action == 'rules':
                    await inter.followup.send(RULES, ephemeral=True)
                    return
                if action == 'private':
                    if inter.user.id not in snapshot['state']['players'] or not snapshot['state'].get('match'):
                        raise PermissionError('Only a dealt player can open a private table.')
                    await self._send_private(inter, snapshot)
                    return
                if action == 'refresh':
                    await self._publish(snapshot)
                    await inter.followup.send('Public table refreshed. The deadline is unchanged.', ephemeral=True)
                    return
                if getattr(inter.user, 'bot', False):
                    raise PermissionError('This table is for human players.')
                deadline = self.deadlines.get(table_id)
                if deadline and deadline[1] <= time.monotonic():
                    raise ValueError('This deadline has expired. Refresh after the timeout resolves.')
                previous = _projection(snapshot)
                snapshot, applied = await asyncio.to_thread(self.store.apply, table_id, revision, inter.user.id,
                    lambda saved: self._change(saved, inter.user.id, action, amount),
                    authorize=lambda saved, actor: (action == 'join' and saved['state']['phase'] == 'lobby')
                        or int(actor) in saved['state']['players'])
                if not applied:
                    await inter.followup.send('That control is stale or the table ended. Refresh for the saved state.', ephemeral=True)
                    return
                self._cancel_task(table_id)
                snapshot = await self._publish(snapshot, previous=previous)
                if private and snapshot['state'].get('match'):
                    await self._send_private(inter, snapshot)
                else:
                    await inter.followup.send('Table updated.', ephemeral=True)
        except (ValueError, PermissionError, discord.HTTPException) as exc:
            await inter.followup.send(str(exc), ephemeral=True)
        except Exception:
            log.exception('Thrilling Cards operation failed; saved state retained')
            await inter.followup.send('The saved table is preserved. Use /casino_thrilling with its ID to resume after the display recovers.', ephemeral=True)

    async def _animated(self, player_id):
        try:
            from economy.EconomyManager import EconomyManager
            return await asyncio.to_thread(EconomyManager.animations_enabled, player_id)
        except Exception:
            log.warning('Animation preference unavailable; using static Thrilling Cards', exc_info=True)
            return False

    async def _payload(self, snapshot, viewer=None, previous=None):
        safe = _projection(snapshot, viewer)
        state = snapshot['state']
        lines = ["**Luigi's Thrilling Cards · practice chips**", f"Table `{snapshot['id']}`"]
        if state['phase'] == 'lobby':
            lines += ['2–4 humans · 75 chips each · maximum 15 per hand · five hands',
                      'Join, then Ready to confirm the limit. Owner starts when everyone is ready.']
        elif safe.get('result'):
            result = safe['result']
            lines += [f"Hand {safe['hand_number']}/5 · <@{result['winner']}> takes {result['pot']} chips ({result['reason']})."]
            lines += [f"<@{p['player_id']}>: {p['chips']} chips ({p['net']:+} net), place {p['place']}"
                      for p in safe['standings']]
        elif state['phase'] == 'playing':
            lines += [f"Hand {safe['hand_number']}/5 · Pot {safe['pot']} · Target {safe['target']}",
                      f"Turn: <@{safe['turn']}> · 90 seconds · refresh does not extend it."]
        for seat in safe['seats']:
            detail = 'ready' if seat.get('ready') else 'not ready' if state['phase'] == 'lobby' else (
                f"{seat['committed']} committed" + (' · folded' if seat['folded'] else ''))
            lines.append(f"<@{seat['player_id']}> · {seat['card'] or 'card back'} · {detail}")
        if snapshot['status'] == 'paused' or state['boot'] != self.boot_id:
            lines.append('Paused — use /casino_thrilling with this table ID to resume.')
        elif snapshot['status'] == 'finished':
            lines.append('Table ended. Use /casino_thrilling to create a new lobby.')
        if viewer is not None:
            lines.append('Private view: your own card is hidden until an eligible showdown.')
        attachments = []
        try:
            from casinogames.expansion_render import render_table
            animate = await self._animated(viewer or int(snapshot['owner']))
            data = await asyncio.to_thread(render_table, KIND, safe, previous=previous, animate=animate)
            is_gif = data.getvalue()[:6] in (b'GIF87a', b'GIF89a')
            attachments = [discord.File(data, filename='thrilling.gif' if is_gif else 'thrilling.png')]
        except Exception:
            log.warning('Thrilling Cards image failed; saved state remains playable as text', exc_info=True)
        return dict(content='\n'.join(lines), attachments=attachments, embed=None,
                    view=ThrillingView(self, snapshot, viewer), allowed_mentions=discord.AllowedMentions.none())

    async def _send_private(self, inter, snapshot):
        # The caller identity, never a component argument, selects the card mask.
        payload = await self._payload(snapshot, inter.user.id)
        payload['files'] = payload.pop('attachments')
        await inter.followup.send(**payload, ephemeral=True)

    async def _message(self, snapshot):
        table_id, state = snapshot['id'], snapshot['state']
        if table_id in self.messages:
            return self.messages[table_id]
        if state.get('message_id'):
            channel = self.bot.get_channel(state['channel_id'])
            if channel is None:
                channel = await self.bot.fetch_channel(state['channel_id'])
            if getattr(getattr(channel, 'guild', None), 'id', None) != int(snapshot['guild']):
                raise PermissionError('Saved table channel does not belong to this server.')
            message = await channel.fetch_message(state['message_id'])
            self.messages[table_id] = message
            return message
        return None

    @staticmethod
    async def _public_send(send, payload, *, creating=False):
        """Retry attachment rejection as the same safe text state, without a draw."""
        try:
            return await send(**payload)
        except discord.HTTPException as exc:
            field = 'files' if creating else 'attachments'
            if isinstance(exc, (discord.Forbidden, discord.NotFound)) or not payload.get(field):
                raise
            fallback = dict(payload, **{field: []})
            return await send(**fallback)

    async def _publish(self, snapshot, *, inter=None, previous=None, allow_create=False):
        table_id = snapshot['id']
        try:
            try:
                message = await self._message(snapshot)
            except discord.NotFound:
                self.messages.pop(table_id, None)
                message = None
            destination = snapshot['state']['channel_id'] if message is not None else getattr(inter, 'channel_id', None)
            if destination is not None and not await self._public_allowed(snapshot['guild'], destination):
                raise PermissionError('Multiplayer needs a public table. Use the configured public casino channel for Thrilling Cards.')
            payload = await self._payload(snapshot, previous=previous)
            if message is None:
                if not allow_create or inter is None:
                    raise ValueError('Public table is missing. Use /casino_thrilling with its ID to resume.')
                payload['files'] = payload.pop('attachments')
                message = await self._public_send(inter.channel.send, payload, creating=True)
                self.messages[table_id] = message
                def bind(saved):
                    saved['state']['channel_id'], saved['state']['message_id'] = inter.channel_id, message.id
                if snapshot['status'] != 'finished':
                    snapshot, _ = await asyncio.to_thread(self.store.apply, table_id, snapshot['revision'], snapshot['owner'], bind)
                    # Binding metadata advances revision. Publish controls for that exact revision.
                    await message.edit(view=ThrillingView(self, snapshot))
            else:
                await self._public_send(message.edit, payload)
            self._arm(snapshot)
            return snapshot
        except Exception:
            self._cancel_task(table_id)
            if snapshot['status'] != 'finished':
                def pause(saved):
                    saved['status'] = 'paused'
                await asyncio.to_thread(self.store.apply, table_id, snapshot['revision'], snapshot['owner'], pause)
            raise

    def _cancel_task(self, table_id):
        task = self.tasks.pop(table_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _arm(self, snapshot):
        table_id, token = snapshot['id'], _clock_token(snapshot)
        self._cancel_task(table_id)
        if token is None or snapshot['state']['boot'] != self.boot_id:
            self.deadlines.pop(table_id, None)
            return
        old = self.deadlines.get(table_id)
        seconds = self.lobby_seconds if token[0] == 'lobby' else self.turn_seconds
        deadline = old[1] if old and old[0] == token else time.monotonic() + seconds
        self.deadlines[table_id] = (token, deadline)
        self.tasks[table_id] = asyncio.create_task(self._timeout(table_id, token, deadline))

    async def _timeout(self, table_id, token, deadline):
        try:
            await asyncio.sleep(max(0, deadline - time.monotonic()))
            async with self._lock(table_id):
                snapshot = await asyncio.to_thread(self.store.get, table_id)
                if (snapshot is None or snapshot['state']['boot'] != self.boot_id
                        or _clock_token(snapshot) != token):
                    return
                previous = _projection(snapshot)
                def expire(saved):
                    if token[0] == 'lobby':
                        saved['state']['phase'], saved['status'] = 'expired', 'finished'
                    else:
                        match = ThrillingMatch.from_dict(saved['state']['match'])
                        match.hand.fold(match.hand.turn)
                        self._save_match(saved, match)
                snapshot, applied = await asyncio.to_thread(self.store.apply, table_id, snapshot['revision'], snapshot['owner'], expire)
                if applied:
                    await self._publish(snapshot, previous=previous)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception('Thrilling Cards timeout publication failed; table preserved for resume')


async def setup(bot):
    await bot.add_cog(ThrillingCardsCog(bot))
