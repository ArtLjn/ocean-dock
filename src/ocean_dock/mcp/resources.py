"""MCP Resources — 3 个资源定义"""

import json

from ocean_dock.mcp.server import _get_work_summary, _resolve_session
from ocean_dock.session_store import list_all_sessions
from ocean_dock.utils import truncate


def register_resources(server):
    """注册所有 MCP Resources。"""

    @server.resource("ocean-dock://sessions")
    def resource_sessions() -> str:
        """所有 session 的列表（JSON 格式）。"""
        sessions = list_all_sessions()
        data = []
        for s in sessions:
            last_at = getattr(s, "_last_at", s.started_at)
            data.append({
                "session_id": s.session_id,
                "cwd": s.cwd,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "last_at": last_at.isoformat() if last_at else None,
                "user_count": getattr(s, "_quick_user_count", 0),
                "assistant_count": getattr(s, "_quick_assistant_count", 0),
                "first_msg": truncate(getattr(s, "_quick_first_msg", ""), 100),
            })
        return json.dumps(data, ensure_ascii=False, indent=2)

    @server.resource("ocean-dock://session/{session_id}/work-summary")
    def resource_work_summary(session_id: str) -> str:
        """指定 session 的原始工作摘要（JSON 格式）。"""
        session = _resolve_session(session_id)
        if session is None:
            return json.dumps({"error": f"未找到 session: {session_id}"}, ensure_ascii=False)
        work = _get_work_summary(session)
        for k, v in work.items():
            if isinstance(v, set):
                work[k] = sorted(v)
        return json.dumps(work, ensure_ascii=False, indent=2)

    @server.resource("ocean-dock://session/{session_id}/messages")
    def resource_messages(session_id: str) -> str:
        """指定 session 的对话流（JSON 格式）。"""
        session = _resolve_session(session_id)
        if session is None:
            return json.dumps({"error": f"未找到 session: {session_id}"}, ensure_ascii=False)
        messages = session.messages or []
        data = []
        for msg in messages:
            data.append({
                "role": msg.msg_type.value,
                "timestamp": msg.timestamp,
                "text": msg.text[:500],
                "git_branch": msg.git_branch,
            })
        return json.dumps(data, ensure_ascii=False, indent=2)
