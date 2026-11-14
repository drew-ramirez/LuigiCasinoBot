"""Practice card tables with consenting opponents and private, confirmed moves."""
import asyncio
import logging
import time
from types import SimpleNamespace

import discord
from discord.ext import commands

from casinogames.duel_session import DuelService
from utils.visibility import resolve_command_visibility

log = logging.getLogger(__name__)
from casinogames.registry import DUEL_GAMES

TITLES = {key: game.title for key, game in DUEL_GAMES.items()}


def seat(public, player):
    return 'Luigi' if player == 0 else f'Seat {public["players"].index(player)+1}'


def card_label(card):
    if card is None:
        return 'back'
    if isinstance(card, dict):
        if 'name' in card:
            return card['name'] + ' ' + '/'.join(str(card.get(k, '')) for k in ('north','east','south','west'))
        return ', '.join(f'{k}={card_label(v)}' for k,v in card.items())
    if isinstance(card, list):
        return ' '.join(card_label(v) for v in card)
    return str(card)


def _formation_lines(public):
    lines=[]
    for player,formations in public.get('formations',{}).items():
        lines.append(seat(public,int(player))+' formations:')
        for i,pile in enumerate(formations):
            spent=' / spent' if pile.get('spent') else ''
            lines.append(f"{i+1}: {card_label(pile.get('cards',[]))} ({pile.get('count',0)} cards{spent})")
    return lines


def _table_lines(public):
    kind=public['kind']
    if kind=='triple_triad':
        return [f"{chr(65+i//3)}{i%3+1}: "+
                (f"{seat(public,item['owner'])} {card_label(item['card'])}" if item else 'empty')
                for i,item in enumerate(public.get('table',[]))]
    if kind=='platoon':
        return _formation_lines(public)
    if kind=='pazaak':
        return [f"{seat(public,int(player))}: {card_label(board)}; total {public.get('totals',{}).get(player,0)}"
                for player,board in public.get('boards',{}).items()]
    return ['Table: '+card_label(public.get('table',[]))]


def readable(public):
    """Text is derived from the same permitted view as the image, never storage."""
    kind=public['kind']
    lines=[f'**{TITLES[kind]} · practice only · no community coins**']
    lines.append(' | '.join(f'{seat(public,p)}: <@{p}>' if p else 'Luigi' for p in public['players']))
    lines.append(f"Phase: {public.get('phase', 'playing')} · {public.get('session_status', 'active')}")
    if public.get('turn') is not None:
        lines.append(f"Turn: {seat(public, public['turn'])}")
    if public.get('rule_name'):
        lines.append(f"Rule: {public.get('rule', '')} — {public['rule_name']}")
    lines.extend(_table_lines(public))
    for player, hand in public.get('hands', {}).items():
        lines.append(f"{seat(public,int(player))} hand: {card_label(hand)}")
    for key in ('scores','points','permanents','predictions','committed','gross','net','last_set','ledger','qualifying'):
        if public.get(key) is not None:
            lines.append(key.replace('_',' ').title()+': '+card_label(public[key]))
    if public.get('result'):
        result=public['result'];winner=result.get('winner')
        lines.append('**'+('Draw' if winner is None else seat(public,winner)+' wins')+'** — '+str(result.get('reason',result.get('outcome','finished'))))
        lines.append('Result: '+card_label(result))
    lines.extend(str(event) for event in public.get('log', [])[-4:])
    return '\n'.join(lines)


def text_pages(text, limit=1850):
    pages, current=[], ''
    for line in text.splitlines():
        while len(line)>limit:
            if current: pages.append(current);current=''
            pages.append(line[:limit]);line=line[limit:]
        if len(current)+len(line)+1>limit:
            pages.append(current);current=''
        current+=(('\n' if current else '')+line)
    if current:pages.append(current)
    return pages or ['No additional details.']


