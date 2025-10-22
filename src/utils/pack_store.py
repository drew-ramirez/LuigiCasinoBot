import json
from pathlib import Path
from typing import Dict, Set


class PackStore:
    async def get_enabled(self, guild_id: int) -> Set[str]:
        raise NotImplementedError

    async def set_enabled(self, guild_id: int, pack_ids: Set[str]) -> None:
        raise NotImplementedError

    async def enable(self, guild_id: int, pack_id: str) -> None:
        raise NotImplementedError

    async def disable(self, guild_id: int, pack_id: str) -> None:
        raise NotImplementedError


class JsonPackStore(PackStore):
    """
    File-based store. Swap to Mongo later without touching callers.
    """

    def __init__(self, path: str = "data/guild_packs.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self) -> Dict[str, list]:
        return json.loads(self.path.read_text(encoding="utf-8") or "{}")

    def _save(self, data: Dict[str, list]) -> None:
        self.path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    async def get_enabled(self, guild_id: int) -> Set[str]:
        data = self._load()
        return set(data.get(str(guild_id), []))

    async def set_enabled(self, guild_id: int, pack_ids: Set[str]) -> None:
        data = self._load()
        data[str(guild_id)] = sorted(pack_ids)
        self._save(data)

    async def enable(self, guild_id: int, pack_id: str) -> None:
        enabled = await self.get_enabled(guild_id)
        enabled.add(pack_id)
        await self.set_enabled(guild_id, enabled)

    async def disable(self, guild_id: int, pack_id: str) -> None:
        enabled = await self.get_enabled(guild_id)
        enabled.discard(pack_id)
        await self.set_enabled(guild_id, enabled)
