"""Private cosmetic previews, explicit purchases and persistent wardrobe choices."""
import asyncio
from dataclasses import replace
import logging
import uuid

import discord
from discord.ext import commands

log = logging.getLogger(__name__)
PAGE_SIZE = 25


def display_name(inter):
    return getattr(inter.user, 'display_name', getattr(inter.user, 'name', str(inter.user.id)))


class CosmeticsView(discord.ui.View):
    def __init__(self, cog, owner, guild, snapshot, mode, *, page=0, selected=None, request_id=None):
        super().__init__(timeout=480)
        self.cog, self.owner, self.guild = cog, owner, guild
        self.snapshot, self.mode = snapshot, mode
        self.selected = selected
        self.request_id = request_id or uuid.uuid4().hex
        self.quote_id = None
        if mode == 'wardrobe':
            entries = [item for item in cog.catalog.values() if item.id in snapshot['owned']]
        else:
            entries = list(cog.offers.values())
        self.page = min(max(0, page), max(0, (len(entries)-1)//PAGE_SIZE))
        self.entries = entries[self.page*PAGE_SIZE:(self.page+1)*PAGE_SIZE]
        if self.entries:
            options=[]
            for entry in self.entries:
                if mode == 'wardrobe':
                    equipped = snapshot['equipped'].get(entry.slot) == entry.id
                    description = entry.slot.replace('_', ' ') + (' · equipped' if equipped else ' · owned')
                else:
                    description = ('Free' if entry.price == 0 else f'{entry.price:,} coins') + ' · preview before confirming'
                options.append(discord.SelectOption(label=entry.name[:100], value=entry.id,
                                                     description=description[:100], default=entry.id == selected))
            select=discord.ui.Select(placeholder='Preview an owned item' if mode == 'wardrobe' else 'Preview an offer', options=options, row=0)
            async def choose(inter):
                value=inter.data['values'][0]
                if value not in {entry.id for entry in self.entries}:
                    return await inter.response.send_message('That choice is no longer available. Reopen the menu.', ephemeral=True)
                await self.cog.handle(inter, self, 'select', selection=value)
            select.callback=choose
            self.add_item(select)
        if selected:
            if mode == 'wardrobe':
                item=cog.catalog.get(selected)
                if item and selected in snapshot['owned'] and snapshot['equipped'].get(item.slot) != selected:
                    self.button('Equip selected item', 'equip', 1, discord.ButtonStyle.success)
            else:
                offer=cog.offers.get(selected)
                if offer:
                    self.quote_id=offer.quote_id
                    if not all(item in snapshot['owned'] for item in offer.item_ids):
                        label='Confirm free claim' if offer.price == 0 else f'Confirm purchase · {offer.price:,} coins'
                        self.button(label, 'purchase', 1, discord.ButtonStyle.success)
        if self.page:
            self.button('Previous', 'previous', 2)
        if (self.page+1)*PAGE_SIZE < len(entries):
            self.button('Next', 'next', 2)
        self.button('Shop' if mode == 'wardrobe' else 'Wardrobe', 'switch', 3)
        self.button('Refresh', 'refresh', 3)

    def button(self, label, action, row, style=discord.ButtonStyle.secondary):
        button=discord.ui.Button(label=label[:80], row=row, style=style)
        async def callback(inter):
            await self.cog.handle(inter, self, action)
        button.callback=callback
        self.add_item(button)

    async def interaction_check(self, inter):
        if inter.user.id != self.owner or (inter.guild_id or 0) != self.guild:
            await inter.response.send_message('This private menu belongs to another player or server.', ephemeral=True)
            return False
        return True


class CosmeticsCog(commands.Cog):
    def __init__(self, bot, *, store=None, catalog=None, offers=None):
        self.bot=bot
        if store is None:
            from cosmetics.store import CosmeticsStore
            store=CosmeticsStore()
        if catalog is None or offers is None:
            from cosmetics.catalog import CATALOG, OFFERS
            if catalog is None: catalog=CATALOG
            if offers is None: offers=OFFERS
        self.store, self.catalog, self.offers=store, catalog, offers
        self.locks={}

    def lock(self, owner):
        return self.locks.setdefault(owner, asyncio.Lock())

    def preview_appearance(self, snapshot, mode, selected):
        appearance=snapshot['appearance']
        if not selected:
            return appearance
        if mode == 'wardrobe':
            item=self.catalog.get(selected)
            if item is None or selected not in snapshot['owned']:
                raise ValueError('That owned item is no longer available.')
            items=[item]
        else:
            offer=self.offers.get(selected)
            if offer is None:
                raise ValueError('That offer is no longer available.')
            items=[self.catalog[item] for item in offer.item_ids]
        return replace(appearance, **{item.slot:item.asset_key for item in items})

    async def payload(self, snapshot, owner, guild, username, mode, *, page=0, selected=None, request_id=None, notice=None):
        view=CosmeticsView(self, owner, guild, snapshot, mode, page=page, selected=selected, request_id=request_id)
        lines=['**Casino Wardrobe**' if mode == 'wardrobe' else '**Casino Shop**', f"Balance: {snapshot['balance']:,} coins"]
        if notice: lines.append(notice)
        if mode == 'wardrobe':
            lines.append('Preview owned cosmetics, then equip your choice. Cosmetics do not change game outcomes.')
            lines.append('Table styles currently apply to Triple Triad, Red7, Scopa, Cuttle, Platoon, Pazaak and Casino War.')
            lines.extend(f"• {self.catalog[item].name} ({slot.replace('_', ' ')})" for slot,item in snapshot['equipped'].items() if item in self.catalog)
            if selected:
                lines.append('**Preview: '+discord.utils.escape_markdown(self.catalog[selected].name)+'**')
                if snapshot['equipped'].get(self.catalog[selected].slot) == selected:
                    lines.append('Already equipped.')
        else:
            lines.append('Select an offer to preview its contents. Only confirmation can make a purchase.')
            if selected:
                offer=self.offers[selected]
                lines.extend(['**'+discord.utils.escape_markdown(offer.name)+'**', 'Price: '+('Free · 0 coins' if offer.price == 0 else f'{offer.price:,} coins'),
                              'Includes: '+', '.join(self.catalog[item].name for item in offer.item_ids)])
                if len({self.catalog[item].slot for item in offer.item_ids}) < len(offer.item_ids):
                    lines.append('Preview shows one option per slot. The Wardrobe lets you preview and equip each included item.')
                if all(item in snapshot['owned'] for item in offer.item_ids):lines.append('You already own everything in this offer.')
            else:
                lines.extend(f"• {offer.name}: {'Free' if offer.price == 0 else str(offer.price)+' coins'}" for offer in view.entries)
        lines.append(f'Page {view.page+1} · previews do not equip or spend coins.')
        attachments=[]
        try:
            from cosmetics.profile import render_profile
            appearance=self.preview_appearance(snapshot, mode, selected)
            profile=snapshot.get('profile', {})
            public={'name':profile.get('name',username), 'balance':snapshot['balance'], 'games_played':profile.get('games_played',0), 'career_stars':profile.get('career_stars',0)}
            data=await asyncio.to_thread(render_profile, public, appearance, animate=bool(snapshot.get('animations_enabled',False)))
            attachments=[discord.File(data, filename='cosmetics.gif' if data.getvalue().startswith(b'GIF') else 'cosmetics.png')]
        except Exception:
            log.warning('Cosmetic preview unavailable; keeping saved text and controls', exc_info=True)
        return {'content':'\n'.join(lines)[:1950], 'attachments':attachments, 'view':view,
                'allowed_mentions':discord.AllowedMentions.none()}

    async def deliver(self, inter, payload):
        try:
            return await inter.edit_original_response(**payload)
        except discord.HTTPException as exc:
            if isinstance(exc, (discord.Forbidden,discord.NotFound)) or not payload.get('attachments'):
                raise
            return await inter.edit_original_response(**{**payload, 'attachments':[]})

    async def handle(self, inter, view, action, *, selection=None):
        if not await view.interaction_check(inter):return
        await inter.response.defer(ephemeral=True)
        username=display_name(inter)
        try:
            async with self.lock(view.owner):
                mode, page, selected=view.mode, view.page, view.selected
                notice=None
                request_id=view.request_id
                if action == 'purchase':
                    if mode != 'shop' or selected not in self.offers or view.quote_id is None:
                        raise ValueError('Choose and preview an offer before confirming.')
                    result=await asyncio.to_thread(self.store.purchase, view.owner, selected, view.quote_id, request_id, username)
                    snapshot=result['snapshot']
                    notice={'purchased':'Purchase saved. Your new items are in the Wardrobe.', 'replayed':'This confirmation was already saved. No second charge.', 'already_owned':'You already own this offer. No coins spent.'}.get(result['status'], 'Your wardrobe is up to date.')
                elif action == 'equip':
                    if mode != 'wardrobe' or selected not in self.catalog:
                        raise ValueError('Preview an owned item before equipping.')
                    snapshot, applied=await asyncio.to_thread(self.store.equip, view.owner, selected, view.snapshot['revision'], username)
                    notice='Equipped. Your profile and supported card tables use this selection.' if applied else 'That menu was stale. Showing your current saved wardrobe.'
                else:
                    snapshot=await asyncio.to_thread(self.store.get, view.owner, username)
                    if action == 'select':
                        selected=selection
                        request_id=uuid.uuid4().hex
                        valid=selected in snapshot['owned'] and selected in self.catalog if mode == 'wardrobe' else selected in self.offers
                        if not valid:raise ValueError('That choice is no longer available.')
                    elif action in ('next','previous'):
                        page=max(0, page+(1 if action == 'next' else -1));selected=None
                        request_id=uuid.uuid4().hex
                    elif action == 'switch':
                        mode='shop' if mode == 'wardrobe' else 'wardrobe';page=0;selected=None
                        request_id=uuid.uuid4().hex
                    elif action == 'refresh':
                        selected=None
                        request_id=uuid.uuid4().hex
                    else:raise ValueError('Unknown wardrobe action.')
                payload=await self.payload(snapshot, view.owner, view.guild, username, mode, page=page, selected=selected, request_id=request_id, notice=notice)
                await self.deliver(inter, payload)
        except (ValueError,PermissionError) as exc:
            await inter.followup.send(str(exc), ephemeral=True)
        except Exception:
            log.exception('Cosmetic action/display failed; authoritative saved state retained')
            await inter.followup.send('Reopen the wardrobe or shop to see your saved choices and balance. A saved purchase will not be charged again by this confirmation.', ephemeral=True)

    async def open(self, inter, mode):
        await inter.response.defer(ephemeral=True, thinking=True)
        try:
            username=display_name(inter)
            snapshot=await asyncio.to_thread(self.store.get, inter.user.id, username)
            await self.deliver(inter, await self.payload(snapshot, inter.user.id, inter.guild_id or 0, username, mode))
        except Exception:
            log.exception('Cosmetics menu unavailable')
            await inter.edit_original_response(content='The wardrobe is temporarily unavailable. Your saved choices are unchanged.', view=None, attachments=[])

    @discord.app_commands.command(name='casino_wardrobe', description='Privately preview and equip your owned casino cosmetics')
    async def wardrobe(self, inter:discord.Interaction):
        await self.open(inter, 'wardrobe')

    @discord.app_commands.command(name='casino_shop', description='Privately browse fixed cosmetic offers and preview before confirming')
    async def shop(self, inter:discord.Interaction):
        await self.open(inter, 'shop')


async def setup(bot):
    await bot.add_cog(CosmeticsCog(bot))
