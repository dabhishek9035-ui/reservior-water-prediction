"""Tiny in-memory session store. Swap for Redis/SQLite later if you need persistence."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    turns: list[dict] = field(default_factory=list)   # [{"role": "user"|"assistant", "content": str}]
    last_dam_id: Optional[str] = None
    last_horizon: Optional[int] = None


class SessionStore:
    def __init__(self, max_sessions: int = 200) -> None:
        self._s: "OrderedDict[str, Session]" = OrderedDict()
        self._max = max_sessions

    def get(self, sid: str) -> Session:
        if sid in self._s:
            self._s.move_to_end(sid)
            return self._s[sid]
        sess = Session()
        self._s[sid] = sess
        while len(self._s) > self._max:
            self._s.popitem(last=False)
        return sess

    def add_turn(self, sid: str, user: str, assistant: str, dam_id: Optional[str], horizon: Optional[int]) -> None:
        s = self.get(sid)
        s.turns.append({"role": "user", "content": user})
        s.turns.append({"role": "assistant", "content": assistant})
        s.turns = s.turns[-40:]
        if dam_id:
            s.last_dam_id = dam_id
        if horizon:
            s.last_horizon = horizon

    def clear(self, sid: str) -> None:
        self._s.pop(sid, None)
