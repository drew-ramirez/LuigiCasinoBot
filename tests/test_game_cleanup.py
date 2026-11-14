import copy
from types import SimpleNamespace

import discord
import pytest
from PIL import Image

from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import LuckyStarsView
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchUI import MemoryMatchControls
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGoneUI import PairControls
from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import render_board
from casinogames.picturepoker.PicturePokerUI import PicturePokerView
from cogs.base_game_cog import BaseGameCog
from economy.EconomyManager import EconomyManager


@pytest.mark.asyncio
@pytest.mark.parametrize("animated", [False, True])
@pytest.mark.parametrize("kind", ["memory", "pair", "poker", "lucky"])
async def test_registered_cleanup_renders_status_and_board_without_mutating_game(
    monkeypatch, kind, animated
):
    monkeypatch.setattr(EconomyManager, "ensure_user", lambda *args, **kwargs: {"balance": 100})
    monkeypatch.setattr(EconomyManager, "star_bonus_count", lambda *args, **kwargs: 0)
    player = SimpleNamespace(id=1, name="Player", display_name="Player", display_avatar=None)
    if kind == "memory":
        game = MemoryMatch(25)
        view_class = MemoryMatchControls
    elif kind == "pair":
        game = PairAGone(25)
        view_class = PairControls
    elif kind == "poker":
        game = PicturePoker()
        game.start_round(forced_bet=25)
        view_class = PicturePokerView
    else:
        game = LuckyStars(25)
        game.deal_round()
        game.pick_card(0)
        view_class = LuckyStarsView

    view = view_class(game, player, None, animations_enabled=animated)
    cog = BaseGameCog(None, "Test", session_timeout_seconds=0)
    await cog.register_active_game(player.id, game=game, view=view, cleanup_renderer=view.cleanup_payload)
    before = copy.deepcopy(vars(game))
    colour = discord.Colour.red()
    payload = await cog._render_cleanup_payload(cog.active_games[player.id], "Session ended", colour=colour)

    assert vars(game) == before
    assert len(payload["attachments"]) == 1
    attachment = payload["attachments"][0]
    assert attachment.filename.endswith(".png")
    with Image.open(attachment.fp) as image:
        assert image.size == (512, 768)
    attachment.fp.seek(0)
    if kind == "poker":
        assert attachment.fp.read() == render_board(game, reveal=True).getvalue()
    elif kind == "lucky":
        assert attachment.fp.read() == render_lucky_board(game, reveal=True).getvalue()
    if animated:
        assert "Session ended" in payload["content"]
        assert payload["embed"] is None
    else:
        assert payload["content"] is None
        embed = payload["embed"]
        assert embed.colour == colour
        assert any("Session ended" in field.value for field in embed.fields)
        assert embed.image.url == f"attachment://{attachment.filename}"
    attachment.close()