class CardTableView(discord.ui.View):
    def __init__(self, cog, saved, viewer=None, *, group=None, page=0, group_page=0, choice=None):
        super().__init__(timeout=None)
        self.cog,self.saved,self.viewer=cog,saved,viewer
        self.group,self.page,self.group_page,self.choice=group,page,group_page,choice
        if viewer is None:
            self._public_controls()
        else:
            self._private_controls()

    def _public_controls(self):
        if self.saved['status']!='finished':
            if self.saved['state']['phase']=='invited':
                self.button('Accept invitation','accept',0)
                self.button('Decline / cancel','decline',0)
            else:
                self.button('My hand / play','private',0)
        self.button('Refresh table','refresh',1)
        self.button('Rules','rules',1)

    def _private_controls(self):
        if self.saved['state']['phase']=='invited' and self.saved['status']!='finished':
            if self.viewer != int(self.saved['owner']):
                self.button('Accept invitation','accept',0)
            self.button('Cancel invitation','decline',0)
        elif self.saved['status']=='paused':
            self.button('Resume saved match','resume',0)
        elif self.saved['status']=='active':
            self._active_controls()
        self.button('Refresh','private',4)
        self.button('Rules','rules',4)
        self.button('Details','details',4)

    def _active_controls(self):
        actions=self.cog.service.actions(self.saved,self.viewer)
        if self.choice:
            if any(a['id']==self.choice for a in actions):
                self.button('Confirm move','confirm',2,style=discord.ButtonStyle.success)
                self.button('Back to moves','menu',2)
        else:
            groups=list(dict.fromkeys(a.get('group','Moves') for a in actions))
            if groups:
                self._group_controls(groups)
            chosen=self.group if self.group in groups else groups[0] if len(groups)==1 else None
            if chosen:
                self.group=chosen
                self._move_controls([a for a in actions if a.get('group','Moves')==chosen])
        self.button('Pause','pause',4)
        self.button('Concede','concede_prompt',4)

    def _group_controls(self,groups):
        start=self.group_page*25
        options=[discord.SelectOption(label=g[:100],value=str(i))
                 for i,g in enumerate(groups[start:start+25],start)]
        menu=discord.ui.Select(placeholder='Choose a card or move type',options=options,row=0)
        async def select_group(inter):
            await self.navigate(inter,group=groups[int(inter.data['values'][0])],page=0)
        menu.callback=select_group
        self.add_item(menu)
        if len(groups)>25:
            if self.group_page:self.button('Previous cards','groups_prev',3)
            if start+25<len(groups):self.button('More cards','groups_next',3)

    def _move_controls(self,actions):
        self.page=min(self.page,max(0,(len(actions)-1)//25))
        start=self.page*25
        options=[discord.SelectOption(label=a['label'][:100],value=str(i),
                    description=a.get('description','')[:100] or None)
                 for i,a in enumerate(actions[start:start+25],start)]
        menu=discord.ui.Select(placeholder='Choose move, then confirm',options=options,row=1)
        async def select_move(inter):
            await self.navigate(inter,choice=actions[int(inter.data['values'][0])]['id'])
        menu.callback=select_move
        self.add_item(menu)
        if self.page:self.button('Previous moves','page_prev',3)
        if start+25<len(actions):self.button('More moves','page_next',3)

    def button(self,label,action,row,style=discord.ButtonStyle.secondary):
        button=discord.ui.Button(label=label,row=row,style=style)
        async def callback(inter):
            if action in ('menu','groups_prev','groups_next','page_prev','page_next'):
                return await self.navigate(inter, choice=None,
                    page=0 if action.startswith('groups_') else max(0,self.page+({'page_prev':-1,'page_next':1}.get(action,0))),
                    group_page=max(0,self.group_page+({'groups_prev':-1,'groups_next':1}.get(action,0))),
                    **({'group':None} if action.startswith('groups_') else {}))
            await self.dispatch(inter,action)
        button.callback=callback;self.add_item(button)

    async def interaction_check(self,inter):
        if self.viewer is not None and inter.user.id!=self.viewer:
            await inter.response.send_message('This private view belongs to another player.',ephemeral=True)
            return False
        return True

    async def navigate(self,inter,**changes):
        if not await self.interaction_check(inter):return
        current=await asyncio.to_thread(self.cog.service.get,self.saved['id'],inter.guild_id or 0,actor=inter.user.id)
        if current['revision']!=self.saved['revision']:
            await self.dispatch(inter,'private');return
        await inter.response.defer()
        options=dict(group=self.group,page=self.page,group_page=self.group_page,choice=self.choice)
        options.update(changes)
        view=CardTableView(self.cog,current,self.viewer,**options)
        payload=await self.cog.payload(current,self.viewer,animate=False,view=view)
        if options['choice']:
            action=next(a for a in self.cog.service.actions(current,self.viewer) if a['id']==options['choice'])
            payload['content']='**Confirm: '+discord.utils.escape_markdown(action['label'])+'**\n'+payload['content']
            payload['content']=payload['content'][:2000]
        await self.cog._send(inter.edit_original_response,payload)

    async def dispatch(self,inter,action):
        if not await self.interaction_check(inter):return
        await self.cog.handle(inter,self.saved,action,viewer=self.viewer,choice=self.choice)


class CardTablesCog(commands.Cog):
    def __init__(self,bot,*,store=None,registry=None,cosmetics=None):
        self.bot=bot
        self.cosmetics=cosmetics
        self.service=DuelService(store,registry)
        self.locks={};self.messages={};self.private_messages={};self.tasks={};self.deadlines={}
        self.timeout_seconds=480

    def cog_unload(self):
        for task in self.tasks.values():task.cancel()
        self.tasks.clear()

    def lock(self,table_id):return self.locks.setdefault(table_id,asyncio.Lock())

    async def visible(self,guild,channel,kind):
        context=SimpleNamespace(guild=SimpleNamespace(id=int(guild)) if guild else None,channel_id=channel)
        return not (await asyncio.to_thread(resolve_command_visibility,context,kind)).ephemeral

    async def animated(self,actor):
        from economy.EconomyManager import EconomyManager
        try:return await asyncio.to_thread(EconomyManager.animations_enabled,actor)
        except Exception:
            log.warning('Using static practice-table rendering; preference unavailable',exc_info=True)
            return False

    async def render_appearance(self,player):
        from cosmetics.catalog import Appearance
        if self.cosmetics is None:
            return Appearance()
        try:
            appearance=await asyncio.wait_for(asyncio.to_thread(self.cosmetics.appearance_for,int(player)),timeout=2.0)
            if not isinstance(appearance,Appearance):
                raise TypeError('Cosmetics lookup did not return an Appearance')
            return appearance
        except Exception:
            log.warning('Using classic practice-table appearance; cosmetics unavailable',exc_info=True)
            return Appearance()

    async def payload(self,saved,viewer=None,*,animate=False,view=None,transition=False):
        public=self.service.projection(saved,viewer)
        content=readable(public)
        if saved['state']['phase']=='invited':
            content+='\nInvited opponent must Accept before cards are dealt.'
        content+=f"\nTable `{saved['id']}` · reopen this command with `table` to resume."
        if len(content)>1950:content=content[:1820]+'\nUse Details for the complete readable table.'
        files=[]
        try:
            from casinogames.duel_render import render_duel, render_sequence
            from cosmetics.rendering import run_with_appearance
            appearance=await self.render_appearance(saved['owner'] if viewer is None else viewer)
            history=self.service.frames(saved,viewer) if transition else []
            previous=history[0] if len(history)>1 else None
            if animate and len(history)>1:
                data=await asyncio.to_thread(run_with_appearance,appearance,render_sequence,saved['kind'],history)
            else:
                data=await asyncio.to_thread(run_with_appearance,appearance,render_duel,saved['kind'],public,previous=previous,animate=animate)
            files=[discord.File(data,filename='table.gif' if data.getvalue().startswith(b'GIF') else 'table.png')]
        except Exception:
            log.warning('Using saved public text after table image failure',exc_info=True)
        return dict(content=content,attachments=files,embed=None,
                    view=view or CardTableView(self,saved,viewer),allowed_mentions=discord.AllowedMentions.none())

    async def _send(self,send,payload,*,creating=False):
        payload=dict(payload)
        if creating:payload['files']=payload.pop('attachments')
        try:return await send(**payload)
        except discord.HTTPException as exc:
            field='files' if creating else 'attachments'
            if isinstance(exc,(discord.Forbidden,discord.NotFound)) or not payload.get(field):raise
            payload[field]=[]
            return await send(**payload)

    async def public_message(self,saved,*,channel=None,transition=False):
        if not saved['state'].get('public'):return saved
        table_id=saved['id'];state=saved['state']
        if not await self.visible(saved['guild'],state['channel_id'],saved['kind']):
            raise PermissionError('This channel is no longer configured for public tables.')
        message=await self._saved_public_message(saved)
        animate=state.get('animations',False)
        payload=await self.payload(saved,animate=animate,transition=transition)
        if message is None:
            if channel is None or channel.id!=state['channel_id']:
                raise ValueError('Return to the saved public channel and reopen this command to restore its message.')
            message=await self._send(channel.send,payload,creating=True)
            def bind(s):s['state']['message_id']=message.id
            if saved['status']!='finished':
                saved,_=await asyncio.to_thread(self.service.store.apply,table_id,saved['revision'],saved['owner'],bind)
                await message.edit(view=CardTableView(self,saved))
        else:
            await self._send(message.edit,payload)
        self.messages[table_id]=message
        return saved

    async def _saved_public_message(self,saved):
        table_id=saved['id']
        state=saved['state']
        message=self.messages.get(table_id)
        if message is None and state.get('message_id'):
            destination=self.bot.get_channel(state['channel_id']) or await self.bot.fetch_channel(state['channel_id'])
            if getattr(getattr(destination,'guild',None),'id',None)!=int(saved['guild']):
                raise PermissionError('The saved table channel belongs to another server.')
            try:message=await destination.fetch_message(state['message_id'])
            except discord.NotFound:message=None
        return message

    async def private_message(self,inter,saved,*,original=False,transition=False):
        payload=await self.payload(saved,inter.user.id,animate=saved['state'].get('animations',False),transition=transition)
        if original:
            message=await self._send(inter.edit_original_response,payload)
        else:
            async def send(**kwargs):return await inter.followup.send(**kwargs,ephemeral=True,wait=True)
            message=await self._send(send,payload,creating=True)
        self.private_messages[(saved['id'],inter.user.id)]=message

    def arm(self,saved):
        table_id=saved['id'];old=self.tasks.pop(table_id,None)
        if old and old is not asyncio.current_task():old.cancel()
        if saved['status']!='active':self.deadlines.pop(table_id,None);return
        token=saved['revision'];prior=self.deadlines.get(table_id)
        seconds=120 if saved['state']['phase']=='invited' else self.timeout_seconds
        deadline=prior[1] if prior and prior[0]==token else time.monotonic()+seconds
        self.deadlines[table_id]=(token,deadline)
        self.tasks[table_id]=asyncio.create_task(self.expire(saved['id'],token,deadline))

    async def expire(self,table_id,revision,deadline):
        try:
            await asyncio.sleep(max(0,deadline-time.monotonic()))
            async with self.lock(table_id):
                saved=await asyncio.to_thread(self.service.store.get,table_id)
                if not saved or saved['revision']!=revision or saved['status']!='active':return
                action='cancel' if saved['state']['phase']=='invited' else 'pause'
                saved,applied=await asyncio.to_thread(self.service.change,table_id,revision,int(saved['owner']),action,guild=saved['guild'])
                if applied:
                    await self.public_message(saved)
                    await self._refresh_private(saved)
                self.deadlines.pop(table_id,None)
        except asyncio.CancelledError:pass
        except Exception:log.exception('Practice timeout saved; display unavailable')

    async def _refresh_private(self,saved):
        for (table_id,viewer),message in list(self.private_messages.items()):
            if table_id!=saved['id'] or not message:
                continue
            try:
                await self._send(message.edit,await self.payload(saved,viewer))
            except discord.HTTPException:
                pass

    async def handle(self,inter,old,action,*,viewer=None,choice=None):
        await inter.response.defer(ephemeral=True,thinking=True) if viewer is None else await inter.response.defer()
        table_id=old['id']
        try:
            async with self.lock(table_id):
                saved=await asyncio.to_thread(self.service.get,table_id,inter.guild_id or 0)
                if await self._inspect_action(inter,saved,action,viewer):
                    return
                actual='play' if action=='confirm' else action
                saved,applied=await asyncio.to_thread(self.service.change,table_id,old['revision'],inter.user.id,actual,guild=inter.guild_id or 0,choice=choice)
                if not applied:
                    await inter.followup.send('That control is stale. Showing the saved current table.',ephemeral=True)
                await self._publish_change(inter,saved,original=viewer is not None,transition=applied)
        except (ValueError,PermissionError,discord.HTTPException) as exc:
            await inter.followup.send(str(exc),ephemeral=True)
        except Exception:
            log.exception('Practice table preserved after failure')
            await inter.followup.send('The saved match is preserved. Reopen its command with the table ID to recover.',ephemeral=True)

    async def _inspect_action(self,inter,saved,action,viewer):
        if action=='rules':
            text=self.service.engines[saved['kind']].RULES+'\nEight-minute inactivity pauses practice play. Reopen the command to resume. No community coins.'
            for page in text_pages(text):await inter.followup.send(page,ephemeral=True)
            return True
        if action=='refresh' and inter.user.id not in saved['state']['players']:
            await self.public_message(saved)
            await inter.followup.send('Public table refreshed.',ephemeral=True)
            return True
        if inter.user.id not in saved['state']['players']:
            raise PermissionError('Only the two seated players can use these controls.')
        if action=='details':
            for page in text_pages(readable(self.service.projection(saved,inter.user.id))):
                await inter.followup.send(page,ephemeral=True)
        elif action=='concede_prompt':
            await self._confirm_concession(inter,saved)
        elif action in ('private','refresh'):
            if action=='refresh':saved=await self.public_message(saved)
            await self.private_message(inter,saved,original=viewer is not None)
        else:
            return False
        return True

    async def _confirm_concession(self,inter,saved):
        view=discord.ui.View(timeout=120)
        button=discord.ui.Button(label='Confirm concession',style=discord.ButtonStyle.danger)
        async def confirm(i):
            if i.user.id!=inter.user.id:
                await i.response.send_message('This confirmation belongs to another player.',ephemeral=True)
                return
            await self.handle(i,saved,'concede',viewer=i.user.id)
        button.callback=confirm
        view.add_item(button)
        await inter.followup.send('Concede this practice match? This ends it for both players.',view=view,ephemeral=True)

    async def _publish_change(self,inter,saved,*,original,transition=False,channel=None):
        try:
            saved=await self.public_message(saved,channel=channel,transition=transition)
            await self.private_message(inter,saved,original=original,transition=transition)
            self.arm(saved)
        except Exception:
            if saved['status']=='active':
                await asyncio.to_thread(self.service.change,saved['id'],saved['revision'],inter.user.id,
                                        'pause',guild=inter.guild_id or 0)
            raise

    async def _open_table(self,inter,kind,opponent,table):
        guild=inter.guild_id or 0
        actor=inter.user.id
        if table:
            saved=await asyncio.to_thread(self.service.get,table,guild,actor=actor)
            if saved['kind']!=kind:
                raise ValueError('Use this saved table\'s original game command.')
            return saved
        existing=await asyncio.to_thread(self.service.store.active,guild,actor,kind)
        if opponent and existing is None and not await self.visible(guild,inter.channel_id,kind):
            raise ValueError('Human invitations need a configured public casino channel.')
        return await asyncio.to_thread(self.service.start,guild,actor,kind,opponent.id if opponent else 0)

    async def start(self,inter,kind,opponent=None,table=None,animations=None):
        await inter.response.defer(ephemeral=True,thinking=True)
        try:
            guild=inter.guild_id or 0;actor=inter.user.id
            if opponent and (opponent.bot or opponent.id==actor):raise ValueError('Choose another human opponent, or omit opponent for Luigi.')
            saved=await self._open_table(inter,kind,opponent,table)
            async with self.lock(saved['id']):
                saved=await asyncio.to_thread(self.service.get,saved['id'],guild,actor=actor)
                if saved['status']=='paused':
                    saved,_=await asyncio.to_thread(self.service.change,saved['id'],saved['revision'],actor,'resume',guild=guild)
                animations_on=await self.animated(actor) if animations is None else animations
                visible=await self.visible(guild,inter.channel_id,kind)
                saved=await asyncio.to_thread(self.service.configure_display,saved,actor,
                    channel_id=inter.channel_id,public=visible,animations=animations_on)
                await self._publish_change(inter,saved,original=True,channel=inter.channel)
        except (ValueError,PermissionError,discord.HTTPException) as exc:
            await inter.edit_original_response(content=str(exc),view=None)
        except Exception:
            log.exception('Practice command failed; stored state preserved')
            await inter.edit_original_response(content='Saved state is preserved. Reopen the game command to recover.',view=None)

    @discord.app_commands.command(name='casino_tripletriad',description='Triple Triad Basic/Open: place cards and capture stronger edges')
    async def tripletriad(self,inter:discord.Interaction,opponent:discord.User|None=None,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'triple_triad',opponent,table,animations)

    @discord.app_commands.command(name='casino_red7',description='Red7 Basic: change your palette or the winning rule')
    async def red7(self,inter:discord.Interaction,opponent:discord.User|None=None,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'red7',opponent,table,animations)

    @discord.app_commands.command(name='casino_scopa',description='Scopa: capture matching sums and score a complete 40-card deal')
    async def scopa(self,inter:discord.Interaction,opponent:discord.User|None=None,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'scopa',opponent,table,animations)

    @discord.app_commands.command(name='casino_cuttle',description='Classic Cuttle: points, powers, scuttles and explicit counters')
    async def cuttle(self,inter:discord.Interaction,opponent:discord.User|None=None,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'cuttle',opponent,table,animations)

    @discord.app_commands.command(name='casino_platoon',description='Platoon practice: arrange formations, predict winners and choose battles')
    async def platoon(self,inter:discord.Interaction,opponent:discord.User|None=None,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'platoon',opponent,table,animations)

    @discord.app_commands.command(name='casino_pazaak',description='Pazaak practice: customize a side deck and win three sets')
    async def pazaak(self,inter:discord.Interaction,opponent:discord.User|None=None,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'pazaak',opponent,table,animations)

    @discord.app_commands.command(name='casino_war',description='Casino War practice: compare high cards, surrender or go to war')
    async def war(self,inter:discord.Interaction,table:str|None=None,animations:bool|None=None):
        await self.start(inter,'casino_war',None,table,animations)


async def setup(bot):
    try:
        from cosmetics.store import CosmeticsStore
        cosmetics=CosmeticsStore()
    except Exception:
        log.warning('Using classic practice-table appearance; cosmetics setup unavailable',exc_info=True)
        cosmetics=None
    await bot.add_cog(CardTablesCog(bot,cosmetics=cosmetics))
