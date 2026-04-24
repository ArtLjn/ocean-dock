"""Claude Code Session 数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SessionKind(str, Enum):
    INTERACTIVE = "interactive"
    PRINT = "print"


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    QUEUE_OPERATION = "queue-operation"


@dataclass
class SessionMessage:
    uuid: str
    timestamp: str
    session_id: str
    msg_type: MessageType
    text: str = ""
    cwd: str = ""
    git_branch: str = ""
    parent_uuid: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Session:
    session_id: str
    pid: int
    cwd: str
    started_at: datetime
    kind: SessionKind
    entrypoint: str = ""
    messages: list[SessionMessage] = field(default_factory=list)
    jsonl_path: str = ""

    @property
    def user_messages(self) -> list[SessionMessage]:
        return [m for m in self.messages if m.msg_type == MessageType.USER and m.text]

    @property
    def assistant_messages(self) -> list[SessionMessage]:
        return [m for m in self.messages if m.msg_type == MessageType.ASSISTANT and m.text]

    @property
    def first_user_message(self) -> str:
        for m in self.user_messages:
            # 跳过 IDE 打开的文件信息
            text = m.text.strip()
            if text and not text.startswith("<ide_opened_file>"):
                return text
        return ""

    @property
    def message_count(self) -> int:
        return len(self.user_messages) + len(self.assistant_messages)

    @property
    def time_range(self) -> str:
        if not self.messages:
            return ""
        first_ts = self.messages[0].timestamp
        last_ts = self.messages[-1].timestamp
        return f"{first_ts} ~ {last_ts}"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "pid": self.pid,
            "cwd": self.cwd,
            "started_at": self.started_at.isoformat(),
            "kind": self.kind.value,
            "entrypoint": self.entrypoint,
            "message_count": self.message_count,
            "user_message_count": len(self.user_messages),
            "assistant_message_count": len(self.assistant_messages),
            "first_user_message": self.first_user_message[:200],
            "time_range": self.time_range,
        }
