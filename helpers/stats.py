from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path
from typing import Any, Dict



class StatsStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Dict[str, Dict[str, int]]:
        if not self.path.exists():
            return {}

        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                return {}

            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except:
            return {}

    def save(self, data: Dict[str, Dict[str, int]]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def bump(self, user_id: str, field: str, amount: int = 1) -> Dict[str, int]:
        data = self.load()
        user = data.get(user_id, {})

        user[field] = int(user.get(field, 0)) + amount
        data[user_id] = user
        self.save(data)

        return user

    def set_bump(self, user_id: str, field: str, value: str):
        data = self.load()
        user = data.get(user_id, {})

        current = set(user.get(field, []))
        current.add(value)

        user[field] = list(current)
        data[user_id] = user
        self.save(data)

        return user

    def get(self, user_id):
        return self.load().get(str(user_id), {
            "messages": 0,
            "files": 0,
            "ereuse_reacts": 0
        })

    def all(self):
        return self.load()