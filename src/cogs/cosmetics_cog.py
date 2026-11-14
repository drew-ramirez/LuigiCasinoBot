"""Private cosmetic previews, explicit purchases and persistent wardrobe choices."""
import asyncio
import logging
import uuid

import discord
from discord.ext import commands

log = logging.getLogger(__name__)
PAGE_SIZE = 25


def display_name(inter):
    return getattr(inter.user, 'display_name', getattr(inter.user, 'name', str(inter.user.id)))


class CosmeticsView(discord.ui.View):
    def __init__(self, cog, guild, snapshot, mode, *, page=0, selected=None, request_id=None):
        super().__init__(timeout=480)
        self.cog, self.owner, self.guild = cog, snapshot['user_id'], guild
        self.snapshot, self.mode = snapshot, mode
        self.selected = selected
        self.request_id = request_id or uuid.uuid4().hex
        self.quote_id = None
        entries = cog.domain.entries(snapshot, mode)
        self.page = min(max(0, page), max(0, (len(entries)-1)//PAGE_SIZE))
        self.entries = entries[self.page*PAGE_SIZE:(self.page+1)*PAGE_SIZE]
        self._add_selection()
        self._add_confirmation()
        if self.page:
            self.button('Previous', 'previous', 2)
        if (self.page+1)*PAGE_SIZE < len(entries):
            self.button('Next', 'next', 2)
        self.button('Shop' if mode == 'wardrobe' else 'Wardrobe', 'switch', 3)
        self.button('Refresh', 'refresh', 3)

    def _option(self, entry):
        if self.mode == 'wardrobe':
            equipped = self.snapshot['equipped'].get(entry.slot) == entry.id
            description = entry.slot.replace('_', ' ') + (' · equipped' if equipped else ' · owned')
        else:
            description = ('Free' if entry.price == 0 else f'{entry.price:,} coins') + ' · preview before confirming'
        return discord.SelectOption(label=entry.name[:100], value=entry.id,
                                    description=description[:100], default=entry.id == self.selected)

    def _add_selection(self):
        if not self.entries:
            return
        select=discord.ui.Select(placeholder='Preview an owned item' if self.mode == 'wardrobe' else 'Preview an offer',
                                 options=[self._option(entry) for entry in self.entries], row=0)
        async def choose(inter):
            value=inter.data['values'][0]
            if value not in {entry.id for entry in self.entries}:
                return await inter.response.send_message('That choice is no longer available. Reopen the menu.', ephemeral=True)
            await self.cog.handle(inter, self, 'select', selection=value)
        select.callback=choose
        self.add_item(select)

    def _add_confirmation(self):
        if not self.selected:
            return
        if self.mode == 'wardrobe':
            item=self.cog.catalog.get(self.selected)
            if item and self.selected in self.snapshot['owned'] and self.snapshot['equipped'].get(item.slot) != self.selected:
                self.button('Equip selected item', 'equip', 1, discord.ButtonStyle.success)
            return
        offer=self.cog.offers.get(self.selected)
        if offer:
            self.quote_id=offer.quote_id
            if not self.cog.domain.offer_owned(self.snapshot, offer):
                label='Confirm free claim' if offer.price == 0 else f'Confirm purchase · {offer.price:,} coins'
                self.button(label, 'purchase', 1, discord.ButtonStyle.success)

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
    def __init__(self, bot, *, store=None):
        self.bot=bot
        if store is None:
            from cosmetics.store import CosmeticsStore
            store=CosmeticsStore()
        self.store, self.domain=store, store.catalog
        self.catalog, self.offers=self.domain.items, self.domain.offers
        self.locks={}

    def lock(self, owner):
        return self.locks.setdefault(owner, asyncio.Lock())

    def _wardrobe_lines(self, snapshot, selected):
        lines=['Preview owned cosmetics, then equip your choice. Cosmetics do not change game outcomes.',
               'Table styles currently apply to Triple Triad, Red7, Scopa, Cuttle, Platoon, Pazaak and Casino War.']
        lines.extend(f"• {self.catalog[item].name} ({slot.replace('_', ' ')})" for slot,item in snapshot['equipped'].items() if item in self.catalog)
        if selected:
            item=self.catalog[selected]
            lines.append('**Preview: '+discord.utils.escape_markdown(item.name)+'**')
            if snapshot['equipped'].get(item.slot) == selected:
                lines.append('Already equipped.')
        return lines

    def _shop_lines(self, snapshot, selected, entries):
        lines=['Select an offer to preview its contents. Only confirmation can make a purchase.']
        if not selected:
            lines.extend(f"• {offer.name}: {'Free' if offer.price == 0 else str(offer.price)+' coins'}" for offer in entries)
            return lines
        offer=self.offers[selected]
        lines.extend(['**'+discord.utils.escape_markdown(offer.name)+'**', 'Price: '+('Free · 0 coins' if offer.price == 0 else f'{offer.price:,} coins'),
                      'Includes: '+', '.join(self.catalog[item].name for item in offer.item_ids)])
        if len({self.catalog[item].slot for item in offer.item_ids}) < len(offer.item_ids):
            lines.append('Preview shows one option per slot. The Wardrobe lets you preview and equip each included item.')
        if self.domain.offer_owned(snapshot, offer):lines.append('You already own everything in this offer.')
        return lines

    async def _preview_attachment(self, snapshot, mode, selected):
        try:
            from cosmetics.profile import render_profile
            appearance=self.domain.preview(snapshot, mode, selected)
            data=await asyncio.to_thread(render_profile, snapshot['profile'], appearance, animate=bool(snapshot.get('animations_enabled',False)))
            return [discord.File(data, filename='cosmetics.gif' if data.getvalue().startswith(b'GIF') else 'cosmetics.png')]
        except Exception:
            log.warning('Cosmetic preview unavailable; keeping saved text and controls', exc_info=True)
            return []

    async def payload(self, snapshot, guild, mode, *, page=0, selected=None, request_id=None, notice=None):
        view=CosmeticsView(self, guild, snapshot, mode, page=page, selected=selected, request_id=request_id)
        lines=['**Casino Wardrobe**' if mode == 'wardrobe' else '**Casino Shop**', f"Balance: {snapshot['balance']:,} coins"]
        if notice: lines.append(notice)
        lines.extend(self._wardrobe_lines(snapshot, selected) if mode == 'wardrobe' else self._shop_lines(snapshot, selected, view.entries))
        lines.append(f'Page {view.page+1} · previews do not equip or spend coins.')
        attachments=await self._preview_attachment(snapshot, mode, selected)
        return {'content':'\n'.join(lines)[:1950], 'attachments':attachments, 'view':view,
                'allowed_mentions':discord.AllowedMentions.none()}

    async def deliver(self, inter, payload):
        try:
            return await inter.edit_original_response(**payload)
        except discord.HTTPException as exc:
            if isinstance(exc, (discord.Forbidden,discord.NotFound)) or not payload.get('attachments'):
                raise
            return await inter.edit_original_response(**{**payload, 'attachments':[]})

    async def _purchase(self, view, username):
        if view.mode != 'shop' or view.selected not in self.offers or view.quote_id is None:
            raise ValueError('Choose and preview an offer before confirming.')
        result=await asyncio.to_thread(self.store.purchase, view.owner, view.selected, view.quote_id, view.request_id, username)
        notice={'purchased':'Purchase saved. Your new items are in the Wardrobe.', 'replayed':'This confirmation was already saved. No second charge.', 'already_owned':'You already own this offer. No coins spent.'}.get(result['status'], 'Your wardrobe is up to date.')
        return result['snapshot'], notice

    async def _equip(self, view, username):
        if view.mode != 'wardrobe' or view.selected not in self.catalog:
            raise ValueError('Preview an owned item before equipping.')
        snapshot, applied=await asyncio.to_thread(self.store.equip, view.owner, view.selected, view.snapshot['revision'], username)
        notice='Equipped. Your profile and supported card tables use this selection.' if applied else 'That menu was stale. Showing your current saved wardrobe.'
        return snapshot, notice

    def _navigation(self, view, snapshot, action, selection):
        mode, page, selected=view.mode, view.page, None
        if action == 'select':
            selected=selection
            if not self.domain.selectable(snapshot, mode, selected):raise ValueError('That choice is no longer available.')
        elif action in ('next','previous'):
            page=max(0, page+(1 if action == 'next' else -1))
        elif action == 'switch':
            mode='shop' if mode == 'wardrobe' else 'wardrobe';page=0
        elif action != 'refresh':
            raise ValueError('Unknown wardrobe action.')
        return mode, page, selected, uuid.uuid4().hex

    async def handle(self, inter, view, action, *, selection=None):
        if not await view.interaction_check(inter):return
        await inter.response.defer(ephemeral=True)
        username=display_name(inter)
        try:
            async with self.lock(view.owner):
                mode, page, selected, request_id=view.mode, view.page, view.selected, view.request_id
                notice=None
                if action == 'purchase':
                    snapshot,notice=await self._purchase(view, username)
                elif action == 'equip':
                    snapshot,notice=await self._equip(view, username)
                else:
                    snapshot=await asyncio.to_thread(self.store.get, view.owner, username)
                    mode,page,selected,request_id=self._navigation(view, snapshot, action, selection)
                payload=await self.payload(snapshot, view.guild, mode, page=page, selected=selected, request_id=request_id, notice=notice)
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
            await self.deliver(inter, await self.payload(snapshot, inter.guild_id or 0, mode))
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
